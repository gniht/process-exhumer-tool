# process-exhumer-tool

A framework that takes a task and "unearths" a programmatic process for accomplishing it — through recursive contract-first decomposition, codification of each unit, and structural composition of the results. The long-term ambition is that produced artifacts contain as little AI-call dependence as possible, so that work once done by judgment becomes reliably reproducible code.

## Status

**v1 built — untested.** Architectural spec captured in [`spec.md`](spec.md) via a [project-spec-interrogator](https://github.com/gniht/project-spec-interrogator) session on 2026-06-04. The core data model (contract, node, recursion, per-stage prompt format) was resolved 2026-06-05, and further commitments accreted during the stage builds (2026-06-09) — see the **Core Data Model** section of the spec. All five pipeline stages exist as skills; no stage has been exercised yet. The first end-to-end run is next.

## v1 in one sentence

A Claude Code skill that runs end-to-end *interrogator → decomposition → codification → verification → composition* on an arbitrary task, designed with clean stage boundaries so it can be ported to a standalone MCP server later.

## Next steps

The three pre-build blockers are now resolved (see `spec.md` → **Core Data Model**):

- ✅ Contract data structure — `behavior` (required) + resolvable `inputs`/`outputs`; identity only
- ✅ Interrogator → decomposition handoff — none needed; the contract is the handoff
- ✅ Per-stage prompt extraction format — each stage is a self-contained `prompt.md` (`## Input` / `## Output` / `## Prompt`), wrapped by a thin `SKILL.md`

Stage 1 — **interrogator** — is built at `.claude/skills/process-exhumer-interrogator/` (single-context human dialog → root contract). It is untested; refinement is deferred until the pipeline shape is clearer.

Stage 2 — **decomposition** — is built at `.claude/skills/process-exhumer-decomposition/`. The stage prompt is *flat* (one contract in → `codify` | `decompose` | `reject` out, no tree context); the recursion is a worklist loop owned by the `SKILL.md` harness, mirroring the planned MCP shape (stateless stage-tools, tree-walk as orchestration). Two commitments landed here and are recorded in the spec's **Core Data Model**: *glue is deterministic — judgment lives only in leaves*, and the codify-or-decompose decision is the *strict-progress test*. Untested, like Stage 1.

Stage 3 — **codification** — is built at `.claude/skills/process-exhumer-codification/`. Flat stage prompt (one leaf contract in → `codified` | `reject` out); the loop over leaves lives in the harness. The commitment that landed here, recorded in the spec's **Core Data Model**: the **AI seam** — all judgment in generated code flows through one canonical `ai(instruction, payload)` function, so *determinism = zero seam calls*, a count rather than an opinion. The calling convention (entry-point signature from the contract; bare / dict-by-name / nothing returns) is fixed alongside it. Untested, like the others.

Stage 4 — **verification** — is built at `.claude/skills/process-exhumer-verification/`. Flat stage prompt (one unit in → `verified` verdict | `reject` out), two unit types: leaves checked as code-against-contract, internal nodes checked **assume-guarantee** (granting each child its contract, does the glue satisfy the parent's?) — which is what makes the whole tree verifiable before composition exists. Commitments recorded in the spec's **Core Data Model**: verification checks *everything except the inside of the seam* (seam-interior truths are **deferred to the run** — named, never silently passed); verdicts are *fail-closed* with per-check `executed`/`static` evidence labels; and *any stage may reject the contract it is handed*, always indicting the upstream author. Untested, like the others.

Stage 5 — **composition** — is built at `.claude/skills/process-exhumer-composition/`. The stage prompt is **deliberately mechanical**: one function per node (qualified `<wiring-name>__<id>` names), contract-derived signatures, leaf code nested verbatim, wiring names bound in parent bodies, `self` bound under `recursive-over-data`, a JSON-stdin shell on the root — and *composition never patches*: every hole is a reject naming the owning stage. The seam runtime is an **input** (v1 ships a `claude -p` reference implementation in the harness); the harness runs the artifact on real inputs, feeds seam observations back into result records by node id, and settles verification's deferred list. Recorded in the spec as the pipeline's own deterministic leaf — the first stage expected to become pure code in the MCP era.

**The pipeline is complete.** Next: the **first ad-hoc end-to-end run** — rotate through small, diverse tasks (no privileged test case, per the spec's scope risks), exercise all five stages, and let the failures drive the first refinement pass. The deferred interrogator-refinement requirements (entry-boundary input concreteness, derivability check, AI-user front door) are queued behind that.

See [`spec.md`](spec.md) for full architectural commitments, scope decisions, assumptions, and open questions.
