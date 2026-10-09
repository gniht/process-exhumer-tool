import datetime
import re

_ISO_8601 = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})"
    r"(?:[T ]\d{2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?(?:Z|[+-]\d{2}(?::?\d{2})?)?)?"
)


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


def _parse(raw, date_format):
    if date_format == "iso8601":
        if not isinstance(raw, str):
            return None
        match = _ISO_8601.fullmatch(raw.strip())
        if not match:
            return None
        year, month, day = (int(part) for part in match.groups())
        return datetime.date(year, month, day).isoformat()
    if date_format == "epoch_millis":
        if isinstance(raw, bool):
            return None
        if isinstance(raw, str) and re.fullmatch(r"\d+", raw.strip()):
            raw = int(raw.strip())
        if not isinstance(raw, (int, float)):
            return None
        moment = datetime.datetime.fromtimestamp(raw / 1000, tz=datetime.timezone.utc)
        return moment.date().isoformat()
    return None


def read_posted_date(payload, source):
    date = source.get("date")
    if not date:
        return {"value": None, "evidence": []}
    reached = [(path, raw) for path, raw in _read_path(payload, date["path"]) if raw is not None]
    if not reached:
        return {"value": None, "evidence": []}
    path, raw = reached[0]
    try:
        value = _parse(raw, date.get("format"))
    except (ValueError, OverflowError, OSError):
        value = None
    return {"value": value, "evidence": [{"path": path, "span": None, "raw": raw, "value": value}]}
