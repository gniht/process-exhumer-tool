---
name: process-exhumer-codification
description: >
  Stage 3 of the process-exhumer pipeline. Consumes the node tree from
  decomposition and writes the implementation of every leaf — one entry-point
  function per leaf contract, with all judgment confined to the canonical
  decide(request) seam — a question for a person, never a model call.
  Discovers each leaf's determinism outcome, records it in the node's result
  record, and puts every decision point to the user for ratification. Use after decomposition has
  produced a tree, or on any single leaf contract. Produces the codified tree
  that verification consumes.
---

# Process-Exhumer · Codification (Stage 3)

The stage where the framework's question gets answered, leaf by leaf: *does
this unit reduce to deterministic code?* It writes each leaf's implementation
once — no refinement loop in v1 — and reports what it discovered.

The stage prompt in [`prompt.md`](prompt.md) is **flat**: one leaf contract
in, one implementation out, no tree context. The loop over leaves lives here,
in the harness.

## What this stage does — and does not — do

- **Does:** implement every leaf; confine judgment to the `decide()` seam,
  each decision point with a declared fallback; discover and record each
  leaf's determinism outcome; put each decision point to the user.
- **Does NOT:** check code against contracts (verification's job), wire
  leaves together (composition's job), implement `decide()` itself
  (composition supplies the decision runtime), write any code that calls a
  model, or re-decompose smelly leaves (the annotations it emits are the signal a
  future loop consumes; v1 writes once and moves on).

## How to run it

1. **Input:** the decomposition stage's tree ```json block (or a file, or a
   single pasted leaf contract). Optionally the target language — use the
   same one glue was written in (default: python).
2. **Identify the leaves:** every node without
   `assembly_pattern`/`glue`/`children`. Leaves are independent — order does
   not matter, which also makes each one a natural subagent call later.
3. **Loop — for each leaf:** apply `prompt.md` to its contract *alone* (plus
   the language). No tree context, no siblings — flatness is the portability
   discipline.
   - `decision: "codified"` → store `code` on the node and initialize its
     result record:
     `result: { "determinism": ..., "decisions": [...] }`.
     Verification adds its verdict to the same record later.
   - `decision: "reject"` → **stop and surface it.** A rejected leaf indicts
     its parent's decomposition — it declared codifiable something that
     is not (non-concrete I/O, unsatisfiable behavior). Show the user the
     reason and re-run the parent node's decomposition. Do not silently
     retry the leaf.
4. **Summarize the discovery.** After the loop, report the numbers the
   framework exists to drive to zero: leaves deterministic vs.
   decision_required, total decision points, the judgments they hold and
   their fallbacks. Leaves with several decision points are
   under-decomposition smells — name them, don't fix them.
5. **Ratify the residue — stop and ask.** Every decision point is a claim that
   some judgment cannot be made reproducible, and that claim is the run's
   second deliverable. Do not finalize it alone. Put each one to the user: the
   judgment, its `cause`, why deterministic code is claimed not to reach it,
   the `nearest_codifiable_alternative` with what adopting it would trade
   away, and the declared fallback. Ask the user to choose:
   - **adopt the alternative** as the implementation — often the right
     answer: the decision point disappears for the price of a narrower
     contract. The narrowing belongs upstream, so re-decompose the parent and
     re-codify; or
   - **keep the decision point**, with the declared fallback or one the user
     prefers (re-codify if it changes).

   Say so when a decision point would fire on most inputs. A question the user
   would have to answer on every run defeats the program, so in practice its
   fallback *is* the implementation, and the user should weigh it as one.
   Entries stand as `provisional` until the user chooses; mark the ones they
   ratify. An autonomous run with no user to ask leaves every entry
   provisional rather than promoting its own claims.
6. **Emit** the updated tree as a single fenced ```json block — the handoff
   to verification. Leaf nodes now carry `code` and `result`:

   ```json
   {
     "id": "n2",
     "contract": { "...": "..." },
     "code": "...",
     "result": { "determinism": "deterministic", "decisions": [] }
   }
   ```

   For long runs, also write the tree to a file if the user wants one.

## Subagents (later)

Each prompt application is flat — contract in, implementation out — and
leaves are mutually independent, so this stage fans out naturally. Per the
spec, default to single-context while the prompt is young; pull subagents in
to validate contract discipline once it stabilizes.

`prompt.md` is the real artifact — self-contained and model-agnostic, so it
can be lifted and run against another model or a future MCP tool. This
`SKILL.md` is only the Claude-Code harness (and v1 orchestrator) around it.
