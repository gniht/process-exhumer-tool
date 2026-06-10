# Project Spec: Process Exhumer Tool

**Created**: 2026-06-04
**Status**: Draft

---

## Goal

A framework that takes a task or goal and "unearths" a process for accomplishing it programmatically — through recursive decomposition into atomic, contract-bound units of work, codification of each unit, and structural composition of the results. The longer-term ambition is that produced artifacts contain as little AI-call dependence as possible (ideally zero), so that work that was once judgment-based becomes reliably reproducible code.

---

## Success Criteria

**For v1 (Claude Code skill prototype):**

- [ ] Given an arbitrary task description, the framework can run end-to-end and produce: (a) a refined task spec from interrogation, (b) a decomposition into sub-tasks with assembly relationships and contracts, (c) generated code for each leaf, (d) verification results, (e) a composed result that performs the original task.
- [ ] The framework runs entirely within Claude Code using the user's Max plan; no external API costs.
- [ ] Each pipeline stage (interrogator, decomposition, codification, verification, composition) produces a cleanly extractable, structured output that does not depend on conversation context.
- [ ] The decomposition step explicitly produces (assembly_pattern, glue_code, sub_task_contracts) at each node — not just a list of sub-tasks.
- [ ] Verification operates on contract satisfaction — a leaf "passes" iff its generated code satisfies its declared contract.
- [ ] When a leaf cannot satisfy a deterministic contract, the framework either recurses on it or accepts the leaf with an explicit "requires AI" annotation in the contract. No fuzzy reducibility heuristics.
- [ ] The skill is structured to map cleanly onto a future MCP server architecture (explicit stage boundaries, structured outputs, no implicit context).
- [ ] At least one ad-hoc end-to-end run produces a result a non-technical observer would recognize as "the framework did what it was supposed to do."

**Broader vision (post-v1, informational):**

- [ ] Eventually rebuilt as a standalone MCP server + CLI, usable by anyone with any MCP client.
- [ ] Eventually supports AI-agent delegation as a first-class invocation pattern.
- [ ] Eventually viable on weak local models (e.g., Gemma ~4B) for structural-pattern-following portions of its work.
- [ ] Eventually grows a pattern library that calibrates pattern selection against accumulated outcomes.

---

## User Model

### Who Uses This

**v1 primary user**: the project author, exploring whether the framework's core abstractions hold up under real use. Working knowledge of Claude Code, comfortable with multi-turn dialog, familiar with the framework's design intent.

**Long-term users** (post-v1):
- Developers who want a structured way to derive programmatic implementations of recurring tasks.
- AI agents delegating sub-tasks to the framework as part of their own work.
- Anyone with an MCP client who wants to capture work-as-process rather than work-as-LLM-call.

### Entry Point

**v1**: User invokes the skill in a Claude Code session. The interrogator phase starts multi-turn dialog to refine the task; subsequent stages run in the same conversation (with optional subagent isolation for stages below interrogation, once prompts stabilize).

**Long-term**:
- Humans run a `process-exhume` CLI command.
- AI agents call MCP tools directly with structured task descriptions matching the framework's input schema.

### Key Workflows

1. **Task refinement.** Interrogator-style dialog (or schema-conformant input for AI agents) produces a clear spec for the work to be done.
2. **Decomposition.** The framework recursively decomposes the task. At each node it produces an assembly relationship, glue code, and contracts for each sub-task.
3. **Codification.** For each leaf, generate code that satisfies the leaf's contract.
4. **Verification.** Check that each leaf's code, and each composed node's code, satisfies its respective contract.
5. **Composition.** Assemble the verified leaves upward through the recursion into a working implementation of the original task.

### User Decisions

- The task to bring to the framework.
- During interrogation: how to clarify, refine, and bound the task.
- Whether to accept the resulting implementation, request revisions, or stop.
- (Post-v1) Configuration choices for the LLM backend and storage location.

### System Decisions

- The decomposition shape at each node (assembly pattern, sub-task structure, contracts).
- The implementation of each leaf, given its contract.
- Whether a leaf has satisfied its contract (verification verdict).
- Whether to recurse further on an under-satisfied leaf or accept with explicit AI dependence.

---

## Scope

### In Scope (v1)

- A Claude Code skill (or small set of related skills) implementing the framework's pipeline end-to-end.
- **Interrogator phase**: multi-turn dialog producing a structured task spec.
- **Decomposition phase**: contract-first decomposition producing (assembly_pattern, glue_code, sub_task_contracts) at each node.
- **Fixed assembly vocabulary**: sequential, parallel-and-combine, iterative, conditional, recursive-over-data, asymmetric-with-integration-subtask. Vocabulary is presented as **menu-as-hint** — the schema is fixed, the menu suggested, and novel patterns are allowed provided they satisfy the structural template.
- **Codification phase**: generate code for each leaf, constrained by the leaf's contract, with instruction to minimize AI dependence.
- **Verification phase**: check that generated code satisfies declared contracts.
- **Composition phase**: assemble verified results upward through the recursion.
- **Cleanly extractable per-stage prompts** — each stage's prompt can be lifted and run against a different model without rebuilding the framework.
- **Optional subagent invocation** from decomposition stages downward, to validate contract discipline once prompts stabilize.

### Explicitly Out of Scope (v1)

- **Standalone MCP server.** v1 runs only inside Claude Code.
- **Universal usability.** v1 requires Claude Code; non-Claude-Code users are not served.
- **Pattern library — any form.** No outcome capture, no retrieval, no stubs. Pipeline seams kept clean so a library can be added later without architectural surgery.
- **AI-delegation front door.** No structured invocation contract for external AI agents in v1.
- **Iterative refinement of leaves to remove LLM calls.** The model writes each leaf once with the instruction to minimize AI dependence. Iterative reduction is deferred (the "post-codification feedback" loop into decomposition).
- **Packaged outputs.** Generated code remains in-chat; not packaged into reusable MCP tools or installable artifacts.
- **Weak-model support (real).** v1 will be designed in ways consistent with weak-model usability (menu-as-hint, structured prompting, extractable stage prompts), but no weak-model testing or adaptation is *in* v1. Gemma testing happens post-build, not as a v1 requirement.

### Scope Risks

- **Pull toward "just a little library."** The library's value is tempting; we may be tempted to add capture-only logging or stubs "for later." We've decided against. Watch for this drifting back in.
- **Pull toward a privileged test case.** Ad-hoc runs during development are fine; enshrining one task as *the* validation target is not. Watch for "but it works great on X" being used to justify design choices.
- **Pull toward implicit context.** Decomposition is interface-first; each stage is extractable. Watch for prompts that quietly accumulate context-dependent behavior, which would block weak-model testing and MCP portability simultaneously.
- **LWE bias in the architecture.** The empirical input was a game-dev project. Post-build validation on diverse tasks is the check on how well we abstracted.
- **Conflating "the skill works" with "the architecture works."** v1 is a prototype. Its working does not prove the MCP-port version will. Both validations matter, separately.

---

## Constraints

- **v1 runs entirely inside Claude Code** under the user's Max plan. No external API calls, no per-token costs during development or use.
- **v1 must be designed for clean conversion to a standalone MCP server later.** This implies: explicit stage boundaries, structured outputs at each stage, no implicit conversation-context dependence, extractable per-stage prompts. The eventual conversion is a *rebuild informed by the skill*, not a refactor.
- **No new runtime dependencies for v1** beyond what Claude Code provides. The skill is markdown + structured prompting.
- **Interrogator phase must operate as multi-turn dialog with a human.** Subagent isolation is incompatible with this phase; interrogator stays single-context.
- **Decomposition and downstream stages may use subagents** to validate contract discipline once prompts stabilize. Default during early iteration is single-context; subagent invocation pulls in later.
- **Contracts are the framework's load-bearing primitive.** Anything that determines what a leaf must do, what assembly must produce, or what verification must check, is expressed as a contract.

---

## Core Data Model

*Resolved 2026-06-05 (v1 build session). This section answers the **contract data structure** and **interrogator → decomposition handoff** Open Questions, fixes the **per-stage prompt extraction format**, and pins the recursion model. The reasoning is recorded alongside the conclusions because the load-bearing part — *why the contract is this small* — is the part that drifts back toward complexity if it isn't written down.*

### The contract is the only primitive

A **contract** is a declaration of identity — *what a node is* — and nothing else. It is the single primitive that flows through every pipeline stage, and it is deliberately minimal:

```
contract = {
  inputs:  [ {name, type, description} ],   # resolvable; may be absent early
  outputs: [ {name, type, description} ],   # resolvable; may be absent early
  behavior                                   # REQUIRED: what must be true of outputs given inputs
}
```

- **`behavior` is the only required field** — the irreducible seed. A node can be processed with behavior alone; decomposition resolves I/O *from* it (it aims at the behavior and, in doing so, proposes an output shape). With no behavior there is no target to aim at, which means there is no task.
- **`inputs`/`outputs` are resolvable, monotonically.** A contract may enter a stage under-resolved and leave it more resolved; resolution only ever increases down the tree. By the time a leaf reaches codification its I/O must be concrete.
- **The contract describes *shape*, never *content*.** "Find the interesting clusters" has output shape `set of {cluster, description}` even though the count and contents are unknown. Most "I don't know the output" is really "I don't know the contents" — which the contract never claimed to know.
- **`type` may be prose** ("a list of integers") in v1. Formal types belong to the MCP / weak-model era.

Each field earns its place by one test: *which downstream stage consumes it, and would that stage break without it?* Fields that failed the test were cut — and they live elsewhere (below), where they are actually produced.

### What the contract deliberately does NOT contain

- **No `id`.** Identity-of-position belongs to the **node**, not the declarative spec. A contract must stay liftable — runnable against another model with no tree context. A positional id would smuggle tree-context into the contract and break under re-decomposition (the framework's main loop).
- **No `determinism` field.** Whether a unit reduces to deterministic code is *discovered during codification*, not authored up front (the abandoned `"undecided"` value was the tell). It is a result annotation.
- **No `verification` field.** The `behavior` statement *is* the acceptance criterion. Verification is a stage that *reads* `behavior` and checks it — not data written twice.

The rule: the contract is purely declarative ("what must be true"). Anything about *how it is checked*, *how it is built*, or *what happened when it ran* lives outside it.

### Node and result records

The contract is wrapped by a **node** — the tree element — which carries everything that is *not* identity:

```
node = {
  id,                  # stable, opaque handle (NOT a positional path)
  contract,            # the declarative spec above
  # once decomposed:
  assembly_pattern,    # how children combine (from the assembly vocabulary, or novel)
  glue,                # wiring; references children by LOCAL names
  children,            # each child is itself a node
  # once codified (leaf):
  code,                # generated implementation
  result               # verification verdict, determinism outcome, failures
}
```

- **`id` is on the node, opaque, position-independent.** Re-decomposition shifts positions; references must survive it. A display path can be computed by walking the tree — it is a *view*, never the identity.
- **`glue` references children by local names** scoped to the parent, not global positions — so wiring also survives re-decomposition.
- **`result` is where outcome / failure history lives** — keyed *to* the contract's handle, never stored *inside* the contract. The post-v1 outcome-tracker aggregates across result records at this seam, *by reference*. Complexity accretes *around* the contract, never *in* it. (This is the home for the user's "track failure modes and learn from them" intuition — outside the contract, by design.)

### The recursion: one mechanism, two answers

The contract tells a node *what it is*. The node then asks two questions, which are the two halves of decomposition:

- **"What am I made of?"** → the parts → child contracts.
- **"How do you build me?"** → the process → `assembly_pattern` + `glue`.

They are distinct but produced together, and they feed each other bidirectionally: parts can reveal an assembly, **or an assembly pattern can generate the parts it needs** (choosing *iterative* yields "the per-item operation" as the child; choosing *asymmetric-with-integration* introduces an integrator child that is a product of the build strategy, not a piece of the goal). The assembly vocabulary is therefore a **generative lens**, not a post-hoc label.

**Codify vs. decompose is one mechanism, different trigger** — the base and recursive cases of "how do you build me?":
- answerable directly in code → **leaf** (codify),
- answerable only as parts-plus-assembly → **node** (decompose, recurse).

### Glue is deterministic — judgment lives only in leaves

*(Resolved 2026-06-09, decomposition-stage build.)* Glue moves data: it calls children, loops, branches on mechanical predicates, reshapes results. It never interprets, scores, or chooses by meaning — any judgment the build needs is pushed into a child contract, where it stays contract-bound and the recursion can keep working on it. This is what makes the termination rule meaningful: AI-dependence can only ever live in leaves, so reducing it is purely a question of how far decomposition pushes.

A corollary pins **monotonic resolution** concretely: a contract's I/O *surface* (entry names and arity) is fixed by whoever wires it — the parent's glue, at child creation; only a root contract may arrive with absent I/O for a stage to propose. Downstream stages sharpen types and descriptions but never add, remove, or rename entries. A contract that cannot be satisfied with the I/O it was granted is **rejected** (a third stage outcome alongside codify/decompose), sending the caller back to re-decompose the parent rather than papering over the mis-wiring.

### The AI seam — judgment in code has one name

*(Resolved 2026-06-09, codification-stage build.)* All judgment in generated code flows through a single canonical function: `ai(instruction, payload) -> value`. The `instruction` is **static** — written at codification time, contract-shaped (what must be true of the return given the payload, including the return's shape); runtime data travels only in `payload`. Codification never implements `ai()`; the run environment supplies it at composition time (in v1, e.g., a `claude -p` subprocess under the Max plan — preserving the no-API-cost constraint).

The seam is what makes the framework's goal *operational* rather than aspirational: **determinism outcome = zero seam calls** — a count, not an opinion. AI-dependence becomes visible per call site, mechanically detectable by verification, and annotatable in the node's `result` record (one entry per site: the judgment, and why it is irreducible). "Deterministic" means *free of judgment*, not free of declared effects — a leaf that fetches a URL its contract declares is deterministic in this sense.

The **calling convention** is fixed alongside it, shared by glue and leaf code: a codified leaf is one entry-point function whose parameters are the contract's input names in order; one declared output returns bare, several return a map keyed by output names, none returns nothing. Local wiring names bind at composition, so leaf code stays nameless — flat and liftable, like its contract.

### Verification is local — assume-guarantee over contracts

*(Resolved 2026-06-09, verification-stage build.)* Verification never needs the tree: every node is verified flat. A **leaf** is checked as code-against-contract (surface, closure, seam discipline, behavior — executed where an environment exists). An **internal node** is checked **assume-guarantee**: *granting each child its contract, does the glue satisfy the parent's?* Child implementations are not its input — the child's own verification covers them — which is what makes internal nodes verifiable before composition exists, from nothing but their own decomposition record. The original workflow's wrinkle ("check each composed node's code" before a composition stage has run) resolves to: local verification pre-composition, end-to-end observation at composition.

Verification's boundary is the seam: it checks **everything except the inside of `ai()` calls** — including auditing codification's determinism claims as counts — and records seam-interior aspects as **deferred to the run**: named, attributed to their call sites, never silently passed. The deferred list is composition's watch list. Verdicts are **fail-closed** (a checkable aspect whose satisfaction cannot be determined fails, with the uncertainty recorded), and every check carries its `method` — `executed` vs. `static` — so a verdict's strength is its evidence.

Two pipeline-wide patterns are now explicit: **every stage may reject the contract it is handed** (the interrogator's out-of-domain gate, decomposition's and codification's and verification's `reject`), and a rejection always indicts the upstream author, never the rejecting stage.

### Composition is mechanical — the pipeline's own deterministic leaf

*(Resolved 2026-06-09, composition-stage build.)* Composition is specified as a deterministic algorithm, not a judgment task: one module-level function per node (qualified name = `<wiring-name>__<node-id>`, root uses `root`), signatures derived from contracts, leaf code nested verbatim inside its wrapper (helper collisions impossible), child wiring names bound to qualified names in the parent's body, `self` bound to the node's own function under `recursive-over-data`, returns appended per the calling convention, and a JSON-stdin/stdout shell on the root. The leaf entry point is identified mechanically — the function whose parameter list equals the contract's input names in order. **Composition never patches:** any structural hole is a reject naming the node and the owning stage. A model executes the algorithm in v1, but this is the first stage expected to become pure code in the MCP era.

The **seam runtime is composition's input, not its invention**: `ai_runtime` code satisfying the seam-runtime contract — return the instruction-declared shape; log every call as one JSON line `{caller, instruction, payload, return}` (the caller's qualified name carries the node id, so attributing run-time judgments to nodes is mechanical); fail loudly on nonconformance, never coerce. v1 ships a `claude -p` reference runtime in the stage harness (Max plan — the no-API-cost constraint holds at run time too). **Assembling is the stage; running is the orchestrator's** — the MCP-era `compose` tool returns an artifact, and executing it on real inputs (feeding seam observations back into result records, settling verification's deferred list) is harness work, like the tree-walk.

### Where the goal lives

The declared goal — *minimize AI-call dependence* — does **not** shape the contract. The contract is goal-neutral. The goal lives in the recursion's **termination rule**: keep pushing "how do you build me?" downward until the answer is deterministic code, or you have isolated an irreducible AI-required leaf (accepted with an explicit annotation). Loading the goal into the contract would put it in the wrong place.

### Handoff: there isn't a separate one

The interrogator emits a **root contract**. Decomposition consumes a contract and emits `(assembly_pattern, glue, child_contracts)`. The same primitive flows end-to-end, so there is no distinct interrogator → decomposition handoff schema to define — **the contract *is* the handoff.**

### Per-stage prompt extraction format

Each pipeline stage is a self-contained, model-agnostic prompt expressed as a markdown file with three delimited sections:

- **`## Input`** — the schema of what the stage consumes (in terms of the contract / node model above).
- **`## Output`** — the schema of what the stage must produce.
- **`## Prompt`** — the liftable instructions.

A stage prompt restates the slice of the data model it needs so it stays liftable standalone (this prioritizes extractability over DRY, per the spec's stated requirement). In the v1 Claude Code skill, this prompt is `prompt.md`, and a thin `SKILL.md` wraps it for in-session invocation. The split is deliberate: `prompt.md` is the thing that ports to another model or a future MCP tool; `SKILL.md` is the Claude-Code-specific harness around it.

### Recursion mechanism (post-v1 MCP) — kept open by design

For the eventual MCP server, the recursion is **not** carried by the MCP re-invoking itself, nor by agents-all-the-way-down. The MCP stays **flat**: stateless stage-tools (`decompose` / `codify` / `verify` / `compose`) over contracts. The tree-walk is an **orchestration concern** the MCP does not own — the default carrier is a deterministic control loop (best for determinism, weak-model viability, cost, debuggability). Agents enter only as a possible *implementation of a hard stage* (where decomposing or codifying a node needs tool-use and experimentation), never as the recursion topology. This decision does not block v1: keeping v1 stages flat and typed keeps all orchestration architectures reachable later.

---

## Validation Criteria

| Component | Validation Method |
|-----------|-------------------|
| Interrogator | Produces a structured task spec from vague input. The spec contains enough to drive decomposition without re-asking the user. |
| Decomposition | At each node, output includes (assembly_pattern from the menu OR a novel pattern satisfying the template, glue_code, sub_task_contracts). Output is structurally valid even when contents are novel. |
| Codification | Each leaf's generated code references only its declared inputs and produces its declared outputs, conforming to its contract. |
| Verification | Detects contract violations: wrong output shape, AI calls in code that should be deterministic, missing required behavior. |
| Composition | Assembled code runs end-to-end on the original task; results match the spec. |
| Stage-prompt extractability | Each stage's prompt can be lifted out and run against a different LLM with the same expected input shape. |
| MCP-portability | A human reviewer can mentally map each skill stage to a planned MCP tool with a clear input/output schema. |

Validation does NOT include a privileged test task. Ad-hoc runs during development are ephemeral and should rotate through different tasks. Post-build validation runs multiple diverse tasks chosen *after* v1 stabilizes. Weak-model viability is checked by lifting per-stage prompts and running them against a local Gemma ~4B model, also post-build.

---

## Open Questions / Unknowns

- [ ] **Tag vocabulary and consistency.** Tags are the load-bearing piece for any future pattern library. v1 doesn't need them, but the post-v1 library has to address: where the vocabulary comes from (fixed taxonomy / free-form / LLM-derived / multi-dimensional), how consistency is enforced across runs, who generates tags, how decomposition-time tag assignment couples to decomposition quality.
- [x] **Interrogator → decomposition handoff schema.** ~~The shape of the structured spec the interrogator produces, and what decomposition consumes.~~ **Resolved (2026-06-05):** there is no separate handoff — the interrogator emits a root contract; decomposition consumes a contract; the contract is the handoff. See **Core Data Model**.
- [x] **Contract data structure.** ~~"A contract" is treated as a primitive throughout this spec but its concrete shape isn't decided.~~ **Resolved (2026-06-05):** `behavior` (required) + resolvable `inputs`/`outputs`; identity only; no `id`/`determinism`/`verification` fields. See **Core Data Model**.
- [ ] **What counts as "the model cannot produce a deterministic implementation."** The decision rule for whether to recurse further or accept an AI-dependent leaf. Now framed as the recursion's **termination rule** (see Core Data Model → *Where the goal lives*). **Partially addressed (2026-06-09):** the v1 rule ships in the decomposition stage prompt as the *strict-progress test* — decompose only if glue is deterministic, every child's behavior is strictly narrower than the parent's, and remaining judgment is confined to strictly narrower children; degenerate decompositions (restated parent, re-partitioned judgment, "everything else" child) force a leaf. The *measurement* side is now crisp (2026-06-09, codification build): determinism = zero `ai()` seam calls, counted mechanically. The *decision* side — whether a given seam call is genuinely irreducible — still relies on the model's own judgment; a tighter check remains open.
- [ ] **Outcome-tracker library design.** The shape of the eventual v2 outcome-tracker — data model, storage location (per-project / per-user), integration points. Its **seam is fixed**: it aggregates across node `result` records by reference (see Core Data Model → *Node and result records*); the internals remain open.
- [ ] **Resolution / task-shape menu.** A post-v1 question surfaced 2026-06-05: recurring task or contract-resolution shapes may eventually warrant their own *menu-as-hint* (mirroring the assembly vocabulary), and later feed the outcome-tracker. Deliberately not built in v1 — kept on the right side of the "no pattern library" scope line.
- [ ] **Recursive self-application.** Whether the framework's own pipeline can produce parts of itself. Not a v1 goal but worth holding as a longer-term question. **First concrete instance identified (2026-06-09):** the composition stage is specified as a fully deterministic algorithm — the pipeline's own "irreducible leaf" that turned out to be codifiable — and is the natural first candidate to be replaced by generated code.

---

## Assumptions

- **For anything reliably accomplishable, a process exists.** The foundational philosophical premise behind the framework's value prop. If false, the framework's reach has a hard ceiling.
- **A strong model (Claude Code's underlying model) can reliably perform decomposition, contract generation, and codification at the quality the architecture requires.** v1's pipeline assumes this.
- **Accurate tagging of tasks is achievable, mostly, with LLM assistance.** (User-flagged.) The post-v1 pattern library depends on this; v1 does not, but the library's eventual usefulness is contingent on it.
- **The fixed assembly vocabulary covers most real-world decomposition shapes.** If many real tasks require novel patterns, the menu-as-hint approach still works but loses much of its weak-model accessibility benefit.
- **Generated code can be verified against contracts in a tractable way.** Verification is load-bearing in this architecture; if contract checking is hard or unreliable, the termination story falls apart.
- **Claude Code's multi-turn dialog facility is suitable for the interrogator phase.** No UX work is in v1; the skill leans on Claude Code's existing dialog handling.

---

## Assumptions NOT Made

- **The framework will work with weak models out of the box.** Designed for it (menu-as-hint, structured prompting), but not assumed; explicitly testable post-build.
- **Novel assembly patterns will emerge frequently.** Allowed, but the bet is that most tasks fit the fixed vocabulary.
- **Users have technical expertise.** Interrogator should handle vague, non-technical task descriptions; expertise is not a prerequisite.
- **The pattern library is necessary for v1 to provide value.** v1 ships without one; the bet is that strong-model reasoning + clean architecture is enough for initial usefulness.
- **The skill version will become the MCP server version through refactoring.** Acknowledged as a rebuild, not a refactor.
- **Specific tasks define success.** No privileged test case; success is judged by post-build diverse-task validation.

---

## Notes

Architecture and design emerged from a multi-turn interrogator session on 2026-06-04 with the project author. Empirical input was the author's prior project (latent-world-engine), particularly the experience of using structural skeletons + per-cell AI generation as a partial reduction of AI dependence in game-dev content generation. Many of the framework's load-bearing ideas — interface-first decomposition, contracts as termination criterion, the fixed assembly vocabulary, menu-as-hint prompting, MCP server as the long-term primitive, classical-recursion-only model — were resolved during that session.

The full interrogation conversation contains additional context worth preserving for future reference, including: why MCP was chosen over Claude Code skills as the long-term primitive; why the pattern library was decomposed into "fixed vocabulary in v1" vs. "learned outcome-tracker post-v1"; why classical recursion was preferred over the originally-considered dual decomposition+reduction model; and why contract satisfaction replaces the criterion-(4) reduction heuristics.
