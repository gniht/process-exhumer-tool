# Stage 4 — verification, 2026-09-21

Input: `codified-tree.json`. Output: `verified-tree.json`, checks in `verify/all-checks.json`,
harnesses in `verify/`. Every unit checked alone — leaves as code-against-contract, internal
nodes assume-guarantee.

**70 checks, 64 executed (91%), 6 static. 2 failures, 1 deferred. 11 of 13 nodes pass.**

| id | unit | name | verdict |
|---|---|---|---|
| n1 | node | (root) | pass |
| n2 | node | acquire_new_postings | pass |
| n7 | leaf | retrieve_from_source | pass |
| n3 | leaf | merge_corpus | **fail** |
| n4 | node | extract_fields | **fail** |
| n8 | node | extract_entry_fields | pass |
| n10 | node | derive_field | pass (1 deferred) |
| n12 | leaf | pluck_mapped_field | pass |
| n13 | leaf | infer_field_from_text | pass |
| n5 | node | assess_postings | pass |
| n9 | node | assess_entry | pass |
| n11 | leaf | evaluate_criterion | pass |
| n6 | leaf | summarize_criteria | pass |

Claim audit: **6/6 leaves clean** — every `determinism` and `ai_dependence` annotation matches
the AST. One seam call site in the tree, at `n13`, annotated once, claimed `ai_required`.

## The two failures

**`n3 merge_corpus` — closure, caught by execution.** Called twice on identical inputs, the
entries came back with different `retrieved_at` values. That is a wall-clock read, and the
contract grants no clock and declares no such effect, while the entry shape demands the field.
Codification flagged this when it wrote the leaf; verification confirmed it empirically rather
than taking the note on trust.

**`n4 extract_fields` — behavior, caught by assume-guarantee.** Children were granted their
contracts and the glue still failed: a corpus entry whose source is no longer in the configured
list makes `source_by_id[entry["source_id"]]` raise `KeyError`. Removing a source is ordinary
use, and the node's contract requires entry count and dispositions preserved for *all* entries,
so a run that dies on previously-stored postings cannot satisfy it. This is the defect
deliberately left in at Stage 2 to test whether Stage 4 would find it. **It did, by execution,
and for the right reason.**

## The deferred item — composition's watch list

One, at `n10 derive_field`: whether `infer_field_from_text`'s judgment returns a *correct* value
for an unmapped field cannot be known before the run environment supplies `ai()`. Everything
around the seam was verified — the mechanical text preparation, the fixed three-key return
shape, the verbatim-evidence demotion — but the judgment inside it is exactly the truth that
does not exist yet. Named, attributed to `n13`, carried forward.

## The finding verification did *not* flag, and should not have

`n7` drops postings whose published timestamp is absent or unparseable. Codification flagged
this as a probable cross-contract violation. Verification **passed it**, at `n7` and at `n1`,
and that is correct: `n7`'s contract is written wholly in window terms, so a timestamp-less
posting is not demonstrably "at or after window_start"; and the root's no-silent-drop clause
is scoped to postings that "fall within that source's recency window," which such a posting
provably does not.

So the code satisfies both contracts and the user's actual intent is still violated. **The
defect is in the root contract, not in anything the pipeline built from it.** This is a clean
demonstration of the framework's real boundary: verification checks code against contracts, and
cannot check a contract against what someone meant. The clause needs to be rewritten — postings
a source offers but that cannot be placed in time should be surfaced, not dropped — and that is
interrogator work.

Worth keeping as a standing example: three suspected defects went into this stage, and the two
that were *code* defects were caught by execution while the one that was a *contract* defect
passed every check. That is the system working as designed, and also the clearest statement of
what it does not do for you.
