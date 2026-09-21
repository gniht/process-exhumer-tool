# Run 2 — job-search triage · Stage 1 (interrogator), IN PROGRESS

**Started** 2026-09-09. **Paused** mid-dialog, before draft contract. No contract emitted yet.

Second attempt at a completed end-to-end run. (Run 1, 2026-06-09, aborted at stage 1 when
the author withdrew the LWE task.) The author chose this task explicitly as a *modest* one —
"may not be an ideal test of the tool but at least it'll be something" — and noted that
arriving without a formed idea is itself a test of stage 1's clarity-building half.

Against the run-2 task criteria in the project memory: **foreign territory** ✅ (not LWE),
**bounded instance** ✅. **Inputs-in-hand** ⚠️ unresolved — that is open question B below.

## Task as given

> "some kind of tool to assist with job search activities" → narrowed by the author to:
> "something that can identify jobs i might want to apply for, so i don't have to read
> through a bunch of job postings ... it should be configurable ... a first step might be
> something that just fetches new job posts and does some analysis on them. the analysis
> part is probably what we'll want to be able to configure/adjust later."

## Settled in dialog

1. **Behavior is not "predicts what I'd want."** That is only checkable by reading the
   postings — i.e. by redoing the work the tool exists to avoid. Reframed toward *faithful
   assessment against stated criteria, grounded in specific evidence from the posting text,
   nothing discarded without a recorded reason*. Author did not confirm in so many words but
   built on it ("precisely because of what you noted in (1)"), so: accepted implicitly —
   **re-confirm on resume before emitting.**

2. **The false-negative asymmetry.** Stated goal is *not reading a bunch of postings*, so the
   costly failure is the invisible one: a wanted job silently discarded. A false positive
   costs seconds of reading; a false negative costs the job and is never observed. Behavior
   and output shape both have to answer to this.

3. **Criteria are a configurable input, and that is not deferrable.** The author's own
   argument, and it is stronger than the one offered: *because* "jobs I might want" cannot be
   defined up front, it has to be resolved by **iterative refinement** — so the tool is the
   instrument by which the unknown gets defined. Configurability is therefore the mechanism,
   not a feature. A baked-in-criteria contract and a criteria-as-input contract are different
   contracts; building the first and wanting the second means redoing the tree.

4. **"New" is a parameter, not a value.** Author: could mean since-last-search, could mean
   last-couple-months if no recent search. "Defining 'new' is less important at this stage
   than building a mechanism in which it can be defined." Same move as (3) — fix that it is
   configurable, leave the value open.

5. **Retrieval is probably in scope.** Stage 1 recommended scoping the root to
   *given a batch of postings, assess them* and treating acquisition as separate plumbing.
   The author did not take that off-ramp — responded with "we'll have to figure out where
   we're fetching from and know the shape of that data." Read as leaning in-scope, but
   **not explicitly confirmed — settle on resume.**

## Open — resume here

**A. Where does the refinement loop live, inside the contract or outside?** Three options put
to the author, materially different contracts:

- *You refine* — criteria are data the human edits between runs; each run applies them
  faithfully and stops there. Cleanest, fully checkable.
- *It refines* — tool learns criteria from the human's reactions. Returns "did it work" to
  the unverifiable swamp of (1). Stage 1's position: avoid.
- *You refine, it hands you the material* — applies criteria faithfully **and** reports where
  they broke down: undecidables, near-misses, criteria that never discriminated, terms in
  postings no criterion mentions. Changes nothing itself. **Recommended** — keeps behavior
  checkable, converges the loop faster, and is the direct attack on the false-negative
  asymmetry, since the near-misses and undecidables are where a silently-dropped good job hides.

**B. Source class — poll-it-yourself or hand-it-a-file?** The specific board can stay open;
the *kind* cannot, because it fixes the input shape and decomposition stalls without it.
Network retrieval brings credentials, rate limits, and site-terms questions; a file-shaped
input (export, saved search, paste) brings none. This is also the run's **input-concreteness**
question — the one run 1 died on, so do not let it slide.

**C. Cross-run memory — flagged, folding in unless the author objects.** "New since our last
search" means the tool remembers: a watermark or a seen-set. That has to be a declared
**input** (what did we see last time) *and* a declared **output** (what have we seen now), or
the mechanism (4) asks for has nowhere to stand.

## Contract sketch (NOT the handoff — pending A/B/C)

- `inputs` — source spec (shape depends on B); recency spec; criteria (structured, human-editable); prior seen-state
- `outputs` — per-posting assessment carrying its evidence and reason; the refinement-material report (if A = third option); updated seen-state
- `behavior` — every retrieved posting in the window is assessed against the supplied criteria; each verdict cites specific posting content; no posting is discarded without a recorded reason

## Stage-1 observations (for the deferred interrogator-refinement pass)

- **Cold start worked.** The author had no idea at all. Asking for *a repeated judgment you'd
  recognize the result of but can't write the rule for* — rather than "what do you want to
  build" — produced usable raw material in one turn. Candidate list to react against beat
  open generation, which was the author's stated sticking point.
- **Pre-emptive steering earned its keep.** Warning early that persuasive-writing outputs
  (cover letters, tailored résumés) pass the shape gate but fail the checkable-behavior gate
  appears to have kept the task off that rock without the author ever proposing it.
- **"A tool for X" is a product category, not a unit of work.** Naming that immediately, and
  asking *which* unit, did real work. Likely a general opening move worth encoding.
- **The author out-argued the stage on configurability** — and the better argument (refinement
  as the mechanism of definition, since the target cannot be specified up front) is worth
  encoding: when behavior resists definition, ask whether the contract's job is to *apply* a
  definition or to be the *instrument that discovers* one.
- **Still unexercised**, as after run 1: the out-of-domain gate, the draft-confirm loop, and
  contract emission. Stage 1 remains partially exercised, not validated.

---

# STAGE 1 COMPLETE — 2026-09-21

Contract confirmed by the author ("sounds correct ... go for it") and emitted to
`root-contract.json` in this directory. That file is the handoff to decomposition.

**First full exercise of stage 1.** Run 1 reached only the dialog phase. This run exercised
the out-of-domain gate (stable output shape — assessed set + updated corpus every run, only
contents vary → in domain), the draft-confirm loop (three drafts, each materially revised by
author pushback), and contract emission. Stage 1 is now validated end-to-end.

## How the contract moved (the drafts are the evidence)

- **Draft 1** — criteria as an acquisition filter; assess what you fetch; three separate
  pieces of state (fetch-state, assessment-state, corpus).
- **Draft 2** — author's insight: storage is free, so fetch everything and filter
  non-destructively over the store. Criteria move *off* the intake path. Three state pieces
  collapse to one: **the corpus is the memory**, watermarks derivable from what it holds.
- **Draft 3 (final)** — author's methodological correction (below): the seam fires **once per
  posting at intake, to extract fields**; criteria then evaluate over those fields as ordinary
  code. Evidence-citation moves to extraction-time provenance (field ← span), which the
  deterministic criteria path inherits for free. Dispositions (viewed/suppressed) join the
  record; suppression hides from presentation, never from storage, and is reversible by
  construction.

## Decisions the author made against stage-1 recommendation

- **Cross-source job identity: declined.** Stage 1 argued identity was needed or the seen-state
  would leak. Author's counter held: per-source watermarks already give cross-*run* memory, so
  cross-source identity only buys not-seeing-it-twice-in-one-batch. Deferred, and correctly
  identified as becoming load-bearing only when tracking what has been *applied to*.
- **Refinement loop: outside the contract** (author edits criteria; tool never learns them).
- **Criteria diagnostics: kept** (stage-1 call the author accepted). Third diagnostic —
  recurring posting terms no criterion mentions — deliberately cut; it is the only support for
  the "criterion you didn't know you had" moment, and the cheapest thing to add after real output.

## Observations for the deferred interrogator-refinement pass

- **Cold start works.** Author had literally no idea. Asking for *a repeated judgment you'd
  recognize the result of but can't write the rule for* — instead of "what do you want to
  build" — produced usable material in one turn. Candidate-list-to-react-against beat open
  generation, which was the author's stated sticking point. Encode as the opening move.
- **"A tool for X" is a product category, not a unit of work.** Naming that immediately and
  asking *which* unit did real work. General opening move.
- **Pre-emptive gate steering earned its keep.** Warning early that persuasive-writing outputs
  (cover letters, résumés) pass the shape gate but fail checkable-behavior kept the task off
  that rock without the author ever proposing it. Consider encoding as a standing warning.
- **The author out-argued the stage twice, and both are worth encoding.** (1) *When the target
  cannot be defined up front, the contract's job may be to be the instrument that discovers the
  definition, not to apply one* — which makes configurability the mechanism, not a feature.
  (2) *Destructive vs. reversible filtering*: a false negative is only permanent at acquisition;
  keep the destructive side dumb and put all judgment on the reversible side. Both generalize
  well beyond this task.
- **NEW, and the sharpest correction of the run — the leftover-reasoning test.** Author:
  "the budget for reasoning is almost entirely up-front ... any left-over budget in reasoning
  likely represents a failure of this skill." Stage 1 had priced assessment as a per-run
  judgment cost (N postings x M criteria seam calls per pass) and treated it as a caching
  problem for stage 2. That was the wrong architecture, not a real constraint. The correct
  shape — seam once at intake to extract, deterministic code forever after — is *discoverable
  at stage 1* and materially changes the contract's outputs (provenance on extracted fields).
  **Candidate stage-1 probe: "which parts of this must a model still decide at run time, and
  can that judgment be moved to a one-time extraction?"** Highest-value refinement item from
  this run; arguably belongs in the stage prompt rather than the backlog.
