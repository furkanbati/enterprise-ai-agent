import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


CONFIG_PATH = Path(__file__).resolve().parents[1] / "app" / "config.py"


def load_config_with_environment(
    monkeypatch,
    name,
    value,
):
    monkeypatch.setenv(name, value)

    spec = importlib.util.spec_from_file_location(
        "test_config_module",
        CONFIG_PATH,
    )

    module = importlib.util.module_from_spec(spec)

    with pytest.raises(ValueError):
        spec.loader.exec_module(module)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("GENERATOR_MAX_RETRIES", "-1"),
        ("EXECUTOR_MAX_RETRIES", "-1"),
        ("PIPELINE_MAX_REPLANS", "-1"),
        ("RETRY_BASE_DELAY", "-1"),
        ("TOOL_TIMEOUT", "-1"),
    ],
)
def test_rejects_negative_retry_settings(name, value):
    environment = os.environ | {name: value}

    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert f"{name} must be zero or greater." in result.stderr


@pytest.mark.parametrize(
    "name",
    [
        "OLLAMA_HOST",
        "CHAT_MODEL",
    ],
)
def test_rejects_empty_string_settings(name):
    environment = os.environ | {name: ""}

    result = subprocess.run(
        [sys.executable, "-c", "import app.config"],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert f"{name} cannot be empty." in result.stderr


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("GENERATOR_MAX_RETRIES", "-1"),
        ("EXECUTOR_MAX_RETRIES", "-1"),
        ("PIPELINE_MAX_REPLANS", "-1"),
        ("RETRY_BASE_DELAY", "-1"),
        ("TOOL_TIMEOUT", "-1"),
        ("OLLAMA_HOST", ""),
        ("CHAT_MODEL", ""),
    ],
)
def test_config_validation_runs_under_coverage(
    monkeypatch,
    name,
    value,
):
    load_config_with_environment(
        monkeypatch,
        name,
        value,
    )