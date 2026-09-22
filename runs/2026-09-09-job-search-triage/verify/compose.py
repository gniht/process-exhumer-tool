"""Stage 5 assembly: mechanical. Every step is naming, wrapping, binding, ordering."""
import ast, json, sys

tree = json.load(open("verified-tree.json"))
AI_RUNTIME = open("verify/ai_runtime.py").read().rstrip("\n")

def inames(c): return [e["name"] for e in c["inputs"]]
def onames(c): return [e["name"] for e in c["outputs"]]
def ind(src, n=1): return "\n".join(("    "*n + l) if l.strip() else l for l in src.split("\n"))

def qual(node, wiring): return f"{wiring}__{node['id']}"

def entry_name(node):
    want = inames(node["contract"])
    hits = [f.name for f in ast.parse(node["code"]).body
            if isinstance(f, ast.FunctionDef) and [a.arg for a in f.args.args] == want]
    if len(hits) != 1:
        sys.exit(f"REJECT: node {node['id']} -- entry point not mechanically identifiable "
                 f"({len(hits)} functions match params {want})")
    return hits[0]

def ret_stmt(contract):
    outs = onames(contract)
    if not outs: return ""
    if len(outs) == 1: return f"    return {outs[0]}"
    return "    return {" + ", ".join(f'"{o}": {o}' for o in outs) + "}"

def glue_returns(glue):
    body = ast.parse(glue).body
    return bool(body) and isinstance(body[-1], ast.Return)

FUNCS, SEAM = [], False
def emit(node, wiring="root"):
    global SEAM
    name = qual(node, wiring)
    params = ", ".join(inames(node["contract"]))
    if "children" in node:
        for ch in node["children"]: emit(ch, ch["name"])
        binds = "\n".join(f"    {ch['name']} = {qual(ch, ch['name'])}" for ch in node["children"])
        if node["assembly_pattern"] == "recursive-over-data":
            binds += f"\n    self = {name}"
        body = [binds, "    # --- glue, verbatim ---", ind(node["glue"]), "    # --- end glue ---"]
        if not glue_returns(node["glue"]):
            body.append(ret_stmt(node["contract"]))
        FUNCS.append(f"def {name}({params}):\n" + "\n".join(x for x in body if x))
    else:
        if "ai(" in node["code"]: SEAM = True
        ep = entry_name(node)
        FUNCS.append(
            f"def {name}({params}):\n"
            f"    # --- leaf {node['id']} code, verbatim ---\n"
            + ind(node["code"]) + "\n"
            f"    # --- end leaf code ---\n"
            f"    return {ep}({params})")
emit(tree)

root_name = qual(tree, "root")
parts = ['"""', tree["contract"]["behavior"], '"""', ""]
if SEAM: parts += [AI_RUNTIME, ""]
parts += ["\n\n".join(FUNCS), "", 'if __name__ == "__main__":',
          "    import sys, json",
          "    args = json.loads(sys.stdin.read())",
          f"    print(json.dumps({root_name}(**args), default=str))", ""]
artifact = "\n".join(parts)
open("job_triage.py", "w").write(artifact)
ast.parse(artifact)
print(f"composed: {len(FUNCS)} node functions, seam runtime {'inserted' if SEAM else 'omitted'}, entry {root_name}")
print(f"artifact: job_triage.py, {len(artifact.splitlines())} lines")
