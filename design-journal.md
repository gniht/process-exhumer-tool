# Design journal

A contemporaneous record of the v1 build — what was decided at each stage, and when. The architectural conclusions live in [`spec.md`](spec.md); this records the order in which they landed. (Moved out of the README; dates preserved.)

## 2026-06-04 — Spec

Architectural spec captured in [`spec.md`](spec.md) via a [project-spec-interrogator](https://github.com/gniht/project-spec-interrogator) session.

## 2026-06-05 — Core data model

The core data model (contract, node, recursion, per-stage prompt format) was resolved — see the **Core Data Model** section of the spec. This settled the three pre-build blockers:

- ✅ Contract data structure — `behavior` (required) + resolvable `inputs`/`outputs`; identity only
- ✅ Interrogator → decomposition handoff — none needed; the contract is the handoff
- ✅ Per-stage prompt extraction format — each stage is a self-contained `prompt.md` (`## Input` / `## Output` / `## Prompt`), wrapped by a thin `SKILL.md`

## 2026-06-09 — Stage builds

Further commitments accreted during the stage builds; each is recorded in the spec's **Core Data Model** section.

### Stage 1 — interrogator

Built at `.claude/skills/process-exhumer-interrogator/` (single-context human dialog → root contract). First live exercise 2026-06-09, in a run aborted when the author withdrew the task mid-interrogation: the dialog phase behaved as designed per the author's assessment (pushback, surfacing the contract-shaping fork, probing input concreteness), and stopping rather than inventing a contract is a legitimate stage-1 exit. The out-of-domain gate, draft-confirm loop, and contract emission remain unexercised. Refinement is deferred until after a completed end-to-end run.

### Stage 2 — decomposition

Built at `.claude/skills/process-exhumer-decomposition/`. The stage prompt is *flat* (one contract in → `codify` | `decompose` | `reject` out, no tree context); the recursion is a worklist loop owned by the `SKILL.md` harness, mirroring the planned MCP shape (stateless stage-tools, tree-walk as orchestration). Two commitments landed here and are recorded in the spec's **Core Data Model**: *glue is deterministic — judgment lives only in leaves*, and the codify-or-decompose decision is the *strict-progress test*. Untested, like Stage 1.

### Stage 3 — codification

Built at `.claude/skills/process-exhumer-codification/`. Flat stage prompt (one leaf contract in → `codified` | `reject` out); the loop over leaves lives in the harness. The commitment that landed here, recorded in the spec's **Core Data Model**: the **AI seam** — all judgment in generated code flows through one canonical `ai(instruction, payload)` function, so *determinism = zero seam calls*, a count rather than an opinion. The calling convention (entry-point signature from the contract; bare / dict-by-name / nothing returns) is fixed alongside it. Untested, like the others.

### Stage 4 — verification

Built at `.claude/skills/process-exhumer-verification/`. Flat stage prompt (one unit in → `verified` verdict | `reject` out), two unit types: leaves checked as code-against-contract, internal nodes checked **assume-guarantee** (granting each child its contract, does the glue satisfy the parent's?) — which is what makes the whole tree verifiable before composition exists. Commitments recorded in the spec's **Core Data Model**: verification checks *everything except the inside of the seam* (seam-interior truths are **deferred to the run** — named, never silently passed); verdicts are *fail-closed* with per-check `executed`/`static` evidence labels; and *any stage may reject the contract it is handed*, always indicting the upstream author. Untested, like the others.

### Stage 5 — composition

Built at `.claude/skills/process-exhumer-composition/`. The stage prompt is **deliberately mechanical**: one function per node (qualified `<wiring-name>__<id>` names), contract-derived signatures, leaf code nested verbatim, wiring names bound in parent bodies, `self` bound under `recursive-over-data`, a JSON-stdin shell on the root — and *composition never patches*: every hole is a reject naming the owning stage. The seam runtime is an **input** (v1 ships a `claude -p` reference implementation in the harness); the harness runs the artifact on real inputs, feeds seam observations back into result records by node id, and settles verification's deferred list. Recorded in the spec as the pipeline's own deterministic leaf — the first stage expected to become pure code in the MCP era.

## Pipeline complete — next

The pipeline is complete. Next: the **first ad-hoc end-to-end run** — rotate through small, diverse tasks (no privileged test case, per the spec's scope risks), exercise all five stages, and let the failures drive the first refinement pass. The deferred interrogator-refinement requirements (entry-boundary input concreteness, derivability check, AI-user front door) are queued behind that.
