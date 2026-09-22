# Stage 5 — composition, 2026-09-21

Input: `verified-tree.json` (13/13 pass, gate clear). Output: **`job_triage.py`** — 581 lines,
one self-contained file, standard library plus the seam runtime. Entry `root__n1`, JSON on
stdin, JSON on stdout. **The file is the deliverable.** It needs the `claude` CLI on PATH,
because one leaf is ai_required; nothing else.

Assembly was mechanical throughout: 13 node functions named `<wiring-name>__<id>`, children
before parents, leaf code nested verbatim, glue verbatim, seam runtime inserted once.
Composition patched nothing.

## The live run

```
python3 job_triage.py < inputs.json > outputs.json 2> seam.log
exit 0, 4m19s
```

Two live sources (Greenhouse/GitLab, Lever/Spotify), 7-day window, empty corpus, three
criteria chosen to exercise both branches of `derive_field`: `title contains "Engineer"`
(mapped on both sources), `remote eq True` (mapped on Lever, unmapped on Greenhouse),
`salary_floor gte 150000` (unmapped on both).

**29 postings retrieved, stored, extracted, assessed. 46 seam calls — exactly the predicted
count** (17 Greenhouse × remote + 29 × salary_floor). All 46 returns conformed to the declared
three-key shape. Every criterion discriminated; `salary_floor` came back not-answerable on all
17 Greenhouse postings, which is correct — Greenhouse postings do not state pay.

### Realized AI-dependence

**46 calls, all at `n13`, zero anywhere else.** The shape is the thing worth recording: once per
posting per field that posting's source does not state structurally, and **zero on every
criteria evaluation**. Re-running against changed criteria over the same corpus costs nothing
unless the criteria name a field never extracted. The leftover-reasoning test, measured.

### The deferred item, settled

Seam-interior correctness was the one thing verification could not check. Observed, and it
holds: `salary_floor` values trace to real compensation text (`$156,800`, `Salary Range
$120,400`), `remote` values to real location text (`Remote, Canada`, `remote role`). No
fabricated provenance survived — the verbatim-location rule would have demoted it, and nothing
needed demoting. **This assessment is judgment, not execution.**

## The run's real finding: the common schema is common in name only

Four Lever postings whose `workplaceType` is literally `"remote"` — including *Backend
Engineer, Personalization* — were reported **not_satisfied** against `remote eq True`.

The cause is a value-space collision nothing in the tree owns. `remote` arrives as a `bool` from
Greenhouse and a `str` from Lever, because the two paths that produce fields do not agree on a
value space and nothing requires them to:

- `pluck_mapped_field` returns the source's **raw** value, uncoerced — `"remote"`, `"hybrid"`.
- the seam returns a **normalized** value, because its instruction asks for the field's value and
  a model naturally answers `true`.

So the *deterministic* path is the one that failed to normalize, and the judgment path is the one
that got it right. The criterion then compared `"remote" == True` and returned `not_satisfied`.

This is precisely the failure the whole design was organized against: **a silent false negative.**
Not `not_answerable`, which would have shown up in the diagnostics and prompted a fix — a
confident, wrong "no". The user would never have seen those four jobs and would never have known.

**Where the defect lives:** the root contract says fields are extracted "into a common schema"
and never says what a field's *values* may be. Decomposition then built a tree where common
means common field *names*. The fix is a contract change — declare a value space per field —
plus either coercion in `pluck_mapped_field` or a normalization step the tree currently lacks.
It is interrogator-and-decomposition work, not a patch to the artifact.

Note what found it: not verification, which passed all 70 checks, because every node satisfied
its own contract. **Only running the thing on real data from two different sources exposed it.**
That is the argument for this stage existing, and it is the second contract-level defect this
run has surfaced that no amount of local checking could reach.

## Other run findings

**No per-source error isolation.** Ashby 403s under the `Python-urllib` User-Agent while serving
curl fine (verified directly). It was dropped from the run because including it would have
**killed the whole run** — `retrieve_from_source` lets `HTTPError` propagate and `acquire_new_postings`
has no per-source guard, so one unreachable source loses every other source's postings. The
source definition also carries no request headers, so a source needing a User-Agent cannot be
configured at all. Both are decomposition gaps.

**Two composition-spec conflicts, handled and worth fixing in the prompts.**

1. *Who owns the return statement.* Composition's wrapper spec appends a return built from the
   contract's outputs, but decomposition's glue already ends in one, so the appended return would
   be dead code. The composer detects a trailing `Return` and skips. The stage prompts disagree;
   decomposition's "glue must finish by producing the parent's outputs" reads as "bind the names,"
   while the return convention for *children* invites glue to return too.

2. *Seam attribution is defeated by verbatim nesting.* The reference runtime takes
   `inspect.stack()[1].function` as `caller`, which is supposed to carry the node id. But leaf code
   is nested verbatim inside its wrapper, so the immediate caller is the leaf's **inner** entry
   function (`infer_field_from_text`) — unqualified, no node id. Two leaves sharing an inner entry
   name would be indistinguishable in the log. The runtime here walks the stack for the nearest
   `__n<id>` frame instead, which restored mechanical attribution: all 46 lines logged as
   `infer_field_from_text__n13`. **The reference runtime in the Stage 5 SKILL should be corrected.**

## Verdict

Would a non-technical observer say the framework did what it was supposed to? **For the pipeline,
yes.** A vague wish — "something that finds jobs I'd want so I don't read every posting" — became a
contract, a 13-node tree, six leaves, 70 executed checks, and a standalone 581-line program that
ran on live data and produced evidence-cited assessments with one model call per unstated field.

**For the program, not yet** — and for a reason the framework surfaced rather than hid. It silently
mis-judged four remote jobs, which is the exact failure the user spent an hour designing against.
The run says so, in the root's result record, rather than reporting success.
