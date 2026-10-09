import json
import re

_DECLARED = {"remote", "hybrid", "onsite"}
_WORDS = [
    ("remote", re.compile(r"(?<![^\W_])remote(?![^\W_])", re.IGNORECASE)),
    ("hybrid", re.compile(r"(?<![^\W_])hybrid(?![^\W_])", re.IGNORECASE)),
    ("onsite", re.compile(r"(?<![^\W_])(?:on-site|onsite|in-office|in\s+office)(?![^\W_])", re.IGNORECASE)),
]


def _read_path(value, path):
    """Every (indexed path, value) the path reaches; a key followed by [] steps into each element."""
    found = [("", value)]
    for part in path.split("."):
        step_in = part.endswith("[]")
        key = part[:-2] if step_in else part
        reached = []
        for prefix, current in found:
            if key:
                if not isinstance(current, dict) or key not in current:
                    continue
                current = current[key]
                prefix = f"{prefix}.{key}" if prefix else key
            if step_in:
                if isinstance(current, list):
                    reached.extend(
                        (f"{prefix}.{index}" if prefix else str(index), element)
                        for index, element in enumerate(current)
                    )
            else:
                reached.append((prefix, current))
        found = reached
    return found


def _as_key(raw):
    return raw if isinstance(raw, str) else json.dumps(raw)


def derive_work_arrangement(payload, source, location):
    evidence, value = [], None
    for locator in (source.get("fields") or {}).get("work_arrangement") or []:
        values = locator.get("values") or {}
        for path, raw in _read_path(payload, locator["path"]):
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                continue
            mapped = values.get(_as_key(raw))
            if mapped not in _DECLARED:
                mapped = None
            evidence.append({"path": path, "span": None, "raw": raw, "value": mapped})
            if value is None and mapped is not None:
                value = mapped
    if value is not None:
        return {"value": value, "evidence": evidence}

    matches = []
    for entry in (location or {}).get("evidence") or []:
        text = entry.get("value")
        if not isinstance(text, str):
            continue
        for arrangement, pattern in _WORDS:
            for match in pattern.finditer(text):
                matches.append({"path": entry["path"], "span": [match.start(), match.end()],
                                "raw": match.group(0), "value": arrangement})
    named = {match["value"] for match in matches}
    value = named.pop() if len(named) == 1 else None
    return {"value": value, "evidence": evidence + matches}
