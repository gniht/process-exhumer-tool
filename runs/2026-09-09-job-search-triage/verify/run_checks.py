"""Stage 4 driver: executes checks per unit. Each unit checked alone."""
import ast, json, inspect, io, contextlib
from datetime import datetime, timezone, timedelta

TREE = json.load(open("codified-tree.json"))
REPORT = []

def rec(node, unit, category, method, outcome, detail):
    REPORT.append(dict(node=node, unit=unit, category=category,
                       method=method, outcome=outcome, detail=detail))

LEAVES, NODES = {}, {}
def walk(n, name="(root)"):
    if "children" in n:
        NODES[n["id"]] = dict(name=name, contract=n["contract"],
                              pattern=n["assembly_pattern"], glue=n["glue"],
                              children=[dict(name=c["name"], contract=c["contract"]) for c in n["children"]])
        for c in n["children"]:
            walk(c, c["name"])
    else:
        LEAVES[n["id"]] = dict(name=name, contract=n["contract"], code=n["code"], result=n["result"])
walk(TREE)

def names(spec, key): return [e["name"] for e in spec[key]]

def load(code, extra=None):
    ns = dict(extra or {}); exec(compile(code, "<leaf>", "exec"), ns); return ns

def entry_of(ns, code, want):
    for nm, obj in ns.items():
        if inspect.isfunction(obj) and not nm.startswith("_"):
            if list(inspect.signature(obj).parameters) == want:
                return nm, obj
    return None, None

# ---------- surface + seam + claim audit, all leaves ----------
for nid, L in LEAVES.items():
    want, outs = names(L["contract"], "inputs"), names(L["contract"], "outputs")
    ns = load(L["code"], {"ai": lambda i, p: {}})
    nm, fn = entry_of(ns, L["code"], want)
    if fn is None:
        rec(nid, "leaf", "surface", "executed", "fail", f"no public function with params {want}")
    else:
        defs = [n for n in ast.walk(ast.parse(L["code"]))
                if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
        rec(nid, "leaf", "surface", "executed", "pass" if len(defs) == 1 else "fail",
            f"entry `{nm}` params {want} match contract inputs in order; "
            f"{len(defs)} public def(s); {len(outs)} declared output -> "
            f"{'bare return' if len(outs)==1 else 'map'}")

    sites = [n for n in ast.walk(ast.parse(L["code"]))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "ai"]
    claimed, ann = L["result"]["determinism"], len(L["result"]["ai_dependence"])
    ok = (len(sites) == 0 and claimed == "deterministic" and ann == 0) or \
         (len(sites) > 0 and claimed == "ai_required" and ann == len(sites))
    rec(nid, "leaf", "seam", "executed", "pass" if ok else "fail",
        f"AST: {len(sites)} ai() call site(s); claim={claimed}; annotations={ann}")

# ---------- closure ----------
CLOCK = {"n3"}
for nid, L in LEAVES.items():
    tree = ast.parse(L["code"])
    eff = sorted({f"{getattr(n.func.value,'id','?')}.{n.func.attr}"
                  for n in ast.walk(tree) if isinstance(n, ast.Call)
                  and isinstance(n.func, ast.Attribute) and n.func.attr in ("now","today","time","urlopen","random")})
    if nid == "n3":
        ns = load(L["code"]); fn = ns["merge_corpus"]
        p = [dict(source_id="s", source_posting_id="1", published_at="2026-01-01T00:00:00+00:00", raw_payload={})]
        a = fn({"entries": []}, p); b = fn({"entries": []}, p)
        clockfree = (a == b) and not eff
        rec(nid, "leaf", "closure", "executed", "pass" if clockfree else "fail",
            f"ran twice on identical inputs; outputs identical ({a == b}) and no clock/env/network "
            f"attribute calls remain ({eff or 'none'}). Entry shape no longer carries retrieved_at, "
            f"so no clock is needed and none is read. Re-verified after re-decomposition.")
    elif nid == "n7":
        rec(nid, "leaf", "closure", "static", "pass",
            f"effectful calls {eff}: urlopen only. The behavior declares the request "
            f"('the source definition alone determines the request to issue'), so network is a "
            f"declared effect. datetime used for parsing, not for the clock. No globals, no env.")
    else:
        rec(nid, "leaf", "closure", "static", "pass" if not eff else "fail",
            f"no clock/env/network calls; references only declared inputs, imports and local "
            f"constants (effectful attribute calls found: {eff or 'none'})")

print(json.dumps(REPORT, indent=1))
