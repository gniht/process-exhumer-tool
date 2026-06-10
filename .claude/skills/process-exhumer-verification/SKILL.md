---
name: process-exhumer-verification
description: >
  Stage 4 of the process-exhumer pipeline. Verifies every node of the
  codified tree flat: leaves as code-against-contract, internal nodes
  assume-guarantee (granting each child its contract, does the glue satisfy
  the parent's?). Audits codification's determinism claims, executes checks
  for real where possible, records verdicts in node result records, and
  surfaces the seam-interior aspects deferred to run time. Use after
  codification, or on any single leaf or node. Produces the verified tree
  that composition consumes.
---

# Process-Exhumer · Verification (Stage 4)

The stage that makes the termination story honest: a leaf "passes" iff its
code satisfies its declared contract, and an internal node "passes" iff its
wiring satisfies its contract *given* its children's contracts. Everything is
checked locally — no node needs the tree — which is what lets verification
run before composition exists.

The stage prompt in [`prompt.md`](prompt.md) is **flat**: one unit in, one
verdict out. The loop over nodes lives here, in the harness.

## What this stage does — and does not — do

- **Does:** verify every node (leaves *and* internal nodes); audit
  codification's determinism claims against the actual code; execute checks
  for real; record verdicts and failures in result records; name what was
  deferred to run time.
- **Does NOT:** fix anything (v1 has no refinement loop), assemble the tree
  (composition's job), or check end-to-end behavior on the original task
  (that is composition's run — local verification is what makes that run
  likely to succeed).

## How to run it

1. **Input:** the codification stage's tree ```json block (or a file, or a
   single pasted unit). Use the same target language as the rest of the run
   (default: python).
2. **Walk every node, any order** — each check is local:
   - leaf → `{ unit: "leaf", contract, code, claims: {determinism,
     ai_dependence} }` (claims come from the node's `result`);
   - internal node → `{ unit: "node", contract, assembly_pattern, glue,
     children: [{name, contract}] }`.
   Apply `prompt.md` to that unit *alone*. Never pass the rest of the tree —
   flatness is the portability discipline.
3. **Execute for real.** In Claude Code an execution environment exists, so
   `executed` must mean executed: write the leaf code and a small harness to
   a temp dir, stub `ai()` with canned returns of the declared shape, run
   it, report what happened. Same for glue with contract-conformant child
   stubs. Do not simulate execution mentally and label it `executed`.
4. **Record verdicts** in result records:
   - leaf → merge into the existing record:
     `result: { determinism, ai_dependence, verdict, failures }`,
     where `failures` is the checks that did not pass (fail + deferred);
   - internal node → create `result: { verdict, failures }`.
   Full check logs stay in the stage output; the tree carries verdict plus
   non-passing checks.
5. **`decision: "reject"`** → stop and surface it. An uncheckable behavior
   indicts whoever authored the contract — the interrogator at the root,
   the parent's decomposition below. Re-run that stage; do not soften the
   behavior yourself.
6. **On failures: no auto-fix.** Summarize and put the choice to the user
   per failed node: re-codify the leaf, re-decompose the parent, or accept
   with the failure recorded.
7. **Summarize the stage:** pass/fail per node; executed-vs-static ratio
   (the honesty metric); claim-audit mismatches; and the full deferred list
   — that list is composition's watch list for the live run.
8. **Emit** the updated tree as a single fenced ```json block — the handoff
   to composition.

## Subagents (later)

Each prompt application is flat — one unit in, one verdict out — and nodes
are mutually independent, so this stage fans out naturally. Per the spec,
default to single-context while the prompt is young; pull subagents in to
validate contract discipline once it stabilizes.

`prompt.md` is the real artifact — self-contained and model-agnostic, so it
can be lifted and run against another model or a future MCP tool. This
`SKILL.md` is only the Claude-Code harness (and v1 orchestrator) around it.
