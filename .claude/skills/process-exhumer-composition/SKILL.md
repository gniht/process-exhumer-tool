---
name: process-exhumer-composition
description: >
  Stage 5 (final) of the process-exhumer pipeline. Mechanically assembles the
  verified tree into one self-contained, runnable program — one function per
  node, wiring names bound, the seam runtime inserted — then runs it
  end-to-end on the original task, feeds run-time ai() observations back into
  node result records, and reports against verification's deferred watch
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

- **Does:** assemble the artifact; supply the v1 seam runtime; run the
  artifact end-to-end on real inputs; record seam observations into result
  records; assess the run against the root behavior and verification's
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
2. **Assemble:** apply `prompt.md` to `{tree, language, ai_runtime}`. Use
   the reference seam runtime below iff any leaf is ai_required.
   `decision: "reject"` → surface it; the reason names the node and the
   owning stage — re-run that stage, never hand-patch the artifact.
3. **Present and persist:** show the artifact in chat (the deliverable is
   in-chat by scope) and write it to a file to run.
4. **Collect real inputs:** ask the user for the actual values of the root
   contract's inputs — this is the original task, live. Build the JSON
   object the shell expects on stdin.
5. **Run:** `python artifact.py < inputs.json`, capturing stdout (the
   outputs) and stderr (the seam log). Report crashes verbatim — a crash is
   data about which contract lied.
6. **Record, by reference:** every seam-log line's `caller` carries a node
   id — append each observation to that node's `result`. The root's
   `result` gets the end-to-end outcome: ran/crashed, outputs, and your
   assessment of the root `behavior` against them (this assessment is
   judgment — label it as such).
7. **Report:**
   - did it run, and do the outputs satisfy the root behavior — would a
     non-technical observer say the framework did what it was supposed to?
   - realized AI-dependence: seam calls actually incurred, per node —
     the number the framework exists to drive down;
   - the deferred list, settled: each deferred aspect observed (with your
     assessment) or not exercised by this run's inputs (say so);
   - claim mismatches: anything the run contradicted (a "deterministic"
     leaf that misbehaved, a seam return that broke its declared shape).
8. **Emit** the final tree (results now carrying run observations) as a
   fenced ```json block, alongside the artifact. The pipeline is complete.

## v1 reference seam runtime (`claude -p`, Max plan — no API cost)

```python
import inspect, json, subprocess, sys

def ai(instruction, payload):
    caller = inspect.stack()[1].function
    prompt = (instruction
              + "\n\nPayload (JSON):\n" + json.dumps(payload)
              + "\n\nRespond with ONLY the return value, as JSON.")
    r = subprocess.run(["claude", "-p", prompt],
                       capture_output=True, text=True, timeout=300)
    raw = r.stdout.strip()
    if raw.startswith("```"):
        raw = raw.strip("`\n")
        raw = raw[raw.find("\n") + 1:] if raw.startswith("json") else raw
    value = json.loads(raw)  # nonconforming return fails loudly, by design
    print(json.dumps({"caller": caller, "instruction": instruction,
                      "payload": payload, "return": value}), file=sys.stderr)
    return value
```

Adjust mechanics (timeout, fence-stripping) as the environment demands, but
keep the contract: declared-shape returns, one JSON log line per call with
the enclosing function name, loud failure — never silent coercion.

`prompt.md` is the real artifact — self-contained and model-agnostic, so it
can be lifted, run against another model, or — fitting, for this stage —
replaced by a deterministic program. This `SKILL.md` is only the Claude-Code
harness (runtime supplier, runner, and recorder) around it.
