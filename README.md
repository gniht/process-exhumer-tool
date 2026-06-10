# process-exhumer-tool

A framework that takes a task and "unearths" a programmatic process for accomplishing it — through recursive contract-first decomposition, codification of each unit, and structural composition of the results. The long-term ambition is that produced artifacts contain as little AI-call dependence as possible, so that work once done by judgment becomes reliably reproducible code.

## Status

**v1 build in progress.** Architectural spec captured in [`spec.md`](spec.md) via a [project-spec-interrogator](https://github.com/gniht/project-spec-interrogator) session on 2026-06-04. The core data model (contract, node, recursion, per-stage prompt format) was resolved 2026-06-05 — see the **Core Data Model** section of the spec. Build of the first stage (interrogator) is underway.

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

Next: **composition** — the last stage: binds local wiring names to verified leaf and glue code, supplies the v1 `ai()` implementation, assembles the tree upward into a runnable artifact, and runs it end-to-end on the original task — watching the deferred list verification produced.

See [`spec.md`](spec.md) for full architectural commitments, scope decisions, assumptions, and open questions.
