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

Next: **design the decomposition stage** — the load-bearing one, where the assembly vocabulary, the recurse-or-codify decision, and the termination rule all land. It consumes a root contract and emits `(assembly_pattern, glue, child_contracts)`. Stages after that, in pipeline order: codification, verification, composition — each a `prompt.md` + `SKILL.md` pair in the same extraction format.

See [`spec.md`](spec.md) for full architectural commitments, scope decisions, assumptions, and open questions.
