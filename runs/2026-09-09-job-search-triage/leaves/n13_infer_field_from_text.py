"""Leaf n13 - infer_field_from_text."""

import html
import json
import re

_INSTRUCTION = (
    "You are given the plain text of a single job posting and the name of one field. "
    "Determine that field's value as stated by this posting text, and nothing else.\n\n"
    "Return a JSON object with exactly these three keys:\n"
    "  value    - the field's value as the text states it, or null if the text does not state it\n"
    "  stated   - true only if the posting text states this field; false otherwise\n"
    "  evidence - the shortest verbatim substring of the posting text that states the value, "
    "or null when stated is false\n\n"
    "Rules: never infer a value the text does not support; when the text is silent about the "
    "field, stated must be false and value must be null. When stated is true, evidence must "
    "appear verbatim in the posting text. Return the JSON object and nothing else."
)


def _collect_strings(value, out):
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            _collect_strings(item, out)
    elif isinstance(value, list):
        for item in value:
            _collect_strings(item, out)


def _plain_text(raw_payload):
    if isinstance(raw_payload, str):
        pieces = [raw_payload]
    else:
        pieces = []
        _collect_strings(raw_payload, pieces)
    text = "\n".join(pieces)
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t\r\f\v]+", " ", text).strip()


def _as_object(answer):
    if isinstance(answer, dict):
        return answer
    if isinstance(answer, str):
        try:
            parsed = json.loads(answer)
        except ValueError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def infer_field_from_text(raw_payload, field):
    text = _plain_text(raw_payload)

    answer = _as_object(ai(_INSTRUCTION, {"field": field, "posting_text": text}))

    if not answer.get("stated"):
        return {
            "value": None,
            "stated": False,
            "provenance": {
                "kind": "not_stated",
                "field": field,
                "searched": "posting_text",
            },
        }

    evidence = answer.get("evidence")
    start = text.find(evidence) if isinstance(evidence, str) and evidence else -1
    if start < 0:
        return {
            "value": None,
            "stated": False,
            "provenance": {
                "kind": "not_stated",
                "field": field,
                "searched": "posting_text",
                "note": "no verbatim evidence located in the payload text",
            },
        }

    return {
        "value": answer.get("value"),
        "stated": True,
        "provenance": {
            "kind": "text_span",
            "field": field,
            "start": start,
            "end": start + len(evidence),
            "quote": evidence,
        },
    }
