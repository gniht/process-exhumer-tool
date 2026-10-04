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

Built at `.claude/skills/process-exhumer-interrogator/` (single-context human dialog → root contract). First live exercise 2026-06-09, in a run aborted when the author withdrew the task mid-interrogation: the dialog phase behaved as designed per the author's assessment (pushback, surfacing the contract-shaping fork, probing input concreteness), and stopping rather than inventing a contract is a legitimate stage-1 exit. Refinement is deferred until after a completed end-to-end run.

**Validated 2026-09-21** in the second e2e run (`runs/2026-09-09-job-search-triage/`), which exercised the parts run 1 never reached: the out-of-domain gate, the draft-confirm loop, and contract emission. The draft-confirm loop earned its keep — three drafts, each materially revised by author pushback. Two of the corrections came from the author rather than the stage, and both generalize: **destructive vs. reversible filtering** (a false negative is only permanent at acquisition, so keep the destructive side dumb and put the judgment on the reversible side — this collapsed three pieces of state into one), and the **leftover-reasoning test** ("the budget for reasoning is almost entirely up-front; any left-over budget in reasoning likely represents a failure of this skill"), which caught the stage pricing assessment as a per-run seam cost and deferring it to Stage 2 as a caching problem. That was the wrong architecture rather than a real constraint: the right shape — seam once per posting at intake to extract fields, deterministic code thereafter — was discoverable at Stage 1 and changed the contract's outputs. Queued as the highest-value refinement item, and a candidate for the stage prompt itself rather than the backlog.

### Stage 2 — decomposition

Built at `.claude/skills/process-exhumer-decomposition/`. The stage prompt is *flat* (one contract in → `codify` | `decompose` | `reject` out, no tree context); the recursion is a worklist loop owned by the `SKILL.md` harness, mirroring the planned MCP shape (stateless stage-tools, tree-walk as orchestration). Two commitments landed here and are recorded in the spec's **Core Data Model**: *glue is deterministic — judgment lives only in leaves*, and the codify-or-decompose decision is the *strict-progress test*. Untested, like Stage 1.

**Exercised 2026-09-21** in run 2: 13 nodes, 6 leaves, depth 5 (exactly the harness limit), with judgment landing where Stage 1 predicted. It misfired in two ways. It invented a `retrieved_at` field the root contract never asked for and nothing ever read, which is what forced a clock read at Stage 3. It also ran in the same context as the interrogation, so the run cannot show that the tree would be found from the contract alone. That is the experiment the spec reserves for subagent isolation, and run 2 is an argument for pulling it forward. The live run later traced two of the program's three remaining defects partly or wholly to decomposition (see run 2 below).

### Stage 3 — codification

Built at `.claude/skills/process-exhumer-codification/`. Flat stage prompt (one leaf contract in → `codified` | `reject` out); the loop over leaves lives in the harness. The commitment that landed here, recorded in the spec's **Core Data Model**: the **AI seam** — all judgment in generated code flows through one canonical `ai(instruction, payload)` function, so *determinism = zero seam calls*, a count rather than an opinion. The calling convention (entry-point signature from the contract; bare / dict-by-name / nothing returns) is fixed alongside it. Untested, like the others.

**Exercised 2026-09-21** in run 2: five of six leaves came out deterministic, and the one seam site landed at `n13 infer_field_from_text`, matching Stage 1's prediction without being told. Its one miss: `merge_corpus` read the wall clock, an undeclared effect, and was written with a note rather than rejected. That cost a verification cycle to learn what a reject would have said immediately.

### Stage 4 — verification

Built at `.claude/skills/process-exhumer-verification/`. Flat stage prompt (one unit in → `verified` verdict | `reject` out), two unit types: leaves checked as code-against-contract, internal nodes checked **assume-guarantee** (granting each child its contract, does the glue satisfy the parent's?) — which is what makes the whole tree verifiable before composition exists. Commitments recorded in the spec's **Core Data Model**: verification checks *everything except the inside of the seam* (seam-interior truths are **deferred to the run** — named, never silently passed); verdicts are *fail-closed* with per-check `executed`/`static` evidence labels; and *any stage may reject the contract it is handed*, always indicting the upstream author. Untested, like the others.

**Exercised 2026-09-21** in run 2: 70 checks, 64 executed. It caught both code defects, the clock read by execution and a wiring defect deliberately left in at Stage 2 by assume-guarantee. Both were resolved by re-decomposition rather than patching. It correctly *passed* a third suspect, postings dropped for lacking a timestamp, because that defect is in the root contract. That is the clearest instance yet of the stage's boundary: it checks code against contracts, never a contract against what its author meant. It also showed that checks are written against a contract and must be regenerated, not replayed, when the contract changes.

### Stage 5 — composition

Built at `.claude/skills/process-exhumer-composition/`. The stage prompt is **deliberately mechanical**: one function per node (qualified `<wiring-name>__<id>` names), contract-derived signatures, leaf code nested verbatim, wiring names bound in parent bodies, `self` bound under `recursive-over-data`, a JSON-stdin shell on the root — and *composition never patches*: every hole is a reject naming the owning stage. The seam runtime is an **input** (v1 ships a `claude -p` reference implementation in the harness); the harness runs the artifact on real inputs, feeds seam observations back into result records by node id, and settles verification's deferred list. Recorded in the spec as the pipeline's own deterministic leaf — the first stage expected to become pure code in the MCP era.

**Exercised 2026-09-21** in run 2: assembled `job_triage.py` (581 lines) mechanically, patched nothing, and settled verification's one deferred item on the live run. It surfaced two conflicts in its own spec: whether glue or the wrapper owns the return statement, and a reference seam runtime that attributed calls to the leaf's inner function rather than its node. It also found the run's most important defect, which had passed every check.

## Pipeline complete — next

The pipeline is complete. Next: the **first ad-hoc end-to-end run** — rotate through small, diverse tasks (no privileged test case, per the spec's scope risks), exercise all five stages, and let the failures drive the first refinement pass. The deferred interrogator-refinement requirements (entry-boundary input concreteness, derivability check, AI-user front door) are queued behind that.

## 2026-09-21 — Runs

Run records live under `runs/`, one directory per end-to-end attempt: the dialog record and per-stage artifacts, including the emitted contract that hands off to the next stage.

**Run 1** (2026-06-09, LWE content generation) — aborted at Stage 1 when the author withdrew the task mid-interrogation. Not kept as a directory; recorded in the Stage 1 note above.

**Run 2** (`runs/2026-09-09-job-search-triage/`) — job-posting triage. Chosen deliberately as a modest task after the author could not find an ideal one, and started with no formed idea at all, which made the cold start itself a test of Stage 1. **Stage 1 cleared 2026-09-21**; `root-contract.json` is the handoff. Stages 2–5 are next and remain untested.

The contract carries a prediction worth checking downstream: the criteria-evaluation subtree should come out **fully deterministic — zero seam calls** — with field extraction as the sole `ai()` leaf. That exercises the determinism claim and verification's claims audit on a real case rather than a contrived one.

**Completed 2026-09-21** — the first run through all five stages. The prediction held: the live run over Greenhouse and Lever made 46 seam calls, all at `n13`, which is exactly the count the contract implied, with none during criteria evaluation. The pipeline did its job. The program it produced is not yet correct, and three defects remain in it. All three sit upstream of the code, so they were deliberately not patched into the artifact:

- **Value spaces.** The contract required a common field schema but never said what values a field may take. Lever's `remote` is mapped and plucked raw as the string `"remote"`, while the seam answers `true` for Greenhouse. So `remote eq True` silently failed four remote Lever jobs, which is the one failure the contract was designed against. It passed all 70 checks. Interrogator and decomposition work.
- **Postings without a timestamp are dropped.** The root's no-silent-drop clause covers only postings inside the recency window, and a posting with no timestamp provably is not inside it. The code satisfies both contracts, and the user's intent is still violated. Interrogator work.
- **One unreachable source kills the run.** There is no per-source error isolation, and a source definition cannot carry request headers. (Ashby returns 403 to Python's default User-Agent and was left out of the run for that reason.) Decomposition work.

Two of the three are contract defects that no local check can reach. The first surfaced only because the live run used two differently shaped sources, which is why composition now requires at least two structurally different instances.

The run's residue is one entry: `n13`, reading a named field from posting prose where the source gives no structural locator for it. The entry predates the 2026-09-25 residue vocabulary, so it carries no `cause` and has not been through ratification. It stands as provisional.

## 2026-09-25 — Run-2 learnings folded into the stages

Commit `beee5ff`. The spec states the principle; the stage prompts and harnesses carry the mechanics.

- **The residue is a deliverable** (spec: Goal; Core Data Model). Out-of-domain exits, rejects, and seam residue are one family, places where process gives out. A run reports them as its second output rather than as shortfalls. Entries must be earned, stay provisional until the user ratifies them, and a not-derivable output is always a reject, never residue.
- **Every stage prompt restates the goal in one line.** This lands the item queued under Stage 1 as the highest-value refinement: run 2 lost the goal mid-sentence at Stage 1, and nothing downstream would have caught it.
- **Codification** owns the residue vocabulary (a closed `cause` set, plus `nearest_codifiable_alternative` so a concession states its trade-off) and puts each seam site to the user for ratification. Its reject gate now covers ambient capabilities (clock, randomness, network, filesystem, environment) and outputs not derivable from the granted inputs.
- **Decomposition** records `codify_basis`, meaning whether a leaf was reached because code suffices or by concession, and its glue owns the return statement.
- **Composition** appends no return and rejects glue that does not return. Its reference seam runtime attributes each call by walking to the nearest `__n<id>` frame. A live run needs at least two structurally different instances and reports the residue and a differential check across them.
- **Verification** regenerates checks after a contract change instead of replaying them.

None of this has been exercised yet.

## Next

**Run 3, on a different task**, to exercise the 2026-09-25 revisions. It should not be a re-run of run 2, whose known defects would leak into the dialog. Still queued behind it:

- Fixing run 2's program, starting from the root contract (the three defects above).
- The subagent-isolation experiment: decompose run 2's root contract in an isolated context and diff the trees.
- The deferred interrogator refinements: entry-boundary input concreteness, a derivability check, and an AI-user front door.
- The residue-log decision (spec, Open Questions).
