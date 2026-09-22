"""Leaf n12 - pluck_mapped_field."""


def _resolve(payload, locator):
    """Walk a dotted locator (numeric segments index lists); None if it does not resolve."""
    if locator in (None, "", "."):
        return payload
    current = payload
    for part in str(locator).split("."):
        if isinstance(current, list):
            try:
                index = int(part)
            except ValueError:
                return None
            if not -len(current) <= index < len(current):
                return None
            current = current[index]
        elif isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        else:
            return None
    return current


def pluck_mapped_field(raw_payload, field, locator):
    value = _resolve(raw_payload, locator)
    resolved = value is not None
    return {
        "value": value if resolved else None,
        "stated": resolved,
        "provenance": {
            "kind": "locator",
            "field": field,
            "locator": locator,
            "resolved": resolved,
        },
    }
