from fastapi import FastAPI
from pydantic import BaseModel

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


class ChatRequest(BaseModel):
    question: str


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


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    result: AgentResult = pipeline.run(request.question)

    return ChatResponse(
        answer=result.answer,
        tool=result.tool,
        arguments=result.arguments,
        tool_result=result.tool_result,
        error=result.error,
    )