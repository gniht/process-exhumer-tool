# process-exhumer-tool

A framework that takes a task and "unearths" a programmatic process for accomplishing it — through recursive contract-first decomposition, codification of each unit, and structural composition of the results. The long-term ambition is that produced artifacts contain as little AI-call dependence as possible, so that work once done by judgment becomes reliably reproducible code.

## Status

**Pre-build.** Architectural spec captured in [`spec.md`](spec.md) via a [project-spec-interrogator](https://github.com/gniht/project-spec-interrogator) session on 2026-06-04. No implementation yet. v1 build begins in the next working session.

## v1 in one sentence

A Claude Code skill that runs end-to-end *interrogator → decomposition → codification → verification → composition* on an arbitrary task, designed with clean stage boundaries so it can be ported to a standalone MCP server later.

## Next steps

Before writing code, the following items in `spec.md`'s **Open Questions** need concrete answers:

- Contract data structure (the framework's load-bearing primitive)
- Interrogator → decomposition handoff schema
- Per-stage prompt extraction format

Then: build the interrogator stage as a skill, iterate prompts in single-context mode, and switch to subagent invocation once prompts stabilize.

See [`spec.md`](spec.md) for full architectural commitments, scope decisions, assumptions, and open questions.
