"""Behavior checks for the assess tree's leaves, executed, each leaf alone on inputs built from its
contract."""
import itertools

from harness import check, load_leaf, short, unchanged

T = "assess"
AS_OF = "2026-10-08"


def field(value, path="p", raw=None):
    return {"value": value, "evidence": [{"path": path, "span": None, "raw": raw if raw is not None else value,
                                          "value": value}]} if value is not None else {"value": None, "evidence": []}


def posting(source_id="s", posting_id="1", first_seen="2026-10-01", status="listed", since=None, **fields):
    base = {name: {"value": None, "evidence": []} for name in (
        "title", "link", "company", "location", "department_team", "full_text", "countries", "regions",
        "work_arrangement", "employment_type", "seniority", "salary", "years_of_experience", "posted_date")}
    for name, value in fields.items():
        if name == "full_text" and value is not None:
            base[name] = {"value": value, "evidence": [{"path": f"body.{i}", "span": None, "raw": v, "value": v}
                                                        for i, v in enumerate(value)]}
        else:
            base[name] = field(value, path=f"payload.{name}")
    return {"source_id": source_id, "posting_id": posting_id, "first_seen": first_seen,
            "listing": {"status": status, "since": since}, "payload": {}, "fields": base}


def rule(rule_id, field_name, test, action="require", unknowns="show", **params):
    return {"id": rule_id, "field": field_name, "test": test, "action": action, "unknowns": unknowns, **params}


# ---------------------------------------------------------------- n5 evaluate_rule

def n5():
    evaluate, _ = load_leaf(T, "n5")

    def verdict(p, r):
        out, same = unchanged(evaluate, p, r, AS_OF)
        assert same, "inputs changed"
        return out

    p = posting(title="Senior Software Engineer", full_text=["About us", "We use Python and Go-to-market tools.\nSoftware\n  Engineer role."])
    out = verdict(p, rule("r1", "title", "contains", keywords=["engineer"]))
    check(T, "n5", "surface", set(out) == {"rule_id", "result", "field", "value", "evidence"},
          f"executed: one output, returned bare as a verdict {{rule_id, result, field, value, evidence}}: {short(out)}")
    check(T, "n5", "behavior",
          out["result"] == "met" and out["evidence"] == [
              {"path": "payload.title", "span": [16, 24], "raw": "Engineer", "value": "engineer"}]
          and out["field"] == "title" and out["value"] == "Senior Software Engineer",
          f"contains on title, case-insensitive whole word; a met contains test's evidence is one entry per "
          f"match with the keyword as value: {short(out, 300)}")

    contains = [
        (["engine"], "title", "not_met"), (["engineer*"], "title", "met"), (["software engineer"], "full_text", "met"),
        (["python"], "full_text", "met"), (["go"], "full_text", "met"), (["about us"], "title", "not_met"),
        (["ruby", "python"], "full_text", "met"), (["pyth"], "full_text", "not_met"),
    ]
    got = [(k, f, verdict(p, rule("r", f, "contains", keywords=k))["result"]) for k, f, _ in contains]
    check(T, "n5", "behavior", got == contains,
          f"contains: whole words only ('engine' not in 'Engineer'); trailing * continues ('engineer*'); a "
          f"phrase matches across a line break and spaces; 'go' bounded by '-' counts; any keyword; any piece "
          f"of full_text; title searched alone: {got}")
    out = verdict(p, rule("r", "full_text", "contains", keywords=["software engineer"]))
    check(T, "n5", "behavior", out["evidence"] == [{"path": "body.1", "span": [38, 57], "raw": "Software\n  Engineer",
                                                     "value": "software engineer"}],
          f"a met phrase's evidence names its piece and span: {short(out['evidence'])}")
    out = verdict(p, rule("r", "title", "contains", keywords=["manager"]))
    check(T, "n5", "behavior", out["result"] == "not_met" and out["evidence"] == p["fields"]["title"]["evidence"],
          f"a contains test not met rests on the field record's evidence: {short(out)}")
    odd = posting(title="C++ / node_modules café", full_text=None)
    got = [(k, verdict(odd, rule("r", "title", "contains", keywords=[k]))["result"]) for k in ("c++", "node", "caf")]
    check(T, "n5", "behavior", got == [("c++", "met"), ("node", "met"), ("caf", "not_met")],
          f"bounded by characters that are not letters or digits ('_' bounds, 'é' is a letter): {got}")

    p = posting(company="GitLab", work_arrangement="remote", employment_type="full-time",
                department_team=["Engineering", "Platform"], status="no_longer_listed", since="2026-10-01")
    single = [("company", [" gitlab "], "met"), ("company", ["Linear"], "not_met"),
              ("work_arrangement", ["hybrid", "remote"], "met"), ("employment_type", ["contract"], "not_met"),
              ("listing_status", ["no_longer_listed"], "met"), ("department_team", ["platform"], "met"),
              ("department_team", ["Sales"], "not_met")]
    got = [(f, v, [verdict(p, rule("r", f, "one_of", action=a, values=v))["result"]
                   for a in ("require", "exclude", "prefer")]) for f, v, _ in single]
    check(T, "n5", "behavior", all(results == [expected] * 3 for (_, _, expected), (_, _, results) in zip(single, got)),
          f"one_of on company, work_arrangement, employment_type, listing_status (ignoring case and surrounding "
          f"whitespace) and department_team (any value), the same result for every action: {got}")
    out = verdict(p, rule("r", "listing_status", "one_of", values=["listed"]))
    check(T, "n5", "behavior",
          out["value"] == "no_longer_listed" and out["evidence"] == [
              {"path": "entry.listing", "span": None, "raw": {"status": "no_longer_listed", "since": "2026-10-01"},
               "value": "no_longer_listed"}],
          f"listing status comes from the entry, evidence path 'entry.listing': {short(out)}")

    alts = [
        ("countries", ["CA", "US"], ["US"], ("met", "not_met", "met")),
        ("countries", ["US"], ["us"], ("met", "met", "met")),
        ("countries", ["DE"], ["US"], ("not_met", "not_met", "not_met")),
        ("seniority", ["senior", "staff"], ["staff"], ("met", "not_met", "met")),
        ("regions", ["europe"], ["emea"], ("met", "met", "met")),
        ("regions", ["emea"], ["europe"], ("cant_tell", "cant_tell", "cant_tell")),
        ("regions", ["asia"], ["europe"], ("not_met", "not_met", "not_met")),
        ("regions", ["emea", "north_america"], ["europe"], ("cant_tell", "not_met", "cant_tell")),
        ("regions", ["europe", "north_america"], ["europe"], ("met", "not_met", "met")),
        ("regions", ["europe", "emea"], ["europe"], ("met", "cant_tell", "met")),
        ("regions", ["americas"], ["north_america", "americas"], ("met", "met", "met")),
    ]
    got = []
    for f, value, values, expected in alts:
        p = posting(**{f: value})
        got.append((f, value, values, tuple(verdict(p, rule("r", f, "one_of", action=a, values=values))["result"]
                                            for a in ("require", "exclude", "prefer"))))
    check(T, "n5", "behavior", [g[3] for g in got] == [a[3] for a in alts],
          f"alternatives (results for require, exclude, prefer): require/prefer met when any value meets, "
          f"else cant_tell when any cannot be told, else not_met; exclude met when every value meets, not_met "
          f"when any fails, else cant_tell; a region meets when it or a region containing it is a rule value, "
          f"cannot be told when a rule value lies strictly inside it: {got}")

    usd = {"minimum": 90000, "maximum": 120000, "currency": "USD", "pay_period": "year"}
    sal = [
        ("at_least", 100000, "USD", "year", usd, ("met", "not_met")),
        ("at_least", 120000, "USD", "year", usd, ("met", "not_met")),
        ("at_least", 120001, "USD", "year", usd, ("not_met", "not_met")),
        ("at_least", 90000, "usd", "year", usd, ("met", "met")),
        ("at_most", 95000, "USD", "year", usd, ("met", "not_met")),
        ("at_most", 120000, "USD", "year", usd, ("met", "met")),
        ("at_least", 100000, "EUR", "year", usd, ("cant_tell", "cant_tell")),
        ("at_least", 100000, "USD", "hour", usd, ("cant_tell", "cant_tell")),
        ("at_least", 100000, "USD", "year", {**usd, "pay_period": None}, ("cant_tell", "cant_tell")),
        ("at_least", 100000, "USD", "year", {**usd, "currency": None}, ("cant_tell", "cant_tell")),
    ]
    got = [(t, amt, cur, per, tuple(verdict(posting(salary=s), rule("r", "salary", t, action=a, amount=amt,
                                                                       currency=cur, pay_period=per))["result"]
                                   for a in ("require", "exclude")))
           for t, amt, cur, per, s, _ in sal]
    check(T, "n5", "behavior", [g[4] for g in got] == [s[5] for s in sal],
          f"salary over a 90,000-120,000 USD yearly range (results for require, exclude): every amount in the "
          f"range is an alternative, inclusive; a currency or pay period that is null or differs gives "
          f"cant_tell: {got}")

    years = [(3, "at_least", 3, "met"), (3, "at_least", 4, "not_met"), (3, "at_most", 3, "met"),
             (5, "at_most", 3, "not_met"), (None, "at_least", 1, "cant_tell")]
    got = [(v, t, a, verdict(posting(years_of_experience=v), rule("r", "years_of_experience", t, amount=a))["result"])
           for v, t, a, _ in years]
    check(T, "n5", "behavior", got == years, f"years_of_experience inclusive; unknown -> cant_tell: {got}")

    days = [("posted_date", "2026-10-01", 7, "met"), ("posted_date", "2026-09-30", 7, "not_met"),
            ("posted_date", AS_OF, 0, "met"), ("posted_date", None, 7, "cant_tell"),
            ("first_seen", "2026-09-08", 30, "met"), ("first_seen", "2026-09-07", 30, "not_met")]
    got = []
    for f, date, n, _ in days:
        p = posting(first_seen=date) if f == "first_seen" else posting(posted_date=date)
        got.append((f, date, n, verdict(p, rule("r", f, "within_days", days=n))["result"]))
    out = verdict(posting(first_seen="2026-09-08"), rule("r", "first_seen", "within_days", days=30))
    check(T, "n5", "behavior",
          got == days and out["evidence"] == [{"path": "entry.first_seen", "span": None, "raw": "2026-09-08",
                                               "value": "2026-09-08"}],
          f"within_days counts back from as_of {AS_OF}, on or after is met; first_seen from the entry with "
          f"evidence path 'entry.first_seen': {got}")

    nulls = [("title", "contains", {"keywords": ["x"]}), ("countries", "one_of", {"values": ["US"]}),
             ("regions", "one_of", {"values": ["europe"]}), ("seniority", "one_of", {"values": ["senior"]}),
             ("salary", "at_least", {"amount": 1, "currency": "USD", "pay_period": "year"}),
             ("work_arrangement", "one_of", {"values": ["remote"]})]
    got = [(f, [verdict(posting(), rule("r", f, t, action=a, **params))["result"] for a in ("require", "exclude", "prefer")])
           for f, t, params in nulls]
    check(T, "n5", "behavior", all(r == ["cant_tell"] * 3 for _, r in got),
          f"a null value gives cant_tell under every test and action: {got}")


# ---------------------------------------------------------------- n3 place_postings

def _v(rule_id, result):
    return {"rule_id": rule_id, "result": result, "field": "f", "value": None, "evidence": []}


def n3():
    place, _ = load_leaf(T, "n3")
    rules = [rule("req", "f", "one_of", "require"), rule("exc", "f", "one_of", "exclude"),
             rule("pref1", "f", "one_of", "prefer"), rule("pref2", "f", "one_of", "prefer"),
             rule("req_hide", "f", "one_of", "require", unknowns="hide"),
             {"id": "exc_default", "field": "f", "test": "one_of", "action": "exclude", "values": ["x"]}]
    table = {  # posting_id: (verdicts by rule, marks, posted_date, first_seen)
        "a": ({"req": "met", "exc": "not_met", "pref1": "met", "pref2": "met", "req_hide": "met", "exc_default": "not_met"}, [], "2026-10-01", "2026-10-02"),
        "b": ({"req": "not_met", "exc": "met", "pref1": "met", "pref2": "not_met", "req_hide": "cant_tell", "exc_default": "cant_tell"}, [], "2026-10-05", "2026-10-05"),
        "c": ({"req": "not_met", "exc": "not_met", "pref1": "cant_tell", "pref2": "not_met", "req_hide": "met", "exc_default": "not_met"}, ["applied", "saved", "viewed"], None, "2026-10-07"),
        "d": ({"req": "met", "exc": "not_met", "pref1": "not_met", "pref2": "met", "req_hide": "met", "exc_default": "not_met"}, ["hidden", "saved"], "2026-10-06", "2026-10-06"),
        "e": ({"req": "cant_tell", "exc": "cant_tell", "pref1": "met", "pref2": "not_met", "req_hide": "met", "exc_default": "cant_tell"}, ["viewed"], "2026-10-03", "2026-10-03"),
        "f": ({"req": "met", "exc": "not_met", "pref1": "met", "pref2": "not_met", "req_hide": "met", "exc_default": "not_met"}, [], "2026-10-03", "2026-10-01"),
        "g": ({"req": "met", "exc": "not_met", "pref1": "not_met", "pref2": "not_met", "req_hide": "met", "exc_default": "not_met"}, ["hidden"], None, "2026-09-01"),
    }
    postings, verdicts, marks = [], [], []
    for pid, (by_rule, m, posted, seen) in table.items():
        p = posting("s", pid, first_seen=seen, posted_date=posted,
                    status="no_longer_listed" if pid == "c" else "listed", since="2026-10-07" if pid == "c" else None)
        postings.append(p)
        verdicts.append({"source_id": "s", "posting_id": pid, "verdicts": [_v(r["id"], by_rule[r["id"]]) for r in rules]})
        if m:
            marks.append({"source_id": "s", "posting_id": pid, "marks": m})
    marks.append({"source_id": "other", "posting_id": "zz", "marks": ["saved"]})
    out, same = unchanged(place, postings, rules, verdicts, marks)
    check(T, "n3", "surface", isinstance(out, dict) and list(out) == ["shown", "hidden"],
          f"executed: two outputs returned as a map keyed ['shown', 'hidden']: keys {list(out)}")

    reasons = {r["posting_id"]: r["reasons"] for r in out["hidden"]}
    expected_reasons = {
        "b": [{"kind": "failed", "rule_id": "req"}, {"kind": "failed", "rule_id": "exc"},
              {"kind": "couldnt_check", "rule_id": "req_hide"}],
        "d": [{"kind": "hidden_by_you"}],
        "g": [{"kind": "hidden_by_you"}],
    }
    check(T, "n3", "behavior", reasons == expected_reasons,
          f"reasons: failed for require not_met / exclude met; couldnt_check only for a rule set to hide "
          f"unknowns (b's exclude with unknowns left out defaults to show); saved suppresses rule reasons (c "
          f"fails 'req' but is saved -> shown; d is saved and hidden -> hidden_by_you only); hidden_by_you "
          f"first; prefer never hides: {reasons}")
    shown_ids = [r["posting_id"] for r in out["shown"]]
    check(T, "n3", "behavior", shown_ids == ["a", "e", "f", "c"],
          f"shown ordered by prefer_met most first (a 2; e and f 1; c 0, its prefer cant_tell counted as not "
          f"met), then posted_date or first_seen newest first (e and f tie on 2026-10-03), then source_id and "
          f"posting_id (e before f): got {shown_ids} with prefer_met "
          f"{[r['prefer_met'] for r in out['shown']]} and dates "
          f"{[r['fields']['posted_date']['value'] or r['first_seen'] for r in out['shown']]}")
    check(T, "n3", "behavior", [r["posting_id"] for r in out["hidden"]] == ["b", "d", "g"]
          and sorted(shown_ids + list(reasons)) == sorted(table) and same,
          f"every posting exactly once; hidden ordered by source_id then posting_id; inputs not modified ({same})")
    c = next(r for r in out["shown"] if r["posting_id"] == "c")
    e = next(r for r in out["shown"] if r["posting_id"] == "e")
    check(T, "n3", "behavior",
          set(c) == {"source_id", "posting_id", "fields", "first_seen", "listing", "verdicts", "prefer_met", "marks", "flags"}
          and c["marks"] == ["viewed", "saved", "applied"] and c["flags"] == {"new": False, "no_longer_listed": True,
                                                                               "no_posting_date": True}
          and e["flags"] == {"new": False, "no_longer_listed": False, "no_posting_date": False}
          and [v["rule_id"] for v in c["verdicts"]] == [r["id"] for r in rules]
          and c["fields"] == postings[2]["fields"] and c["listing"] == postings[2]["listing"],
          f"record shape; marks in the order viewed, saved, applied, hidden; flags new/no_longer_listed/"
          f"no_posting_date; verdicts in rule order; fields as stored: c={short({k: c[k] for k in ('marks', 'flags', 'prefer_met')})}")
    a = next(r for r in out["shown"] if r["posting_id"] == "a")
    check(T, "n3", "behavior", a["marks"] == [] and a["flags"]["new"] is True,
          f"an unmarked posting has empty marks and is new: {short({k: a[k] for k in ('marks', 'flags')})}")

    # overfit: ties broken by source then posting ID, across sources, with string IDs that are not numbers
    tied = [posting("z", "x1", first_seen="2026-10-01"), posting("a", "x2", first_seen="2026-10-01"),
            posting("a", "x10", first_seen="2026-10-01")]
    out = place(tied, [], [{"source_id": p["source_id"], "posting_id": p["posting_id"], "verdicts": []} for p in tied], [])
    check(T, "n3", "behavior",
          [(r["source_id"], r["posting_id"]) for r in out["shown"]] == [("a", "x10"), ("a", "x2"), ("z", "x1")]
          and out["hidden"] == [],
          f"no rules: everything shown, equal dates ordered by source_id then posting_id: "
          f"{[(r['source_id'], r['posting_id']) for r in out['shown']]}")
    empty = place([], rules, [], [])
    check(T, "n3", "behavior", empty == {"shown": [], "hidden": []}, f"boundary: no postings: {empty}")


# ---------------------------------------------------------------- n4 diagnose_rules

def n4():
    diagnose, _ = load_leaf(T, "n4")
    rules = [rule("r1", "f", "one_of", "require", unknowns="hide"), rule("r2", "f", "one_of", "exclude"),
             rule("r3", "f", "one_of", "prefer")]
    grid = {("s", "2"): ("cant_tell", "met", "met"), ("s", "10"): ("not_met", "not_met", "cant_tell"),
            ("a", "1"): ("cant_tell", "cant_tell", "not_met"), ("s", "3"): ("met", "not_met", "met")}
    verdicts = [{"source_id": s, "posting_id": p, "verdicts": [_v(r["id"], res) for r, res in zip(rules, results)]}
                for (s, p), results in grid.items()]
    hidden = [
        {"source_id": "a", "posting_id": "1", "reasons": [{"kind": "couldnt_check", "rule_id": "r1"}]},
        {"source_id": "s", "posting_id": "10", "reasons": [{"kind": "hidden_by_you"}, {"kind": "failed", "rule_id": "r1"}]},
        {"source_id": "s", "posting_id": "2", "reasons": [{"kind": "couldnt_check", "rule_id": "r1"},
                                                          {"kind": "failed", "rule_id": "r2"}]},
    ]
    out, same = unchanged(diagnose, rules, verdicts, hidden)
    check(T, "n4", "surface", isinstance(out, list) and not (isinstance(out, dict)),
          f"executed: one output returned bare (a list of per-rule records): {short(out, 100)}")
    expected = [
        {"rule_id": "r1", "met": 1, "not_met": 1, "cant_tell": 2, "hid": 3, "hid_couldnt_check": 2,
         "could_not_check": [{"source_id": "a", "posting_id": "1"}, {"source_id": "s", "posting_id": "2"}]},
        {"rule_id": "r2", "met": 1, "not_met": 2, "cant_tell": 1, "hid": 1, "hid_couldnt_check": 0,
         "could_not_check": [{"source_id": "a", "posting_id": "1"}]},
        {"rule_id": "r3", "met": 2, "not_met": 1, "cant_tell": 1, "hid": 0, "hid_couldnt_check": 0,
         "could_not_check": [{"source_id": "s", "posting_id": "10"}]},
    ]
    check(T, "n4", "behavior", out == expected and same,
          f"per rule in rule order: verdict counts over all postings; hid counts hidden records whose reasons "
          f"name the rule, hid_couldnt_check those naming it as couldnt_check; could_not_check ordered by "
          f"source_id then posting_id ('10' before '2' as strings); inputs unchanged ({same}): {out}")
    check(T, "n4", "behavior", diagnose([], verdicts, hidden) == [] and diagnose(rules, [], [])[0]["met"] == 0,
          "boundary: no rules -> []; no postings -> zero counts")


def run():
    for leaf in (n5, n3, n4):
        leaf()
