"""Behavior checks for the refresh tree's leaves, executed. Each leaf runs alone, on inputs built from
its contract: hand-made cases for each clause, the saved fixture postings for typical input, and
shapes unlike either for overfitting."""
import copy
import datetime
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from harness import FIELDS, check, load_fixture, load_leaf, record_problems, short, unchanged
from sources import BOARDS, PAY_FLOORS

T = "refresh"


def surface_return(node_id, result, outputs):
    """Return convention: one output bare, several as a map keyed by the output names."""
    if len(outputs) == 1:
        ok = not (isinstance(result, dict) and set(result) == {outputs[0]})
        how = "bare"
    else:
        ok = isinstance(result, dict) and list(result) == outputs
        how = f"map keyed {outputs}"
    check(T, node_id, "surface", ok, f"executed: return convention {how}; got {short(result, 100)}")


# ---------------------------------------------------------------- n5 fetch_source

class _Board(BaseHTTPRequestHandler):
    routes, hits, headers_seen = {}, [], {}

    def log_message(self, *args):
        pass

    def do_GET(self):
        _Board.hits.append((self.command, self.path))
        _Board.headers_seen[self.path] = dict(self.headers.items())
        status, body, extra = _Board.routes.get(self.path, (404, b"{}", {}))
        if status == "sleep":
            time.sleep(body)
            status, body, extra = 200, b"[]", {}
        self.send_response(status)
        for k, v in extra.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)


def n5():
    fetch_source, namespace = load_leaf(T, "n5")
    j = lambda v: json.dumps(v).encode()
    _Board.routes = {
        "/gh": (200, j({"jobs": [{"id": 11, "t": "a"}, {"id": 12, "t": "b"}], "meta": {"total": 2}}), {}),
        "/lever": (200, j([{"id": "u-1", "x": {"deep": [1, 2]}}, {"id": "u-2"}]), {}),
        "/nested": (200, j({"data": {"items": [{"ref": {"key": "q1"}}, {"ref": {"key": 7}}]}}), {}),
        "/404": (404, b"not here", {}),
        "/500": (500, b"oops", {}),
        "/text": (200, b"<html>hello</html>", {}),
        "/nolist": (200, j({"jobs": {"id": 1}}), {}),
        "/missing": (200, j({"other": []}), {}),
        "/noid": (200, j([{"id": 1}, {"name": "x"}]), {}),
        "/nonobject": (200, j([{"id": 1}, 5]), {}),
        "/dup": (200, j([{"id": 1, "v": "first"}, {"id": "1", "v": "second"}, {"id": 2}]), {}),
        "/boolid": (200, j([{"id": True}]), {}),
        "/floatid": (200, j([{"id": 1.5}]), {}),
        "/emptyid": (200, j([{"id": ""}]), {}),
        "/empty": (200, j({"jobs": []}), {}),
        "/slow": ("sleep", 3, {}),
        "/redirect": (302, b"", {"Location": "/gh"}),
        "/headers": (200, j([]), {}),
    }
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Board)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def src(path, list_path="jobs", id_path="id", headers=None, **extra):
        return {"id": f"s{path}", "company": "C", "endpoint": base + path, "headers": headers or {},
                "list_path": list_path, "id_path": id_path, "date": None, "fields": {}, **extra}

    def run(source):
        _Board.hits.clear()
        try:
            return fetch_source(source), list(_Board.hits), None
        except Exception as error:  # the contract says it never raises; record it if it does
            return None, list(_Board.hits), error

    r, hits, err = run(src("/gh"))
    surface_return("n5", r, ["fetch_result"])
    check(T, "n5", "behavior",
          err is None and r == {"source_id": "s/gh", "status": "ok", "postings": [
              {"posting_id": "11", "payload": {"id": 11, "t": "a"}},
              {"posting_id": "12", "payload": {"id": 12, "t": "b"}}]} and hits == [("GET", "/gh")],
          f"typical (Greenhouse envelope, list_path 'jobs', integer IDs): one GET {hits}; ok with IDs as "
          f"strings in response order, payload unchanged: {short(r)}")

    r, hits, err = run(src("/lever", list_path=None))
    check(T, "n5", "behavior",
          err is None and r["status"] == "ok" and [p["posting_id"] for p in r["postings"]] == ["u-1", "u-2"]
          and r["postings"][0]["payload"] == {"id": "u-1", "x": {"deep": [1, 2]}},
          f"list_path null (Lever bare list): whole body is the list; {short(r)}")

    r, hits, err = run(src("/nested", list_path="data.items", id_path="ref.key"))
    check(T, "n5", "behavior",
          err is None and r["status"] == "ok" and [p["posting_id"] for p in r["postings"]] == ["q1", "7"],
          f"overfit: nested list_path 'data.items' and dotted id_path 'ref.key', mixed string/integer IDs: {short(r)}")

    r, hits, err = run(src("/dup", list_path=None))
    check(T, "n5", "behavior",
          err is None and r["status"] == "ok" and [(p["posting_id"], p["payload"].get("v")) for p in r["postings"]]
          == [("1", "first"), ("2", None)],
          f"repeated ID (1 and '1' are the same ID as strings): later element omitted, first kept: {short(r)}",)

    r, hits, err = run(src("/empty"))
    check(T, "n5", "behavior", err is None and r == {"source_id": "s/empty", "status": "ok", "postings": []},
          f"boundary: an empty list is a successful fetch with no postings: {short(r)}")

    failures = {
        "/404": ("404", src("/404")), "/500": ("500", src("/500")),
        "/text": ("JSON", src("/text")), "/nolist": ("'jobs'", src("/nolist")),
        "/missing": ("'jobs'", src("/missing")), "/noid": ("ID", src("/noid", list_path=None)),
        "/nonobject": ("object", src("/nonobject", list_path=None)),
        "/boolid": ("ID", src("/boolid", list_path=None)), "/floatid": ("ID", src("/floatid", list_path=None)),
    }
    results = {}
    for path, (needle, source) in failures.items():
        r, hits, err = run(source)
        results[path] = (err is None and r.get("status") == "failed" and needle in r.get("reason", "")
                         and set(r) == {"source_id", "status", "reason"} and len(hits) == 1, r and r.get("reason"))
    check(T, "n5", "behavior", all(ok for ok, _ in results.values()),
          "each failure kind yields status 'failed', no postings and a reason naming it, after exactly one "
          "request: " + "; ".join(f"{p} -> {reason!r}" for p, (ok, reason) in results.items()))

    # the network failing: nothing listening, and an endpoint that is not a URL
    import socket
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    closed_port = probe.getsockname()[1]
    probe.close()
    r1, _, e1 = run({**src("/x"), "endpoint": f"http://127.0.0.1:{closed_port}/x"})
    r2, _, e2 = run({**src("/x"), "endpoint": "not a url"})
    r3, _, e3 = run({"id": "broken", "endpoint": base + "/gh", "list_path": "jobs"})  # no id_path
    check(T, "n5", "behavior",
          e1 is None and e2 is None and e3 is None and r1["status"] == r2["status"] == r3["status"] == "failed",
          f"never raises: connection refused -> {r1 and r1.get('reason')!r}; endpoint 'not a url' -> "
          f"{r2 and r2.get('reason')!r}; definition without id_path -> {r3 and r3.get('reason')!r}")

    # bounded timeout: the module constant is the bound; shorten it to watch it fire
    original = namespace["_TIMEOUT_SECONDS"]
    namespace["_TIMEOUT_SECONDS"] = 1
    started = time.monotonic()
    r, hits, err = run(src("/slow", list_path=None))
    elapsed = time.monotonic() - started
    namespace["_TIMEOUT_SECONDS"] = original
    check(T, "n5", "behavior",
          err is None and r["status"] == "failed" and "timed out" in r["reason"] and elapsed < 2.5,
          f"timeout: bound set to 1s against a server that waits 3s -> {r and r.get('reason')!r} after "
          f"{elapsed:.1f}s; the shipped bound is {original}s")

    # reading 4: "exactly its headers"
    r, hits, err = run(src("/headers", list_path=None, headers={"User-Agent": "job-triage/2", "X-Probe": "1"}))
    seen = _Board.headers_seen.get("/headers", {})
    r0, _, _ = run(src("/headers", list_path=None))
    seen_none = dict(_Board.headers_seen.get("/headers", {}))
    transport = {"Host", "Accept-Encoding", "Connection"}
    check(T, "n5", "behavior",
          seen.get("User-Agent") == "job-triage/2" and seen.get("X-Probe") == "1"
          and set(seen) - transport == {"User-Agent", "X-Probe"} and set(seen_none) <= transport,
          f"reading 4, 'exactly its headers': with {{User-Agent, X-Probe}} the server received {sorted(seen)}; "
          f"with no headers it received {sorted(seen_none)} (no default User-Agent). Host, Accept-Encoding "
          f"and Connection come from the HTTP transport, not the leaf; judged within the contract")

    # a redirect is followed by the transport: two requests, the second to another address
    r, hits, err = run(src("/redirect"))
    check(T, "n5", "behavior",
          err is None and r["status"] == "ok" and hits == [("GET", "/redirect"), ("GET", "/gh")],
          f"redirect: the leaf issues one request; urllib follows the 302, so the server saw {hits} and the "
          f"result is {r and r['status']!r}. Read as within 'sends one GET request to its endpoint' (the "
          f"leaf sends one; the response is 2xx); noted for composition")

    # an empty-string ID: the contract's 'a string' admits it, the leaf treats it as no ID
    r, hits, err = run(src("/emptyid", list_path=None))
    check(T, "n5", "behavior", err is None and r["status"] == "failed",
          f"boundary: an element whose ID is '' -> {r and r.get('reason')!r}. Judged within the contract: "
          f"'' is not an ID, which the failure list names ('an element without an ID')")

    server.shutdown()


# ---------------------------------------------------------------- n7 read_stated_text

def n7():
    read_stated_text, _ = load_leaf(T, "n7")
    outputs = ["title", "link", "company", "location", "department_team", "full_text"]

    # typical: every fixture posting under its board's definition
    problems, counted, tags_left, double_spaces = [], 0, [], []
    for fixture, source in BOARDS:
        for payload in load_fixture(fixture):
            out, same = unchanged(read_stated_text, payload, source)
            counted += 1
            if not same:
                problems.append(f"{source['id']}: payload changed")
            if list(out) != outputs:
                problems.append(f"keys {list(out)}")
            texts = {e["path"]: e["value"] for f in out.values() for e in f["evidence"]}
            for f, record in out.items():
                problems += [f"{source['id']} {p}" for p in record_problems(f, record)]
                if f in ("location", "department_team", "full_text") and record["value"] is not None:
                    if [e["value"] for e in record["evidence"]] != record["value"]:
                        problems.append(f"{f}: evidence does not list the pieces in order")
            for piece in out["full_text"]["value"] or []:
                if "<" in piece and ">" in piece and "</" in piece:
                    tags_left.append(piece[:60])
                if "  " in piece:
                    double_spaces.append(repr(piece[max(0, piece.index("  ") - 30):piece.index("  ") + 30]))
            if out["company"] != {"value": source["company"], "evidence": [
                    {"path": "source.company", "span": None, "raw": source["company"], "value": source["company"]}]}:
                problems.append("company record")
    surface_return("n7", out, outputs)
    check(T, "n7", "behavior", not problems and not tags_left,
          f"typical: {counted} fixture postings (Greenhouse escaped_html, Lever plain+html lists, Ashby html): "
          f"six records keyed by output name, values in their declared spaces, one evidence entry per piece "
          f"in order, company from the definition, payload unchanged, no markup left; problems: "
          f"{problems[:5] or 'none'}")
    check(T, "n7", "behavior", not double_spaces,
          f"html conversion collapses whitespace runs: {len(double_spaces)} fixture pieces still hold a run "
          f"of two spaces, e.g. {double_spaces[:3]}")

    src = lambda fields, company="Acme": {"id": "s", "company": company, "fields": fields}
    cases = [
        ("plain collapses and trims", {"t": "  Senior \n  Engineer\t "}, {"title": [{"path": "t"}]},
         "title", "Senior Engineer"),
        ("html: tags out, blocks to line breaks, entities decoded",
         {"d": "<h2>About</h2><p>We&#39;re <b>hiring</b>&nbsp;now.</p><ul><li>One</li><li>Two</li></ul>Tail<br>end"},
         {"full_text": [{"path": "d", "format": "html"}]}, "full_text", ["About\nWe're hiring now.\nOne\nTwo\nTail\nend"]),
        ("html: whitespace split across inline tags", {"d": "<p>Hello <b> world</b>  again</p>"},
         {"full_text": [{"path": "d", "format": "html"}]}, "full_text", ["Hello world again"]),
        ("escaped_html decoded once, then as html", {"d": "&lt;p&gt;Fish &amp;amp; chips&lt;/p&gt;"},
         {"full_text": [{"path": "d", "format": "escaped_html"}]}, "full_text", ["Fish & chips"]),
        ("list path: indexed evidence paths, repeats and empties dropped",
         {"offices": [{"name": "Berlin"}, {"name": " "}, {"name": "Berlin"}, {"name": "Paris"}], "loc": "Paris"},
         {"location": [{"path": "offices[].name"}, {"path": "loc"}]}, "location", ["Berlin", "Paris"]),
        ("title is the first contributed text", {"a": "", "b": "First", "c": "Second"},
         {"title": [{"path": "a"}, {"path": "b"}, {"path": "c"}]}, "title", "First"),
        ("non-text values contribute nothing", {"n": 5, "o": {"x": 1}, "l": None},
         {"department_team": [{"path": "n"}, {"path": "o"}, {"path": "l"}]}, "department_team", None),
        ("overfit: nested steps through two lists", {"a": {"b": [{"c": [{"d": "x"}, {"d": "y"}]}, {"c": [{"d": "z"}]}]}},
         {"department_team": [{"path": "a.b[].c[].d"}]}, "department_team", ["x", "y", "z"]),
    ]
    outcomes = []
    for label, payload, fields, field, expected in cases:
        out = read_stated_text(payload, src(fields))
        outcomes.append((label, out[field]["value"] == expected, out[field]["value"], expected,
                         [e["path"] for e in out[field]["evidence"]]))
    for label, ok, got, expected, paths in outcomes:
        check(T, "n7", "behavior", ok, f"{label}: got {got!r}, expected {expected!r}; evidence paths {paths}")

    out = read_stated_text({}, src({}))
    check(T, "n7", "behavior",
          all(out[f] == {"value": None, "evidence": []} for f in outputs if f != "company")
          and out["company"]["value"] == "Acme",
          f"boundary: a definition with no locators gives every stated field null with no evidence, "
          f"company still from the definition: {short(out)}")


# ---------------------------------------------------------------- n8 derive_geography

def _location(*texts):
    return {"value": list(texts) or None,
            "evidence": [{"path": f"loc.{i}", "span": None, "raw": t, "value": t} for i, t in enumerate(texts)]}


def n8():
    derive_geography, _ = load_leaf(T, "n8")
    read_stated_text, _ = load_leaf(T, "n7")
    none = {"id": "s", "company": "C", "fields": {}}

    # typical: fixture postings, location from read_stated_text (a contract-conformant input)
    problems, seen = [], []
    for fixture, source in BOARDS:
        for payload in load_fixture(fixture):
            location = read_stated_text(payload, source)["location"]
            out, same = unchanged(derive_geography, payload, source, location)
            if not same:
                problems.append("inputs changed")
            texts = {e["path"]: e["value"] for e in location["evidence"]}
            for f in ("countries", "regions"):
                problems += record_problems(f, out[f], texts)
            seen.append((location["value"], out["countries"]["value"], out["regions"]["value"]))
    surface_return("n8", out, ["countries", "regions"])
    check(T, "n8", "behavior", not problems,
          f"typical: {len(seen)} fixture postings; both records in their declared spaces, spans read back "
          f"the raw text from the location pieces; problems {problems[:4] or 'none'}; e.g. "
          f"{short(seen[2], 120)}, {short(seen[30], 120)}")

    def geo(*texts, payload=None, source=none):
        out = derive_geography(payload or {}, source, _location(*texts))
        return out["countries"]["value"], out["regions"]["value"], out

    cases = [
        ("short form 'US'", ("Remote - US",), (["US"], ["north_america"])),
        ("country names, several", ("Remote, Canada; Remote, United Kingdom",), (["CA", "GB"], ["europe", "north_america"])),
        ("state by name implies US", ("Remote, Colorado",), (["US"], ["north_america"])),
        ("state postal code that is not an ISO code implies US", ("Austin, TX",), (["US"], ["north_america"])),
        ("state code that is also an ISO code is not read in location text", ("San Francisco, CA",), (None, None)),
        ("'Georgia' is not in the table", ("Atlanta, Georgia",), (None, None)),
        ("'New South Wales' is Australia, not Wales", ("Sydney, New South Wales",), (["AU"], ["oceania"])),
        ("'Indiana' is not India", ("Indianapolis, Indiana",), (["US"], ["north_america"])),
        ("region names; a region never implies a country", ("Remote, EMEA",), (None, ["emea"])),
        ("region synonym", ("LATAM",), (None, ["latin_america"])),
        ("one region is not added because another names it", ("Europe",), (None, ["europe"])),
        ("a country implying two regions", ("Istanbul, Turkey",), (["TR"], ["europe", "middle_east"])),
        ("narrowed contract: an entry counts where the text means something else", ("Lebanon, NH",),
         (["LB", "US"], ["middle_east", "north_america"])),
        ("cities are not read", ("Bangalore",), (None, None)),
    ]
    for label, texts, (countries, regions) in cases:
        got_c, got_r, out = geo(*texts)
        check(T, "n8", "behavior", (got_c, got_r) == (countries, regions),
              f"{label}: {texts} -> countries {got_c}, regions {got_r}; expected {countries}, {regions}")

    got_c, got_r, out = geo("Remote, US")
    implied = [e for e in out["regions"]["evidence"] if e["value"] == "north_america"]
    country = out["countries"]["evidence"][0]
    check(T, "n8", "behavior", implied == [{**country, "value": "north_america"}],
          f"an implied region's evidence is its country's evidence with value the region: {short(implied)}")

    # countries locators: an ISO code is read whole, by declaration
    locator_src = {"id": "s", "company": "C", "fields": {"countries": [{"path": "c"}]}}
    def by_locator(value):
        out = derive_geography({"c": value}, locator_src, None)
        return out["countries"], out["regions"]
    c, r = by_locator("CA")
    check(T, "n8", "behavior", c["value"] == ["CA"] and r["value"] == ["north_america"],
          f"a countries-locator value 'CA' is the ISO code (Canada), not California: {c['value']}, {r['value']}")
    c, r = by_locator("Narnia")
    check(T, "n8", "behavior", c == {"value": None, "evidence": [{"path": "c", "span": None, "raw": "Narnia", "value": None}]}
          and r["value"] is None,
          f"a locator value naming nothing is kept as evidence with value null: {short(c)}")
    c, r = by_locator("European Union")
    w_c, w_r = by_locator("Worldwide")
    check(T, "n8", "behavior",
          c == {"value": None, "evidence": []} and r["value"] == ["europe"]
          and r["evidence"] == [{"path": "c", "span": None, "raw": "European Union", "value": "europe"}]
          and w_c == {"value": None, "evidence": [{"path": "c", "span": None, "raw": "Worldwide", "value": None}]}
          and w_r["value"] is None,
          f"the amended example: 'European Union' at a countries locator names the region europe ({short(r)}), "
          f"and 'Worldwide' names neither a country nor a region in the tables, kept with value null "
          f"({short(w_c)})")

    c, r = by_locator("  Canada,  Mexico")
    spans_ok = all(e["span"] is None or "  Canada,  Mexico"[e["span"][0]:e["span"][1]] == e["raw"]
                   for e in c["evidence"])
    converted = "Canada, Mexico"
    spans_converted = all(e["span"] is None or converted[e["span"][0]:e["span"][1]] == e["raw"] for e in c["evidence"])
    check(T, "n8", "behavior", spans_converted,
          f"span offsets are into the text 'as converted to plain text': locator value '  Canada,  Mexico' "
          f"converts to {converted!r}; spans {[e['span'] for e in c['evidence']]} read back the raw value "
          f"({spans_ok}) but not the converted text ({spans_converted}). Only when a locator value has extra "
          f"whitespace")

    html_src = {"id": "s", "company": "C", "fields": {"countries": [{"path": "c", "format": "html"}]}}
    value = "<p>Remote in <b>Canada</b> &amp;  Mexico</p>"
    out = derive_geography({"c": value}, html_src, None)
    converted = "Remote in Canada & Mexico"
    check(T, "n8", "behavior",
          out["countries"]["value"] == ["CA", "MX"]
          and all(converted[e["span"][0]:e["span"][1]] == e["raw"] for e in out["countries"]["evidence"]),
          f"a countries locator in html format is converted as the locator says before it is read, and spans "
          f"index the converted text {converted!r}: {short(out['countries'])}")

    # reading 1: codes are matched in capitals only; the contract says case-insensitive
    lower = [geo(t)[0] for t in ("Join us in Italy", "Remote, uk", "remote (usa)", "no relocation; it team")]
    upper = [geo(t)[0] for t in ("Remote - US", "Remote, UK", "remote (USA)")]
    names = [geo(t)[0] for t in ("remote - united states", "LONDON, ENGLAND", "toronto, canada")]
    check(T, "n8", "behavior",
          lower == [["IT"], None, None, None] and upper == [["US"], ["GB"], ["US"]]
          and names == [["US"], ["GB"], ["CA"]],
          f"the amended case rule: two- and three-letter names count only in capitals ({upper}); in lower "
          f"case they do not, so 'join us', 'it', 'no' are not countries ({lower}; 'Italy' is read as a "
          f"name); longer names count in any case ({names})")

    # overfit: the locator path, its shape and the location paths are the definition's to choose
    odd = {"id": "s", "company": "C", "fields": {"countries": [{"path": "geo.list[].iso"}]}}
    out = derive_geography({"geo": {"list": [{"iso": "de"}, {"iso": "FR"}]}}, odd, _location("Remote"))
    check(T, "n8", "behavior", out["countries"]["value"] == ["DE", "FR"]
          and [e["path"] for e in out["countries"]["evidence"]] == ["geo.list.0.iso", "geo.list.1.iso"],
          f"overfit: a locator stepping into a list ('geo.list[].iso'), a lower-case code: "
          f"{out['countries']['value']}, paths {[e['path'] for e in out['countries']['evidence']]}")


# ---------------------------------------------------------------- n9 derive_work_arrangement

def n9():
    derive, _ = load_leaf(T, "n9")
    read_stated_text, _ = load_leaf(T, "n7")
    problems, values = [], []
    for fixture, source in BOARDS:
        for payload in load_fixture(fixture):
            location = read_stated_text(payload, source)["location"]
            out, same = unchanged(derive, payload, source, location)
            texts = {e["path"]: e["value"] for e in location["evidence"]}
            problems += record_problems("work_arrangement", out, texts) + ([] if same else ["inputs changed"])
            values.append(out["value"])
    surface_return("n9", out, ["work_arrangement"])
    check(T, "n9", "behavior", not problems,
          f"typical: {len(values)} fixture postings; values {sorted(set(map(str, values)))}; problems {problems[:4] or 'none'}")

    wa = lambda locators: {"id": "s", "company": "C", "fields": {"work_arrangement": locators}}
    lev = wa([{"path": "w", "values": {"remote": "remote", "hybrid": "hybrid", "onsite": "onsite"}}])
    out = derive({"w": "unspecified"}, lev, _location("Remote - Berlin"))
    check(T, "n9", "behavior",
          out["value"] == "remote" and out["evidence"][0] == {"path": "w", "span": None, "raw": "unspecified", "value": None}
          and out["evidence"][1]["value"] == "remote" and out["evidence"][1]["span"] == [0, 6],
          f"unmapped board value kept as evidence with value null, then location text read: {short(out)}")
    two = wa([{"path": "a", "values": {"x": "hybrid"}}, {"path": "b", "values": {"true": "remote"}}])
    out = derive({"a": "x", "b": True}, two, _location("On-site"))
    check(T, "n9", "behavior",
          out["value"] == "hybrid" and [e["value"] for e in out["evidence"]] == ["hybrid", "remote"],
          f"first mapped value in locator order wins; a JSON true is looked up as 'true'; location not read: {short(out)}")
    cases = [("Remote - US", "remote"), ("Hybrid, NYC", "hybrid"), ("On-site in Berlin", "onsite"),
             ("onsite", "onsite"), ("In office, London", "onsite"), ("in-office", "onsite"),
             ("Remote or Hybrid", None), ("Berlin", None), ("Remotely", None)]
    got = [(t, derive({}, wa([]), _location(t))["value"]) for t, _ in cases]
    check(T, "n9", "behavior", got == cases,
          f"location words (whole words, case-insensitive; two arrangements -> null; none -> null, never "
          f"onsite): {got}")


# ---------------------------------------------------------------- n10 derive_employment_type

def _title(text, path="title"):
    return {"value": text, "evidence": [{"path": path, "span": None, "raw": text, "value": text}]}


def n10():
    derive, _ = load_leaf(T, "n10")
    read_stated_text, _ = load_leaf(T, "n7")
    problems, values = [], []
    for fixture, source in BOARDS:
        for payload in load_fixture(fixture):
            title = read_stated_text(payload, source)["title"]
            out, same = unchanged(derive, payload, source, title)
            problems += record_problems("employment_type", out, {e["path"]: e["value"] for e in title["evidence"]})
            values.append((title["value"], out["value"]))
    surface_return("n10", out, ["employment_type"])
    check(T, "n10", "behavior", not problems,
          f"typical: {len(values)} fixture postings; problems {problems[:4] or 'none'}; e.g. "
          f"{[v for v in values if v[1] is not None and 'ontract' in v[0]][:2]}")

    et = {"id": "s", "company": "C", "fields": {"employment_type": [
        {"path": "c", "values": {"Permanent": "full-time", "Intern": "internship"}}]}}
    out = derive({"c": "Short Term"}, et, _title("Designer (Contract)"))
    check(T, "n10", "behavior",
          out["value"] == "contract" and out["evidence"][0]["value"] is None and len(out["evidence"]) == 2,
          f"unmapped board value 'Short Term' kept with value null, then the title read: {short(out)}")
    out = derive({"c": "Permanent"}, et, _title("Software Engineering Intern"))
    check(T, "n10", "behavior", out["value"] == "full-time" and len(out["evidence"]) == 1,
          f"a mapped locator value wins and the title is not read: {short(out)}")
    none = {"id": "s", "company": "C", "fields": {}}
    cases = [("Software Engineering Intern", "internship"), ("Summer Internship 2027", "internship"),
             ("Contracts Manager", None), ("Contract Specialist", None), ("Designer (Contract)", "contract"),
             ("Data Analyst - Contract", "contract"), ("Candidate Experience Specialist, Contractor", "contract"),
             ("Part-time Barista", "part-time"), ("Part Time Tutor", "part-time"), ("Temporary Receptionist", "temporary"),
             ("Full-time Engineer", "full-time"), ("Full Time / Part Time Associate", None), ("Engineer", None)]
    got = [(t, derive({}, none, _title(t))["value"]) for t, _ in cases]
    check(T, "n10", "behavior", got == cases, f"title words from the contract's list: {got}")
    subject = [("Internship Program Manager", None), ("Intern Recruiter", None),
               ("Temporary Housing Coordinator", None), ("Full-Time Equivalent Planning Analyst", None),
               ("Intern Coordinator", "internship"), ("Interns", "internship")]
    got = [(t, derive({}, none, _title(t))["value"]) for t, _ in subject]
    check(T, "n10", "behavior", got == subject,
          f"the narrowed contract: a match inside an exception phrase gives nothing ('Internship Program', "
          f"'Full-Time Equivalent' and the table's others); the table decides, so a listed word in a phrase "
          f"its exceptions lack counts ('Intern Coordinator' gives 'internship', as the contract says): {got}")


# ---------------------------------------------------------------- n11 derive_seniority

def n11():
    derive, _ = load_leaf(T, "n11")
    read_stated_text, _ = load_leaf(T, "n7")
    problems, values = [], []
    for fixture, source in BOARDS:
        for payload in load_fixture(fixture):
            title = read_stated_text(payload, source)["title"]
            out, same = unchanged(derive, title)
            problems += record_problems("seniority", out, {e["path"]: e["value"] for e in title["evidence"]})
            values.append((title["value"], out["value"]))
    surface_return("n11", out, ["seniority"])
    check(T, "n11", "behavior", not problems,
          f"typical: {len(values)} fixture titles; spans read back the title; problems {problems[:4] or 'none'}; "
          f"e.g. {values[15]}, {values[33]}")
    cases = [("Senior / Staff Fullstack Engineer", ["senior", "staff"]), ("Sr. Engineer", ["senior"]),
             ("Area Vice President - Financial Services", ["executive"]), ("VP, Sales", ["executive"]),
             ("Chief Technology Officer", ["executive"]), ("Director of Engineering", ["director"]),
             ("Engineering Manager", ["manager"]), ("Principal Product Designer", ["principal"]),
             ("Team Lead, Platform", ["lead"]), ("Junior Developer", ["junior"]), ("Entry-Level Analyst", ["junior"]),
             ("Software Intern", ["intern"]), ("Chief of Staff, CRO", None), ("Lead Generation Specialist", None),
             ("Staff Pharmacist", ["staff"]), ("Head of Design", None), ("Associate Product Manager", ["manager"]),
             ("Internal Tools Engineer", None), ("Leadership Coach", None), ("Staffing Coordinator", None),
             ("Engineer", None)]
    got = [(t, derive(_title(t))["value"]) for t, _ in cases]
    check(T, "n11", "behavior", got == cases,
          f"level table, exception phrases, whole words, sorted distinct; reading 2 ('Manager' counts from the "
          f"word, 'Head of' and 'Associate' give nothing) and the narrowed 'Staff Pharmacist' case: {got}")
    out = derive(_title("Senior Engineer", path="text"))
    check(T, "n11", "behavior", out["evidence"] == [{"path": "text", "span": [0, 6], "raw": "Senior", "value": "senior"}],
          f"evidence path is the title's own path (overfit: 'text', as on Lever): {short(out)}")
    check(T, "n11", "behavior", derive({"value": None, "evidence": []}) == {"value": None, "evidence": []},
          "boundary: an unknown title gives null with no evidence")


# ---------------------------------------------------------------- n12 derive_salary

def _text(*pieces):
    return {"value": list(pieces), "evidence": [{"path": f"body.{i}", "span": None, "raw": p, "value": p}
                                                for i, p in enumerate(pieces)]}


def _countries(*codes):
    return {"value": list(codes) or None, "evidence": []}


def n12():
    derive, _ = load_leaf(T, "n12")
    read_stated_text, _ = load_leaf(T, "n7")
    derive_geography, _ = load_leaf(T, "n8")
    problems, found = [], []
    for fixture, source in BOARDS:
        for payload in load_fixture(fixture):
            stated = read_stated_text(payload, source)
            countries = derive_geography(payload, source, stated["location"])["countries"]
            out, same = unchanged(derive, stated["full_text"], countries, PAY_FLOORS)
            problems += record_problems("salary", out, {e["path"]: e["value"] for e in stated["full_text"]["evidence"]})
            if out["evidence"]:
                found.append((stated["title"]["value"], out["value"], [e["raw"] for e in out["evidence"]]))
    surface_return("n12", out, ["salary"])
    check(T, "n12", "behavior", not problems,
          f"typical: 45 fixture postings, {len(found)} with salary statements; spans read back the raw text; "
          f"problems {problems[:4] or 'none'}; e.g. {short(found[:2], 300)}")

    def sal(text, countries=(), floors=PAY_FLOORS):
        return derive(_text(text), _countries(*countries), floors)

    cases = [
        ("ISO code after, em dash, no period: yearly above the USD floor", "$139,200 — $235,200 USD", (),
         {"minimum": 139200, "maximum": 235200, "currency": "USD", "pay_period": "year"}),
        ("ISO code before", "USD 90,000 - 120,000", ("CA",),
         {"minimum": 90000, "maximum": 120000, "currency": "USD", "pay_period": "year"}),
        ("euro with k", "€50k–€60k", ("DE",), {"minimum": 50000, "maximum": 60000, "currency": "EUR", "pay_period": "year"}),
        ("pound, 'to'", "£40,000 to £50,000 per annum", ("GB",),
         {"minimum": 40000, "maximum": 50000, "currency": "GBP", "pay_period": "year"}),
        ("bare $ with countries exactly ['US']", "$100,000 - $150,000", ("US",),
         {"minimum": 100000, "maximum": 150000, "currency": "USD", "pay_period": "year"}),
        ("bare $ with other countries: currency null, so no floor, period null", "$100,000 - $150,000", ("US", "CA"),
         {"minimum": 100000, "maximum": 150000, "currency": None, "pay_period": None}),
        ("stated hourly", "$50 - $60 per hour", ("US",), {"minimum": 50, "maximum": 60, "currency": "USD", "pay_period": "hour"}),
        ("'/hr'", "$50-$60/hr", ("US",), {"minimum": 50, "maximum": 60, "currency": "USD", "pay_period": "hour"}),
        ("below the floor, no period stated: null", "$3,000 - $4,000", ("US",),
         {"minimum": 3000, "maximum": 4000, "currency": "USD", "pay_period": None}),
        ("currency without a floor entry: null", "CHF 120,000 - 140,000", ("CH",),
         {"minimum": 120000, "maximum": 140000, "currency": "CHF", "pay_period": None}),
        ("k after the high figure only (read as both)", "$50-60k", ("US",),
         {"minimum": 50000, "maximum": 60000, "currency": "USD", "pay_period": "year"}),
        ("single figure: not a statement", "$150,000 per year", ("US",), None),
        ("no currency: not a statement", "2020 - 2024", ("US",), None),
    ]
    for label, text, countries, expected in cases:
        out = sal(text, countries)
        check(T, "n12", "behavior", out["value"] == expected,
              f"{label}: {text!r} with countries {list(countries)} -> {out['value']}; expected {expected}")

    out = derive(_text("Base pay $100,000 - $120,000.", "Senior band: $110,000 - $140,000"), _countries("US"), PAY_FLOORS)
    check(T, "n12", "behavior",
          out["value"] == {"minimum": 100000, "maximum": 140000, "currency": "USD", "pay_period": "year"}
          and [e["path"] for e in out["evidence"]] == ["body.0", "body.1"],
          f"agreeing statements in two pieces: value spans lowest minimum to highest maximum, both kept as "
          f"evidence: {short(out, 250)}")
    out = sal("Salary $120,000 - $150,000. Relocation stipend of $1,000 - $2,000 monthly.", ("US",))
    check(T, "n12", "behavior", out["value"] is None and len(out["evidence"]) == 2,
          f"reading 3: a stipend range disagrees on pay period, so the value is null with both statements "
          f"as evidence, as the contract says for disagreeing statements: {short(out, 250)}")

    near = sal("Hourly rate: $50 - $60", ("US",))["value"]
    far = sal("$100,000 - $120,000. Our benefits are generous and reviewed monthly.", ("US",))["value"]
    check(T, "n12", "behavior", near["pay_period"] == "hour" and far["pay_period"] == "year",
          f"reading 5, 'beside the figures' read as within 40 characters on the same line: a period just "
          f"before the figures counts ({near['pay_period']}); 'monthly' 49 characters on, in another sentence, "
          f"does not, so the floor applies ({far['pay_period']})")
    text = "$4,000 - $5,000 per month or $50,000 - $60,000 per year"
    out = sal(text, ("US",))
    periods = [e["value"]["pay_period"] for e in out["evidence"]]
    check(T, "n12", "behavior", out["value"] is None and periods == ["month", "year"],
          f"reading 5, two statements side by side: {text!r}. A period within the window counts for the "
          f"statement it is nearer, so the first is monthly and the second yearly ({periods}); they disagree "
          f"and the value is null, as the contract says: {out['value']}")
    text = "Monthly: $4,000 - $5,000; $50 - $60"
    out = sal(text, ("US",))
    check(T, "n12", "behavior", [e["value"]["pay_period"] for e in out["evidence"]] == ["month", None],
          f"a period beside one statement does not reach a later one it is farther from: {text!r} -> "
          f"{[e['value']['pay_period'] for e in out['evidence']]} (the second is below the floor, so null)")
    got = [sal("US$90,000 - US$110,000", ("CA",))["value"], sal("C$80,000 - C$100,000", ("CA",))["value"]]
    check(T, "n12", "behavior",
          got[0]["currency"] == "USD" and got[1]["currency"] == "CAD" and got[1]["pay_period"] is None,
          f"symbols that name one currency (US$, C$) are read as that currency; the contract names only "
          f"'€' and '£' but defines a statement's currency as 'given as a symbol', and these are not a bare "
          f"'$'. Judged within the contract. CAD has no pay-floor entry in this table, so its period stays "
          f"null: {got}")
    out = sal("We raised $20 - 30M in our Series B. Salary: $150,000 - $180,000.", ("US",))
    check(T, "n12", "behavior",
          out["value"] is None and [e["raw"] for e in out["evidence"]] == ["$20 - 30", "$150,000 - $180,000"],
          f"a funding range has the form of a salary statement (two figures, a currency), so it counts as one, "
          f"disagrees on pay period with the real salary, and the value is null: {short(out, 260)}. Within "
          f"the contract, which defines a statement by its form; for composition's watch list")
    out = sal("$1,500 - $2,000\nper month", ("US",))
    check(T, "n12", "behavior", out["value"]["pay_period"] is None,
          f"the window stops at a line break (a period on the next line is not 'beside'): {short(out['value'])}")


# ---------------------------------------------------------------- n13 derive_years_of_experience

def n13():
    derive, _ = load_leaf(T, "n13")
    read_stated_text, _ = load_leaf(T, "n7")
    problems, found = [], []
    for fixture, source in BOARDS:
        for payload in load_fixture(fixture):
            full_text = read_stated_text(payload, source)["full_text"]
            out, same = unchanged(derive, full_text)
            problems += record_problems("years_of_experience", out, {e["path"]: e["value"] for e in full_text["evidence"]})
            if out["evidence"]:
                found.append((out["value"], [e["raw"] for e in out["evidence"]][:3]))
    surface_return("n13", out, ["years_of_experience"])
    check(T, "n13", "behavior", not problems,
          f"typical: 45 fixture postings, {len(found)} with requirement statements; spans read back the raw "
          f"text; problems {problems[:4] or 'none'}; e.g. {short(found[:3], 300)}")
    cases = [("5+ years of experience", 5), ("3-5 years in a similar role", 3), ("3 to 5 years", 3),
             ("at least 4 years", 4), ("a minimum of 2 years", 2), ("Minimum 6 years", 6), ("two or more years", 2),
             ("Seven years of professional software experience", 7), ("10+ yrs", 10),
             ("after 4 years", None), ("every 2 years", None), ("founded 10 years ago", None),
             ("1.5 years", None)]
    got = [(t, derive(_text(t))["value"]) for t, _ in cases]
    check(T, "n13", "behavior", got == cases, f"the contract's forms and its non-requirements: {got}")
    out = derive(_text("8+ years of experience", "or 5 years with a PhD and 5 years of research experience"))
    check(T, "n13", "behavior", out["value"] == 5 and len(out["evidence"]) == 2,
          f"lowest N across all statements and pieces, every statement kept as evidence: {short(out, 250)}")
    forms = [("We have been fully remote for at least 3 years.", 3),
             ("Our customers have 10+ years of history with us.", 10),
             ("In 2 years you will gain experience leading a team.", None),
             ("5 years experience in sales", 5), ("5 years' experience in sales", 5),
             ("5 years\u2019 experience in sales", 5), ("3 years of building systems and experience", 3)]
    got = [(t, derive(_text(t))["value"]) for t, _ in forms]
    check(T, "n13", "behavior", got == forms,
          f"the narrowed contract: the forms decide. A mention in a form counts even when it states no "
          f"requirement ('fully remote for at least 3 years' gives 3, as the contract says); a mention in "
          f"none does not ('in 2 years you will gain experience'); 'N years experience', \"N years' "
          f"experience\" and 'N years of' + up to four words + 'experience' count: {got}")


# ---------------------------------------------------------------- n14 read_posted_date

def n14():
    read, _ = load_leaf(T, "n14")
    got = []
    for fixture, source in BOARDS:
        payload = load_fixture(fixture)[0]
        out, same = unchanged(read, payload, source)
        got.append((source["id"], out["value"], out["evidence"][0]["raw"]))
    lever_raw = got[1][2]
    lever_utc = datetime.datetime.fromtimestamp(lever_raw / 1000, tz=datetime.timezone.utc).date().isoformat()
    surface_return("n14", out, ["posted_date"])
    check(T, "n14", "behavior",
          got[0][1] == got[0][2][:10] and got[2][1] == got[2][2][:10] and got[1][1] == lever_utc,
          f"typical, the three fixture boards: {got}; Lever's epoch millis independently -> {lever_utc}")
    iso = {"id": "s", "company": "C", "date": {"path": "d", "format": "iso8601"}, "fields": {}}
    ms = {"id": "s", "company": "C", "date": {"path": "d", "format": "epoch_millis"}, "fields": {}}
    cases = [
        ("as written in its own offset, not converted to UTC", {"d": "2026-09-01T23:30:00-04:00"}, iso, "2026-09-01"),
        ("date only", {"d": "2026-09-01"}, iso, "2026-09-01"),
        ("fractional seconds, Z", {"d": "2021-04-27T20:13:45.158Z"}, iso, "2021-04-27"),
        ("epoch millis, last ms of a UTC day", {"d": 86399999}, ms, "1970-01-01"),
        ("epoch millis, next UTC day", {"d": 86400000}, ms, "1970-01-02"),
        ("not a date", {"d": "yesterday"}, iso, None),
        ("impossible date", {"d": "2026-13-40"}, iso, None),
        ("a number under iso8601", {"d": 1782214185805}, iso, None),
        ("a boolean under epoch_millis", {"d": True}, ms, None),
    ]
    results = []
    for label, payload, source, expected in cases:
        out = read(payload, source)
        ok = out["value"] == expected and out["evidence"] == [
            {"path": "d", "span": None, "raw": payload["d"], "value": expected}]
        results.append((label, ok, out["value"]))
    check(T, "n14", "behavior", all(ok for _, ok, _ in results),
          f"each case keeps the board's value as evidence (value null when it does not parse): {results}")
    edge = [read({}, iso), read({"d": None}, iso), read({"d": "2026-09-01"}, {"id": "s", "date": None, "fields": {}})]
    check(T, "n14", "behavior", all(e == {"value": None, "evidence": []} for e in edge),
          f"path holds nothing, null at the path, definition date null: undated with no evidence: {edge}")
    nested = {"id": "s", "date": {"path": "meta.dates[].posted", "format": "iso8601"}, "fields": {}}
    out = read({"meta": {"dates": [{"posted": "2026-01-02"}]}}, nested)
    check(T, "n14", "behavior", out["value"] == "2026-01-02" and out["evidence"][0]["path"] == "meta.dates.0.posted",
          f"overfit: a date path stepping into a list: {short(out)}")


# ---------------------------------------------------------------- n4 merge_into_store

def _entry(source_id, posting_id, first_seen="2026-09-01", status="listed", since=None, tag="old"):
    return {"source_id": source_id, "posting_id": posting_id, "first_seen": first_seen,
            "listing": {"status": status, "since": since}, "payload": {"tag": tag}, "fields": {"tag": tag}}


def n4():
    merge, _ = load_leaf(T, "n4")
    as_of = "2026-10-08"
    stored = [
        _entry("a", "1"), _entry("a", "2"), _entry("a", "3", status="no_longer_listed", since="2026-09-20"),
        _entry("a", "4", status="no_longer_listed", since="2026-09-25"),
        _entry("b", "1"), _entry("gone", "9"),
    ]
    results = [
        {"source_id": "b", "status": "failed", "reason": "HTTP 500"},
        {"source_id": "a", "status": "ok", "postings": [
            {"posting_id": "1", "payload": {"tag": "new"}, "fields": {"tag": "new"}},
            {"posting_id": "4", "payload": {"tag": "new"}, "fields": {"tag": "new"}},
            {"posting_id": "10", "payload": {"tag": "new"}, "fields": {"tag": "new"}}]},
    ]
    out, same = unchanged(merge, stored, results, as_of)
    surface_return("n4", out, ["updated_postings", "source_report"])
    by_key = {(e["source_id"], e["posting_id"]): e for e in out["updated_postings"]}
    expected = {
        ("a", "1"): ("2026-09-01", "listed", None, "new"), ("a", "10"): (as_of, "listed", None, "new"),
        ("a", "2"): ("2026-09-01", "no_longer_listed", as_of, "old"),
        ("a", "3"): ("2026-09-01", "no_longer_listed", "2026-09-20", "old"),
        ("a", "4"): ("2026-09-01", "listed", None, "new"),
        ("b", "1"): ("2026-09-01", "listed", None, "old"), ("gone", "9"): ("2026-09-01", "listed", None, "old"),
    }
    actual = {k: (e["first_seen"], e["listing"]["status"], e["listing"]["since"], e["payload"]["tag"])
              for k, e in by_key.items()}
    check(T, "n4", "behavior", actual == expected,
          f"listed postings replaced with first_seen kept (a/1) or as_of (a/10, new); listed again cleared "
          f"(a/4); missed becomes no_longer_listed since as_of (a/2) or keeps its date (a/3); failed source "
          f"(b) and source with no result (gone) unchanged: {actual}")
    check(T, "n4", "behavior",
          [(e["source_id"], e["posting_id"]) for e in out["updated_postings"]]
          == sorted(by_key) and len(out["updated_postings"]) == 7 and same,
          f"no entry removed (6 in, 6 kept + 1 new), sorted by source_id then posting_id (posting IDs are "
          f"strings, so '10' sorts before '2'), inputs not modified: {same}")
    check(T, "n4", "behavior",
          out["source_report"] == [
              {"source_id": "b", "status": "failed", "reason": "HTTP 500"},
              {"source_id": "a", "status": "ok", "listed": 3, "new": 1, "no_longer_listed": 1, "listed_again": 1}],
          f"report: one record per result in result order, counts listed/new/no_longer_listed/listed_again: "
          f"{out['source_report']}")
    out2 = merge(out["updated_postings"], [results[1]], as_of)
    check(T, "n4", "behavior",
          out2["updated_postings"] == out["updated_postings"]
          and out2["source_report"][0] == {"source_id": "a", "status": "ok", "listed": 3, "new": 0,
                                           "no_longer_listed": 0, "listed_again": 0},
          f"the same fetch merged again changes nothing and counts nothing new: {out2['source_report']}")
    out3 = merge([], [], as_of)
    check(T, "n4", "behavior", out3 == {"updated_postings": [], "source_report": []},
          f"boundary: empty store and no results: {out3}")


def run():
    for leaf in (n5, n7, n8, n9, n10, n11, n12, n13, n14, n4):
        leaf()
