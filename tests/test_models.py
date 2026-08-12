import pytest
from pydantic import ValidationError

from app.models import PlannerResponse


def test_valid_tool_response():
    response = PlannerResponse(
        tool="calculator",
        arguments={"expression": "10 / 2"},
    )

    assert response.tool == "calculator"
    assert response.arguments == {"expression": "10 / 2"}


def test_valid_no_tool_response():
    response = PlannerResponse(
        tool=None,
        arguments={},
    )

    assert response.tool is None
    assert response.arguments == {}


def test_rejects_arguments_when_no_tool():
    with pytest.raises(ValidationError):
        PlannerResponse(
            tool=None,
            arguments={"expression": "10 / 2"},
        )


def test_rejects_empty_tool_name():
    with pytest.raises(ValidationError):
        PlannerResponse(
            tool="",
            arguments={},
        )


def test_rejects_extra_fields():
    with pytest.raises(ValidationError):
        PlannerResponse(
            tool="calculator",
            arguments={"expression": "10 / 2"},
            unexpected="value",
        )