import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("MAX_RETRIES", "-1"),
        ("RETRY_BASE_DELAY", "-1"),
        ("TOOL_MAX_RETRIES", "-1"),
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
