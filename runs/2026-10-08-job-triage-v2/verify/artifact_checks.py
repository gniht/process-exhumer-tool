"""Run stage 4's leaf behavior checks against the assembled programs, where composition nested each leaf
inside a wrapper function, and write verify/artifact-checks.json.

    VERIFY_ARTIFACT=1 python3 verify/artifact_checks.py
"""
import json
import os

import harness
import leaves_assess
import leaves_refresh

assert harness.ARTIFACT, "set VERIFY_ARTIFACT=1"
leaves_refresh.run()
leaves_assess.run()
with open(os.path.join(harness.RUN, "verify", "artifact-checks.json"), "w") as f:
    json.dump(harness.REPORT, f, indent=1, ensure_ascii=False)
    f.write("\n")
fails = [r for r in harness.REPORT if r["outcome"] != "pass"]
print(f"{len(harness.REPORT)} leaf checks against the assembled programs, {len(fails)} not passing")
for r in fails:
    print(" ", r["tree"], r["node"], r["detail"][:200])
