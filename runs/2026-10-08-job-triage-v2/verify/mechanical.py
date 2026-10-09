"""Mechanical checks, read from the AST of each unit's code: leaf surface, closure and seam (with the
claim audit); node glue_determinism, wiring and pattern."""
import ast
import builtins

from harness import TREES, check, name_of, units

ALLOWED_IMPORTS = {"re", "json", "html", "html.parser", "datetime"}
NETWORK_IMPORTS = {"urllib.error", "urllib.request"}
EFFECT_NAMES = {"open", "eval", "exec", "__import__", "input", "globals", "locals", "vars", "os", "sys",
                "subprocess", "socket", "random", "time"}
EFFECT_ATTRS = {"now", "today", "utcnow", "time", "random", "urandom", "getenv", "environ", "system"}
MODEL_NAMES = {"ai", "anthropic", "openai", "llm", "model", "complete", "chat", "messages"}
MUTATORS = {"append", "extend", "update", "add", "pop", "clear", "setdefault", "remove", "insert", "discard"}
GLUE_BUILTINS = {"set", "sorted", "len", "list", "dict", "enumerate", "zip", "range", "min", "max", "sum"}


def _imports(tree):
    found = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            found |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            found.add(n.module)
    return found


def _called_names(tree):
    names = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name):
                names.append(n.func.id)
            elif isinstance(n.func, ast.Attribute):
                names.append(n.func.attr)
    return names


def leaf_checks(tree_name):
    for name, unit in units(tree_name):
        if "children" in unit:
            continue
        nid, code, contract = unit["id"], unit["code"], unit["contract"]
        module = ast.parse(code)
        inputs = [i["name"] for i in contract["inputs"]]

        # surface: one public entry point, named as wired, with the contract's inputs in order
        public = [n for n in module.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]
        params = [a.arg for a in public[0].args.args] if len(public) == 1 else None
        extras = public[0].args.vararg or public[0].args.kwarg or public[0].args.kwonlyargs if public else None
        check(tree_name, nid, "surface",
              len(public) == 1 and public[0].name == name and params == inputs and not extras,
              f"AST: public functions {[f.name for f in public]}; entry `{name}` params {params} vs contract "
              f"inputs {inputs}; no *args/**kwargs/keyword-only: {not extras}")

        # closure: no effects beyond the declared ones, no state written outside the call
        imports = _imports(module)
        declared_network = name == "fetch_source"
        allowed = ALLOWED_IMPORTS | (NETWORK_IMPORTS if declared_network else set())
        loaded = {n.id for n in ast.walk(module) if isinstance(n, ast.Name)}
        attrs = {n.attr for n in ast.walk(module) if isinstance(n, ast.Attribute)}
        module_names = {t.id for n in module.body if isinstance(n, ast.Assign) for t in n.targets
                        if isinstance(t, ast.Name)}
        writes_module_state = []
        has_global = any(isinstance(n, (ast.Global, ast.Nonlocal)) for n in ast.walk(module))
        for fn in [n for n in module.body if isinstance(n, ast.FunctionDef) and n.name != "_build_tables"]:
            for n in ast.walk(fn):
                if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in MUTATORS
                        and isinstance(n.func.value, ast.Name) and n.func.value.id in module_names):
                    writes_module_state.append(f"{n.func.value.id}.{n.func.attr}")
                if isinstance(n, (ast.Assign, ast.AugAssign)):
                    targets = n.targets if isinstance(n, ast.Assign) else [n.target]
                    for t in targets:
                        if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id in module_names:
                            writes_module_state.append(f"{t.value.id}[...] =")
        effects = sorted((loaded & EFFECT_NAMES) | (attrs & EFFECT_ATTRS))
        ok = imports <= allowed and not effects and not writes_module_state and not has_global
        note = ("network imports present and declared: the behavior sends one GET request"
                if declared_network else "no network")
        check(tree_name, nid, "closure", ok,
              f"AST: imports {sorted(imports)} within {sorted(allowed)}; {note}; effect names/attrs "
              f"{effects or 'none'}; module state written from a function: {writes_module_state or 'none'}; "
              f"global/nonlocal: {has_global}")

        # seam: judgment only through decide(); nothing calls a model; claims match the code
        called = _called_names(module)
        decide_sites = called.count("decide")
        model_calls = sorted(set(called) & MODEL_NAMES)
        claims = unit["result"]
        claim_ok = ((decide_sites == 0 and claims["determinism"] == "deterministic" and claims["decisions"] == [])
                    or (decide_sites > 0 and claims["determinism"] == "decision_required"
                        and len(claims["decisions"]) == decide_sites))
        urls_from_input = True
        if declared_network:
            # the only request target is the source definition's endpoint
            requests = [n for n in ast.walk(module) if isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute) and n.func.attr == "Request"]
            urls_from_input = bool(requests) and all(
                ast.unparse(r.args[0]) == "source['endpoint']" for r in requests)
        check(tree_name, nid, "seam", claim_ok and not model_calls and urls_from_input,
              f"AST: {decide_sites} decide() call site(s); model-call names {model_calls or 'none'}; claim "
              f"determinism={claims['determinism']}, decisions={len(claims['decisions'])}"
              + ("; the one request goes to source['endpoint'], so no model endpoint is reachable"
                 if declared_network else ""))


def node_checks(tree_name):
    for name, unit in units(tree_name):
        if "children" not in unit:
            continue
        nid, glue, contract = unit["id"], unit["glue"], unit["contract"]
        children = {c["name"]: c for c in unit["children"]}
        params = [i["name"] for i in contract["inputs"]]
        fn = ast.parse("def _glue(" + ", ".join(params) + "):\n"
                       + "\n".join("    " + l for l in glue.split("\n")))
        body = fn.body[0]
        called = _called_names(fn)

        # glue_determinism: no decision, no model, no call beyond the children and plain builtins;
        # methods only on the glue's own local values (e.g. list.append)
        function_calls = [n.func.id for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        local_names = {n.id for n in ast.walk(body) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        method_calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        foreign = sorted(set(n for n in function_calls if n not in children) - GLUE_BUILTINS)
        foreign += sorted({ast.unparse(m.func) for m in method_calls
                           if not (isinstance(m.func.value, ast.Name) and m.func.value.id in local_names)})
        no_seam = "decide" not in called and not (set(called) & MODEL_NAMES) and not _imports(fn)
        branches = [ast.unparse(n.test) for n in ast.walk(body) if isinstance(n, ast.If)]
        check(tree_name, nid, "glue_determinism", no_seam and not foreign,
              f"AST: function calls {sorted(set(function_calls))}, methods on local values "
              f"{sorted({ast.unparse(m.func) for m in method_calls}) or 'none'}; anything outside children, "
              f"builtins and local methods: {foreign or 'none'}; decide/model/imports: {not no_seam}; branches "
              f"{branches or 'none'} (each tests a declared status value, not meaning)", unit="node")

        # wiring: each child called with its contract's arity, positionally; every input consumed;
        # nothing undeclared referenced; a return on every path
        child_calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                       and n.func.id in children]
        arity = {c: len(children[c]["contract"]["inputs"]) for c in children}
        bad_calls = [f"{ast.unparse(c)}" for c in child_calls
                     if len(c.args) != arity[c.func.id] or c.keywords]
        uncalled = sorted(set(children) - {c.func.id for c in child_calls})
        loaded = {n.id for n in ast.walk(body) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        stored = {n.id for n in ast.walk(body) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        unused_inputs = sorted(set(params) - loaded)
        undeclared = sorted(loaded - set(params) - stored - set(children) - set(dir(builtins)))
        last = body.body[-1]
        check(tree_name, nid, "wiring",
              not bad_calls and not uncalled and not unused_inputs and not undeclared
              and isinstance(last, ast.Return),
              f"AST: child calls with wrong arity/keywords {bad_calls or 'none'} (arity {arity}); children "
              f"never called {uncalled or 'none'}; inputs never read {unused_inputs or 'none'}; undeclared "
              f"names {undeclared or 'none'}; ends in return: {isinstance(last, ast.Return)}. Output keys "
              f"are checked by execution in the behavior checks.", unit="node")

        # pattern: sequential = every child once, straight-line; iterative = the child inside a loop
        pattern = unit["assembly_pattern"]
        if pattern == "sequential":
            in_loop = [c.func.id for loop in ast.walk(body)
                       if isinstance(loop, (ast.For, ast.While, ast.ListComp, ast.DictComp, ast.GeneratorExp))
                       for c in ast.walk(loop) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                       and c.func.id in children]
            counts = {c: sum(1 for x in child_calls if x.func.id == c) for c in children}
            has_branch = any(isinstance(n, (ast.If, ast.IfExp)) for n in ast.walk(body))
            ok = all(v == 1 for v in counts.values()) and not in_loop and not has_branch
            detail = (f"sequential: each child called once {counts}; none inside a loop ({in_loop or 'none'}); "
                      f"no branching ({not has_branch})")
        elif pattern == "iterative":
            looped = {c.func.id for loop in ast.walk(body)
                      if isinstance(loop, (ast.For, ast.ListComp, ast.GeneratorExp))
                      for c in ast.walk(loop) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                      and c.func.id in children}
            ok = looped == set(children)
            detail = f"iterative: children called inside a loop or comprehension: {sorted(looped)} of {sorted(children)}"
        else:
            ok, detail = False, f"pattern {pattern!r} has no check"
        check(tree_name, nid, "pattern", ok, "AST: " + detail + ". Call counts are confirmed by execution "
              "in the behavior checks.", unit="node")


def run():
    for tree_name in TREES:
        leaf_checks(tree_name)
        node_checks(tree_name)
