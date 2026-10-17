import logging
from typing import Any

from prometheus_client import Counter, Histogram

from app.config import AGENT_MAX_STEPS
from app.executor import Executor
from app.generator import Generator
from app.models import AgentResult, AgentStep, ChatToolCall, ToolCall, ToolResult
from app.tool_registry import ToolRegistry


logger = logging.getLogger(__name__)


AGENT_TOOL_CALLS = Histogram(
    "agent_tool_calls_per_request",
    "Number of tool calls made to answer one request.",
    buckets=(0, 1, 2, 3, 4, 5, 10),
)

AGENT_STEP_LIMIT_REACHED_TOTAL = Counter(
    "agent_step_limit_reached_total",
    "Total number of requests that used up the tool call budget.",
)


SYSTEM_PROMPT = """
You are a helpful AI assistant with access to tools.

Use a tool whenever it is needed to answer accurately, for example for
calculations or the current date and time. You may call tools several
times and use earlier results in later calls.

Rules:
- Never invent tool results.
- If a tool reports an error you can fix, such as a malformed expression,
  call it again with corrected arguments. Keep the user's values.
- If a tool rejects a request, explain the reason to the user. Do not
  change the user's values to make a request succeed.
- When you have the information you need, answer the user directly and
  do not mention internal tools.
""".strip()


STEP_LIMIT_PROMPT = (
    "The tool call limit for this request has been reached. Answer the "
    "user now using only the tool results above. If they are not enough "
    "to answer, say so instead of guessing."
)


FALLBACK_ANSWER = "I could not complete this request with the available tools."


# Upper bound for tool output passed back to the model, so a large tool
# result cannot crowd the question out of the model's context window.
MAX_PROMPT_VALUE_CHARS = 4_000


def format_for_prompt(value) -> str:
    """Render a tool value as bounded text for an LLM prompt."""

    try:
        text = str(value)
    except ValueError:
        # str() refuses integers above Python's digit conversion limit.
        return "[value too large to display]"

    if len(text) <= MAX_PROMPT_VALUE_CHARS:
        return text

    return (
        text[:MAX_PROMPT_VALUE_CHARS]
        + f"\n[truncated: {len(text)} characters in total]"
    )


class Agent:
    """Answers a question with a native tool calling loop.

    Each turn, the model either requests tool calls or answers. Tool results
    and errors are added to the conversation, so the model can use them in
    later calls or correct a failed call itself.
    """

    def __init__(
        self,
        generator: Generator,
        executor: Executor,
        registry: ToolRegistry,
        max_steps: int = AGENT_MAX_STEPS,
    ):
        self.generator = generator
        self.executor = executor
        self.registry = registry
        self.max_steps = max_steps

    def run(self, question: str) -> AgentResult:
        logger.info("Agent run started")

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ]
        tools = self.registry.tool_schemas()
        steps: list[AgentStep] = []

        while True:
            message = self.generator.chat(messages, tools=tools)

            if not message.tool_calls:
                return self._finish(message.content, steps)

            if tools is None:
                # Tools were withdrawn, so further calls are not executed.
                # Returning here also guarantees the loop terminates.
                logger.warning(
                    "Model requested tools after they were withdrawn"
                )
                return self._finish(
                    message.content.strip() or FALLBACK_ANSWER,
                    steps,
                )

            messages.append(self._assistant_message(message.tool_calls))

            for tool_call in message.tool_calls:
                if len(steps) >= self.max_steps:
                    messages.append(
                        self._tool_message(
                            tool_call.name,
                            "Not executed: the tool call limit was reached.",
                        )
                    )
                    continue

                result = self._execute(tool_call, steps)

                messages.append(
                    self._tool_message(
                        tool_call.name,
                        self._describe_result(result),
                    )
                )

                if not result.retryable:
                    # Offering tools again would let the model change the
                    # user's values to get a result, e.g. turning
                    # "2 ** 5000000" into "2 ** 10". Make it explain instead.
                    logger.warning(
                        "Tool '%s' rejected the request, "
                        "asking for a final answer",
                        tool_call.name,
                    )
                    tools = None

            if len(steps) >= self.max_steps and tools is not None:
                logger.warning(
                    "Agent reached the tool call limit of %s",
                    self.max_steps,
                )
                AGENT_STEP_LIMIT_REACHED_TOTAL.inc()
                messages.append({"role": "user", "content": STEP_LIMIT_PROMPT})
                tools = None

    def _execute(
        self,
        tool_call: ChatToolCall,
        steps: list[AgentStep],
    ) -> ToolResult:
        logger.info(
            "Agent step %s: calling tool '%s'",
            len(steps) + 1,
            tool_call.name,
        )

        result = self.executor.execute(
            ToolCall(
                tool=tool_call.name,
                arguments=tool_call.arguments,
            )
        )

        steps.append(
            AgentStep(
                tool=tool_call.name,
                arguments=tool_call.arguments,
                success=result.success,
                result=result.result if result.success else None,
                error=None if result.success else result.error,
            )
        )

        return result

    def _finish(
        self,
        answer: str,
        steps: list[AgentStep],
    ) -> AgentResult:
        AGENT_TOOL_CALLS.observe(len(steps))

        logger.info(
            "Agent run finished after %s tool call(s)",
            len(steps),
        )

        last = steps[-1] if steps else None

        # tool, arguments, tool_result and error describe the last tool call
        # so that single-tool clients keep working; steps has the full trace.
        return AgentResult(
            answer=answer,
            tool=last.tool if last else None,
            arguments=last.arguments if last else None,
            tool_result=last.result if last else None,
            error=last.error if last else None,
            steps=steps,
        )

    @staticmethod
    def _describe_result(result: ToolResult) -> str:
        if result.success:
            return format_for_prompt(result.result)

        if not result.retryable:
            return (
                "The tool rejected this request: "
                f"{format_for_prompt(result.error)}"
            )

        return f"Error: {format_for_prompt(result.error)}"

    @staticmethod
    def _assistant_message(
        tool_calls: list[ChatToolCall],
    ) -> dict[str, Any]:
        return {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": tool_call.name,
                        "arguments": tool_call.arguments,
                    }
                }
                for tool_call in tool_calls
            ],
        }

    @staticmethod
    def _tool_message(tool_name: str, content: str) -> dict[str, Any]:
        return {
            "role": "tool",
            "tool_name": tool_name,
            "content": content,
        }
