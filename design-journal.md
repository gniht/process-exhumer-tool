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

**Correction 2026-10-04.** The note above misreads the leftover-reasoning test, as did run 2's own records. "Up-front" meant *while the program is being built*: a finished program should make no model calls unless the author expressly permits one. Extracting once per posting at intake reduced run 2's run-time calls but did not remove them, so it is not the right shape the note credits; it fails the test. Corrected with dated notes in the run's stage 1, 3 and 5 write-ups and in `source-shapes.md`.

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

**Completed 2026-09-21** — the first run through all five stages. The prediction held: the live run over Greenhouse and Lever made 46 seam calls, all at `n13`, which is exactly the count the contract implied, with none during criteria evaluation. The pipeline ran end to end, but those 46 calls are themselves a shortfall: nobody expressly permitted them (see the 2026-10-04 correction under Stage 1). The program is also not yet correct, and three defects remain in it. All three sit upstream of the code, so they were deliberately not patched into the artifact:

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

## 2026-10-04 — The decision seam replaces `ai()`

Prompted by correcting run 2's reading of the leftover-reasoning test. The author's principle, now stated outright: **a produced program never calls a model**, and codifying the whole process is always the aim. The `ai(instruction, payload)` seam, answered by a model at run time, is retired.

- **`decide(request)`** takes its place. A request carries a question written for a person, the shape an answer must take, the evidence, and a fallback. The runtime returns an answer the user has stored, or else applies the fallback; it never consults a model. Questions go out with a run and answers come back in on the next, so a program with decision points is still deterministic given its inputs and its stored answers.
- **Fallbacks are declared at codification**, from a closed set: `codified` (the nearest codifiable alternative, run as a stand-in, and the usual case, since by then the user has already declined it as the primary path), `unknown`, `set_aside`, and `stop` as the last resort. A fallback the contract cannot carry is a reject, and decomposition now gives conceded leaves outputs that can carry one.
- **A fallback must never look like a decision.** Every value obtained through `decide()` carries its source into the outputs, and every run reports how each decision point's decisions went.
- **Ratification becomes a choice**: adopt the nearest codifiable alternative (narrowing the contract), or keep the decision point with its fallback.
- **Wiring in a model is the user's act, outside the program.** Requests are structured, so they can be rendered for a person or for a model, and an answerer the user builds can fill the stored answers. The framework ships none.
- **Verification gets stronger.** With no model behind the seam, every leaf can be executed, decision points included; only how decision points fare on real inputs is deferred.
- **The interviewer asks the corrected question**: which judgment would still be needed at run time, and how it can be settled while the program is being built.

Not yet exercised. The job-triage redo will be the first run under it.

## 2026-10-08 — Job-triage v2, Stage 1

**Job-triage v2** (`runs/2026-10-08-job-triage-v2/`) revises run 2's contract into a version for real use: multi-user in structure, local storage, basic authentication, and as many configurable rules as the data supports. **Stage 1 cleared 2026-10-08** with two root contracts, `root-contract-refresh.json` (fetch and extract, shared) and `root-contract-assess.json` (one user's rules over the stored postings), whose shared interface, the stored postings, is stated in identical text in both. Accounts, sessions and the page are the host's, built outside the pipeline. The contracts address all three of run 2's defects:

- every field has a declared value space;
- undated postings are shown and marked;
- each source fails alone.

Run 2's model extraction is gone. The prediction is **zero decision points**: every field is structured data or text that plain pattern matching reads.

The interrogator's new item 7 ("move judgment into the build") was exercised for the first time and settled five recurring judgments as rules. The author improved one: an unstated pay period counts as yearly only above a per-currency floor, set at the minimum wage's full-time yearly equivalent.

## 2026-10-08 — Job-triage v2, Stages 2–3

**Stage 2** produced two trees: refresh has 14 nodes and 10 leaves, assess has 5 nodes and 3 leaves. The stored-postings interface is checked mechanically to be identical in both. Decomposition found two gaps in the root, which the author confirmed as amendments: the posting's link was missing, and the any/every rule for alternatives was scoped too wide.

**Stage 3: 13 leaves, all deterministic, zero decision points.** The prediction held. The judgment item 7 moved into the build now lives in tables in the code: countries, regions, level words and their exceptions.

That exposed a pattern worth carrying forward. Two leaf contracts promised what a name "denotes", which a table delivers only as far as its entries reach. By codification's own rule that is faked determinism. The remedy the author ratified is a narrower contract in which **the table decides**, stating both directions of its limit:
- a name the table lacks comes out unknown, which is shown by default;
- a table entry counts even where the text means something else by it.

Decomposition could write leaf contracts that way from the start whenever a leaf's behavior is a lookup. Not yet folded into the prompt; queued below.

## 2026-10-08 — Job-triage v2, Stage 4

**199 checks, 97% executed, 10 failures in 8 of 19 units, nothing deferred.** All 13 claim audits are clean. The failures fall into three kinds:

- **Code against contract (3).** Whitespace across inline HTML tags, spans into raw rather than converted text, and two salary statements sharing one pay-period window. Small re-codifications.
- **Open language, again (n10, n13, and two n8 wording conflicts).** Stage 3 cleared n10 and n13 because their word lists were closed, but each also carries an exclusion clause ("a word naming the subject of the work", "a mention of years that states no requirement") that no list can keep. Execution found inputs that get through. Stage 3's test for faked determinism should look for clauses like these, not only for verbs like "denotes".
- **Clauses dropped between leaf and root (both roots, and n6).** An iterative node that promises "the verdict of that rule" or "the extraction of its payload" names its child's result without restating it, so the root's clauses fall through a contract that flat verification can see. Separately, the narrowing ratified at stage 3 contradicts the "only where its meaning matches" clause in n6 and the root, which stage 3 missed. Assume-guarantee caught all three by reading, not execution.

The author took every recommended fix: contract wording in seven units (the refresh root among them), and five re-codified leaves. **Re-verified: 201 checks, 0 failures, 19 of 19 units pass, still zero decision points.** On the 45 fixture postings the fixed leaves give identical output to the old ones; the defects lived only in edge cases, which only hand-built inputs reached.

## Next

**First, the job-triage program made usable**: revise run 2's root contract (its three defects, the user's show/hide rules, no decision the user must answer on every run) and re-run stages 2–5 under the decision seam, with a way to use it day to day (a local web page is the current direction). **Then run 3, on a different task**, to exercise the 2026-09-25 and 2026-10-04 revisions on something whose defects aren't already known. Still queued:

- The subagent-isolation experiment: decompose run 2's root contract in an isolated context and diff the trees.
- The deferred interrogator refinements: entry-boundary input concreteness, a derivability check, and an AI-user front door.
- The residue-log decision (spec, Open Questions).
- From job-triage v2:
  - a cross-tree interface check in the decomposition harness;
  - a size criterion in the codify test;
  - for leaves whose behavior is a lookup, decomposition writes "the leaf's table decides" into the contract.
  - a clause-carry check in decomposition: every clause of a parent's behavior must follow from its children's contracts;
  - codification's faked-determinism test also looks for exclusion clauses in open language.
