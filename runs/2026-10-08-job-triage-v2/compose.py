"""Stage 5 assembly, mechanical: every step is naming, wrapping, binding, ordering. A hole in a tree
is a reject naming the node and the owning stage, never a patch.

    python3 compose.py    # writes job_triage_refresh.py and job_triage_assess.py beside this file
"""
import ast
import builtins
import io
import json
import os
import sys
import tokenize

RUN = os.path.dirname(os.path.abspath(__file__))
BUILTIN_NAMES = set(dir(builtins))


def reject(node, owner, hole):
    sys.exit(f"REJECT ({owner}): node {node['id']} -- {hole}")


def inputs(contract):
    return [i["name"] for i in contract["inputs"]]


def indent(source, levels=1):
    """Indent every line of code one level, but never a line that continues a multi-line string literal:
    its leading spaces are the string's content, and adding to them would change what the code means."""
    continuation, open_fstrings = set(), []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.STRING and token.start[0] != token.end[0]:
            continuation.update(range(token.start[0] + 1, token.end[0] + 1))
        elif token.type == getattr(tokenize, "FSTRING_START", None):
            open_fstrings.append(token.start[0])
        elif token.type == getattr(tokenize, "FSTRING_END", None):
            continuation.update(range(open_fstrings.pop() + 1, token.end[0] + 1))
    return "\n".join(line if number in continuation or not line.strip() else "    " * levels + line
                     for number, line in enumerate(source.split("\n"), start=1))


def same_code(nested_body, source):
    """Whether statements nested in a wrapper are, as syntax, exactly the source they were made from."""
    return [ast.dump(n) for n in nested_body] == [ast.dump(n) for n in ast.parse(source).body]


def entry_point(node):
    """The function in the leaf's code whose parameters are the contract's inputs, in order."""
    want = inputs(node["contract"])
    hits = [f.name for f in ast.parse(node["code"]).body
            if isinstance(f, ast.FunctionDef) and [a.arg for a in f.args.args] == want]
    if len(hits) != 1:
        reject(node, "codification", f"entry point not identifiable: {len(hits)} functions take {want}")
    return hits[0]


def check_glue(node):
    params = inputs(node["contract"])
    children = [c["name"] for c in node["children"]]
    fn = ast.parse(f"def _glue({', '.join(params)}):\n" + indent(node["glue"])).body[0]
    stored = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    loaded = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    allowed = set(params) | set(children) | stored | BUILTIN_NAMES
    if node["assembly_pattern"] == "recursive-over-data":
        allowed.add("self")
    undeclared = sorted(loaded - allowed)
    if undeclared:
        reject(node, "decomposition", f"glue references undeclared names {undeclared}")
    if not isinstance(fn.body[-1], ast.Return):
        reject(node, "decomposition", "glue does not end by returning the node's outputs")


def compose(tree, program_name):
    functions = []

    def emit(node, wiring):
        name = f"{wiring}__{node['id']}"
        params = ", ".join(inputs(node["contract"]))
        if "children" in node:
            for key in ("assembly_pattern", "glue"):
                if key not in node:
                    reject(node, "decomposition", f"internal node lacks {key}")
            for child in node["children"]:
                emit(child, child["name"])
            check_glue(node)
            binds = [f"    {c['name']} = {c['name']}__{c['id']}" for c in node["children"]]
            if node["assembly_pattern"] == "recursive-over-data":
                binds.append(f"    self = {name}")
            functions.append(f"def {name}({params}):\n" + "\n".join(binds)
                             + "\n    # --- glue, verbatim ---\n" + indent(node["glue"])
                             + "\n    # --- end glue ---")
        else:
            if "code" not in node:
                reject(node, "codification", "leaf lacks code")
            calls = {n.func.id for n in ast.walk(ast.parse(node["code"]))
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
            if "ai" in calls:
                reject(node, "codification", "leaf calls the retired ai() seam")
            if "decide" in calls:
                reject(node, "composition input", "leaf calls decide() and no decision runtime was supplied")
            entry = entry_point(node)
            functions.append(f"def {name}({params}):\n"
                             f"    # --- leaf {node['id']} code, verbatim ---\n" + indent(node["code"])
                             + f"\n    # --- end leaf code ---\n    return {entry}({params})")
        return name

    root = emit(tree, "root")
    header = (f'"""{program_name}: assembled by process-exhumer stage 5 from a verified tree. No model is '
              f'called, and there are no\ndecision points, so no decision runtime is included.\n\n'
              f'Usage: python3 {program_name} < inputs.json > outputs.json\n\nWhat this program is (the root '
              f'contract\'s behavior):\n\n' + tree["contract"]["behavior"] + '\n"""')
    shell = ('if __name__ == "__main__":\n    import json\n    import sys\n'
             '    args = json.loads(sys.stdin.read())\n'
             f'    print(json.dumps({root}(**args), default=str))\n')
    artifact = "\n\n\n".join([header] + functions + [shell])
    assembled = {n.name: n for n in ast.parse(artifact).body if isinstance(n, ast.FunctionDef)}

    # every nested leaf and glue must be, as syntax, the code that was verified: wrapping may add
    # bindings and a return around it, and nothing else
    def confirm(node, wiring):
        body = assembled[f"{wiring}__{node['id']}"].body
        if "children" in node:
            for child in node["children"]:
                confirm(child, child["name"])
            ok = same_code(body[len(node["children"]) + (node["assembly_pattern"] == "recursive-over-data"):], node["glue"])
        else:
            ok = same_code(body[:-1], node["code"])
        if not ok:
            sys.exit(f"ASSEMBLY ERROR (composition): node {node['id']} -- nested code differs from the verified code")

    confirm(tree, "root")
    return artifact, root, len(functions)


for tree_name in ("refresh", "assess"):
    tree = json.load(open(os.path.join(RUN, f"verified-tree-{tree_name}.json")))
    program = f"job_triage_{tree_name}.py"
    artifact, root, count = compose(tree, program)
    with open(os.path.join(RUN, program), "w") as f:
        f.write(artifact)
    print(f"composed {program}: {count} node functions, entry {root}, {len(artifact.splitlines())} lines, "
          f"decision runtime omitted (no decide() calls)")
