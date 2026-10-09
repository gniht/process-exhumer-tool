"""Behavior checks for internal nodes, assume-guarantee: each node's glue runs against stubs that keep
its children's contracts (and record how they were called), and the parent's clauses are traced
through the children's contracts. Child implementations are not used here."""
from harness import FIELDS, check, glue_function, node, short, store_problems


class Calls:
    def __init__(self):
        self.log = []

    def stub(self, name, fn):
        def wrapped(*args):
            self.log.append((name, args))
            return fn(*args)
        return wrapped

    def names(self):
        return [name for name, _ in self.log]


def null_fields():
    return {f: {"value": None, "evidence": []} for f in FIELDS}


# ---------------------------------------------------------------- refresh

def refresh_n2():
    calls = Calls()
    outcomes = {"a": "ok", "b": "failed", "c": "ok"}

    def fetch_source(source):
        if outcomes[source["id"]] == "ok":
            return {"source_id": source["id"], "status": "ok", "postings": [
                {"posting_id": f"{source['id']}1", "payload": {"n": 1}}]}
        return {"source_id": source["id"], "status": "failed", "reason": "HTTP 503"}

    glue = glue_function("refresh", "n2", {"fetch_source": calls.stub("fetch_source", fetch_source)})
    sources = [{"id": i} for i in ("a", "b", "c")]
    out = glue(sources)
    check("refresh", "n2", "pattern", calls.names() == ["fetch_source"] * 3
          and [args[0]["id"] for _, args in calls.log] == ["a", "b", "c"],
          f"executed with a stub child: fetch_source called once per source, in order: "
          f"{[args[0]['id'] for _, args in calls.log]}", unit="node")
    check("refresh", "n2", "behavior",
          [r["source_id"] for r in out] == ["a", "b", "c"] and out[1]["status"] == "failed"
          and out[0]["status"] == out[2]["status"] == "ok",
          f"executed: one result per source in the same order; b's failure leaves a and c as fetched: "
          f"{short([(r['source_id'], r['status']) for r in out])}. Static: each result is fetch_source's "
          f"result for that source alone (the child never raises, so one source cannot stop the list), "
          f"which carries the ok/failed clauses", unit="node")
    check("refresh", "n2", "behavior", glue([]) == [], "executed: no sources -> no results", unit="node")


def refresh_n3():
    calls = Calls()

    def extract_posting(payload, source, pay_floors):
        fields = null_fields()
        fields["company"] = {"value": source["company"], "evidence": [
            {"path": "source.company", "span": None, "raw": source["company"], "value": source["company"]}]}
        return fields

    glue = glue_function("refresh", "n3", {"extract_posting": calls.stub("extract_posting", extract_posting)})
    sources = [{"id": "a", "company": "A"}, {"id": "b", "company": "B"}, {"id": "unused", "company": "U"}]
    floors = {"USD": 15080}
    failed = {"source_id": "x", "status": "failed", "reason": "HTTP 500"}
    results = [
        {"source_id": "b", "status": "ok", "postings": [{"posting_id": "1", "payload": {"k": 1}},
                                                        {"posting_id": "2", "payload": {"k": 2}}]},
        failed,
        {"source_id": "a", "status": "ok", "postings": [{"posting_id": "9", "payload": {"k": 9}}]},
    ]
    out = glue(results, sources, floors)
    companies = [[p["fields"]["company"]["value"] for p in r.get("postings", [])] for r in out]
    check("refresh", "n3", "pattern",
          [(a[0], a[1]["id"], a[2] is floors) for _, a in calls.log] == [({"k": 1}, "b", True), ({"k": 2}, "b", True),
                                                                        ({"k": 9}, "a", True)],
          f"executed with a stub child: extract_posting called once per posting of each ok result, with that "
          f"posting's payload, its own source's definition and the pay-floor table: "
          f"{[(a[0], a[1]['id']) for _, a in calls.log]}", unit="node")
    check("refresh", "n3", "behavior",
          [r["source_id"] for r in out] == ["b", "x", "a"] and out[1] is failed
          and companies == [["B", "B"], [], ["A"]]
          and all(set(p) == {"posting_id", "payload", "fields"} for r in out for p in r.get("postings", []))
          and results[0]["postings"][0] == {"posting_id": "1", "payload": {"k": 1}},
          f"executed: results in the same order; the failed result passes through as the same object; each "
          f"ok posting gains fields from its own source (companies {companies}) and keeps posting_id and "
          f"payload; the input results are not modified", unit="node")


def refresh_n6():
    calls = Calls()
    record = lambda tag: {"value": None, "evidence": [{"path": tag, "span": None, "raw": tag, "value": None}]}

    def read_stated_text(payload, source):
        return {f: record(f"stated.{f}") for f in ("title", "link", "company", "location", "department_team", "full_text")}

    stubs = {
        "read_stated_text": read_stated_text,
        "derive_geography": lambda payload, source, location: {"countries": record("geo.countries"),
                                                               "regions": record("geo.regions")},
        "derive_work_arrangement": lambda payload, source, location: record("work"),
        "derive_employment_type": lambda payload, source, title: record("employment"),
        "derive_seniority": lambda title: record("seniority"),
        "derive_salary": lambda full_text, countries, pay_floors: record("salary"),
        "derive_years_of_experience": lambda full_text: record("years"),
        "read_posted_date": lambda payload, source: record("date"),
    }
    glue = glue_function("refresh", "n6", {k: calls.stub(k, v) for k, v in stubs.items()})
    payload, source, floors = {"p": 1}, {"id": "s"}, {"USD": 15080}
    out = glue(payload, source, floors)
    args = {name: a for name, a in calls.log}
    tag = lambda value: value["evidence"][0]["path"] if isinstance(value, dict) and "evidence" in value else value
    wired = {name: [tag(x) if isinstance(x, dict) and "evidence" in x else ("payload" if x is payload else
                    "source" if x is source else "pay_floors" if x is floors else x) for x in a]
             for name, a in args.items()}
    expected = {
        "read_stated_text": ["payload", "source"],
        "derive_geography": ["payload", "source", "stated.location"],
        "derive_work_arrangement": ["payload", "source", "stated.location"],
        "derive_employment_type": ["payload", "source", "stated.title"],
        "derive_seniority": ["stated.title"],
        "derive_salary": ["stated.full_text", "geo.countries", "pay_floors"],
        "derive_years_of_experience": ["stated.full_text"],
        "read_posted_date": ["payload", "source"],
    }
    check("refresh", "n6", "behavior", wired == expected,
          f"executed with stub children: each child receives the records its contract names (location to "
          f"geography and work arrangement, title to employment type and seniority, full_text and the derived "
          f"countries to salary): {wired}", unit="node")
    check("refresh", "n6", "behavior",
          sorted(out) == sorted(FIELDS) and all(tag(out[f]) == t for f, t in [
              ("title", "stated.title"), ("countries", "geo.countries"), ("regions", "geo.regions"),
              ("salary", "salary"), ("posted_date", "date"), ("seniority", "seniority")]),
          f"executed: a field record for every declared field, each the record its child returned: keys "
          f"{sorted(out)}", unit="node")
    check("refresh", "n6", "behavior", True,
          "static, assume-guarantee: every value comes from a child whose output is a field record in its "
          "field's declared space or null, carrying the evidence it was derived from; the glue reads nothing "
          "but payload, source and pay_floors, so the result depends only on these inputs",
          unit="node", method="static")
    geo = node("refresh", "n8")["contract"]["behavior"]
    sen = node("refresh", "n11")["contract"]["behavior"]
    admits = "even where the text means something else" in geo and "'Staff Pharmacist' gives 'staff'" in sen
    check("refresh", "n6", "behavior", not admits,
          "static, assume-guarantee: n6 promises 'a board's value being mapped into a value space only where "
          "its meaning matches'. The values maps keep it (their author judges each board value). The narrowed "
          "derive_geography and derive_seniority contracts, ratified at stage 3, do not: 'an entry counts "
          "wherever it appears, even where the text means something else by it' and \"'Staff Pharmacist' "
          f"gives 'staff'\" (both present: {admits}). So the clause cannot be derived from the children. The "
          "stage 3 record said the narrowing left n6's contract holding; that missed this clause, which the "
          "root states too", unit="node", method="static")


def refresh_n1():
    calls = Calls()
    as_of, floors = "2026-10-08", {"USD": 15080}

    def fetch_sources(sources):
        return [{"source_id": s["id"], "status": "ok", "postings": [{"posting_id": "n", "payload": {}}]}
                if s["id"] != "b" else {"source_id": "b", "status": "failed", "reason": "timeout"} for s in sources]

    def extract_fetched(fetch_results, sources, pay_floors):
        return [{**r, "postings": [{**p, "fields": null_fields()} for p in r["postings"]]} if r["status"] == "ok" else r
                for r in fetch_results]

    def merge_into_store(stored, extracted, as_of):
        # a stub that keeps merge_into_store's contract
        store = {(e["source_id"], e["posting_id"]): e for e in stored}
        report = []
        for r in extracted:
            if r["status"] != "ok":
                report.append({"source_id": r["source_id"], "status": "failed", "reason": r["reason"]})
                continue
            listed = {p["posting_id"] for p in r["postings"]}
            new = again = 0
            for p in r["postings"]:
                old = store.get((r["source_id"], p["posting_id"]))
                new += old is None
                again += old is not None and old["listing"]["status"] == "no_longer_listed"
                store[(r["source_id"], p["posting_id"])] = {
                    "source_id": r["source_id"], "posting_id": p["posting_id"],
                    "first_seen": old["first_seen"] if old else as_of, "listing": {"status": "listed", "since": None},
                    "payload": p["payload"], "fields": p["fields"]}
            gone = [k for k, e in store.items() if k[0] == r["source_id"] and k[1] not in listed
                    and e["listing"]["status"] == "listed"]
            for k in gone:
                store[k] = {**store[k], "listing": {"status": "no_longer_listed", "since": as_of}}
            report.append({"source_id": r["source_id"], "status": "ok", "listed": len(r["postings"]), "new": new,
                           "no_longer_listed": len(gone), "listed_again": again})
        return {"updated_postings": [store[k] for k in sorted(store)], "source_report": report}

    stubs = {"fetch_sources": fetch_sources, "extract_fetched": extract_fetched, "merge_into_store": merge_into_store}
    glue = glue_function("refresh", "n1", {k: calls.stub(k, v) for k, v in stubs.items()})
    old = lambda s, p: {"source_id": s, "posting_id": p, "first_seen": "2026-09-01",
                        "listing": {"status": "listed", "since": None}, "payload": {"old": True}, "fields": null_fields()}
    stored = [old("a", "o"), old("b", "o"), old("retired", "o")]
    sources = [{"id": "a"}, {"id": "b"}]
    out = glue(sources, stored, floors, as_of)
    log = calls.log
    flow = (calls.names() == ["fetch_sources", "extract_fetched", "merge_into_store"]
            and log[0][1][0] is sources
            and log[1][1][1] is sources and log[1][1][2] is floors
            and log[2][1][0] is stored and log[2][1][2] == as_of)
    check("refresh", "n1", "behavior", flow,
          f"executed with stub children: fetch -> extract -> merge in that order; extract receives the "
          f"sources and pay-floor table, merge the stored postings and as_of; each step's output is the "
          f"next step's input", unit="node")
    by_key = {(e["source_id"], e["posting_id"]): e for e in out["updated_postings"]}
    check("refresh", "n1", "behavior",
          list(out) == ["updated_postings", "source_report"] and not store_problems(out["updated_postings"])
          and by_key[("a", "n")]["first_seen"] == as_of and by_key[("a", "o")]["listing"]["status"] == "no_longer_listed"
          and by_key[("b", "o")] == stored[1] and by_key[("retired", "o")] == stored[2]
          and [r["source_id"] for r in out["source_report"]] == ["a", "b"] and out["source_report"][1]["reason"] == "timeout",
          f"executed: both outputs, store well-formed; a's new posting first seen today and its missed one "
          f"no longer listed; failed source b and retired source unchanged; report per source in order: "
          f"{out['source_report']}", unit="node")

    # static, assume-guarantee, clause by clause: what the children's contracts carry to the root
    n3 = node("refresh", "n3")["contract"]["behavior"] + " " + node("refresh", "n3")["contract"]["outputs"][0]["description"]
    carried_salary = "bare $" in n3 or "bare '$'" in n3 or "pay-floor entry" in n3 or "lower figure" in n3
    carried_mapping = "meaning matches" in n3
    check("refresh", "n1", "behavior", carried_salary and carried_mapping,
          "static, assume-guarantee over the children's contracts: the store, listing, failure, no-removal "
          "and report clauses follow from fetch_sources, extract_fetched and merge_into_store, and every "
          "value's space and evidence from the field-record shape extract_fetched promises. Two root "
          "clauses are not carried: extract_fetched's contract promises 'the extraction of its payload under "
          "its own source's definition and the pay-floor table' and the field shapes, but neither "
          f"'a board's value being mapped into a value space only where its meaning matches' (present: "
          f"{carried_mapping}) nor the salary clause (bare $ only for a US-only posting; an unstated period "
          f"yearly only at or above the pay floor) (present: {carried_salary}). The leaves below do keep "
          "both (derive_salary's contract states the salary rules; extract_posting's states the mapping "
          "rule), but the contracts between them and the root drop them, so a different extract_fetched "
          "satisfying its own contract could break the root", unit="node", method="static")


# ---------------------------------------------------------------- assess

def assess_n2():
    calls = Calls()
    glue = glue_function("assess", "n2", {"evaluate_rule": calls.stub(
        "evaluate_rule", lambda posting, rule, as_of: {"rule_id": rule["id"], "result": "cant_tell",
                                                       "field": rule["field"], "value": None, "evidence": []})})
    postings = [{"source_id": "s", "posting_id": p} for p in ("2", "1")]
    rules = [{"id": "r2", "field": "title"}, {"id": "r1", "field": "company"}]
    out = glue(postings, rules, "2026-10-08")
    check("assess", "n2", "pattern",
          [(a[0]["posting_id"], a[1]["id"], a[2]) for _, a in calls.log]
          == [("2", "r2", "2026-10-08"), ("2", "r1", "2026-10-08"), ("1", "r2", "2026-10-08"), ("1", "r1", "2026-10-08")],
          f"executed with a stub child: evaluate_rule once per posting and rule, postings in order, rules in "
          f"order within each: {[(a[0]['posting_id'], a[1]['id']) for _, a in calls.log]}", unit="node")
    check("assess", "n2", "behavior",
          [(i["posting_id"], [v["rule_id"] for v in i["verdicts"]]) for i in out] == [("2", ["r2", "r1"]), ("1", ["r2", "r1"])]
          and all(set(i) == {"source_id", "posting_id", "verdicts"} for i in out)
          and glue([], rules, "2026-10-08") == [] and glue(postings, [], "2026-10-08")[0]["verdicts"] == [],
          f"executed: one item per posting in posting order, naming it, verdicts one per rule in rule order; "
          f"no postings -> []; no rules -> empty verdict lists: {short(out)}", unit="node")


def assess_n1():
    calls = Calls()
    seen = {}

    def evaluate_rules(postings, rules, as_of):
        seen["postings"] = postings
        return [{"source_id": p["source_id"], "posting_id": p["posting_id"],
                 "verdicts": [{"rule_id": r["id"], "result": "met", "field": r["field"], "value": None, "evidence": []}
                              for r in rules]} for p in postings]

    def place_postings(postings, rules, verdicts, marks):
        hidden = [p for p in postings if p["posting_id"] == "h"]
        shown = [p for p in postings if p["posting_id"] != "h"]
        rec = lambda p: {"source_id": p["source_id"], "posting_id": p["posting_id"], "fields": p["fields"],
                         "first_seen": p["first_seen"], "listing": p["listing"], "verdicts": [], "prefer_met": 0,
                         "marks": [], "flags": {"new": True, "no_longer_listed": False, "no_posting_date": True}}
        return {"shown": [rec(p) for p in shown],
                "hidden": [{**rec(p), "reasons": [{"kind": "hidden_by_you"}]} for p in hidden]}

    def diagnose_rules(rules, verdicts, hidden):
        seen["diagnose"] = (verdicts, hidden)
        return [{"rule_id": r["id"], "met": len(verdicts), "not_met": 0, "cant_tell": 0, "hid": 0,
                 "hid_couldnt_check": 0, "could_not_check": []} for r in rules]

    stubs = {"evaluate_rules": evaluate_rules, "place_postings": place_postings, "diagnose_rules": diagnose_rules}
    glue = glue_function("assess", "n1", {k: calls.stub(k, v) for k, v in stubs.items()})
    entry = lambda s, p: {"source_id": s, "posting_id": p, "first_seen": "2026-10-01",
                          "listing": {"status": "listed", "since": None}, "payload": {}, "fields": {}}
    stored = [entry("a", "1"), entry("a", "h"), entry("b", "1"), entry("c", "2")]
    rules = [{"id": "r", "field": "title"}]
    marks = [{"source_id": "a", "posting_id": "h", "marks": ["hidden"]}]
    out = glue(stored, ["c", "a", "zzz"], rules, marks, "2026-10-08")
    keys = [(p["source_id"], p["posting_id"]) for p in seen["postings"]]
    check("assess", "n1", "behavior",
          keys == [("a", "1"), ("a", "h"), ("c", "2")]
          and calls.names() == ["evaluate_rules", "place_postings", "diagnose_rules"]
          and calls.log[1][1][3] is marks and calls.log[2][1][1] is calls.log[1][1][2]
          and seen["diagnose"][1] == out["hidden"],
          f"executed with stub children: only watched sources' postings go in ({keys}; source b unwatched, "
          f"'zzz' watched but absent), in stored order; the same verdicts reach placement and diagnosis; "
          f"diagnosis gets the hidden records", unit="node")
    check("assess", "n1", "behavior",
          list(out) == ["shown", "hidden", "rule_diagnostics"]
          and sorted((r["source_id"], r["posting_id"]) for r in out["shown"] + out["hidden"]) == sorted(keys),
          f"executed: all three outputs; every watched posting exactly once across shown and hidden: "
          f"{short(out, 200)}", unit="node")

    n2 = node("assess", "n1")["children"][0]["contract"]
    n2_text = n2["behavior"] + " " + n2["outputs"][0]["description"]
    clauses = {
        "can't tell exactly when the field is unknown or not comparable": "cant_tell when" in n2_text or "unknown or not comparable" in n2_text,
        "alternatives: any for require/prefer, every for exclude": "every value" in n2_text,
        "keyword tests: case-insensitive whole words, trailing *": "whole word" in n2_text,
        "within-days counts back from the current date": "counts back" in n2_text or "minus days" in n2_text,
    }
    check("assess", "n1", "behavior", all(clauses.values()),
          "static, assume-guarantee over the children's contracts: watched filtering is the glue's own; "
          "exactly-once placement, reasons, ordering, flags and marks follow from place_postings; diagnostics "
          "from diagnose_rules over the watched postings' verdicts; same inputs, same outputs from the three "
          "functions. The verdict clauses are not carried: evaluate_rules promises 'each the verdict of that "
          "rule on that posting at the current date' and the verdict's shape, but none of the root's rules "
          f"for what a verdict is: {clauses}. Only evaluate_rule's contract (below evaluate_rules) states "
          "them, so a different evaluate_rules satisfying its own contract could break the root",
          unit="node", method="static")


def run():
    for fn in (refresh_n2, refresh_n3, refresh_n6, refresh_n1, assess_n2, assess_n1):
        fn()
