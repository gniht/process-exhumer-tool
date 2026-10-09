import re

_EDGE_BEFORE = r"(?<![^\W_])"
_EDGE_AFTER = r"(?![^\W_])"

# Phrases in which a level word names something other than a level. They are matched first and
# consume their text, so the level word inside them yields nothing.
_NOT_LEVELS = re.compile(
    _EDGE_BEFORE
    + r"(?:chief\s+of\s+staff|staff\s+accountant|staff\s+nurse|staff\s+writer|support\s+staff|"
    r"medical\s+staff|lead\s+generation|lead\s+gen|lead\s+qualification)"
    + _EDGE_AFTER,
    re.IGNORECASE,
)

# Each level and the words or phrases that denote it.
_LEVELS = [
    ("executive", r"chief\s+[\w\s&,-]*?officer|vice\s+president|svp|evp|avp|vp"),
    ("director", r"director"),
    ("manager", r"manager|mgr"),
    ("principal", r"principal"),
    ("staff", r"staff"),
    ("lead", r"lead"),
    ("senior", r"senior|sr\.?"),
    ("junior", r"junior|jr\.?|entry[\s-]level"),
    ("intern", r"internship|intern"),
]
_PATTERN = re.compile(
    "|".join(f"(?P<{level}>{_EDGE_BEFORE}(?:{words})(?![^\\W_]))" for level, words in _LEVELS),
    re.IGNORECASE,
)


def derive_seniority(title):
    title = title or {}
    text = title.get("value")
    if not isinstance(text, str):
        return {"value": None, "evidence": []}
    path = next((e["path"] for e in title.get("evidence") or [] if e.get("value") == text), "title")

    excluded = [match.span() for match in _NOT_LEVELS.finditer(text)]
    evidence = []
    for match in _PATTERN.finditer(text):
        start, end = match.span()
        if any(s < end and start < e for s, e in excluded):
            continue
        evidence.append({"path": path, "span": [start, end], "raw": match.group(0), "value": match.lastgroup})
    levels = sorted({entry["value"] for entry in evidence})
    return {"value": levels or None, "evidence": evidence}
