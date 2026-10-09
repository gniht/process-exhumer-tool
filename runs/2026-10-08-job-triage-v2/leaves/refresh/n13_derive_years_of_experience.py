import re

_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
}
_N = r"(?<![\w.])(?:\d{1,2}|" + "|".join(sorted(_WORDS, key=len, reverse=True)) + r")(?![\w.])"
_YEARS = r"(?:years?|yrs?)\b"
_DASH = r"(?:-|–|—|to)"
# Each alternative states a minimum number of years; the named group holds that minimum.
_REQUIREMENT = re.compile(
    "|".join([
        rf"\b(?:at\s+least\s+|(?:a\s+)?minimum\s+(?:of\s+)?)(?P<least>{_N})\s*\+?\s*{_YEARS}",
        rf"(?P<range>{_N})\s*{_DASH}\s*{_N}\s*\+?\s*{_YEARS}",
        rf"(?P<plus>{_N})\s*\+\s*{_YEARS}",
        rf"(?P<more>{_N})\s+or\s+more\s+{_YEARS}",
        rf"(?P<of>{_N})\s+{_YEARS}(?:['’]?\s+experience\b|\s+of\s+(?:[\w-]+\s+){{0,4}}?experience\b)",
    ]),
    re.IGNORECASE,
)


def _to_int(text):
    text = text.lower()
    return int(text) if text.isdigit() else _WORDS[text]


def derive_years_of_experience(full_text):
    evidence = []
    for entry in (full_text or {}).get("evidence") or []:
        text = entry.get("value")
        if not isinstance(text, str):
            continue
        for match in _REQUIREMENT.finditer(text):
            minimum = _to_int(next(group for group in match.groups() if group is not None))
            evidence.append({"path": entry["path"], "span": list(match.span()),
                             "raw": match.group(0), "value": minimum})
    if not evidence:
        return {"value": None, "evidence": []}
    return {"value": min(entry["value"] for entry in evidence), "evidence": evidence}
