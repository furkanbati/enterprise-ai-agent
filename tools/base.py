from abc import ABC, abstractmethod
from typing import Any


class ToolRequestRejected(ValueError):
    """The tool understood the request but will not carry it out.

    Raise this when the request itself cannot be fulfilled, for example
    because it exceeds a limit. Another tool call could only succeed by
    changing what the user asked for, so the agent withdraws the tools and
    has the model explain the failure instead.
    """


class Tool(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]:
        pass

    @abstractmethod
    def execute(self, arguments: dict[str, Any]) -> Any:
        pass