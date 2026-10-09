import json
import urllib.error
import urllib.request

_TIMEOUT_SECONDS = 30


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


def _single(value, path):
    reached = _read_path(value, path)
    return reached[0][1] if len(reached) == 1 else None


def _fetch(source):
    request = urllib.request.Request(
        source["endpoint"], headers=dict(source.get("headers") or {}), method="GET"
    )
    opener = urllib.request.build_opener()
    opener.addheaders = []  # send the definition's headers, not urllib's default User-Agent
    try:
        with opener.open(request, timeout=_TIMEOUT_SECONDS) as response:
            status = response.status
            body = response.read()
    except urllib.error.HTTPError as error:
        return f"HTTP {error.code}", None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        return f"request failed: {getattr(error, 'reason', error)}", None
    if not 200 <= status < 300:
        return f"HTTP {status}", None
    try:
        return None, json.loads(body)
    except ValueError:
        return "response body is not JSON", None


def fetch_source(source):
    source_id = source.get("id") if isinstance(source, dict) else None

    def failed(reason):
        return {"source_id": source_id, "status": "failed", "reason": reason}

    try:
        reason, data = _fetch(source)
        if reason is not None:
            return failed(reason)
        list_path = source.get("list_path")
        listed = data if list_path is None else _single(data, list_path)
        if not isinstance(listed, list):
            return failed(f"no list at {list_path!r}" if list_path else "response is not a list")
        id_path = source["id_path"]
        postings, seen = [], set()
        for index, element in enumerate(listed):
            if not isinstance(element, dict):
                return failed(f"element {index} is not an object")
            raw_id = _single(element, id_path)
            if isinstance(raw_id, bool) or not isinstance(raw_id, (str, int)) or raw_id == "":
                return failed(f"element {index} has no ID at {id_path!r}")
            posting_id = str(raw_id)
            if posting_id in seen:
                continue
            seen.add(posting_id)
            postings.append({"posting_id": posting_id, "payload": element})
        return {"source_id": source_id, "status": "ok", "postings": postings}
    except Exception as error:  # the contract: never raises
        return failed(f"unexpected error: {type(error).__name__}: {error}")
