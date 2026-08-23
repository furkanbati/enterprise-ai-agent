import logging

import httpx
from fastapi import FastAPI, HTTPException
from ollama import ResponseError
from pydantic import BaseModel, Field, field_validator

from app.executor import Executor
from app.generator import Generator
from app.models import AgentResult
from app.pipeline import Pipeline
from app.planner import Planner
from app.tool_registry import ToolRegistry
from tools.calculator import CalculatorTool
from tools.datetime_tool import DateTimeTool


app = FastAPI(
    title="Enterprise AI Agent",
    version="0.1.0",
)

logger = logging.getLogger(__name__)


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