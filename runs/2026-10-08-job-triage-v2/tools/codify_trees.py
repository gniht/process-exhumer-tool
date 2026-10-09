"""Attach leaf code to the node trees and run codification's mechanical checks."""
import ast, json, os, sys

RUN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED_IMPORTS = {"re", "json", "html", "html.parser", "datetime"}
NETWORK_IMPORTS = {"urllib.error", "urllib.request"}
FORBIDDEN_NAMES = {"open", "eval", "exec", "__import__", "input", "decide", "ai"}

def walk(node):
    yield node
    for child in node.get("children", []):
        yield child
        yield from (n for n in walk(child) if n is not child)

def leaves_with_names(node):
    for child in node.get("children", []):
        if "children" in child:
            yield from leaves_with_names(child)
        else:
            yield child

for tree_name in ("refresh", "assess"):
    tree = json.load(open(f"{RUN}/node-tree-{tree_name}.json"))
    files = {f.split("_", 1)[0]: f for f in os.listdir(f"{RUN}/leaves/{tree_name}") if f.endswith(".py")}
    for leaf in leaves_with_names(tree):
        source = open(f"{RUN}/leaves/{tree_name}/{files[leaf['id']]}").read()
        module = ast.parse(source)
        functions = {n.name: n for n in module.body if isinstance(n, ast.FunctionDef)}
        entry = functions[leaf["name"]]
        params = [a.arg for a in entry.args.args]
        expected = [i["name"] for i in leaf["contract"]["inputs"]]
        assert params == expected, (tree_name, leaf["id"], params, expected)
        imports = set()
        for n in ast.walk(module):
            if isinstance(n, ast.Import):
                imports |= {a.name for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                imports.add(n.module)
        allowed = ALLOWED_IMPORTS | (NETWORK_IMPORTS if leaf["name"] == "fetch_source" else set())
        assert imports <= allowed, (leaf["id"], imports - allowed)
        names = {n.id for n in ast.walk(module) if isinstance(n, ast.Name)}
        assert not names & FORBIDDEN_NAMES, (leaf["id"], names & FORBIDDEN_NAMES)
        decide_calls = sum(1 for n in ast.walk(module) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == "decide")
        leaf["code"] = source
        leaf["result"] = {"determinism": "deterministic" if decide_calls == 0 else "decision_required", "decisions": []}
        print(f"{tree_name} {leaf['id']:4} {leaf['name']:28} {len(source.splitlines()):4} lines  imports={sorted(imports)}  decide()={decide_calls}")
    with open(f"{RUN}/codified-tree-{tree_name}.json", "w") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)
        f.write("\n")
