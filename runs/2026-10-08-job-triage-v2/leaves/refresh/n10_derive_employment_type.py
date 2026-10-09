import json
import re

_DECLARED = {"full-time", "part-time", "contract", "temporary", "internship"}
_EDGE_BEFORE = r"(?<![^\W_])"
_EDGE_AFTER = r"(?![^\W_])"
# Title words that name the posting's own employment type. 'Contract' alone usually names the
# subject of the work ('Contracts Manager', 'Contract Specialist'), so it counts only when set off
# from the role: in brackets, or after a separator at the end of the title.
_TITLE_WORDS = [
    ("internship", re.compile(_EDGE_BEFORE + r"(?:internship|interns?)" + _EDGE_AFTER, re.IGNORECASE)),
    ("contract", re.compile(_EDGE_BEFORE + r"contractor" + _EDGE_AFTER, re.IGNORECASE)),
    ("contract", re.compile(r"[(\[]\s*contract\s*[)\]]|[-–—,|:]\s*contract\s*$", re.IGNORECASE)),
    ("part-time", re.compile(_EDGE_BEFORE + r"part[\s-]time" + _EDGE_AFTER, re.IGNORECASE)),
    ("temporary", re.compile(_EDGE_BEFORE + r"temporary" + _EDGE_AFTER, re.IGNORECASE)),
    ("temporary", re.compile(r"[(\[]\s*temp\s*[)\]]", re.IGNORECASE)),
    ("full-time", re.compile(_EDGE_BEFORE + r"full[\s-]time" + _EDGE_AFTER, re.IGNORECASE)),
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


def derive_employment_type(payload, source, title):
    evidence, value = [], None
    for locator in (source.get("fields") or {}).get("employment_type") or []:
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

    title = title or {}
    text = title.get("value")
    if not isinstance(text, str):
        return {"value": None, "evidence": evidence}
    path = next((e["path"] for e in title.get("evidence") or [] if e.get("value") == text), "title")
    matches, taken = [], []
    for employment_type, pattern in _TITLE_WORDS:
        for match in pattern.finditer(text):
            span = match.span()
            if any(s < span[1] and span[0] < e for s, e in taken):
                continue
            taken.append(span)
            matches.append({"path": path, "span": list(span), "raw": match.group(0), "value": employment_type})
    named = {match["value"] for match in matches}
    value = named.pop() if len(named) == 1 else None
    return {"value": value, "evidence": evidence + sorted(matches, key=lambda m: m["span"])}
