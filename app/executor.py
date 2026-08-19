from concurrent.futures import ThreadPoolExecutor, TimeoutError

from app.config import TOOL_MAX_RETRIES, TOOL_TIMEOUT
from app.models import ToolCall, ToolResult
from app.tool_registry import ToolRegistry
from app.tool_validator import ToolArgumentValidator


class Executor:

    def __init__(
        self,
        registry: ToolRegistry,
        validator: ToolArgumentValidator | None = None,
        timeout: float = TOOL_TIMEOUT,
        max_retries: int = TOOL_MAX_RETRIES,
    ):
        self.registry = registry
        self.validator = validator or ToolArgumentValidator()
        self.timeout = timeout
        self.max_retries = max_retries

    def execute(self, tool_call: ToolCall) -> ToolResult:
        try:
            tool = self.registry.get(tool_call.tool)

            self.validator.validate(
                arguments=tool_call.arguments,
                schema=tool.parameters,
            )

            for attempt in range(self.max_retries + 1):
                pool = ThreadPoolExecutor(max_workers=1)

                try:
                    future = pool.submit(
                        tool.execute,
                        tool_call.arguments,
                    )

                    result = future.result(
                        timeout=self.timeout
                    )

                    return ToolResult(
                        success=True,
                        result=result,
                    )

                except TimeoutError:
                    if attempt >= self.max_retries:
                        return ToolResult(
                            success=False,
                            error=(
                                f"Tool execution timed out after "
                                f"{self.timeout} seconds."
                            ),
                        )

                except ConnectionError as exc:
                    if attempt >= self.max_retries:
                        return ToolResult(
                            success=False,
                            error=str(exc),
                        )

                except Exception as exc:
                    return ToolResult(
                        success=False,
                        error=str(exc),
                    )

                finally:
                    pool.shutdown(
                        wait=False
                    )

            return ToolResult(
                success=False,
                error="Tool execution failed.",
            )

        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
            )