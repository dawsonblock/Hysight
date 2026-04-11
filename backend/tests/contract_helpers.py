"""Helpers for validating API payloads against contract/schema.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from copy import deepcopy
from typing import Any, Dict

from jsonschema import FormatChecker
from jsonschema.validators import Draft7Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contract" / "schema.json"


@lru_cache(maxsize=1)
def load_contract_schema() -> Dict[str, Any]:
    with open(SCHEMA_PATH, encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _format_checker() -> FormatChecker:
    return FormatChecker()


def endpoint_contract(
    endpoint: str,
    direction: str = "response",
) -> Dict[str, Any]:
    schema = load_contract_schema()
    try:
        fragment = deepcopy(schema["endpoints"][endpoint][direction])
    except KeyError as exc:
        raise AssertionError(
            f"Missing {direction} contract for endpoint: {endpoint}"
        ) from exc

    return {
        "$schema": schema["$schema"],
        "definitions": deepcopy(schema["definitions"]),
        "allOf": [fragment],
    }


def assert_contract_payload(
    endpoint: str,
    payload: Any,
    direction: str = "response",
) -> None:
    validator = Draft7Validator(
        endpoint_contract(endpoint, direction),
        format_checker=_format_checker(),
    )
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda err: list(err.path),
    )
    if not errors:
        return

    messages = []
    for error in errors:
        path = ".".join(str(part) for part in error.path) or "$"
        messages.append(f"{path}: {error.message}")
    details = "\n".join(messages)
    raise AssertionError(
        f"Contract validation failed for {direction} {endpoint}:\n{details}"
    )
