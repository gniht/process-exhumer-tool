# process-exhumer-tool

A framework that takes a task and "unearths" a programmatic process for accomplishing it.

In plain terms: you describe a task; an interrogation dialog refines it into a precise contract; the framework recursively decomposes that contract into pieces small enough to implement directly, generates and verifies code for each piece, and mechanically assembles the results into a standalone program. The aim is that as much of the work as possible ends up as ordinary deterministic code, with AI judgment surviving only in explicitly marked spots — where it can be counted, audited, and targeted for further reduction.

## Motivation

This grew out of a problem I hit while working on latent-world-engine (LWE), a personal project for leveraging AI in game development. Even with what seemed a very well-articulated spec, I was getting output from AI that shouldn't happen — ever. Eventually I realized it stemmed from an internal bias of the models being used: they want to jump to an "answer" as quickly as possible. That isn't inherently a bad thing, but it is when it means the clear process outlined by the user isn't actually being followed. It became clear that merely insisting in the prompts that the process be followed wasn't enough to completely prevent this. If I couldn't prompt around the problem, I needed another approach.

A short digression that turns out to matter: one of LWE's basic notions — a heuristic, really — is that complex things can generally be decomposed into simpler things, and that you can continue decomposing until you reach elements so simple that going further is infeasible or mostly unhelpful. At that point you have what amounts to an atomic component of a game. The motivation for this is that while gamedev is complex as a whole, an atomic component is relatively simple: it's easy to identify what objects of each component type look like, easy to construct new objects of that type, and — importantly — easy to verify correctness of form. Assuming that's right, and assuming the decomposition is possible, it follows that it should be possible to create games from the ground up leveraging AI, with the entire process supported by robust verification. I think the idea is valid — but AI's failure to consistently follow explicit procedure breaks it.

The way forward was to change the goal. Following the same heuristics LWE was built on, plus one more — that for any repeatable process, there should exist a recipe for doing it — the goal became not to have AI create the atomic elements themselves, but to have it create code that would generate those artifacts. Then erroneous output produces code, not content — and a problem in code is deterministic and repeatable: it can be discovered and fixed. So the new idea was to codify, to the extent possible. This also has a useful side-effect: codified work no longer needs reasoning, so as a byproduct of a more deterministic and reliable system, you're also minimizing token expense.

I can't be the only person running into problems like this, and generating code artifacts to do the thing — instead of just asking AI to do the thing — seemed like it could be useful in many situations, so I created this open-source tool. It uses a derivative of [project-spec-interrogator](https://github.com/gniht/project-spec-interrogator) to refine goals into contracts, then focuses on decomposition and the generation of code artifacts to build processes.

## Status

All five pipeline stages are built as Claude Code skills. None has yet been exercised end-to-end; **the first complete run is the current milestone**, and its write-up will be linked here once it exists.

The architecture was captured in [`spec.md`](spec.md) on 2026-06-04 via a [project-spec-interrogator](https://github.com/gniht/project-spec-interrogator) session — this project's stage-1 interrogator is itself a specialized derivative of that skill. The contemporaneous build record, including the design commitments that landed during each stage build, is in [`design-journal.md`](design-journal.md).

## The pipeline

1. **Interrogation** — a multi-turn dialog refines a vague task into a root *contract*: what must be true of the outputs, given the inputs.
2. **Decomposition** — recursively splits each contract into child contracts plus deterministic glue describing how the children assemble. Judgment is only ever pushed downward into children, never into the wiring.
3. **Codification** — generates code for each leaf contract, with any remaining judgment routed through a single named function.
4. **Verification** — checks every node flat, against its own contract: leaves as code-against-contract, internal nodes by granting each child its contract and asking whether the glue satisfies the parent's.
5. **Composition** — mechanically assembles the verified tree into one standalone, runnable program.

The v1 skill is deliberately structured — flat stages, structured outputs, extractable per-stage prompts — so that it can later be rebuilt as a standalone MCP server. Full architectural detail is in [`spec.md`](spec.md).

## Design highlights

A few of the ideas doing the most work:

- **The AI seam.** All judgment in generated code flows through one canonical function: `ai(instruction, payload)`. "How AI-dependent is this program?" stops being an opinion and becomes a count — determinism means zero seam calls, checkable mechanically and attributable per call site.
- **Judgment lives only in leaves.** Glue — the code that wires components together — moves data and never interprets it. Any judgment a build needs is pushed into a child contract, where the recursion can keep working on it. Reducing AI dependence is therefore purely a question of how far decomposition pushes.
- **The contract is the only primitive.** One small declarative structure — inputs, outputs, and a required behavior clause — flows through every stage. There is no separate handoff format anywhere in the pipeline: the contract *is* the handoff.
- **Any stage may reject what it's handed.** A contract that can't be satisfied as wired is rejected rather than papered over, and a rejection always indicts the upstream author, never the rejecting stage. Errors surface where they were made.

## Files

- [`spec.md`](spec.md) — the architectural spec: goals, scope, the core data model, validation criteria, open questions
- [`design-journal.md`](design-journal.md) — contemporaneous record of the five stage builds and the commitments that landed during each
- `.claude/skills/` — the five pipeline stages, each a self-contained stage prompt (`prompt.md`) wrapped by a thin Claude Code harness (`SKILL.md`)

Usage documentation will follow the first validated end-to-end run.
