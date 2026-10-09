"""Summarize one user's live assessment and check the assess root's clauses against it.

    python3 live/assess_summary.py live/assess-demo-a.input.json live/assess-demo-a.output.json
"""
import collections
import json
import sys

inp = json.load(open(sys.argv[1]))
out = json.load(open(sys.argv[2]))
rules = inp["rules"]
watched = set(inp["watched_sources"])
expected = {(e["source_id"], e["posting_id"]) for e in inp["stored_postings"] if e["source_id"] in watched}
shown, hidden = out["shown"], out["hidden"]
placed = [(r["source_id"], r["posting_id"]) for r in shown + hidden]
marked = {(m["source_id"], m["posting_id"]): set(m["marks"]) for m in inp["marks"]}


def date_of(r):
    return r["fields"]["posted_date"]["value"] or r["first_seen"]


checks = {
    "every watched posting exactly once, no other": sorted(placed) == sorted(expected) and len(placed) == len(set(placed)),
    "one verdict per rule, in rule order": all([v["rule_id"] for v in r["verdicts"]] == [x["id"] for x in rules]
                                                for r in shown + hidden),
    "can't tell exactly when the tested value is unknown (non-salary)": all(
        (v["result"] == "cant_tell") == (v["value"] is None)
        for r in shown + hidden for v in r["verdicts"] if v["field"] != "salary"),
    "shown ordered by prefer_met, then date newest first, then key": shown == sorted(
        sorted(sorted(shown, key=lambda r: (r["source_id"], r["posting_id"])), key=date_of, reverse=True),
        key=lambda r: r["prefer_met"], reverse=True),
    "hidden ordered by key": [(r["source_id"], r["posting_id"]) for r in hidden] == sorted(
        (r["source_id"], r["posting_id"]) for r in hidden),
    "hidden by you exactly when marked hidden": all(
        ({"kind": "hidden_by_you"} in r.get("reasons", [])) == ("hidden" in marked.get((r["source_id"], r["posting_id"]), set()))
        for r in shown + hidden),
    "saved postings carry no rule reasons": all(
        all(x["kind"] == "hidden_by_you" for x in r["reasons"]) for r in hidden
        if "saved" in marked.get((r["source_id"], r["posting_id"]), set())),
    "flags match marks, listing and date": all(
        r["flags"] == {"new": "viewed" not in r["marks"], "no_longer_listed": r["listing"]["status"] == "no_longer_listed",
                       "no_posting_date": r["fields"]["posted_date"]["value"] is None} for r in shown + hidden),
    "diagnostics count every watched posting per rule": all(
        d["met"] + d["not_met"] + d["cant_tell"] == len(expected) for d in out["rule_diagnostics"]),
}

reasons = collections.Counter(
    (x["kind"], x.get("rule_id")) for r in hidden for x in r["reasons"])
summary = {
    "watched": sorted(watched),
    "watched_postings": len(expected),
    "shown": len(shown),
    "hidden": len(hidden),
    "root_clauses_checked": checks,
    "hidden_reasons": [[kind, rule, n] for (kind, rule), n in reasons.most_common()],
    "rule_diagnostics": [{k: (len(v) if k == "could_not_check" else v) for k, v in d.items()} for d in out["rule_diagnostics"]],
    "top_shown": [{"title": r["fields"]["title"]["value"], "company": r["fields"]["company"]["value"],
                   "prefer_met": r["prefer_met"], "date": date_of(r), "marks": r["marks"],
                   "flags": [k for k, v in r["flags"].items() if v],
                   "salary": r["fields"]["salary"]["value"], "regions": r["fields"]["regions"]["value"]}
                  for r in shown[:12]],
    "marked": [{"title": r["fields"]["title"]["value"], "where": "shown" if r in shown else "hidden",
                "marks": r["marks"], "reasons": r.get("reasons")} for r in shown + hidden if r["marks"]],
}
print(json.dumps(summary, indent=1, default=str))
