"""Stage 4 harness: load the codified trees, record checks, and test values against declared shapes.

Every check is local to one unit: a leaf is run alone against inputs built from its contract, and an
internal node's glue is run against stubs that keep its children's contracts.
"""
import ast
import copy
import datetime
import json
import os
import re

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(os.path.dirname(RUN), "2026-09-09-job-search-triage", "fixtures")
TREES = {name: json.load(open(os.path.join(RUN, f"codified-tree-{name}.json"))) for name in ("refresh", "assess")}

REPORT = []


def rec(tree, node_id, unit, category, outcome, detail, method="executed"):
    assert outcome in ("pass", "fail", "deferred"), outcome
    assert method in ("executed", "static"), method
    REPORT.append({"tree": tree, "node": node_id, "unit": unit, "category": category,
                   "method": method, "outcome": outcome, "detail": detail})


def check(tree, node_id, category, ok, detail, unit="leaf", method="executed"):
    """Record a pass/fail check; `ok` is a bool, `detail` says what ran and what came back."""
    rec(tree, node_id, unit, category, "pass" if ok else "fail", detail, method)
    return ok


def walk(node, name="(root)"):
    yield name, node
    for child in node.get("children", []):
        yield from walk(child, child["name"])


def units(tree_name):
    return list(walk(TREES[tree_name]))


def node(tree_name, node_id):
    return next(n for _, n in units(tree_name) if n["id"] == node_id)


def name_of(tree_name, node_id):
    return next(name for name, n in units(tree_name) if n["id"] == node_id)


# When set, leaves are taken from the assembled programs (job_triage_<tree>.py) instead of the tree, so
# the same checks run against the code as composition nested it.
ARTIFACT = bool(os.environ.get("VERIFY_ARTIFACT"))
_PROGRAMS = {}


def _program(tree_name):
    if tree_name not in _PROGRAMS:
        import importlib.util
        spec = importlib.util.spec_from_file_location(f"program_{tree_name}", os.path.join(RUN, f"job_triage_{tree_name}.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _PROGRAMS[tree_name] = module
    return _PROGRAMS[tree_name]


def load_leaf(tree_name, node_id):
    """The leaf's entry point, executed from the code stored on the tree (not the leaves/ copies), or,
    with VERIFY_ARTIFACT set, the node's function in the assembled program."""
    if ARTIFACT:
        return getattr(_program(tree_name), f"{name_of(tree_name, node_id)}__{node_id}"), {}
    leaf = node(tree_name, node_id)
    namespace = {"__name__": f"leaf_{tree_name}_{node_id}"}
    exec(compile(leaf["code"], f"<{tree_name}:{node_id}>", "exec"), namespace)
    return namespace[name_of(tree_name, node_id)], namespace


def glue_function(tree_name, node_id, children):
    """The node's glue as a function of its contract inputs, with `children` bound by wiring name."""
    unit = node(tree_name, node_id)
    params = ", ".join(i["name"] for i in unit["contract"]["inputs"])
    body = "\n".join("    " + line if line.strip() else line for line in unit["glue"].split("\n"))
    namespace = dict(children)
    exec(compile(f"def _glue({params}):\n{body}\n", f"<glue {tree_name}:{node_id}>", "exec"), namespace)
    return namespace["_glue"]


def unchanged(fn, *args):
    """Call fn, and report whether it left its arguments as they were."""
    before = copy.deepcopy(args)
    result = fn(*args)
    return result, before == args


# ---------- declared value spaces (from the stored-postings description) ----------

REGIONS = {"africa", "americas", "apac", "asia", "emea", "europe", "latin_america", "middle_east",
           "north_america", "oceania"}
LEVELS = {"intern", "junior", "senior", "staff", "principal", "lead", "manager", "director", "executive"}
WORK = {"remote", "hybrid", "onsite"}
EMPLOYMENT = {"full-time", "part-time", "contract", "temporary", "internship"}
PERIODS = {"hour", "day", "week", "month", "year"}
FIELDS = ["title", "link", "company", "location", "department_team", "full_text", "countries", "regions",
          "work_arrangement", "employment_type", "seniority", "salary", "years_of_experience", "posted_date"]
TEXT_LISTS = {"location", "department_team", "full_text"}
SORTED_LISTS = {"countries", "regions", "seniority"}


def _is_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return False
    try:
        datetime.date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _element_ok(field, value):
    """Whether one value (an element, for list fields) is in the field's declared space."""
    if field in ("title", "link", "company") or field in TEXT_LISTS:
        return isinstance(value, str) and value != ""
    if field == "countries":
        return isinstance(value, str) and re.fullmatch(r"[A-Z]{2}", value) is not None
    if field == "regions":
        return value in REGIONS
    if field == "seniority":
        return value in LEVELS
    if field == "work_arrangement":
        return value in WORK
    if field == "employment_type":
        return value in EMPLOYMENT
    if field == "salary":
        return (isinstance(value, dict) and set(value) == {"minimum", "maximum", "currency", "pay_period"}
                and all(isinstance(value[k], (int, float)) and not isinstance(value[k], bool)
                        for k in ("minimum", "maximum"))
                and value["minimum"] <= value["maximum"]
                and (value["currency"] is None or re.fullmatch(r"[A-Z]{3}", value["currency"] or "") is not None)
                and (value["pay_period"] is None or value["pay_period"] in PERIODS))
    if field == "years_of_experience":
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    if field == "posted_date":
        return _is_date(value)
    raise KeyError(field)


def record_problems(field, record, texts=None):
    """Every way a field record departs from the declared shape. `texts` maps an evidence path to the
    converted text at that path, when known, so that spans can be checked against it."""
    problems = []
    if not isinstance(record, dict) or set(record) != {"value", "evidence"}:
        return [f"{field}: not a {{value, evidence}} record: {record!r}"[:200]]
    value, evidence = record["value"], record["evidence"]
    if not isinstance(evidence, list):
        return [f"{field}: evidence is not a list"]
    if value is not None:
        if field in TEXT_LISTS or field in SORTED_LISTS:
            if not isinstance(value, list) or not value:
                problems.append(f"{field}: list field value {value!r} is not a non-empty list")
            else:
                problems += [f"{field}: element {v!r} outside value space" for v in value if not _element_ok(field, v)]
                if field in SORTED_LISTS and value != sorted(set(value)):
                    problems.append(f"{field}: {value!r} not sorted and distinct")
        elif not _element_ok(field, value):
            problems.append(f"{field}: value {value!r} outside value space")
    for entry in evidence:
        if not isinstance(entry, dict) or set(entry) != {"path", "span", "raw", "value"}:
            problems.append(f"{field}: evidence entry shape {entry!r}"[:200])
            continue
        if not isinstance(entry["path"], str) or not entry["path"]:
            problems.append(f"{field}: evidence path {entry['path']!r}")
        if entry["value"] is not None and not _element_ok(field, entry["value"]):
            problems.append(f"{field}: evidence value {entry['value']!r} outside value space")
        span = entry["span"]
        if span is not None:
            if not (isinstance(span, list) and len(span) == 2 and all(isinstance(x, int) for x in span)
                    and 0 <= span[0] < span[1]):
                problems.append(f"{field}: span {span!r}")
            elif texts is not None and entry["path"] in texts:
                if texts[entry["path"]][span[0]:span[1]] != entry["raw"]:
                    problems.append(f"{field}: span {span} of {entry['path']} reads "
                                    f"{texts[entry['path']][span[0]:span[1]]!r}, raw says {entry['raw']!r}")
    return problems


def store_problems(entries):
    """Departures of a stored-postings list from its declared shape."""
    problems = []
    keys = [(e.get("source_id"), e.get("posting_id")) for e in entries]
    if keys != sorted(keys) or len(set(keys)) != len(keys):
        problems.append("store not sorted by (source_id, posting_id) with one entry per key")
    for e in entries:
        if set(e) != {"source_id", "posting_id", "first_seen", "listing", "payload", "fields"}:
            problems.append(f"entry keys {sorted(e)}")
            continue
        if not isinstance(e["posting_id"], str) or not _is_date(e["first_seen"]):
            problems.append(f"entry {e['posting_id']!r} id/first_seen")
        listing = e["listing"]
        if listing["status"] == "listed" and listing["since"] is not None:
            problems.append(f"{e['posting_id']}: listed with since {listing['since']}")
        if listing["status"] == "no_longer_listed" and not _is_date(listing["since"]):
            problems.append(f"{e['posting_id']}: no_longer_listed without a since date")
    return problems


def load_fixture(name):
    data = json.load(open(os.path.join(FIXTURES, name)))
    return data if isinstance(data, list) else data["jobs"]


def short(value, limit=160):
    text = json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "..."


def calls_in(code):
    return [n for n in ast.walk(ast.parse(code)) if isinstance(n, ast.Call)]
