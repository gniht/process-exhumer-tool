"""Rebuild every live-run input and rerun stage 5's live runs: three refreshes, then assess for each
demo user in users.json. Inputs and outputs land in live/ (the large ones are git-ignored).

    python3 live/run_live.py            # from the run directory; needs network access to the boards

As of is today's date unless given: python3 live/run_live.py 2026-10-08
"""
import datetime
import importlib.util
import json
import os
import subprocess
import sys

LIVE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.dirname(LIVE)
AS_OF = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
FIXTURES = os.path.join(RUN, "..", "2026-09-09-job-search-triage", "fixtures")


def path(name):
    return os.path.join(LIVE, name)


def run(program, name):
    with open(path(f"{name}.input.json")) as stdin, open(path(f"{name}.output.json"), "w") as stdout:
        subprocess.run([sys.executable, os.path.join(RUN, program)], stdin=stdin, stdout=stdout, check=True)
    return json.load(open(path(f"{name}.output.json")))


sources = json.load(open(path("sources.json")))
floors = json.load(open(path("pay_floors.json")))
# a fourth source, a Greenhouse board that does not exist, to watch one source fail alone
broken = {**sources[0], "id": "greenhouse:no-such-board", "company": "Nobody",
          "endpoint": "https://boards-api.greenhouse.io/v1/boards/no-such-board-v2-check/jobs?content=true"}
base = {"sources": sources + [broken], "pay_floors": floors, "as_of": AS_OF}

# refresh 1: empty store
json.dump({**base, "stored_postings": []}, open(path("refresh-1.input.json"), "w"))
first = run("job_triage_refresh.py", "refresh-1")

# refresh 2: run 1's store, refreshed again
json.dump({**base, "stored_postings": first["updated_postings"]}, open(path("refresh-2.input.json"), "w"))
run("job_triage_refresh.py", "refresh-2")

# refresh 3: a store seeded from run 2's 45 saved postings (saved 2026-09-21), extracted by this program
spec = importlib.util.spec_from_file_location("refresh", os.path.join(RUN, "job_triage_refresh.py"))
program = importlib.util.module_from_spec(spec)
spec.loader.exec_module(program)
by_id = {s["id"]: s for s in sources}
seed = []
for source_id, name in (("greenhouse:gitlab", "greenhouse-gitlab.json"), ("lever:spotify", "lever-spotify.json"),
                        ("ashby:linear", "ashby-linear.json")):
    data = json.load(open(os.path.join(FIXTURES, name)))
    for payload in (data if isinstance(data, list) else data["jobs"]):
        seed.append({"source_id": source_id, "posting_id": str(payload["id"]), "first_seen": "2026-09-21",
                     "listing": {"status": "listed", "since": None}, "payload": payload,
                     "fields": program.extract_posting__n6(payload, by_id[source_id], floors)})
seed.sort(key=lambda e: (e["source_id"], e["posting_id"]))
json.dump({**base, "stored_postings": seed}, open(path("refresh-3.input.json"), "w"))
store = run("job_triage_refresh.py", "refresh-3")["updated_postings"]

# assess: each demo user over refresh 3's store
for user, settings in json.load(open(path("users.json"))).items():
    json.dump({"stored_postings": store, "watched_sources": settings["watched_sources"], "rules": settings["rules"],
               "marks": settings["marks"], "as_of": AS_OF}, open(path(f"assess-{user}.input.json"), "w"))
    out = run("job_triage_assess.py", f"assess-{user}")
    print(f"{user}: {len(out['shown'])} shown, {len(out['hidden'])} hidden")
print("refresh reports:", [r.get("listed", r.get("reason")) for r in first["source_report"]])
