import logging

from app.config import PIPELINE_MAX_REPLANS
from app.executor import Executor
from app.generator import Generator
from app.models import AgentResult
from app.planner import Planner

logger = logging.getLogger(__name__)


class Pipeline:

    def __init__(
        self,
        planner: Planner,
        executor: Executor,
        generator: Generator,
    ):
        self.planner = planner
        self.executor = executor
        self.generator = generator

    def run(self, question: str) -> AgentResult:
        logger.info("Pipeline execution started")

        tool_call = self.planner.plan(question)

        if tool_call is None:
            logger.info("Planner selected no tool")

            answer = self.generator.generate(question)

            return AgentResult(
                answer=answer,
            )

        logger.info(
            "Planner selected tool '%s'",
            tool_call.tool,
        )

        for attempt in range(PIPELINE_MAX_REPLANS + 1):
            tool_result = self.executor.execute(tool_call)

            if tool_result.success:
                logger.info(
                    "Tool '%s' completed successfully",
                    tool_call.tool,
                )

                answer = self.generator.generate(
                    prompt=self._build_final_prompt(
                        question,
                        tool_call,
                        tool_result.result,
                    ),
                    system_prompt=(
                        "You are a helpful AI assistant. "
                        "Answer the user's question using the tool result. "
                        "Do not mention internal tools or planning."
                    ),
                )

                return AgentResult(
                    answer=answer,
                    tool=tool_call.tool,
                    arguments=tool_call.arguments,
                    tool_result=tool_result.result,
                )

            if attempt >= PIPELINE_MAX_REPLANS:
                logger.error(
                    "Pipeline reached maximum replans"
                )
                break

            logger.warning(
                "Tool '%s' failed, starting replan %s/%s",
                tool_call.tool,
                attempt + 1,
                PIPELINE_MAX_REPLANS,
            )

            corrected_tool_call = self.planner.plan(
                question=question,
                previous_tool=tool_call,
                previous_error=tool_result.error,
            )

            if corrected_tool_call is None:
                logger.warning(
                    "Planner declined further tool usage after failure"
                )
                break

            logger.info(
                "Planner selected corrected tool '%s'",
                corrected_tool_call.tool,
            )

            tool_call = corrected_tool_call

        answer = self.generator.generate(
            prompt=self._build_error_prompt(
                question,
                tool_call,
                tool_result.error,
            ),
            system_prompt=(
                "You are a helpful AI assistant. "
                "A tool failed while processing the user's request. "
                "Explain the issue clearly and do not invent a result."
            ),
        )

        return AgentResult(
            answer=answer,
            tool=tool_call.tool,
            arguments=tool_call.arguments,
            tool_result=None,
            error=tool_result.error,
        )

    def _build_final_prompt(
        self,
        question: str,
        tool_call,
        tool_result,
    ) -> str:
        return f"""
User question:
{question}

Tool used:
{tool_call.tool}

Tool result:
{tool_result}

Provide the final answer to the user.
"""

    def _build_error_prompt(
        self,
        question: str,
        tool_call,
        error: str | None,
    ) -> str:
        return f"""
User question:
{question}

Tool used:
{tool_call.tool}

Tool arguments:
{tool_call.arguments}

Tool error:
{error}

Explain the issue to the user without inventing a result.
"""