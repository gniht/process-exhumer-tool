"""Leaf n11 - evaluate_criterion."""

import re

_UNKNOWN = object()


def _compare(operator, actual, expected):
    name = str(operator).strip().lower()
    if name in ("eq", "=="):
        return actual == expected
    if name in ("ne", "!="):
        return actual != expected
    if name in ("lt", "<"):
        return actual < expected
    if name in ("lte", "le", "<="):
        return actual <= expected
    if name in ("gt", ">"):
        return actual > expected
    if name in ("gte", "ge", ">="):
        return actual >= expected
    if name == "in":
        return actual in expected
    if name == "not_in":
        return actual not in expected
    if name == "contains":
        return expected in actual
    if name == "not_contains":
        return expected not in actual
    if name == "matches":
        return re.search(str(expected), str(actual)) is not None
    if name == "not_matches":
        return re.search(str(expected), str(actual)) is None
    return _UNKNOWN


def evaluate_criterion(fields, criterion):
    field_name = criterion["field"]
    record = (fields or {}).get(field_name)

    if record is None or not record.get("stated", False):
        return {
            "criterion_id": criterion.get("id"),
            "outcome": "not_answerable",
            "field": field_name,
            "provenance": (record or {}).get("provenance"),
            "reason": "the posting does not state this field",
        }

    try:
        verdict = _compare(criterion["operator"], record.get("value"), criterion.get("value"))
    except TypeError:
        return {
            "criterion_id": criterion.get("id"),
            "outcome": "not_answerable",
            "field": field_name,
            "provenance": record.get("provenance"),
            "reason": "the stated value cannot be compared with this operator",
        }

    if verdict is _UNKNOWN:
        raise ValueError("unknown criterion operator: {!r}".format(criterion["operator"]))

    return {
        "criterion_id": criterion.get("id"),
        "outcome": "satisfied" if verdict else "not_satisfied",
        "field": field_name,
        "provenance": record.get("provenance"),
        "reason": "operator {} applied to the stated value".format(criterion["operator"]),
    }
