"""
Given a set of configured sources, a recency specification, a set of criteria, and the corpus held from prior runs: every posting offered by a source that falls within that source's recency window and is not already held is retrieved and stored with its raw payload intact; every stored posting has fields extracted into a common schema, each extracted field carrying the location within its raw payload that it was derived from; every posting in the corpus is evaluated against the current criteria, each criterion yielding satisfied, not satisfied, or not answerable from this posting; every verdict names the extracted field and source location it rests on; postings the user has suppressed are withheld from the presented assessments but remain stored, with their suppression reversible; no posting is absent from the presented assessments without a recorded reason; and the returned corpus accounts for every posting the run retrieved together with the dispositions carried in.
"""

import inspect
import json
import re
import subprocess
import sys

_QUALIFIED = re.compile(r"__n\d+$")


def ai(instruction, payload):
    caller = next(
        (f.function for f in inspect.stack()[1:] if _QUALIFIED.search(f.function)),
        inspect.stack()[1].function,
    )
    prompt = (
        instruction
        + "\n\nPayload (JSON):\n"
        + json.dumps(payload)
        + "\n\nRespond with ONLY the return value, as JSON."
    )
    r = subprocess.run(
        ["claude", "-p", prompt], capture_output=True, text=True, timeout=300
    )
    raw = r.stdout.strip()
    if raw.startswith("```"):
        raw = raw.strip("`\n")
        raw = raw[raw.find("\n") + 1:] if raw.startswith("json") else raw
    value = json.loads(raw)
    print(
        json.dumps(
            {
                "caller": caller,
                "instruction": instruction,
                "payload": payload,
                "return": value,
            }
        ),
        file=sys.stderr,
    )
    return value

def retrieve_from_source__n7(source, window_start, held_posting_ids):
    # --- leaf n7 code, verbatim ---
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

    # --- end leaf code ---
    return retrieve_from_source(source, window_start, held_posting_ids)

def acquire_new_postings__n2(sources, recency_spec, corpus):
    retrieve_from_source = retrieve_from_source__n7
    # --- glue, verbatim ---
    from datetime import datetime, timedelta, timezone

    floor = (
        datetime.now(timezone.utc) - timedelta(days=recency_spec["lookback_days"])
    ).isoformat()

    new_postings = []
    for source in sources:
        held = [e for e in corpus["entries"] if e["source_id"] == source["id"]]
        held_posting_ids = sorted({e["source_posting_id"] for e in held})
        published = [e["published_at"] for e in held if e.get("published_at")]
        window_start = max(published) if published else floor
        new_postings.extend(
            retrieve_from_source(source, window_start, held_posting_ids)
        )
    return new_postings
    # --- end glue ---

def merge_corpus__n3(corpus, new_postings):
    # --- leaf n3 code, verbatim ---
    """Leaf n3 - merge_corpus."""


    def merge_corpus(corpus, new_postings):
        entries = []
        seen = set()

        for entry in (corpus or {}).get("entries") or []:
            key = (entry["source_id"], entry["source_posting_id"])
            if key in seen:
                continue
            seen.add(key)
            entries.append(entry)

        for posting in new_postings or []:
            key = (posting["source_id"], posting["source_posting_id"])
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "source_id": posting["source_id"],
                    "source_posting_id": posting["source_posting_id"],
                    "published_at": posting.get("published_at"),
                    "raw_payload": posting["raw_payload"],
                    "fields": {},
                    "dispositions": {"viewed": False, "suppressed": False},
                }
            )

        corpus_with_new = dict(corpus or {})
        corpus_with_new["entries"] = entries
        return corpus_with_new

    # --- end leaf code ---
    return merge_corpus(corpus, new_postings)

def pluck_mapped_field__n12(raw_payload, field, locator):
    # --- leaf n12 code, verbatim ---
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

    # --- end leaf code ---
    return pluck_mapped_field(raw_payload, field, locator)

def infer_field_from_text__n13(raw_payload, field):
    # --- leaf n13 code, verbatim ---
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

    # --- end leaf code ---
    return infer_field_from_text(raw_payload, field)

def derive_field__n10(entry, field, source_definition):
    pluck_mapped_field = pluck_mapped_field__n12
    infer_field_from_text = infer_field_from_text__n13
    # --- glue, verbatim ---
    field_map = source_definition.get("field_map") or {}
    if field in field_map:
        field_record = pluck_mapped_field(entry["raw_payload"], field, field_map[field])
    else:
        field_record = infer_field_from_text(entry["raw_payload"], field)
    return field_record
    # --- end glue ---

def extract_entry_fields__n8(entry, required_fields, source_definition):
    derive_field = derive_field__n10
    # --- glue, verbatim ---
    fields = dict(entry.get("fields") or {})
    for field in required_fields:
        if field in fields:
            continue
        fields[field] = derive_field(entry, field, source_definition)
    entry_with_fields = dict(entry)
    entry_with_fields["fields"] = fields
    return entry_with_fields
    # --- end glue ---

def extract_fields__n4(corpus_with_new, criteria, sources):
    extract_entry_fields = extract_entry_fields__n8
    # --- glue, verbatim ---
    required_fields = sorted({criterion["field"] for criterion in criteria})
    source_by_id = {source["id"]: source for source in sources}
    entries = []
    for entry in corpus_with_new["entries"]:
        entries.append(
            extract_entry_fields(
                entry,
                required_fields,
                source_by_id.get(
                    entry["source_id"], {"id": entry["source_id"], "field_map": {}}
                ),
            )
        )
    extracted_corpus = dict(corpus_with_new)
    extracted_corpus["entries"] = entries
    return extracted_corpus
    # --- end glue ---

def evaluate_criterion__n11(fields, criterion):
    # --- leaf n11 code, verbatim ---
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

    # --- end leaf code ---
    return evaluate_criterion(fields, criterion)

def assess_entry__n9(entry, criteria):
    evaluate_criterion = evaluate_criterion__n11
    # --- glue, verbatim ---
    verdicts = []
    for criterion in criteria:
        verdicts.append(evaluate_criterion(entry["fields"], criterion))
    assessment = {
        "source_id": entry["source_id"],
        "source_posting_id": entry["source_posting_id"],
        "fields": entry["fields"],
        "verdicts": verdicts,
    }
    return assessment
    # --- end glue ---

def assess_postings__n5(extracted_corpus, criteria):
    assess_entry = assess_entry__n9
    # --- glue, verbatim ---
    assessments = []
    for entry in extracted_corpus["entries"]:
        assessments.append(assess_entry(entry, criteria))
    return assessments
    # --- end glue ---

def summarize_criteria__n6(assessments, criteria):
    # --- leaf n6 code, verbatim ---
    """Leaf n6 - summarize_criteria."""


    def summarize_criteria(assessments, criteria):
        diagnostics = []

        for criterion in criteria or []:
            criterion_id = criterion.get("id")
            counts = {"satisfied": 0, "not_satisfied": 0, "not_answerable": 0}
            not_answerable = []

            for assessment in assessments or []:
                for verdict in assessment.get("verdicts") or []:
                    if verdict.get("criterion_id") != criterion_id:
                        continue
                    outcome = verdict.get("outcome")
                    if outcome in counts:
                        counts[outcome] += 1
                    if outcome == "not_answerable":
                        not_answerable.append(
                            {
                                "source_id": assessment.get("source_id"),
                                "source_posting_id": assessment.get("source_posting_id"),
                            }
                        )

            diagnostics.append(
                {
                    "criterion_id": criterion_id,
                    "discriminated": counts["satisfied"] > 0 and counts["not_satisfied"] > 0,
                    "outcome_counts": counts,
                    "not_answerable_posting_ids": not_answerable,
                }
            )

        return diagnostics

    # --- end leaf code ---
    return summarize_criteria(assessments, criteria)

def root__n1(sources, criteria, recency_spec, corpus):
    acquire_new_postings = acquire_new_postings__n2
    merge_corpus = merge_corpus__n3
    extract_fields = extract_fields__n4
    assess_postings = assess_postings__n5
    summarize_criteria = summarize_criteria__n6
    # --- glue, verbatim ---
    new_postings = acquire_new_postings(sources, recency_spec, corpus)
    corpus_with_new = merge_corpus(corpus, new_postings)
    extracted_corpus = extract_fields(corpus_with_new, criteria, sources)
    all_assessments = assess_postings(extracted_corpus, criteria)
    criteria_diagnostics = summarize_criteria(all_assessments, criteria)

    suppressed = {
        (e["source_id"], e["source_posting_id"])
        for e in extracted_corpus["entries"]
        if e["dispositions"].get("suppressed")
    }
    assessments = [
        a for a in all_assessments
        if (a["source_id"], a["source_posting_id"]) not in suppressed
    ]

    return {
        "assessments": assessments,
        "criteria_diagnostics": criteria_diagnostics,
        "updated_corpus": extracted_corpus,
    }
    # --- end glue ---

if __name__ == "__main__":
    import sys, json
    args = json.loads(sys.stdin.read())
    print(json.dumps(root__n1(**args), default=str))
