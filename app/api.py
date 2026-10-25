
import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel, Field, field_validator

from app.agent import Agent
from app.executor import Executor
from app.generator import (
    Generator,
    GeneratorResponseError,
    GeneratorUnavailableError,
)
from app.logging import (
    configure_logging,
    generate_request_id,
    get_request_id,
    reset_request_id,
    set_request_id,
)
from app.models import AgentResult
from app.tool_registry import ToolRegistry
from tools.calculator import CalculatorTool
from tools.date_diff import DateDiffTool
from tools.datetime_tool import DateTimeTool


configure_logging()

app = FastAPI(
    title="Enterprise AI Agent",
    version="0.1.0",
)

logger = logging.getLogger(__name__)


HTTP_REQUESTS_TOTAL = Counter(
    "agent_http_requests_total",
    "Total number of HTTP requests.",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "agent_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
)


class ChatRequest(BaseModel):
    question: str = Field(max_length=4_000)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        question = value.strip()

        if not question:
            raise ValueError("Question cannot be blank.")

        return question


class StepResponse(BaseModel):
    tool: str
    arguments: dict
    success: bool
    result: object | None = None
    error: str | None = None


class ChatResponse(BaseModel):
    answer: str
    # The last tool call, kept for clients written for single-tool answers.
    tool: str | None = None
    arguments: dict | None = None
    tool_result: object | None = None
    error: str | None = None
    # Every tool call made to produce the answer, in order.
    steps: list[StepResponse] = []


registry = ToolRegistry(
    [
        CalculatorTool(),
        DateTimeTool(),
        DateDiffTool(),
    ]
)

generator = Generator()
executor = Executor(registry)

agent = Agent(
    generator=generator,
    executor=executor,
    registry=registry,
)


@app.exception_handler(Exception)
async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
):
    # The request ID middleware resets its context variable before this
    # handler runs, so read the ID it stored on the request state instead.
    request_id = getattr(
        request.state,
        "request_id",
        get_request_id(),
    )
    token = set_request_id(request_id)

    try:
        logger.exception(
            "Unhandled exception on %s %s",
            request.method,
            request.url.path,
        )
    finally:
        reset_request_id(token)

    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred.",
            "request_id": request_id,
        },
        headers={
            "X-Request-ID": request_id,
        },
    )


@app.middleware("http")
async def request_id_middleware(
    request: Request,
    call_next,
):
    request_id = generate_request_id()
    request.state.request_id = request_id
    token = set_request_id(request_id)

    start_time = time.perf_counter()

    try:
        response = await call_next(request)

    except Exception:
        # Unhandled errors propagate to the exception handler outside this
        # middleware; record them here so 500s show up in the metrics.
        _record_request_metrics(request, 500, start_time)
        raise

    else:
        _record_request_metrics(request, response.status_code, start_time)

        response.headers["X-Request-ID"] = request_id

        return response

    finally:
        reset_request_id(token)


def _record_request_metrics(
    request: Request,
    status_code: int,
    start_time: float,
) -> None:
    if request.url.path == "/metrics":
        return

    # Label by route template rather than raw URL path so that requests to
    # arbitrary unknown paths cannot create unbounded metric series.
    route = request.scope.get("route")
    path = getattr(route, "path", None) or "unmatched"

    HTTP_REQUESTS_TOTAL.labels(
        method=request.method,
        path=path,
        status=str(status_code),
    ).inc()

    HTTP_REQUEST_DURATION.labels(
        method=request.method,
        path=path,
    ).observe(time.perf_counter() - start_time)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not generator.is_available():
        logger.warning("AI service is not ready")
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable.",
        )

    return {"status": "ready"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        result: AgentResult = agent.run(request.question)

    except GeneratorUnavailableError as exc:
        logger.exception("AI service is unavailable")
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable.",
        ) from exc

    except GeneratorResponseError as exc:
        logger.exception("AI service returned an invalid response")
        raise HTTPException(
            status_code=502,
            detail="The AI service returned an invalid response.",
        ) from exc

    return ChatResponse(
        answer=result.answer,
        tool=result.tool,
        arguments=result.arguments,
        tool_result=result.tool_result,
        error=result.error,
        steps=[
            StepResponse(
                tool=step.tool,
                arguments=step.arguments,
                success=step.success,
                result=step.result,
                error=step.error,
            )
            for step in result.steps
        ],
    )


app.mount(
    "/metrics",
    make_asgi_app(),
)

