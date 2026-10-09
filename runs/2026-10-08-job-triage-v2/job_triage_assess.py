"""job_triage_assess.py: assembled by process-exhumer stage 5 from a verified tree. No model is called, and there are no
decision points, so no decision runtime is included.

Usage: python3 job_triage_assess.py < inputs.json > outputs.json

What this program is (the root contract's behavior):

Given the stored postings, one user's watched sources, rules and marks, and the current date: every stored posting from a watched source appears exactly once, in shown or in hidden, and no other posting appears; every rule yields for every such posting one of met, not met or can't tell, can't tell exactly when the field it tests is unknown or not comparable (a salary in a different currency or pay period from the rule's), and every verdict names the field value it rests on and the location in the payload that value came from; where a field holds alternatives (countries, regions, seniority, or a salary's range), a require or prefer rule is met when any value meets it and an exclude rule is met only when every value meets it; a keyword test matches case-insensitively on whole words or phrases, a trailing * matching any word ending; a within-days test counts back from the current date; a posting is hidden exactly when the user hid it (hidden by you), or it is not saved and fails a require rule or meets an exclude rule (failed: that rule) or gets can't tell on a require or exclude rule set to hide unknowns (couldn't check: that rule), and every hidden posting carries every reason that applies to it; shown postings are ordered by the number of prefer rules met, most first, a prefer rule's can't tell counting as not met, then by posted date, newest first, using the first-seen date for an undated posting, then by source and posting ID; every record carries the user's marks and is flagged new when this user has not viewed it, no longer listed when so marked, and no posting date when undated; each rule's diagnostics give its counts of met, not met and can't tell over the watched postings, the number of hidden postings it is a reason for and how many of those are couldn't check, and the postings it could not check; and the same inputs always give the same outputs.
"""


def evaluate_rule__n5(posting, rule, as_of):
    # --- leaf n5 code, verbatim ---
    import datetime
    import re

    _PARENT = {
        "north_america": "americas", "latin_america": "americas",
        "europe": "emea", "middle_east": "emea", "africa": "emea",
        "asia": "apac", "oceania": "apac",
    }
    _SINGLE_VALUED = {"company", "work_arrangement", "employment_type", "listing_status"}
    _ALTERNATIVES = {"countries", "regions", "seniority"}


    def _containing(region):
        """The region and every region containing it."""
        chain = [region]
        while chain[-1] in _PARENT:
            chain.append(_PARENT[chain[-1]])
        return chain


    def _norm(value):
        return value.strip().casefold() if isinstance(value, str) else value


    def _keyword_pattern(keyword):
        keyword = keyword.strip()
        continues = keyword.endswith("*")
        if continues:
            keyword = keyword[:-1].rstrip()
        words = keyword.split()
        if not words:
            return None
        body = r"\s+".join(re.escape(word) for word in words)
        tail = r"[^\W_]*" if continues else ""
        return re.compile(r"(?<![^\W_])" + body + tail + r"(?![^\W_])", re.IGNORECASE)


    def _tested(posting, field):
        """The field's value and the evidence it carries."""
        if field == "first_seen":
            value = posting["first_seen"]
            return value, [{"path": "entry.first_seen", "span": None, "raw": value, "value": value}]
        if field == "listing_status":
            listing = posting["listing"]
            return listing["status"], [{"path": "entry.listing", "span": None, "raw": listing, "value": listing["status"]}]
        record = (posting.get("fields") or {}).get(field) or {}
        return record.get("value"), list(record.get("evidence") or [])


    def _over_alternatives(outcomes, action):
        """Combine per-value outcomes ('meets', 'fails', 'unknown') into a verdict for the action."""
        if action == "exclude":
            if all(outcome == "meets" for outcome in outcomes):
                return "met"
            if any(outcome == "fails" for outcome in outcomes):
                return "not_met"
            return "cant_tell"
        if any(outcome == "meets" for outcome in outcomes):
            return "met"
        if any(outcome == "unknown" for outcome in outcomes):
            return "cant_tell"
        return "not_met"


    def _region_outcome(region, wanted):
        if any(r in wanted for r in _containing(region)):
            return "meets"
        if any(region in _containing(w)[1:] for w in wanted):
            return "unknown"  # a rule value lies strictly inside this region
        return "fails"


    def _contains(rule, value, evidence):
        patterns = [(k, p) for k, p in ((k, _keyword_pattern(k)) for k in rule["keywords"]) if p]
        texts = [(e["path"], e["value"]) for e in evidence if isinstance(e.get("value"), str)]
        if rule["field"] == "title":
            texts = [t for t in texts if t[1] == value][:1] or [("title", value)]
        matches = []
        for path, text in texts:
            for keyword, pattern in patterns:
                for match in pattern.finditer(text):
                    matches.append({"path": path, "span": [match.start(), match.end()],
                                    "raw": match.group(0), "value": keyword})
        return ("met", matches) if matches else ("not_met", evidence)


    def _compare(test, amount, number):
        return number >= amount if test == "at_least" else number <= amount


    def evaluate_rule(posting, rule, as_of):
        field, test, action = rule["field"], rule["test"], rule["action"]
        value, evidence = _tested(posting, field)

        def verdict(result, rested_on=None):
            return {"rule_id": rule["id"], "result": result, "field": field, "value": value,
                    "evidence": evidence if rested_on is None else rested_on}

        if value is None:
            return verdict("cant_tell")

        if test == "contains":
            result, rested_on = _contains(rule, value, evidence)
            return verdict(result, rested_on)

        if test == "one_of":
            wanted = [_norm(v) for v in rule["values"]]
            if field in _SINGLE_VALUED:
                return verdict("met" if _norm(value) in wanted else "not_met")
            if field == "department_team":
                return verdict("met" if any(_norm(v) in wanted for v in value) else "not_met")
            if field == "regions":
                outcomes = [_region_outcome(region, wanted) for region in value]
            elif field in _ALTERNATIVES:
                outcomes = ["meets" if _norm(v) in wanted else "fails" for v in value]
            else:
                raise ValueError(f"one_of does not apply to {field!r}")
            return verdict(_over_alternatives(outcomes, action))

        if test in ("at_least", "at_most"):
            amount = rule["amount"]
            if field == "years_of_experience":
                return verdict("met" if _compare(test, amount, value) else "not_met")
            if field == "salary":
                currency, period = value.get("currency"), value.get("pay_period")
                if currency is None or period is None:
                    return verdict("cant_tell")
                if _norm(currency) != _norm(rule["currency"]) or _norm(period) != _norm(rule["pay_period"]):
                    return verdict("cant_tell")
                # Every amount from minimum to maximum is an alternative; the endpoints decide.
                outcomes = ["meets" if _compare(test, amount, v) else "fails"
                            for v in (value["minimum"], value["maximum"])]
                return verdict(_over_alternatives(outcomes, action))
            raise ValueError(f"{test} does not apply to {field!r}")

        if test == "within_days":
            earliest = datetime.date.fromisoformat(as_of) - datetime.timedelta(days=rule["days"])
            return verdict("met" if datetime.date.fromisoformat(value) >= earliest else "not_met")

        raise ValueError(f"unknown test {test!r}")

    # --- end leaf code ---
    return evaluate_rule(posting, rule, as_of)


def evaluate_rules__n2(postings, rules, as_of):
    evaluate_rule = evaluate_rule__n5
    # --- glue, verbatim ---
    return [
        {
            "source_id": entry["source_id"],
            "posting_id": entry["posting_id"],
            "verdicts": [evaluate_rule(entry, rule, as_of) for rule in rules],
        }
        for entry in postings
    ]

    # --- end glue ---


def place_postings__n3(postings, rules, verdicts, marks):
    # --- leaf n3 code, verbatim ---
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

    # --- end leaf code ---
    return place_postings(postings, rules, verdicts, marks)


def diagnose_rules__n4(rules, verdicts, hidden):
    # --- leaf n4 code, verbatim ---
    def diagnose_rules(rules, verdicts, hidden):
        rule_diagnostics = []
        for rule in rules:
            rule_id = rule["id"]
            counts = {"met": 0, "not_met": 0, "cant_tell": 0}
            could_not_check = []
            for item in verdicts:
                for verdict in item["verdicts"]:
                    if verdict["rule_id"] != rule_id:
                        continue
                    counts[verdict["result"]] += 1
                    if verdict["result"] == "cant_tell":
                        could_not_check.append({"source_id": item["source_id"], "posting_id": item["posting_id"]})

            hid = hid_couldnt_check = 0
            for record in hidden:
                kinds = {reason["kind"] for reason in record["reasons"] if reason.get("rule_id") == rule_id}
                if kinds:
                    hid += 1
                    if "couldnt_check" in kinds:
                        hid_couldnt_check += 1

            could_not_check.sort(key=lambda key: (key["source_id"], key["posting_id"]))
            rule_diagnostics.append({
                "rule_id": rule_id,
                **counts,
                "hid": hid,
                "hid_couldnt_check": hid_couldnt_check,
                "could_not_check": could_not_check,
            })
        return rule_diagnostics

    # --- end leaf code ---
    return diagnose_rules(rules, verdicts, hidden)


def root__n1(stored_postings, watched_sources, rules, marks, as_of):
    evaluate_rules = evaluate_rules__n2
    place_postings = place_postings__n3
    diagnose_rules = diagnose_rules__n4
    # --- glue, verbatim ---
    watched = set(watched_sources)
    postings = [entry for entry in stored_postings if entry["source_id"] in watched]
    verdicts = evaluate_rules(postings, rules, as_of)
    placed = place_postings(postings, rules, verdicts, marks)
    rule_diagnostics = diagnose_rules(rules, verdicts, placed["hidden"])
    return {"shown": placed["shown"], "hidden": placed["hidden"], "rule_diagnostics": rule_diagnostics}

    # --- end glue ---


if __name__ == "__main__":
    import json
    import sys
    args = json.loads(sys.stdin.read())
    print(json.dumps(root__n1(**args), default=str))
