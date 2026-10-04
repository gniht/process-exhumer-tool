---
name: process-exhumer-composition
description: >
  Stage 5 (final) of the process-exhumer pipeline. Mechanically assembles the
  verified tree into one self-contained, runnable program — one function per
  node, wiring names bound, the decision runtime inserted — then runs it
  end-to-end on the original task, feeds run-time decision observations back
  into node result records, and reports against verification's deferred watch
  list. Use after verification, on a verified tree. Produces the working
  implementation of the root contract — the pipeline's deliverable.
---

# Process-Exhumer · Composition (Stage 5)

The build. Decomposition asked every node "how do you build me?"; this stage
executes the answers, bottom-up, into a single runnable artifact — and then
actually runs it on the original task.

The stage prompt in [`prompt.md`](prompt.md) is **deliberately mechanical**:
every step is deterministic (naming, wrapping, binding, ordering), and any
gap in the tree is a reject, never an improvisation. A model executes the
algorithm in v1; this is the first stage expected to become pure code in the
MCP era.

## What this stage does — and does not — do

- **Does:** assemble the artifact; supply the decision runtime; run the
  artifact end-to-end on real inputs; record decision observations into
  result records; assess the run against the root behavior and verification's
  deferred list.
- **Does NOT:** patch holes (a structurally incomplete tree is a reject
  naming the owning stage), re-verify nodes (verification did), or decide
  whether a tree with failed verdicts deserves composing — that policy gate
  is below, and the user holds it.

## How to run it

1. **Gate (policy, yours and the user's):** take the verified tree. If any
   node's verdict is `fail` and the user has not explicitly accepted it,
   stop and ask. Pull out the **deferred list** from the result records —
   it is this run's watch list.
2. **Assemble:** apply `prompt.md` to `{tree, language, decision_runtime}`.
   Use the reference decision runtime below iff any leaf is
   decision_required.
   `decision: "reject"` → surface it; the reason names the node and the
   owning stage — re-run that stage, never hand-patch the artifact.
3. **Persist the deliverable:** write the artifact to a file — *the file is
   the product*, a standalone program that outlives the session (agree on
   the path with the user). Show it in chat for review — useful, especially
   for simple cases, but never the deliverable. Note its run-time footprint
   honestly: it runs anywhere its language does and never needs a model; one
   with decision points also reads an optional file of stored answers.
4. **Collect real inputs:** ask the user for the actual values of the root
   contract's inputs — this is the original task, live. Build the JSON
   object the shell expects on stdin. Where the root consumes a collection of
   instances, gather **at least two that are structurally different** — two
   sources, two formats, two providers. A contract defect that survived
   verification usually shows up as an inconsistency *between* instances, and
   a single-instance run cannot see it.
5. **Run:** `python artifact.py [answers.json] < inputs.json`, capturing
   stdout (the outputs) and stderr (the decision log). Run first with **no
   stored answers**, so every decision point falls back: that is the program
   a user gets who never answers anything, and it must already be useful. If
   the user wants to answer some pending decisions, write their answers to a
   JSON file keyed by each decision's `key` and run again. Report crashes
   verbatim — a crash is data about which contract lied.
6. **Record, by reference:** every decision-log line's `caller` carries a node
   id — append each observation to that node's `result`. The root's
   `result` gets the end-to-end outcome: ran/crashed, outputs, and your
   assessment of the root `behavior` against them (this assessment is
   judgment — label it as such).
7. **Report:**
   - did it run, and do the outputs satisfy the root behavior — would a
     non-technical observer say the framework did what it was supposed to?
   - realized decision load, per decision point: how many decisions were
     answered and how many fell back, by fallback kind — the number the
     framework exists to drive to zero — and the pending questions, which are
     the user's to answer or ignore;
   - the deferred list, settled: each deferred aspect observed (with your
     assessment) or not exercised by this run's inputs (say so);
   - claim mismatches: anything the run contradicted (a "deterministic"
     leaf that misbehaved, a stand-in that reached the outputs unmarked, a
     stored answer that broke its declared shape);
   - **the residue**, as a deliverable rather than a list of shortfalls: each
     decision point with its judgment, `cause`, `nearest_codifiable_alternative`,
     fallback, ratified-or-provisional status, and how its decisions went this
     run. Say where decision load differed *across* instances of the same
     contract — a field
     one source states structurally and another leaves to prose is judgment
     caused by the input's shape, not by the task, and is removable by changing
     the source;
   - **differential check:** compare values that should be commensurable across
     the instances you ran. Fields sharing a name but not a value space are the
     signature of a contract that specified names without specifying meaning.
8. **Emit** the final tree (results now carrying run observations) as a
   fenced ```json block, alongside the artifact. The pipeline is complete.

## v1 reference decision runtime

```python
import hashlib, inspect, json, re, sys

_QUALIFIED = re.compile(r"__n\d+$")
_FALLBACKS = {"codified", "unknown", "set_aside", "stop"}
_ANSWERS = {}

class DecisionRequired(Exception):
    def __init__(self, record):
        super().__init__(record["question"])
        self.record = record

def decide(request):
    caller = next(
        (f.function for f in inspect.stack()[1:] if _QUALIFIED.search(f.function)),
        inspect.stack()[1].function,
    )
    fallback = request["fallback"]
    if fallback["kind"] not in _FALLBACKS:
        raise ValueError(f"unknown fallback kind: {fallback['kind']!r}")
    key = hashlib.sha256(json.dumps(
        [caller, request["question"], request["evidence"]], sort_keys=True, default=str
    ).encode()).hexdigest()[:16]
    record = {"caller": caller, "key": key, "question": request["question"],
              "answer_shape": request["answer_shape"], "evidence": request["evidence"]}
    if key in _ANSWERS:
        outcome = {"value": _ANSWERS[key], "source": "answered"}
    else:
        outcome = {"value": fallback.get("value"), "source": "fallback",
                   "fallback_kind": fallback["kind"]}
    print(json.dumps({**record, **outcome}, default=str), file=sys.stderr)
    if outcome["source"] == "fallback" and fallback["kind"] == "stop":
        raise DecisionRequired(record)
    return outcome

def main(root):
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            _ANSWERS.update(json.load(f))
    args = json.loads(sys.stdin.read())
    try:
        result = root(**args)
    except DecisionRequired as stop:
        print(json.dumps({"decision_required": stop.record}, default=str))
        sys.exit(2)
    print(json.dumps(result, default=str))
```

Keep the contract when adjusting mechanics: stored answers or the declared
fallback, never anything else; one JSON log line per call carrying **the
node's qualified name** and the decision's key; a halted run that says what
it needs.

**Stored answers are a JSON object keyed by decision `key`.** The key hashes
the caller, the question and the evidence, so an answer applies to exactly
the decision it was given for. Re-codifying a leaf (a new question) or
re-decomposing (new node ids) orphans its old answers, which is correct: they
answered a different question. Every log line whose `source` is `fallback` is
a pending decision with everything needed to answer it.

**Wiring in a model is the user's act, never the program's.** A user who
wants a model to answer some decisions builds an answerer outside the program
that reads the pending lines and writes stored answers. This harness never
supplies one.

Note why `caller` walks the stack rather than taking the immediate frame. Leaf
code is nested *verbatim* inside its wrapper, so the function that calls
`decide()` is the leaf's own inner entry point — an unqualified name carrying
no node id. Taking `inspect.stack()[1]` breaks node attribution silently, and
two leaves whose inner entry points share a name become indistinguishable in
the log. Walking outward to the nearest `__n<id>` frame restores it
mechanically.

`prompt.md` is the real artifact — self-contained and model-agnostic, so it
can be lifted, run against another model, or — fitting, for this stage —
replaced by a deterministic program. This `SKILL.md` is only the Claude-Code
harness (runtime supplier, runner, and recorder) around it.
