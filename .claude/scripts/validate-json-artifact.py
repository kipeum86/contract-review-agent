#!/usr/bin/env python3
"""Validate project JSON artifacts against the local schema subset.

The project deliberately avoids adding a runtime dependency on ``jsonschema``.
This helper implements the small JSON Schema subset used by ``.claude/schemas``:
type, required, properties, patternProperties, additionalProperties, items,
enum, minimum, minLength, minItems, and pattern.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


class ValidationError(Exception):
    pass


def format_path(parts: list[str]) -> str:
    if not parts:
        return "$"
    return "$" + "".join(parts)


def type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def validate_type(value: Any, schema: dict[str, Any], path: list[str], errors: list[str]) -> None:
    expected = schema.get("type")
    if expected is None:
        return

    if isinstance(expected, list):
        if not any(type_matches(value, item) for item in expected):
            errors.append(f"{format_path(path)}: expected one of {expected}, got {type(value).__name__}")
        return

    if not type_matches(value, expected):
        errors.append(f"{format_path(path)}: expected {expected}, got {type(value).__name__}")


def validate(value: Any, schema: dict[str, Any], path: list[str] | None = None) -> list[str]:
    errors: list[str] = []
    _validate(value, schema, path or [], errors)
    return errors


def _validate(value: Any, schema: dict[str, Any], path: list[str], errors: list[str]) -> None:
    validate_type(value, schema, path, errors)

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{format_path(path)}: value {value!r} is not one of {schema['enum']!r}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            errors.append(f"{format_path(path)}: string shorter than minLength {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{format_path(path)}: string does not match pattern {schema['pattern']!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{format_path(path)}: value is less than minimum {schema['minimum']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            errors.append(f"{format_path(path)}: array shorter than minItems {schema['minItems']}")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate(item, item_schema, path + [f"[{index}]"], errors)

    if isinstance(value, dict):
        required = schema.get("required") or []
        for key in required:
            if key not in value:
                errors.append(f"{format_path(path)}: missing required property {key!r}")

        properties = schema.get("properties") or {}
        pattern_properties = schema.get("patternProperties") or {}
        compiled_patterns = [
            (re.compile(pattern), pattern_schema)
            for pattern, pattern_schema in pattern_properties.items()
        ]

        for key, item in value.items():
            matched = False
            if key in properties:
                matched = True
                _validate(item, properties[key], path + [f".{key}"], errors)

            for pattern, pattern_schema in compiled_patterns:
                if pattern.search(key):
                    matched = True
                    _validate(item, pattern_schema, path + [f".{key}"], errors)

            if not matched and schema.get("additionalProperties") is False:
                errors.append(f"{format_path(path)}: unexpected property {key!r}")


def validate_artifact(schema_path: Path, input_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    data = json.loads(input_path.read_text(encoding="utf-8"))
    errors = validate(data, schema)

    # Project-specific invariant that is awkward to express with the local
    # schema subset: comment text prefix must match the declared audience.
    if schema_path.name == "comments.schema.json" and isinstance(data, dict):
        for clause_id, comments in data.items():
            if clause_id == "_meta" or not isinstance(comments, list):
                continue
            for index, comment in enumerate(comments):
                if not isinstance(comment, dict):
                    continue
                audience = comment.get("audience")
                text = comment.get("text", "")
                if audience in {"EXTERNAL", "INTERNAL"} and not text.startswith(f"[{audience}] "):
                    errors.append(
                        f"$.{clause_id}[{index}].text: prefix must match audience {audience!r}"
                    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a project JSON artifact.")
    parser.add_argument("--schema", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()

    errors = validate_artifact(args.schema, args.input)
    if errors:
        print(json.dumps({"success": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({"success": True, "errors": []}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
