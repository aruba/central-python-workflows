import re
from dataclasses import dataclass
from typing import Any, Callable, Literal


@dataclass(frozen=True)
class Field:
    type: Literal["string", "list[string]", "bool", "int"]
    required: bool
    max_len: int | None
    pattern: str | None
    help: str
    example: Any

    def validate(self, value, field_name):
        if self.type == "string":
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be a string")
            if not value.strip():
                if self.required:
                    raise ValueError(f"{field_name} must be a non-empty string")
                return
            values = [value]
        elif self.type == "list[string]":
            if not isinstance(value, list) or not all(
                isinstance(item, str) for item in value
            ):
                raise ValueError(f"{field_name} must be a list of strings")
            if not value:
                if self.required:
                    raise ValueError(
                        f"{field_name} must be a non-empty list of strings"
                    )
                return
            values = value
        elif self.type == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"{field_name} must be a bool")
            values = []
        elif self.type == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{field_name} must be an int")
            values = []
        else:
            raise ValueError(f"{field_name} has unsupported field type '{self.type}'")

        if self.max_len is not None:
            if self.type == "list[string]" and len(value) > self.max_len:
                raise ValueError(
                    f"{field_name} must contain at most {self.max_len} items"
                )
            if self.type == "string" and len(value) > self.max_len:
                raise ValueError(
                    f"{field_name} must be at most {self.max_len} characters"
                )

        if self.pattern is not None:
            for item in values:
                if not re.fullmatch(self.pattern, item):
                    raise ValueError(
                        f"{field_name} must match pattern {self.pattern}"
                    )


@dataclass(frozen=True)
class AddOnStep:
    key: str
    label: str
    description: str
    field: Field
    run: Callable[[Any, Any], Any]
