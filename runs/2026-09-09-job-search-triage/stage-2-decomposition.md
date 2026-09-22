# Stage 2 — decomposition, 2026-09-21

Input: `root-contract.json`. Output: `node-tree.json`. Language: python.
**13 nodes, 6 leaves, max depth 5** — inside the harness guards (25 nodes / depth 5),
though depth sits exactly at the boundary.

```
n1  [sequential]                (root)
  n2  [iterative]               acquire_new_postings
    n7  LEAF                    retrieve_from_source
  n3  LEAF                      merge_corpus
  n4  [iterative]               extract_fields
    n8  [iterative]             extract_entry_fields
      n10 [conditional]         derive_field
        n12 LEAF                pluck_mapped_field
        n13 LEAF                infer_field_from_text
  n5  [iterative]               assess_postings
    n9  [iterative]             assess_entry
      n11 LEAF                  evaluate_criterion
  n6  LEAF                      summarize_criteria
```

## The shape, and why

The root is a **sequential** chain: acquire, merge, extract, assess, summarise. Suppression
filtering stayed in the root's glue — it is a membership test over a recorded boolean, which
is mechanical, so it needed no child.

Three of the five root children are **iterative** over the obvious collection (sources,
corpus entries, criteria), and their glue is a loop plus collection. The only structurally
interesting node is **n10 `derive_field`**, a **conditional**: where the source definition
declares a locator for a field, the field is plucked deterministically; where it does not,
it is read from the payload's text. The branch predicate — `field in field_map` — is
mechanical, so the conditional is legitimate glue rather than disguised judgment.

That node is the whole determinism story. **`n13 infer_field_from_text` is the only leaf
that should need `ai()`**; the other five should codify to zero seam calls, including
`n11 evaluate_criterion`, which is operator-and-value comparison over already-extracted
fields. That matches the prediction recorded at the end of Stage 1.

## Findings

**1. A real wiring defect, left in deliberately.** `n4`'s glue does
`source_by_id[entry["source_id"]]`. If a source is removed from the configured list while
entries retrieved from it remain in the corpus, that raises `KeyError` and the run dies —
and removing a source is a normal thing to do. The contract does not say stored entries must
outlive their source definition, but it does say the corpus is the run's only memory and that
prior entries are preserved, so a run that crashes on last month's postings violates it.

It is left in the emitted tree rather than quietly patched, because **whether Stage 4 catches
it is a test of Stage 4**. This is assume-guarantee verification's home ground: granting each
child its contract, does `n4`'s glue satisfy `n4`'s? It does not. If verification passes this
node, that is a verification defect worth more than the fix.

**2. Flatness was not achieved, and could not have been.** The harness requires each node be
decomposed from its contract alone — no tree context, no conversation history. The contract
was honoured; the conversation history was not, and could not be: this stage ran in the same
context that had just spent an hour discovering that extraction should be field-mapping first
and seam second. `n10` is precisely that insight. It is *also* derivable from the contract
alone — the contract does say field_map locators exist and that provenance must be recorded —
so the structure is defensible on its own terms. But this run cannot be used as evidence that
it would have been found flat.

That is the exact experiment the spec reserves for **subagent isolation**, and this run is a
concrete argument for pulling it forward: single-context decomposition cannot demonstrate
contract discipline, only fail to. Worth running this same contract through an isolated
subagent later and diffing the trees.
