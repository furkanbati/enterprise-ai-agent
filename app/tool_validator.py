from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


class ToolArgumentValidator:
    """Validates tool arguments against a JSON Schema."""

    def validate(
        self,
        arguments: dict[str, Any],
        schema: dict[str, Any],
    ) -> None:
        """Validate tool arguments against the provided schema.

        Raises:
            ValueError: If the schema itself is invalid or the arguments
                do not satisfy the schema.
        """
        try:
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema)
        except SchemaError as exc:
            raise ValueError(f"Invalid tool schema: {exc.message}") from exc

        errors = sorted(
            validator.iter_errors(arguments),
            key=lambda error: list(error.path),
        )

        if not errors:
            return

        messages = []

        for error in errors:
            path = ".".join(str(part) for part in error.path)

            if path:
                messages.append(f"{path}: {error.message}")
            else:
                messages.append(error.message)

        raise ValueError("Invalid tool arguments: " + "; ".join(messages))