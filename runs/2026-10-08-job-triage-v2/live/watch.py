"""Measure a live refresh against the root contract and composition's watch list.

    python3 live/watch.py live/refresh-1.output.json > live/watch-1.json
"""
import collections
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "verify"))
from harness import FIELDS, record_problems, store_problems  # noqa: E402

out = json.load(open(sys.argv[1]))
store = out["updated_postings"]
by_source = collections.defaultdict(list)
for entry in store:
    by_source[entry["source_id"]].append(entry)

report = {"source_report": out["source_report"], "postings": len(store)}

# the root's shape clauses, over every stored posting and every field
problems = store_problems(store)
for entry in store:
    if sorted(entry["fields"]) != sorted(FIELDS):
        problems.append(f"{entry['posting_id']}: fields {sorted(entry['fields'])}")
        continue
    texts = {e["path"]: e["value"] for f in ("title", "link", "location", "department_team", "full_text")
             for e in entry["fields"][f]["evidence"]}
    for field in FIELDS:
        problems += [f"{entry['source_id']}/{entry['posting_id']} {p}"
                     for p in record_problems(field, entry["fields"][field], texts)]
report["shape_problems"] = problems[:20]
report["shape_problem_count"] = len(problems)

# unknown rate per field per board
report["unknown_rate"] = {
    source: {field: f"{sum(e['fields'][field]['value'] is None for e in entries)}/{len(entries)}" for field in FIELDS}
    for source, entries in by_source.items()
}

# value distributions where the space is small
def dist(source, field, key=lambda v: v):
    return collections.Counter(json.dumps(key(e["fields"][field]["value"])) for e in by_source[source]).most_common(12)

report["distributions"] = {
    source: {f: dist(source, f) for f in ("work_arrangement", "employment_type", "seniority", "regions")}
    for source in by_source
}

# salaries: statements found, values, and postings whose statements disagreed
salary = {}
for source, entries in by_source.items():
    stated = [e for e in entries if e["fields"]["salary"]["evidence"]]
    disagreed = [e for e in stated if e["fields"]["salary"]["value"] is None]
    salary[source] = {
        "postings_with_statements": len(stated),
        "value_known": sum(e["fields"]["salary"]["value"] is not None for e in entries),
        "period_known": sum((e["fields"]["salary"]["value"] or {}).get("pay_period") is not None for e in entries),
        "currency_null": sum((e["fields"]["salary"]["value"] or {"currency": 1}).get("currency") is None for e in entries),
        "disagreeing": [{"title": e["fields"]["title"]["value"],
                         "statements": [(s["raw"], s["value"]["currency"], s["value"]["pay_period"])
                                        for s in e["fields"]["salary"]["evidence"]]} for e in disagreed],
        "examples": [(e["fields"]["title"]["value"], e["fields"]["salary"]["value"],
                      [s["raw"] for s in e["fields"]["salary"]["evidence"]]) for e in stated
                     if e["fields"]["salary"]["value"] is not None][:4],
    }
report["salary"] = salary

# table misses: location texts that yielded no country and no region
misses = collections.Counter()
for entry in store:
    f = entry["fields"]
    if f["countries"]["value"] is None and f["regions"]["value"] is None:
        for text in f["location"]["value"] or ["<no location>"]:
            misses[(entry["source_id"], text)] += 1
report["geography_misses"] = [(s, t, n) for (s, t), n in misses.most_common(40)]

# table entries worth a look: country matches whose raw text is short or a code
suspect = collections.Counter()
for entry in store:
    for e in entry["fields"]["countries"]["evidence"]:
        if e["value"] and e["span"] is not None:
            suspect[(e["raw"], e["value"])] += 1
report["country_matches_from_text"] = [(raw, code, n) for (raw, code), n in suspect.most_common(60)]

# seniority: titles with no level, and every level word matched
report["seniority_null_titles"] = {
    source: [e["fields"]["title"]["value"] for e in entries if e["fields"]["seniority"]["value"] is None][:25]
    for source, entries in by_source.items()
}
report["seniority_matches"] = collections.Counter(
    (ev["raw"].lower(), ev["value"]) for e in store for ev in e["fields"]["seniority"]["evidence"]).most_common(30)
report["employment_from_title"] = [(e["fields"]["title"]["value"], e["fields"]["employment_type"]["value"])
                                   for e in store for ev in e["fields"]["employment_type"]["evidence"]
                                   if ev["span"] is not None]
report["years_examples"] = collections.Counter(
    ev["raw"] for e in store for ev in e["fields"]["years_of_experience"]["evidence"]).most_common(25)
print(json.dumps(report, indent=1, default=str))
