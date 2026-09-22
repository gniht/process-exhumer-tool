"""Leaf n7 - retrieve_from_source."""

import json
import urllib.request
from datetime import datetime, timezone


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


def _to_moment(raw, fmt):
    """Normalise a timestamp in the source's declared format to an aware UTC datetime."""
    if raw is None:
        return None
    name = str(fmt or "iso8601").strip().lower()
    if name in ("epoch_millis", "epoch_milliseconds", "unix_millis"):
        moment = datetime.fromtimestamp(float(raw) / 1000.0, tz=timezone.utc)
    elif name in ("epoch", "epoch_seconds", "unix", "unix_seconds"):
        moment = datetime.fromtimestamp(float(raw), tz=timezone.utc)
    elif name in ("iso8601", "iso", "rfc3339"):
        text = str(raw).strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        moment = datetime.fromisoformat(text)
    else:
        moment = datetime.strptime(str(raw), str(fmt))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _request_url(source):
    endpoint = source["endpoint"]
    if "{" in endpoint:
        try:
            return endpoint.format(**source)
        except (KeyError, IndexError):
            return endpoint
    return endpoint


def retrieve_from_source(source, window_start, held_posting_ids):
    request = urllib.request.Request(
        _request_url(source), headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(request) as response:
        body = json.loads(response.read().decode("utf-8"))

    listing = _resolve(body, source.get("list_path"))
    if listing is None:
        listing = body
    if not isinstance(listing, list):
        listing = []

    floor = _to_moment(window_start, "iso8601")
    already_held = set(held_posting_ids or ())

    postings = []
    for item in listing:
        raw_id = _resolve(item, source.get("id_locator"))
        if raw_id is None:
            continue
        posting_id = str(raw_id)
        if posting_id in already_held:
            continue
        published = _to_moment(
            _resolve(item, source.get("published_locator")),
            source.get("published_format"),
        )
        if published is None or (floor is not None and published < floor):
            continue
        postings.append(
            {
                "source_id": source["id"],
                "source_posting_id": posting_id,
                "published_at": published.isoformat(),
                "raw_payload": item,
            }
        )
    return postings
