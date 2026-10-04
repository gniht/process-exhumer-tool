# process-exhumer-tool

A framework that takes a task and "unearths" a programmatic process for accomplishing it.

In plain terms: you describe a task; an interrogation dialog refines it into a precise contract; the framework recursively decomposes that contract into pieces small enough to implement directly, generates and verifies code for each piece, and mechanically assembles the results into a standalone program. The aim is that all of the work ends up as ordinary deterministic code. A produced program never calls a model: where a judgment genuinely resists codification, it becomes an explicitly marked *decision point* — a question for a person, with a fallback the program uses until it is answered — where it can be counted, audited, and targeted for further reduction.

## Motivation

This grew out of a problem I hit while working on latent-world-engine (LWE), a personal project for leveraging AI in game development. Even with what seemed a very well-articulated spec, I was getting output from AI that shouldn't happen — ever. Eventually I realized it stemmed from an internal bias of the models being used: they want to jump to an "answer" as quickly as possible. That isn't inherently a bad thing, but it is when it means the clear process outlined by the user isn't actually being followed. It became clear that merely insisting in the prompts that the process be followed wasn't enough to completely prevent this. If I couldn't prompt around the problem, I needed another approach.

A short digression that turns out to matter: one of LWE's basic notions — a heuristic, really — is that complex things can generally be decomposed into simpler things, and that you can continue decomposing until you reach elements so simple that going further is infeasible or mostly unhelpful. At that point you have what amounts to an atomic component of a game. The motivation for this is that while gamedev is complex as a whole, an atomic component is relatively simple: it's easy to identify what objects of each component type look like, easy to construct new objects of that type, and — importantly — easy to verify correctness of form. Assuming that's right, and assuming the decomposition is possible, it follows that it should be possible to create games from the ground up leveraging AI, with the entire process supported by robust verification. I think the idea is valid — but AI's failure to consistently follow explicit procedure breaks it.

The way forward was to change the goal. Following the same heuristics LWE was built on, plus one more — that for any repeatable process, there should exist a recipe for doing it — the goal became not to have AI create the atomic elements themselves, but to have it create code that would generate those artifacts. Then erroneous output produces code, not content — and a problem in code is deterministic and repeatable: it can be discovered and fixed. So the new idea was to codify, to the extent possible. This also has a useful side-effect: codified work no longer needs reasoning, so as a byproduct of a more deterministic and reliable system, you're also minimizing token expense.

I can't be the only person running into problems like this, and generating code artifacts to do the thing — instead of just asking AI to do the thing — seemed like it could be useful in many situations, so I created this open-source tool. It uses a derivative of [project-spec-interrogator](https://github.com/gniht/project-spec-interrogator) to refine goals into contracts, then focuses on decomposition and the generation of code artifacts to build processes.

## Status

All five pipeline stages are built as Claude Code skills, and **the first complete end-to-end run finished on 2026-09-21**: [`runs/2026-09-09-job-search-triage/`](runs/2026-09-09-job-search-triage/). A loose wish, for something that finds jobs worth applying to without reading every posting, became a root contract, a 13-node tree with six leaves, 70 verification checks, and a standalone 581-line Python program. That program ran on live job boards. It confined its model calls to one leaf, which reads fields that some boards state only in prose, and made none during criteria evaluation.

The pipeline ran end to end, but the program it produced falls short in two ways.

- **It isn't fully codified.** It still made 46 model calls at run time, and a finished program should make none unless the user expressly permits them. Nobody permitted these.
- **It isn't correct.** The live run found four remote jobs silently judged not remote, because the contract required a common field *schema* but never said what a field's *values* may be. That passed all 70 checks, since every node satisfied its own contract. Verification checks code against contracts. It cannot check a contract against what its author meant, and only running on real data from two differently shaped sources exposed the gap. The [Stage 5 write-up](runs/2026-09-09-job-search-triage/stage-5-composition.md) has the details.

The run's findings were folded back into the spec and the stage prompts on 2026-09-25. Those revisions have not been exercised yet; the next run, on a different task, is what tests them.

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

- **The decision seam.** All judgment in generated code flows through one canonical function, `decide(request)`, which returns an answer a person has stored and never consults a model. Until a decision is answered, the program uses a declared fallback, and every value that came from one is marked as such. "How much judgment is left in this program?" stops being an opinion and becomes a count — determinism means zero decision points, checkable mechanically and attributable per site.
- **Judgment lives only in leaves.** Glue — the code that wires components together — moves data and never interprets it. Any judgment a build needs is pushed into a child contract, where the recursion can keep working on it. Codifying it away is therefore purely a question of how far decomposition pushes.
- **The contract is the only primitive.** One small declarative structure — inputs, outputs, and a required behavior clause — flows through every stage. There is no separate handoff format anywhere in the pipeline: the contract *is* the handoff.
- **Any stage may reject what it's handed.** A contract that can't be satisfied as wired is rejected rather than papered over, and a rejection always indicts the upstream author, never the rejecting stage. Errors surface where they were made.
- **The residue is a deliverable.** A run yields two things: the codified process, and the *residue* — the judgments that resisted codification, each with the argument for why. Irreducibility is a property of the information rather than of the model reading it, so the residue says something durable about the task itself. An entry must be earned (decomposition pushed to exhaustion) and is provisional until the user agrees there is no acceptable way around it.

## Files

- [`spec.md`](spec.md) — the architectural spec: goals, scope, the core data model, validation criteria, open questions
- [`design-journal.md`](design-journal.md) — contemporaneous record of the five stage builds, the runs, and the commitments that landed during each
- `.claude/skills/` — the five pipeline stages, each a self-contained stage prompt (`prompt.md`) wrapped by a thin Claude Code harness (`SKILL.md`)
- `runs/` — one directory per end-to-end attempt: a write-up for each stage, the artifact every stage emitted, and the composed program

Usage documentation will follow the first validated end-to-end run.
