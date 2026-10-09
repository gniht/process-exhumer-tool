_MARK_ORDER = ("viewed", "saved", "applied", "hidden")


def place_postings(postings, rules, verdicts, marks):
    marks_by_key = {(item["source_id"], item["posting_id"]): set(item["marks"]) for item in marks}
    verdicts_by_key = {(item["source_id"], item["posting_id"]): item["verdicts"] for item in verdicts}
    shown, hidden = [], []

    for entry in postings:
        key = (entry["source_id"], entry["posting_id"])
        its_marks = [mark for mark in _MARK_ORDER if mark in marks_by_key.get(key, set())]
        its_verdicts = verdicts_by_key.get(key, [])
        by_rule = {verdict["rule_id"]: verdict for verdict in its_verdicts}

        reasons = []
        if "hidden" in its_marks:
            reasons.append({"kind": "hidden_by_you"})
        if "saved" not in its_marks:
            for rule in rules:
                verdict = by_rule.get(rule["id"])
                if verdict is None or rule["action"] == "prefer":
                    continue
                result = verdict["result"]
                if (rule["action"] == "require" and result == "not_met") or (
                    rule["action"] == "exclude" and result == "met"
                ):
                    reasons.append({"kind": "failed", "rule_id": rule["id"]})
                elif result == "cant_tell" and rule.get("unknowns", "show") == "hide":
                    reasons.append({"kind": "couldnt_check", "rule_id": rule["id"]})

        prefer_met = sum(
            1 for rule in rules
            if rule["action"] == "prefer" and by_rule.get(rule["id"], {}).get("result") == "met"
        )
        posted = ((entry.get("fields") or {}).get("posted_date") or {}).get("value")
        record = {
            "source_id": entry["source_id"],
            "posting_id": entry["posting_id"],
            "fields": entry["fields"],
            "first_seen": entry["first_seen"],
            "listing": entry["listing"],
            "verdicts": [by_rule[rule["id"]] for rule in rules if rule["id"] in by_rule],
            "prefer_met": prefer_met,
            "marks": its_marks,
            "flags": {
                "new": "viewed" not in its_marks,
                "no_longer_listed": entry["listing"]["status"] == "no_longer_listed",
                "no_posting_date": posted is None,
            },
        }
        if reasons:
            hidden.append({**record, "reasons": reasons})
        else:
            shown.append(record)

    def ordering_date(record):
        posted = ((record["fields"] or {}).get("posted_date") or {}).get("value")
        return posted if posted is not None else record["first_seen"]

    # Stable sorts, least significant key first.
    shown.sort(key=lambda r: (r["source_id"], r["posting_id"]))
    shown.sort(key=ordering_date, reverse=True)
    shown.sort(key=lambda r: r["prefer_met"], reverse=True)
    hidden.sort(key=lambda r: (r["source_id"], r["posting_id"]))
    return {"shown": shown, "hidden": hidden}
