#!/usr/bin/env python3
"""Deterministic AI Gate — 5-gate verification contract."""

import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


class GateTaxonomy:
    TYPE = "TYPE"
    RANGE = "RANGE"
    ENUM = "ENUM"
    LENGTH = "LENGTH"
    FORMAT = "FORMAT"


ALLOWED_STATUSES = {"SUCCESS", "CANNOT_FULFILL", "REJECTED"}
ISO_8601_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$")


@dataclass(frozen=True)
class Violation:
    path: str
    gate: str
    expected: str
    actual: str
    message: str


def _violate(path: str, gate: str, expected: str, actual: str, message: str) -> Violation:
    return Violation(path=path, gate=gate, expected=expected, actual=actual, message=message)


def verify_payload(raw_payload: dict) -> dict:
    violations: list[Violation] = []

    if not isinstance(raw_payload, dict):
        return _build_error("Payload root must be a dict")

    touchpoint_id = raw_payload.get("touchpoint_id")
    result = raw_payload.get("result")
    confidence = raw_payload.get("confidence")
    status = raw_payload.get("status")
    metadata = raw_payload.get("metadata")

    # TYPE gate
    if not isinstance(touchpoint_id, str):
        violations.append(_violate("$.touchpoint_id", GateTaxonomy.TYPE, "str", type(touchpoint_id).__name__, "touchpoint_id must be a string"))
    if not isinstance(result, str):
        violations.append(_violate("$.result", GateTaxonomy.TYPE, "str", type(result).__name__, "result must be a string"))
    if not isinstance(confidence, (int, float)):
        violations.append(_violate("$.confidence", GateTaxonomy.TYPE, "float", type(confidence).__name__, "confidence must be a float"))
    if not isinstance(status, str):
        violations.append(_violate("$.status", GateTaxonomy.TYPE, "str", type(status).__name__, "status must be a string"))
    if not isinstance(metadata, dict):
        violations.append(_violate("$.metadata", GateTaxonomy.TYPE, "dict", type(metadata).__name__, "metadata must be a dict"))

    # LENGTH gate
    if isinstance(touchpoint_id, str) and len(touchpoint_id) < 1:
        violations.append(_violate("$.touchpoint_id", GateTaxonomy.LENGTH, "min_length=1", f"len={len(touchpoint_id)}", "touchpoint_id cannot be empty"))
    if isinstance(result, str) and len(result) < 1:
        violations.append(_violate("$.result", GateTaxonomy.LENGTH, "min_length=1", f"len={len(result)}", "result cannot be empty"))
    if isinstance(metadata, dict):
        provider = metadata.get("provider")
        if isinstance(provider, str) and len(provider) < 1:
            violations.append(_violate("$.metadata.provider", GateTaxonomy.LENGTH, "min_length=1", f"len={len(provider)}", "provider cannot be empty"))

    # RANGE gate
    if isinstance(confidence, (int, float)) and not (0.0 <= float(confidence) <= 1.0):
        violations.append(_violate("$.confidence", GateTaxonomy.RANGE, "0.0 <= value <= 1.0", str(float(confidence)), "confidence out of range"))

    # ENUM gate
    if isinstance(status, str) and status not in ALLOWED_STATUSES:
        violations.append(_violate("$.status", GateTaxonomy.ENUM, f"one of {sorted(ALLOWED_STATUSES)}", status, "status not allowed"))

    # FORMAT gate
    if isinstance(metadata, dict):
        timestamp = metadata.get("timestamp")
        if isinstance(timestamp, str) and not ISO_8601_PATTERN.match(timestamp):
            violations.append(_violate("$.metadata.timestamp", GateTaxonomy.FORMAT, ISO_8601_PATTERN.pattern, timestamp, "timestamp must be ISO-8601"))

    if violations:
        return _build_error(
            detail="Payload failed verification gates",
            violations=[asdict(v) for v in violations],
        )

    ts = metadata.get("timestamp") if isinstance(metadata, dict) else ""
    prov = metadata.get("provider") if isinstance(metadata, dict) else ""
    return {
        "touchpoint_id": touchpoint_id,
        "result": result,
        "confidence": float(confidence),
        "status": status,
        "metadata": {
            "timestamp": ts,
            "provider": prov,
        },
    }


def _build_error(detail: str, violations: list[dict] | None = None) -> dict:
    return {
        "error": True,
        "code": "SCHEMA_VIOLATION",
        "status": 400,
        "title": "Schema Violation",
        "detail": detail,
        "violations": violations or [],
        "circuit_breaker": "OPEN",
    }


if __name__ == "__main__":
    broken_payload = {
        "touchpoint_id": "api-summary",
        "result": "",
        "confidence": "high",
        "status": "UNKNOWN",
        "metadata": {
            "timestamp": "bad_date",
            "provider": "anthropic",
        },
    }

    outcome = verify_payload(broken_payload)
    print(json.dumps(outcome, indent=2))
    sys.exit(1 if outcome.get("error") else 0)
