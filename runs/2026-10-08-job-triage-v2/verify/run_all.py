"""Stage 4 driver: run every check, write the full log, and write the verified trees, whose result
records carry each unit's verdict and the checks that did not pass."""
import copy
import json
import os
from collections import Counter

import harness
import leaves_assess
import leaves_refresh
import mechanical
import nodes

mechanical.run()
leaves_refresh.run()
leaves_assess.run()
nodes.run()

REQUIRED = {"leaf": {"surface", "closure", "seam", "behavior"},
            "node": {"glue_determinism", "wiring", "pattern", "behavior"}}

with open(os.path.join(harness.RUN, "verify", "all-checks.json"), "w") as f:
    json.dump(harness.REPORT, f, indent=1, ensure_ascii=False)
    f.write("\n")

summary = []
for tree_name, tree in harness.TREES.items():
    verified = copy.deepcopy(tree)
    for name, unit in harness.walk(verified):
        kind = "node" if "children" in unit else "leaf"
        checks = [r for r in harness.REPORT if r["tree"] == tree_name and r["node"] == unit["id"]]
        missing = REQUIRED[kind] - {r["category"] for r in checks}
        assert not missing, (tree_name, unit["id"], missing)
        failures = [{k: r[k] for k in ("category", "method", "outcome", "detail")}
                    for r in checks if r["outcome"] != "pass"]
        verdict = "fail" if any(r["outcome"] == "fail" for r in checks) else "pass"
        result = unit.get("result", {})
        unit["result"] = {**result, "verdict": verdict, "failures": failures}
        methods = Counter(r["method"] for r in checks)
        summary.append((tree_name, unit["id"], kind, name, verdict, len(checks), methods["executed"],
                        sum(r["outcome"] == "fail" for r in checks)))
    with open(os.path.join(harness.RUN, f"verified-tree-{tree_name}.json"), "w") as f:
        json.dump(verified, f, indent=2, ensure_ascii=False)
        f.write("\n")

total = len(harness.REPORT)
executed = sum(r["method"] == "executed" for r in harness.REPORT)
fails = sum(r["outcome"] == "fail" for r in harness.REPORT)
deferred = sum(r["outcome"] == "deferred" for r in harness.REPORT)
print(f"{total} checks, {executed} executed ({100 * executed // total}%), {total - executed} static; "
      f"{fails} fail, {deferred} deferred")
for row in summary:
    print("  %-8s %-4s %-5s %-28s %-5s checks=%-3d executed=%-3d fails=%d" % row)
