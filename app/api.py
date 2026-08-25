import logging
import time

import httpx
from fastapi import FastAPI, HTTPException, Request
from ollama import ResponseError
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel, Field, field_validator

from app.executor import Executor
from app.generator import Generator
from app.logging import (
    configure_logging,
    generate_request_id,
    reset_request_id,
    set_request_id,
)
from app.models import AgentResult
from app.pipeline import Pipeline
from app.planner import Planner
from app.tool_registry import ToolRegistry
from tools.calculator import CalculatorTool
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


class ChatResponse(BaseModel):
    answer: str
    tool: str | None = None
    arguments: dict | None = None
    tool_result: object | None = None
    error: str | None = None


registry = ToolRegistry(
    [
        CalculatorTool(),
        DateTimeTool(),
    ]
)

generator = Generator()
planner = Planner(generator, registry)
executor = Executor(registry)

pipeline = Pipeline(
    planner=planner,
    executor=executor,
    generator=generator,
)


@app.middleware("http")
async def request_id_middleware(
    request: Request,
    call_next,
):
    request_id = generate_request_id()
    token = set_request_id(request_id)

    start_time = time.perf_counter()

    try:
        response = await call_next(request)

        if request.url.path != "/metrics":
            duration = time.perf_counter() - start_time

            HTTP_REQUESTS_TOTAL.labels(
                method=request.method,
                path=request.url.path,
                status=str(response.status_code),
            ).inc()

            HTTP_REQUEST_DURATION.labels(
                method=request.method,
                path=request.url.path,
            ).observe(duration)

        response.headers["X-Request-ID"] = request_id

        return response

    finally:
        reset_request_id(token)


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
        result: AgentResult = pipeline.run(request.question)

    except ConnectionError as exc:
        logger.exception("AI service connection failed")
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable.",
        ) from exc

    except httpx.TimeoutException as exc:
        logger.exception("AI service request timed out")
        raise HTTPException(
            status_code=503,
            detail="The AI service is temporarily unavailable.",
        ) from exc

    except (ResponseError, ValueError) as exc:
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
    )


app.mount(
    "/metrics",
    make_asgi_app(),
)