import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from prometheus_client import Counter

from app.config import (
    EXECUTOR_MAX_RETRIES,
    RETRY_BASE_DELAY,
    TOOL_TIMEOUT,
)
from app.models import ToolCall, ToolResult
from app.tool_registry import ToolRegistry
from app.tool_validator import ToolArgumentValidator


logger = logging.getLogger(__name__)


TOOL_CALLS_TOTAL = Counter(
    "agent_tool_calls_total",
    "Total number of tool execution calls.",
    ["tool"],
)

TOOL_FAILURES_TOTAL = Counter(
    "agent_tool_failures_total",
    "Total number of failed tool executions.",
    ["tool"],
)


class Executor:

    def __init__(
        self,
        registry: ToolRegistry,
        validator: ToolArgumentValidator | None = None,
        timeout: float = TOOL_TIMEOUT,
        max_retries: int = EXECUTOR_MAX_RETRIES,
        retry_base_delay: float = RETRY_BASE_DELAY,
    ):
        self.registry = registry
        self.validator = validator or ToolArgumentValidator()
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay

    def _get_retry_delay(self, attempt: int) -> float:
        return self.retry_base_delay * (2**attempt)

    def execute(self, tool_call: ToolCall) -> ToolResult:
        start_time = time.perf_counter()

        TOOL_CALLS_TOTAL.labels(
            tool=tool_call.tool,
        ).inc()

        logger.info(
            "Executing tool '%s'",
            tool_call.tool,
        )

        try:
            tool = self.registry.get(tool_call.tool)

        except ValueError:
            logger.error(
                "Unknown tool requested: '%s'",
                tool_call.tool,
            )

            TOOL_FAILURES_TOTAL.labels(
                tool=tool_call.tool,
            ).inc()

            duration = (
                time.perf_counter() - start_time
            )

            return ToolResult(
                success=False,
                tool=tool_call.tool,
                execution_time=duration,
                error=f"Unknown tool: {tool_call.tool}",
            )

        try:
            self.validator.validate(
                arguments=tool_call.arguments,
                schema=tool.parameters,
            )

        except ValueError as exc:
            logger.error(
                "Invalid arguments for tool '%s': %s",
                tool_call.tool,
                exc,
            )

            TOOL_FAILURES_TOTAL.labels(
                tool=tool_call.tool,
            ).inc()

            duration = (
                time.perf_counter() - start_time
            )

            return ToolResult(
                success=False,
                tool=tool_call.tool,
                execution_time=duration,
                error=str(exc),
            )

        for attempt in range(self.max_retries + 1):
            pool = ThreadPoolExecutor(max_workers=1)

            try:
                future = pool.submit(
                    tool.execute,
                    tool_call.arguments,
                )

                result = future.result(
                    timeout=self.timeout,
                )

                duration = (
                    time.perf_counter() - start_time
                )

                logger.info(
                    "Tool '%s' executed successfully in %.3fs",
                    tool_call.tool,
                    duration,
                )

                return ToolResult(
                    success=True,
                    result=result,
                    tool=tool_call.tool,
                    attempts=attempt + 1,
                    execution_time=duration,
                )

            except TimeoutError:
                logger.warning(
                    "Tool '%s' timed out on attempt %s/%s",
                    tool_call.tool,
                    attempt + 1,
                    self.max_retries + 1,
                )

                future.cancel()

                if attempt >= self.max_retries:
                    duration = (
                        time.perf_counter() - start_time
                    )

                    logger.error(
                        "Tool '%s' timed out after %s attempts",
                        tool_call.tool,
                        attempt + 1,
                    )

                    TOOL_FAILURES_TOTAL.labels(
                        tool=tool_call.tool,
                    ).inc()

                    return ToolResult(
                        success=False,
                        tool=tool_call.tool,
                        attempts=attempt + 1,
                        execution_time=duration,
                        error=(
                            f"Tool execution timed out after "
                            f"{self.timeout} seconds."
                        ),
                    )

                delay = self._get_retry_delay(attempt)

                logger.warning(
                    "Retrying tool '%s' in %.2fs",
                    tool_call.tool,
                    delay,
                )

                time.sleep(delay)

            except ConnectionError as exc:
                logger.warning(
                    "Tool '%s' failed with ConnectionError: %s",
                    tool_call.tool,
                    exc,
                )

                if attempt >= self.max_retries:
                    duration = (
                        time.perf_counter() - start_time
                    )

                    logger.error(
                        "Tool '%s' failed after %s attempts",
                        tool_call.tool,
                        attempt + 1,
                    )

                    TOOL_FAILURES_TOTAL.labels(
                        tool=tool_call.tool,
                    ).inc()

                    return ToolResult(
                        success=False,
                        tool=tool_call.tool,
                        attempts=attempt + 1,
                        execution_time=duration,
                        error=str(exc),
                    )

                delay = self._get_retry_delay(attempt)

                logger.warning(
                    "Retrying tool '%s' in %.2fs",
                    tool_call.tool,
                    delay,
                )

                time.sleep(delay)

            except Exception as exc:
                duration = (
                    time.perf_counter() - start_time
                )

                logger.exception(
                    "Tool '%s' raised an unexpected exception",
                    tool_call.tool,
                )

                TOOL_FAILURES_TOTAL.labels(
                    tool=tool_call.tool,
                ).inc()

                return ToolResult(
                    success=False,
                    tool=tool_call.tool,
                    attempts=attempt + 1,
                    execution_time=duration,
                    error=str(exc),
                )

            finally:
                pool.shutdown(wait=False)

        duration = (
            time.perf_counter() - start_time
        )

        logger.error(
            "Tool '%s' failed unexpectedly",
            tool_call.tool,
        )

        TOOL_FAILURES_TOTAL.labels(
            tool=tool_call.tool,
        ).inc()

        return ToolResult(
            success=False,
            tool=tool_call.tool,
            attempts=self.max_retries + 1,
            execution_time=duration,
            error="Tool execution failed.",
        )