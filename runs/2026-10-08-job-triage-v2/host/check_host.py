"""Offline checks for the host: a fixture server stands in for the three boards (run 2's saved responses),
and every check goes through HTTP the way the page does.

    python3 host/check_host.py              # from the run directory; no network needed
"""
import functools
import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import server  # noqa: E402

FIXTURES = os.path.join(server.RUN, "..", "2026-09-09-job-search-triage", "fixtures")
RESULTS = []
server.Handler.log_message = lambda self, *args: None


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"{'pass' if ok else 'FAIL'}  {name}{'' if ok else f'  ({detail})'}")


class QuietFiles(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class Client:
    def __init__(self, base):
        self.base, self.cookie = base, None

    def call(self, path, body=None, headers=None, raw=False):
        headers = dict(headers or {})
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers.setdefault("Content-Type", "application/json")
            headers.setdefault("X-Requested-With", "job-triage")
        if self.cookie:
            headers["Cookie"] = f"session={self.cookie}"
        request = urllib.request.Request(self.base + path, data=data, headers=headers,
                                         method="POST" if body is not None else "GET")
        try:
            response = urllib.request.urlopen(request)
            status, payload, response_headers = response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            status, payload, response_headers = error.code, error.read(), error.headers
        cookie = response_headers.get("Set-Cookie") or ""
        if cookie.startswith("session="):
            self.cookie = cookie.split(";")[0].split("=", 1)[1] or None
        if raw:
            return status, payload, response_headers
        return status, json.loads(payload) if payload else None


def keys(records):
    return [(r["source_id"], r["posting_id"]) for r in records]


def main():
    temp = tempfile.mkdtemp(prefix="host-check-")
    files = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(QuietFiles, directory=FIXTURES))
    threading.Thread(target=files.serve_forever, daemon=True).start()
    boards = f"http://127.0.0.1:{files.server_port}"

    sources = json.load(open(os.path.join(server.LIVE, "sources.json")))
    for source, name in zip(sources, ("greenhouse-gitlab.json", "lever-spotify.json", "ashby-linear.json")):
        source["endpoint"] = f"{boards}/{name}"
    sources.append({**sources[0], "id": "greenhouse:missing", "company": "Missing", "endpoint": f"{boards}/missing.json"})
    sources_path = os.path.join(temp, "sources.json")
    json.dump(sources, open(sources_path, "w"))

    host = server.make_server(0, data_dir=os.path.join(temp, "data"), sources_path=sources_path)
    threading.Thread(target=host.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{host.server_port}"
    data = host.RequestHandlerClass.data
    a, b, stranger = Client(base), Client(base), Client(base)

    # the page and the gate
    status, body, headers = a.call("/", raw=True)
    check("the page is served with a content security policy",
          status == 200 and b"/app.js" in body and "default-src 'self'" in headers.get("Content-Security-Policy", ""))
    check("state needs a session", stranger.call("/api/state")[0] == 401)
    status, session = stranger.call("/api/session")
    check("the demo users are listed", [u["username"] for u in session["demo_users"]] == ["demo-a", "demo-b"])
    check("a wrong password is refused", stranger.call("/api/login", {"username": "demo-a", "password": "nope"})[0] == 401)
    check("an unknown user is refused", stranger.call("/api/login", {"username": "nobody", "password": "demo"})[0] == 401)
    check("a post without the page's header is refused",
          stranger.call("/api/login", {"username": "demo-a", "password": "demo"}, {"X-Requested-With": "x"})[0] == 403)
    check("a post from another origin is refused",
          stranger.call("/api/login", {"username": "demo-a", "password": "demo"}, {"Origin": "http://evil.test"})[0] == 403)
    check("an unexpected Host header is refused", stranger.call("/api/session", headers={"Host": "evil.test"})[0] == 400)
    check("demo-a signs in", a.call("/api/login", {"username": "demo-a", "password": "demo"})[0] == 200)
    check("demo-b signs in", b.call("/api/login", {"username": "demo-b", "password": "demo"})[0] == 200)

    status, state = a.call("/api/state")
    check("an empty store shows nothing", status == 200 and state["stored"] == 0 and state["shown"] == [] == state["hidden"])
    check("demo-a has its 8 seeded rules", len(state["user"]["rules"]) == 8)

    # refresh, through the composed program, against the fixture boards
    status, state = a.call("/api/refresh", {})
    report = {r["source_id"]: r for r in state["refresh"]["source_report"]}
    check("refresh stores every fixture posting", status == 200 and state["stored"] == 45, state.get("stored"))
    check("each working source reports 15 new",
          all(report[s["id"]].get("new") == 15 for s in sources[:3]), report)
    check("the missing board fails alone", report["greenhouse:missing"]["status"] == "failed"
          and "404" in report["greenhouse:missing"]["reason"], report["greenhouse:missing"])
    first_seen = {(p["source_id"], p["posting_id"]): p["first_seen"] for p in data.store}
    status, again = a.call("/api/refresh", {})
    check("a second refresh adds nothing and keeps first-seen dates",
          again["stored"] == 45 and all(r.get("new", 0) == 0 for r in again["refresh"]["source_report"])
          and first_seen == {(p["source_id"], p["posting_id"]): p["first_seen"] for p in data.store})
    check("the store is written to disk", len(json.load(open(data.store_path))) == 45)

    # the page shows exactly what assess returns
    user = data.user("demo-a")
    direct = server.assess_program(stored_postings=data.store, watched_sources=user["watched_sources"],
                                   rules=user["rules"], marks=user["marks"], as_of=server.today())
    status, state = a.call("/api/state")
    check("shown and hidden match assess, in order",
          keys(state["shown"]) == keys(direct["shown"]) and keys(state["hidden"]) == keys(direct["hidden"]))
    check("diagnostics match assess", state["rule_diagnostics"] == direct["rule_diagnostics"])
    check("full texts stay on the server",
          all("full_text" not in r["fields"] for r in state["shown"] + state["hidden"]))
    check("every vocabulary option is offered", [o["value"] for o in state["options"]["seniority"]] == server.CLOSED["seniority"]
          and {"GitLab", "Spotify", "Linear"} <= {o["value"] for o in state["options"]["company"]})

    # rules: validated, ids assigned, keyword evidence shown in context
    rules = state["user"]["rules"]
    for bad, why in (({"field": "colour", "test": "one_of", "values": ["x"], "action": "require"}, "unknown field"),
                     ({"field": "seniority", "test": "one_of", "values": ["mid"], "action": "require"}, "off-vocabulary"),
                     ({"field": "salary", "test": "at_least", "amount": 1, "action": "prefer"}, "no currency"),
                     ({"field": "title", "test": "within_days", "days": 3, "action": "prefer"}, "wrong test"),
                     ({"field": "title", "test": "contains", "keywords": ["*"], "action": "prefer"}, "empty keyword")):
        status, body = a.call("/api/rules", {"rules": rules + [bad]})
        check(f"a bad rule is refused: {why}", status == 400, body)
    status, state = a.call("/api/rules", {"rules": rules + [
        {"field": "full_text", "test": "contains", "keywords": ["python"], "action": "prefer", "unknowns": "hide"}]})
    new = state["user"]["rules"][-1]
    check("a new rule gets a fresh id, and prefer drops can't-tell handling",
          status == 200 and new["id"] not in {r["id"] for r in rules} and "unknowns" not in new, new)
    matches = [e for r in state["shown"] + state["hidden"] for v in r["verdicts"]
               if v["rule_id"] == new["id"] and v["result"] == "met" for e in v["evidence"]]
    check("a full-text match comes with its context",
          bool(matches) and all(e["context"] and e["context"]["match"].lower() == "python" for e in matches), matches[:1])

    # marks: per user, and saved overrides the rules
    shared = set(data.user("demo-b")["watched_sources"])
    target = next(r for r in state["shown"] if r["source_id"] in shared)  # a posting both users see
    key = {"source_id": target["source_id"], "posting_id": target["posting_id"]}
    status, state = a.call("/api/marks", {**key, "mark": "hidden", "on": True})
    hidden = {(r["source_id"], r["posting_id"]): r for r in state["hidden"]}
    check("hiding a posting moves it to hidden, hidden by you",
          {"kind": "hidden_by_you"} in hidden[tuple(key.values())]["reasons"])
    status, other = b.call("/api/state")
    seen_by_b = [r for r in other["shown"] + other["hidden"] if (r["source_id"], r["posting_id"]) == tuple(key.values())]
    check("demo-b doesn't see demo-a's mark", len(seen_by_b) == 1 and "hidden" not in seen_by_b[0]["marks"]
          and {"kind": "hidden_by_you"} not in seen_by_b[0].get("reasons", []))
    check("demo-b sees only its watched sources",
          {r["source_id"] for r in other["shown"] + other["hidden"]} <= set(other["user"]["watched_sources"]))
    status, state = a.call("/api/marks", {**key, "mark": "hidden", "on": False})
    check("unhiding brings it back", tuple(key.values()) in keys(state["shown"]))
    failed = next(r for r in state["hidden"] if all(x["kind"] == "failed" for x in r["reasons"]))
    status, state = a.call("/api/marks", {"source_id": failed["source_id"], "posting_id": failed["posting_id"],
                                          "mark": "saved", "on": True})
    check("saving a posting a rule hides shows it", (failed["source_id"], failed["posting_id"]) in keys(state["shown"]))
    check("a mark on a posting that isn't stored is refused",
          a.call("/api/marks", {"source_id": "x", "posting_id": "y", "mark": "saved", "on": True})[0] == 400)
    check("an unknown mark is refused", a.call("/api/marks", {**key, "mark": "starred", "on": True})[0] == 400)

    # restore defaults and undo
    before = {r["id"]: r.get("unknowns") for r in state["user"]["rules"]}
    check("demo-a starts with a rule that hides what it can't check", "hide" in before.values())
    marks_before, watched_before = data.user("demo-a")["marks"], data.user("demo-a")["watched_sources"]
    status, state = a.call("/api/restore-defaults", {})
    check("restore defaults shows can't tell on every rule",
          all(r.get("unknowns", "show") == "show" for r in state["user"]["rules"]) and state["user"]["can_undo_restore"])
    check("restore defaults keeps rules, sources and marks", [r["id"] for r in state["user"]["rules"]] == list(before)
          and data.user("demo-a")["marks"] == marks_before and data.user("demo-a")["watched_sources"] == watched_before)
    status, state = a.call("/api/restore-defaults", {})
    check("restoring again keeps the undo", state["user"]["can_undo_restore"])
    status, state = a.call("/api/undo-restore", {})
    check("undo brings the settings back", {r["id"]: r.get("unknowns") for r in state["user"]["rules"]} == before
          and not state["user"]["can_undo_restore"])

    # watched sources
    check("watching an unknown source is refused", a.call("/api/watched", {"watched_sources": ["nope"]})[0] == 400)
    status, state = a.call("/api/watched", {"watched_sources": ["lever:spotify"]})
    check("watching one source assesses only it",
          {r["source_id"] for r in state["shown"] + state["hidden"]} == {"lever:spotify"})
    status, other = b.call("/api/state")
    check("demo-b's rules and sources are untouched by demo-a",
          other["user"]["rules"] == data.user("demo-b")["rules"] and len(other["user"]["rules"]) == 5
          and other["user"]["watched_sources"] == ["lever:spotify", "ashby:linear"], len(other["user"]["rules"]))

    # signing out
    old = Client(base)
    old.cookie = a.cookie
    a.call("/api/logout", {})
    check("signing out ends the session", a.call("/api/state")[0] == 401)
    check("the old session token no longer works", old.call("/api/state")[0] == 401)

    host.shutdown()
    files.shutdown()
    passed = sum(RESULTS)
    print(f"\n{passed}/{len(RESULTS)} checks pass")
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
