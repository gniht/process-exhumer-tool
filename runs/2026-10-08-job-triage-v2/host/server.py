"""The job-triage host: a small local server and page around the two programs. Built by hand, outside
the pipeline (stage 1, items 8 and 14).

    python3 host/server.py                  # from the run directory; serves http://127.0.0.1:8765
    python3 host/server.py --port 9000
    python3 host/server.py adduser NAME     # asks for a password

Accounts, sessions, per-user access checks and restore defaults live here. Refresh and assess are
the composed programs, imported and called unchanged; the host never filters, ranks or reads a
posting itself. Everything stays on this machine, in host/data/ (git-ignored): the shared store,
one file per user, and the last refresh's report. On first start the demo users in live/users.json
are created with the password "demo". Sources and pay floors are read from live/ on every refresh.
"""
import argparse
import datetime
import getpass
import hashlib
import hmac
import http.cookies
import importlib.util
import json
import os
import re
import secrets
import sys
import threading
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST_DIR = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(HOST_DIR)
LIVE = os.path.join(RUN, "live")
STATIC = os.path.join(HOST_DIR, "static")
DEMO_PASSWORD = "demo"
ITERATIONS = 200_000
MAX_BODY = 1 << 20


def load_program(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(RUN, f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.root__n1


refresh_program = load_program("job_triage_refresh")
assess_program = load_program("job_triage_assess")


# --- rules: what assess accepts, from its root contract ---

TESTS = {
    "title": {"contains"}, "full_text": {"contains"},
    "company": {"one_of"}, "department_team": {"one_of"}, "countries": {"one_of"}, "regions": {"one_of"},
    "work_arrangement": {"one_of"}, "employment_type": {"one_of"}, "seniority": {"one_of"},
    "listing_status": {"one_of"},
    "salary": {"at_least", "at_most"}, "years_of_experience": {"at_least", "at_most"},
    "posted_date": {"within_days"}, "first_seen": {"within_days"},
}
ONE_OF_FIELDS = [field for field, tests in TESTS.items() if "one_of" in tests]
# The declared value spaces. Company, department/team and countries are open: their options come from the store.
CLOSED = {
    "regions": ["north_america", "latin_america", "americas", "europe", "middle_east", "africa", "emea",
                "asia", "oceania", "apac"],
    "work_arrangement": ["remote", "hybrid", "onsite"],
    "employment_type": ["full-time", "part-time", "contract", "temporary", "internship"],
    "seniority": ["intern", "junior", "senior", "staff", "principal", "lead", "manager", "director", "executive"],
    "listing_status": ["listed", "no_longer_listed"],
}
PAY_PERIODS = ["hour", "day", "week", "month", "year"]
ACTIONS = {"require", "exclude", "prefer"}
MARKS = ("viewed", "saved", "applied", "hidden")
USERNAME = re.compile(r"[a-z0-9_-]{1,32}")


def clean_rule(rule, number):
    """A rule as assess expects it, or ValueError naming what is wrong. `number` is for new rule ids."""
    if not isinstance(rule, dict):
        raise ValueError("a rule must be an object")
    field, test, action = rule.get("field"), rule.get("test"), rule.get("action")
    if field not in TESTS:
        raise ValueError(f"unknown field {field!r}")
    if test not in TESTS[field]:
        raise ValueError(f"{field} can't be tested with {test!r}")
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    rule_id = rule.get("id") or f"r{number}"
    if not isinstance(rule_id, str) or len(rule_id) > 64:
        raise ValueError("a rule id must be a short string")
    clean = {"id": rule_id, "field": field, "test": test}

    if test == "contains":
        keywords = rule.get("keywords")
        if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
            raise ValueError("keywords must be a list of words or phrases")
        clean["keywords"] = [k.strip() for k in keywords if k.strip().rstrip("*").strip()]
        if not clean["keywords"]:
            raise ValueError("give at least one keyword")
    elif test == "one_of":
        values = rule.get("values")
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError("values must be a list")
        values = [v.strip() for v in values if v.strip()]
        if field == "countries":
            values = [v.upper() for v in values]
            bad = [v for v in values if not re.fullmatch(r"[A-Z]{2}", v)]
            if bad:
                raise ValueError(f"countries are two-letter codes: {', '.join(bad)}")
        if field in CLOSED:
            bad = [v for v in values if v not in CLOSED[field]]
            if bad:
                raise ValueError(f"not in the {field} vocabulary: {', '.join(bad)}")
        if not values:
            raise ValueError("choose at least one value")
        clean["values"] = list(dict.fromkeys(values))
    elif test in ("at_least", "at_most"):
        amount = rule.get("amount")
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount < 0:
            raise ValueError("amount must be a number, zero or more")
        clean["amount"] = amount
        if field == "salary":
            currency, period = rule.get("currency"), rule.get("pay_period")
            if not isinstance(currency, str) or not re.fullmatch(r"[A-Za-z]{3}", currency):
                raise ValueError("currency must be a three-letter code")
            if period not in PAY_PERIODS:
                raise ValueError(f"pay period must be one of {', '.join(PAY_PERIODS)}")
            clean["currency"], clean["pay_period"] = currency.upper(), period
    elif test == "within_days":
        days = rule.get("days")
        if isinstance(days, bool) or not isinstance(days, int) or days < 0:
            raise ValueError("days must be a whole number, zero or more")
        clean["days"] = days

    clean["action"] = action
    if action != "prefer":
        unknowns = rule.get("unknowns", "show")
        if unknowns not in ("show", "hide"):
            raise ValueError("can't tell must be show or hide")
        clean["unknowns"] = unknowns
    return clean


def clean_rules(rules):
    if not isinstance(rules, list):
        raise ValueError("rules must be a list")
    taken = {r.get("id") for r in rules if isinstance(r, dict) and r.get("id")}
    number, cleaned = 1, []
    for rule in rules:
        if isinstance(rule, dict) and not rule.get("id"):
            while f"r{number}" in taken:
                number += 1
            taken.add(f"r{number}")
        cleaned.append(clean_rule(rule, number))
    ids = [r["id"] for r in cleaned]
    if len(ids) != len(set(ids)):
        raise ValueError("rule ids must be unique")
    return cleaned


# --- passwords and files ---

def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return {"salt": salt.hex(), "hash": digest.hex(), "iterations": ITERATIONS}


def check_password(record, password):
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(record["salt"]), record["iterations"])
    return hmac.compare_digest(digest.hex(), record["hash"])


_DUMMY = hash_password(secrets.token_hex(8))


def read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path, value, indent=1):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(value, f, indent=indent, ensure_ascii=False, default=str)
        f.write("\n")
    os.replace(tmp, path)


def today():
    return datetime.date.today().isoformat()


# --- what the page sees: assess's records, without the full texts ---

def short(value, limit=200):
    return value[:limit] + "…" if isinstance(value, str) and len(value) > limit else value


def context(texts, path, span, raw, width=90):
    """The text around a keyword match, from the full-text evidence entry the match points into."""
    start, end = span
    for text_path, text in texts:
        if text_path == path and text[start:end].casefold() == str(raw).casefold():
            return {"before": ("…" if start > width else "") + text[max(0, start - width):start],
                    "match": text[start:end],
                    "after": text[end:end + width] + ("…" if end + width < len(text) else "")}
    return None


def slim_verdict(verdict, texts):
    evidence = []
    for item in verdict.get("evidence") or []:
        entry = {"path": item.get("path"), "raw": short(item.get("raw")), "value": short(item.get("value"))}
        if verdict["field"] == "full_text" and item.get("span"):
            entry["context"] = context(texts, item.get("path"), item["span"], item.get("raw"))
        evidence.append(entry)
    return {"rule_id": verdict["rule_id"], "result": verdict["result"], "field": verdict["field"],
            "value": None if verdict["field"] == "full_text" else verdict["value"], "evidence": evidence}


def slim_record(record):
    fields = record.get("fields") or {}
    texts = [(e.get("path"), e["value"]) for e in (fields.get("full_text") or {}).get("evidence") or []
             if isinstance(e.get("value"), str)]
    slim = {key: record[key] for key in ("source_id", "posting_id", "first_seen", "listing", "prefer_met",
                                         "marks", "flags")}
    slim["fields"] = {name: (field or {}).get("value") for name, field in fields.items() if name != "full_text"}
    slim["verdicts"] = [slim_verdict(v, texts) for v in record["verdicts"]]
    if "reasons" in record:
        slim["reasons"] = record["reasons"]
    return slim


def options(store, sources):
    """Every value a one-of rule can name, with how many stored postings carry it, and the salary forms seen."""
    counts = {field: Counter() for field in ONE_OF_FIELDS}
    salaries = Counter()
    for entry in store:
        fields = entry.get("fields") or {}
        for field in ONE_OF_FIELDS:
            value = entry["listing"]["status"] if field == "listing_status" else (fields.get(field) or {}).get("value")
            for v in value if isinstance(value, list) else [value]:
                if v is not None:
                    counts[field][v] += 1
        salary = (fields.get("salary") or {}).get("value")
        if salary and salary.get("currency"):
            salaries[(salary["currency"], salary.get("pay_period"))] += 1
    result = {}
    for field in ONE_OF_FIELDS:
        values = list(CLOSED.get(field, []))
        if field == "company":
            values += sorted({s["company"] for s in sources})
        values += sorted(v for v in counts[field] if v not in values)
        result[field] = [{"value": v, "count": counts[field][v]} for v in values]
    result["salary"] = [{"currency": c, "pay_period": p, "count": n} for (c, p), n in salaries.most_common()]
    result["pay_periods"] = PAY_PERIODS
    return result


# --- the data: the shared store, and one file per user ---

class Data:
    def __init__(self, root, sources_path, floors_path, demo_users_path):
        self.root, self.sources_path, self.floors_path = root, sources_path, floors_path
        self.users_dir = os.path.join(root, "users")
        self.store_path = os.path.join(root, "store.json")
        self.report_path = os.path.join(root, "refresh-report.json")
        os.makedirs(self.users_dir, exist_ok=True)
        self.lock = threading.RLock()
        self.refreshing = threading.Lock()
        self.sessions = {}
        self.store = read_json(self.store_path, [])
        self.report = read_json(self.report_path, None)
        if demo_users_path and not self.usernames():
            self.seed_demo_users(demo_users_path)

    def sources(self):
        return read_json(self.sources_path, [])

    # users

    def user_path(self, name):
        if not USERNAME.fullmatch(name or ""):
            raise ValueError("a username is 1 to 32 lowercase letters, digits, - or _")
        return os.path.join(self.users_dir, f"{name}.json")

    def usernames(self):
        return sorted(f[:-5] for f in os.listdir(self.users_dir) if f.endswith(".json"))

    def user(self, name):
        with self.lock:
            return read_json(self.user_path(name), None)

    def save_user(self, user):
        with self.lock:
            write_json(self.user_path(user["username"]), user)

    def add_user(self, name, password, about="", demo=False, watched=None, rules=(), marks=()):
        with self.lock:
            if os.path.exists(self.user_path(name)):
                raise ValueError(f"user {name!r} already exists")
            self.save_user({"username": name, "about": about, "demo": demo, "password": hash_password(password),
                            "watched_sources": list(watched if watched is not None else
                                                    [s["id"] for s in self.sources()]),
                            "rules": clean_rules(list(rules)), "marks": list(marks), "previous_settings": None})

    def seed_demo_users(self, path):
        for name, settings in read_json(path, {}).items():
            self.add_user(name, DEMO_PASSWORD, settings.get("about", ""), True, settings["watched_sources"],
                          settings["rules"], settings["marks"])

    def update_user(self, name, change):
        """Apply change(user) to a user's file under the lock, and return the updated user."""
        with self.lock:
            user = self.user(name)
            change(user)
            self.save_user(user)
            return user

    # sessions

    def login(self, name, password):
        try:
            user = self.user(name)
        except ValueError:
            user = None
        if not check_password(user["password"] if user else _DUMMY, password or "") or not user:
            return None
        token = secrets.token_urlsafe(32)
        with self.lock:
            self.sessions[token] = name
        return token

    def session_user(self, token):
        with self.lock:
            return self.sessions.get(token)

    def logout(self, token):
        with self.lock:
            self.sessions.pop(token, None)

    # the two programs

    def refresh(self):
        if not self.refreshing.acquire(blocking=False):
            raise ValueError("a refresh is already running")
        try:
            as_of = today()
            result = refresh_program(sources=self.sources(), stored_postings=self.store,
                                     pay_floors=read_json(self.floors_path, {}), as_of=as_of)
            write_json(self.store_path, result["updated_postings"], indent=None)
            report = {"as_of": as_of, "source_report": result["source_report"]}
            write_json(self.report_path, report)
            with self.lock:
                self.store, self.report = result["updated_postings"], report
            return report
        finally:
            self.refreshing.release()

    def state(self, name):
        user, store = self.user(name), self.store
        sources = self.sources()
        out = assess_program(stored_postings=store, watched_sources=user["watched_sources"], rules=user["rules"],
                             marks=user["marks"], as_of=today())
        per_source = Counter(entry["source_id"] for entry in store)
        return {
            "user": {"username": user["username"], "about": user.get("about", ""), "demo": user.get("demo", False),
                     "watched_sources": user["watched_sources"], "rules": user["rules"],
                     "can_undo_restore": bool(user.get("previous_settings"))},
            "sources": [{"id": s["id"], "company": s["company"], "stored": per_source.get(s["id"], 0)}
                        for s in sources],
            "options": options(store, sources),
            "refresh": self.report,
            "stored": len(store),
            "as_of": today(),
            "shown": [slim_record(r) for r in out["shown"]],
            "hidden": [slim_record(r) for r in out["hidden"]],
            "rule_diagnostics": out["rule_diagnostics"],
        }

    # changes a user makes to their own data

    def set_rules(self, name, rules):
        cleaned = clean_rules(rules)
        self.update_user(name, lambda user: user.update(rules=cleaned))

    def set_watched(self, name, watched):
        known = {s["id"] for s in self.sources()}
        if not isinstance(watched, list) or not all(isinstance(w, str) and w in known for w in watched):
            raise ValueError("watched sources must be source ids from sources.json")
        self.update_user(name, lambda user: user.update(watched_sources=list(dict.fromkeys(watched))))

    def set_mark(self, name, source_id, posting_id, mark, on):
        if mark not in MARKS:
            raise ValueError(f"unknown mark {mark!r}")
        if not any(e["source_id"] == source_id and e["posting_id"] == posting_id for e in self.store):
            raise ValueError("no such posting")

        def change(user):
            entries = {(m["source_id"], m["posting_id"]): set(m["marks"]) for m in user["marks"]}
            marks = entries.setdefault((source_id, posting_id), set())
            (marks.add if on else marks.discard)(mark)
            user["marks"] = [{"source_id": s, "posting_id": p, "marks": [m for m in MARKS if m in ms]}
                             for (s, p), ms in sorted(entries.items()) if ms]
        self.update_user(name, change)

    def restore_defaults(self, name):
        """Every setting back to its declared default: each require or exclude rule's can't-tell handling to
        shown. Rules, watched sources and marks are untouched; the settings replaced are kept for undo."""
        def change(user):
            current = {r["id"]: r["unknowns"] for r in user["rules"] if "unknowns" in r}
            if all(value == "show" for value in current.values()):
                return  # already the defaults: keep any earlier undo
            user["previous_settings"] = {"unknowns": current, "date": today()}
            for rule in user["rules"]:
                if "unknowns" in rule:
                    rule["unknowns"] = "show"
        self.update_user(name, change)

    def undo_restore(self, name):
        def change(user):
            previous = (user.get("previous_settings") or {}).get("unknowns", {})
            for rule in user["rules"]:
                if "unknowns" in rule and rule["id"] in previous:
                    rule["unknowns"] = previous[rule["id"]]
            user["previous_settings"] = None
        self.update_user(name, change)


# --- HTTP ---

STATIC_FILES = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                "/style.css": ("style.css", "text/css")}
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class Handler(BaseHTTPRequestHandler):
    server_version = "job-triage-host"
    data = None  # set by make_server
    hosts = ()

    def log_message(self, format, *args):
        if self.path.startswith("/api/"):
            super().log_message(format, *args)

    def send(self, status, body, content_type, headers=()):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for key, value in [*SECURITY_HEADERS.items(), *headers]:
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status, value, headers=()):
        self.send(status, json.dumps(value, ensure_ascii=False, default=str).encode(), "application/json", headers)

    def token(self):
        cookie = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return cookie["session"].value if "session" in cookie else None

    def allowed_host(self):
        # Only this machine's own names, so a page elsewhere can't reach the server through DNS rebinding.
        if self.headers.get("Host") in self.hosts:
            return True
        self.send_json(400, {"error": "unexpected Host header"})
        return False

    def do_GET(self):
        if not self.allowed_host():
            return
        path = urlparse(self.path).path
        if path in STATIC_FILES:
            name, content_type = STATIC_FILES[path]
            with open(os.path.join(STATIC, name), "rb") as f:
                return self.send(200, f.read(), content_type)
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path == "/api/session":
            demo = [{"username": u["username"], "about": u.get("about", "")}
                    for u in map(self.data.user, self.data.usernames()) if u.get("demo")]
            return self.send_json(200, {"user": self.data.session_user(self.token()), "demo_users": demo,
                                        "demo_password": DEMO_PASSWORD})
        if path == "/api/state":
            name = self.data.session_user(self.token())
            if not name:
                return self.send_json(401, {"error": "sign in first"})
            return self.send_json(200, self.data.state(name))
        self.send_json(404, {"error": "not found"})

    def do_POST(self):
        if not self.allowed_host():
            return
        # A cross-site form can't set this header or a JSON content type; the cookie is SameSite=Strict as well.
        origin = self.headers.get("Origin")
        if (self.headers.get("X-Requested-With") != "job-triage"
                or not (self.headers.get("Content-Type") or "").startswith("application/json")
                or (origin is not None and origin not in {f"http://{h}" for h in self.hosts})):
            return self.send_json(403, {"error": "refused"})
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self.send_json(413, {"error": "too large"})
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            return self.send_json(400, {"error": "not JSON"})
        if not isinstance(body, dict):
            return self.send_json(400, {"error": "expected an object"})
        path = urlparse(self.path).path

        if path == "/api/login":
            token = self.data.login(body.get("username"), body.get("password"))
            if not token:
                return self.send_json(401, {"error": "wrong username or password"})
            cookie = f"session={token}; HttpOnly; SameSite=Strict; Path=/"
            return self.send_json(200, {"user": body["username"]}, [("Set-Cookie", cookie)])
        if path == "/api/logout":
            self.data.logout(self.token())
            return self.send_json(200, {"user": None}, [("Set-Cookie", "session=; Max-Age=0; Path=/")])

        name = self.data.session_user(self.token())
        if not name:
            return self.send_json(401, {"error": "sign in first"})
        # Every change below is to the signed-in user's own data, named by the session, never by the request.
        actions = {
            "/api/rules": lambda: self.data.set_rules(name, body.get("rules")),
            "/api/watched": lambda: self.data.set_watched(name, body.get("watched_sources")),
            "/api/marks": lambda: self.data.set_mark(name, body.get("source_id"), body.get("posting_id"),
                                                     body.get("mark"), bool(body.get("on"))),
            "/api/restore-defaults": lambda: self.data.restore_defaults(name),
            "/api/undo-restore": lambda: self.data.undo_restore(name),
            "/api/refresh": self.data.refresh,
        }
        if path not in actions:
            return self.send_json(404, {"error": "not found"})
        try:
            actions[path]()
        except ValueError as error:
            return self.send_json(409 if path == "/api/refresh" else 400, {"error": str(error)})
        self.send_json(200, self.data.state(name))


def make_data(data_dir=None, sources_path=None, floors_path=None, demo_users_path=None):
    return Data(data_dir or os.path.join(HOST_DIR, "data"), sources_path or os.path.join(LIVE, "sources.json"),
                floors_path or os.path.join(LIVE, "pay_floors.json"),
                demo_users_path if demo_users_path is not None else os.path.join(LIVE, "users.json"))


def make_server(port=8765, **paths):
    handler = type("BoundHandler", (Handler,), {"data": make_data(**paths)})
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    handler.hosts = {f"127.0.0.1:{server.server_port}", f"localhost:{server.server_port}"}
    return server


def main():
    parser = argparse.ArgumentParser(description="The job-triage host.")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("command", nargs="*", help="adduser NAME")
    args = parser.parse_args()
    if args.command:
        if len(args.command) != 2 or args.command[0] != "adduser":
            parser.error("the only command is: adduser NAME")
        data = make_data()
        password = getpass.getpass("password: ")
        if password != getpass.getpass("again: "):
            sys.exit("passwords differ")
        try:
            data.add_user(args.command[1], password)
        except ValueError as error:
            sys.exit(str(error))
        print(f"added {args.command[1]}")
        return
    server = make_server(args.port)
    print(f"job-triage host on http://127.0.0.1:{server.server_port}  (Ctrl-C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
