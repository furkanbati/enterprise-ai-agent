
from app.executor import Executor
from app.generator import Generator
from app.models import ToolCall
from app.pipeline import Pipeline
from app.planner import Planner
from app.tool_registry import ToolRegistry
from tools.calculator import CalculatorTool
from tools.datetime_tool import DateTimeTool


# Tool registry
registry = ToolRegistry(
    [
        CalculatorTool(),
        DateTimeTool(),
    ]
)

# Core components
generator = Generator()

planner = Planner(
    generator=generator,
    registry=registry,
)

executor = Executor(
    registry=registry,
)

pipeline = Pipeline(
    planner=planner,
    executor=executor,
    generator=generator,
)


# Normal agent flow tests
questions = [
    "What is 125 * 37?",
    "What is the capital of France?",
    "What time is it right now?",
]


for question in questions:
    print(f"\nQuestion: {question}")

    result = pipeline.run(question)

    print(f"Tool: {result.tool}")
    print(f"Arguments: {result.arguments}")
    print(f"Tool result: {result.tool_result}")
    print(f"Error: {result.error}")
    print(f"Answer: {result.answer}")


# Tool execution error test
print("\n--- Error test ---")

bad_call = ToolCall(
    tool="calculator",
    arguments={},
)

error_result = executor.execute(bad_call)

print(f"Success: {error_result.success}")
print(f"Result: {error_result.result}")
print(f"Error: {error_result.error}")

