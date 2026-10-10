# Stage 3 — codification, 2026-09-21

Input: `node-tree.json`. Output: `codified-tree.json`, leaf sources in `leaves/`.
Language: python. Each leaf written from its contract alone, once, no refinement loop.

| id | leaf | determinism | seam sites |
|---|---|---|---|
| n7 | retrieve_from_source | deterministic | 0 |
| n3 | merge_corpus | deterministic | 0 |
| n12 | pluck_mapped_field | deterministic | 0 |
| n13 | infer_field_from_text | **ai_required** | **1** |
| n11 | evaluate_criterion | deterministic | 0 |
| n6 | summarize_criteria | deterministic | 0 |

**6 leaves, 5 deterministic, 1 seam call site in the whole tree.**

## The prediction held

Stage 1 predicted a fully deterministic criteria-evaluation path with extraction as the sole
`ai()` leaf. That is what codification discovered, without being told: `n11
evaluate_criterion` — the node that decides whether a posting meets a criterion, which is the
tool's entire apparent purpose — came out as an operator table over already-extracted values.
Zero judgment. The judgment all collected in `n13`, and only on the branch where the source
declined to state the field structurally.

This is the author's leftover-reasoning test surviving contact with implementation: the
composed program should spend model calls only on fields a source left to prose, once per
posting per unstated field, and never again on any later criteria change.

*Correction, 2026-10-04.* The author's test is stricter than this reading. "Up-front" meant
while the program is being built, so a finished program should make no model calls unless the
author expressly permits one. Confining the calls to one leaf was progress; it did not pass the
test. See the correction in `stage-1-interrogation.md`.

## The seam

One instruction, static, contract-shaped. Payload carries `field` and `posting_text`; the
posting text is produced mechanically (unescape, strip tags, collapse whitespace) so the seam
sees prose rather than a source's envelope. The return shape is fixed at three keys — `value`,
`stated`, `evidence` — and is consumed mechanically: `evidence` is located verbatim in the
text to produce a character span, and **a value whose evidence cannot be found verbatim is
demoted to not-stated**. The model cannot manufacture provenance that is not in the payload.

## Findings

**1. A contract gap, discovered here and not fixable here.** `n3 merge_corpus` must produce
corpus entries carrying `retrieved_at`, because the entry shape says so — but its contract
grants no clock, and codification may not add inputs. The implementation reads
`datetime.now(timezone.utc)`, which is an **undeclared effect** and a genuine violation of
"closed over its contract." The honest alternatives were worse: emit `None` into a field the
shape requires, or reject the leaf and send Stage 2 back. Recorded rather than papered over —
verification should catch it, and the real fix belongs upstream, either granting a clock input
or dropping `retrieved_at` from the entry shape.

**2. `n7` silently drops timestamp-less postings.** A posting whose published timestamp is
absent or unparseable cannot be placed inside or outside the window, so it is skipped. That is
faithful to *this leaf's* contract, which is written entirely in terms of the window — but it
is exactly the silent-drop failure the root behavior forbids. The contradiction is real and
sits between two contracts, which is where assume-guarantee verification should find it.

**3. `n11` answers "incomparable" with not_answerable.** When a stated value cannot be compared
with the criterion's operator (a string salary against a numeric floor, say), the verdict is
not_answerable rather than an exception or a false negative. Defensible — not-answerable means
"cannot tell from this posting" and this cannot tell — but it is an interpretation the contract
did not dictate, so it is flagged. An unknown *operator*, by contrast, raises: that is a
malformed criterion, not an unanswerable posting.

**4. Flatness produced duplicate code, as designed.** `n7` and `n12` each contain their own
`_resolve` locator walker, independently written, because leaves are codified in isolation and
neither may reference the other. They are not identical. Composition nests leaf code verbatim
into per-node wrappers, so the duplication is harmless — but it is the first concrete instance
of the cost flatness buys, and worth watching as trees grow.

---

## Residue backfill — 2026-10-09

Run 2 predates the residue fields (`cause`, `nearest_codifiable_alternative`) and the
ratification gate. This records the backfill of its one entry, `n13`, and the gate's **first
live use**. Written in run 2's vocabulary, where the seam was `ai(instruction, payload)` and a
seam call meant a model call at run time; the seam has since become `decide(request)`, a
question for a person.

**Outcome: the alternative was adopted. The claim does not stand, and run 2's residue list is
empty.** `cause` was `unstructured_encoding` — the fact is in the payload, but only as prose.

**Writing the nearest alternative out refuted the entry's own argument.** Stage 3 had claimed a
pattern-matcher would "silently report 'not stated'" for phrasings it failed to enumerate —
absence reported where the text speaks, the one failure the behavior forbids. That assumes a
**two-state** extractor. A three-state one does not have the flaw:

1. value parsed → return it
2. an amount found but not resolvable → `stated: false`, provenance naming the span it could
   not parse
3. no amount found → `stated: false`, payload genuinely silent

State 2 is a *flagged* gap, not a silent one: detecting that a posting discusses pay is far
cheaper than parsing the figure out of it, and the original claim missed that asymmetry.

**The author's argument, which flat codification could not have made.** This leaf's consumer is
a triage tool with plural criteria, so a posting that satisfies every other criterion and comes
back `not_answerable` on one surfaces for a human glance that settles it in seconds. The cost of
an unknown is a few seconds of attention, not a lost posting. Coverage is therefore the seam
call's only advantage over deterministic extraction — and the dimension that matters least.

Generalized: **a leaf reaching for the seam is implicitly pricing an unknown, and a flat stage
cannot see what an unknown costs downstream.** The information has to travel in the contract, so
the fix belongs at stage 1.

**The claim was then checked against the recorded calls, and it failed.** `seam.log` holds all
46 with payloads and returns, so the deterministic alternative is measurable against the model's
own output rather than against a guess:

- **`salary_floor`, 29 calls, 12 stated.** Every evidence span is a plain currency amount
  (`$71,200`, `$139,000 — $220,000 USD`, `Salary Range $120,400`, `$132,948–$189,927`). A
  currency regex taking the minimum plausible value scored **12/12 exact** on the low end the
  model picked, and **0/17 false positives** on the calls it called silent.
- **`remote`, 17 calls, 17 stated, all `True`.** Spans are a closed vocabulary: `Remote, Canada`
  (Greenhouse's own `location.name`), `all-remote`, `All of our roles are remote`.

**One design correction the data forced.** 11 of the 17 silent `salary_floor` postings carry
compensation keywords with zero amounts — GitLab boilerplate discusses total rewards without
stating a figure. Triggering state 2 on *keyword presence* would fire on 11/17 and bury the user
in "go look" for postings that state nothing. **State 2 must trigger on an unparseable amount,
never on a keyword.** Defined that way it fires zero times here, which is correct: it is a
safety valve for phrasings outside the vocabulary, not a routine path.

**Structural check, which ruled out a configuration-only fix.** Salary is prose-only across all
three boards — Ashby carries a `compensation` object but Linear leaves it unpopulated
(`shouldDisplayCompensationOnJobPostings: false`), Greenhouse has no salary field, Lever no
`salaryRange`. Meanwhile `remote` is structural everywhere but **never a boolean**:
`isRemote: true`, `workplaceType: "hybrid"`, `location.name: "Remote, Bangalore"`. That second
finding is the value-space defect, and it sits in the *mapped* path (`n12`), not here — `n13`
never sees the postings it spoils.

**What the gate proved.** A model was one step from ratifying a claim that a model is
indispensable, on inherited evidence, with the alternative never attempted. "Ratified by the
user, not asserted by a model" is the rule that caught it.

**Not re-codified.** The follow-on this queued was superseded by job-triage v2
(`runs/2026-10-08-job-triage-v2/`), built on fresh contracts rather than by patching run 2, and
already deriving salary and work arrangement deterministically with every field inside its
declared value space. Run 2's tree stays as the historical record.
