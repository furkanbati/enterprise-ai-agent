
import logging
import time
from pathlib import Path

from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel, Field, field_validator, model_validator

from app.agent import Agent
from app.config import BUSINESS_DB_PATH
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
from business.store import BusinessStore
from tools.calculator import CalculatorTool
from tools.date_diff import DateDiffTool
from tools.datetime_tool import DateTimeTool
from tools.support import support_tools


configure_logging()

app = FastAPI(
    title="Enterprise AI Agent",
    version="0.1.0",
)

logger = logging.getLogger(__name__)

DEMO_PAGE = Path(__file__).parent / "static" / "index.html"


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


MAX_HISTORY_MESSAGES = 10

MAX_HISTORY_CHARS = 20_000


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4_000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        content = value.strip()

        if not content:
            raise ValueError("History messages cannot be blank.")

        return content


class ChatRequest(BaseModel):
    question: str = Field(max_length=4_000)
    # Earlier turns of the conversation, oldest first. The client keeps the
    # conversation; the server stores nothing between requests.
    history: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=MAX_HISTORY_MESSAGES,
    )

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        question = value.strip()

        if not question:
            raise ValueError("Question cannot be blank.")

        return question

    @model_validator(mode="after")
    def limit_history_size(self):
        if sum(len(message.content) for message in self.history) > MAX_HISTORY_CHARS:
            raise ValueError(
                f"History cannot exceed {MAX_HISTORY_CHARS} characters in total."
            )

        return self


class StepResponse(BaseModel):
    tool: str
    arguments: dict
    success: bool
    result: object | None = None
    error: str | None = None
    # True when the tool refused the request (ToolRequestRejected).
    rejected: bool = False


class ChatResponse(BaseModel):
    answer: str
    # The last tool call, kept for clients written for single-tool answers.
    tool: str | None = None
    arguments: dict | None = None
    tool_result: object | None = None
    error: str | None = None
    # Every tool call made to produce the answer, in order.
    steps: list[StepResponse] = []


store = BusinessStore(BUSINESS_DB_PATH)

registry = ToolRegistry(
    [
        *support_tools(store),
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


@app.get("/", include_in_schema=False)
def demo_page():
    """The demo chat UI: a single HTML page that calls the API below."""

    return FileResponse(DEMO_PAGE)


@app.get("/info")
def info():
    """The provider and model behind the agent, for the demo UI."""

    return {
        "provider": generator.provider.name,
        "model": generator.model,
    }


@app.get("/demo/customers")
def demo_customers():
    return {"customers": store.list_customers()}


@app.get("/demo/orders")
def demo_orders():
    return {"orders": store.list_all_orders()}


@app.post("/demo/reset")
def demo_reset():
    """Restore the demo data and remove the tickets opened since."""

    store.reset()

    return {"status": "reset"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        result: AgentResult = agent.run(
            request.question,
            history=[message.model_dump() for message in request.history],
        )

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
                rejected=step.rejected,
            )
            for step in result.steps
        ],
    )


app.mount(
    "/metrics",
    make_asgi_app(),
)

