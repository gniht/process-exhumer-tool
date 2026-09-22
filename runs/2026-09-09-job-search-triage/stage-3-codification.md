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
