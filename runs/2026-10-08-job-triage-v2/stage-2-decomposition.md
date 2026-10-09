# Job-search triage v2 · Stage 2 (decomposition), 2026-10-08

Input: `root-contract-refresh.json` and `root-contract-assess.json`, two root contracts and so two
trees. Output: `node-tree-refresh.json` and `node-tree-assess.json`. Language: python.

- **Refresh:** 14 nodes, 10 leaves, depth 4.
- **Assess:** 5 nodes, 3 leaves, depth 3.

Both are well inside the harness guards (25 nodes, depth 5). Every leaf was declared with
`codify_basis` deterministic; none was conceded.

```
refresh                                   assess
n1  [sequential]          (root)          n1  [sequential]        (root)
  n2  [iterative]         fetch_sources     n2  [iterative]       evaluate_rules
    n5  LEAF              fetch_source        n5  LEAF            evaluate_rule
  n3  [iterative]         extract_fetched   n3  LEAF              place_postings
    n6  [sequential]      extract_posting   n4  LEAF              diagnose_rules
      n7  LEAF            read_stated_text
      n8  LEAF            derive_geography
      n9  LEAF            derive_work_arrangement
      n10 LEAF            derive_employment_type
      n11 LEAF            derive_seniority
      n12 LEAF            derive_salary
      n13 LEAF            derive_years_of_experience
      n14 LEAF            read_posted_date
  n4  LEAF                merge_into_store
```

## The shapes, and why

**Refresh fetches, then extracts, then merges.** Extraction runs only on postings fetched in this
run, and each is extracted under the source definition it was just fetched with. Entries from a
failed source, or from a source no longer in the list, keep the extraction they were stored
with. That removes run 2's stage-2 wiring defect by construction: run 2's glue looked up every
stored entry's source definition and crashed when a source had been removed, while this glue
only looks up sources that are in the list it was given.

**Extraction is one leaf per field family, called in dependency order.** `derive_geography`
runs before `derive_salary` because a bare `$` reads as USD only when the posting's only country
is the US. The glue calls each child once and assembles the record; nothing in it interprets.

**"Maps only where the meaning matches" became data.** A source definition's locators for work
arrangement and employment type carry a `values` map from board values to declared values. A
board value missing from the map stays unmapped (unknown, raw value kept). The judgment that
Lever's "Permanent" says nothing about hours is made once, by whoever writes the source
definition, and no code makes it at run time. This is item 7 of the interrogator applied a
level down.

**Assess is deterministic throughout**, decomposed only for size. `evaluate_rule` carries the
semantics: four test kinds, alternatives, and the region hierarchy. `place_postings` carries
visibility, reasons and order, and `diagnose_rules` the counts. The watched-sources filter
stayed in the root glue, because it is a membership test.

## Resolved at this stage (the author should see these)

Each one sharpens the root without contradicting it.

1. **Regions are stored as stated, plus each listed country's most specific regions. Containment
   is applied when a rule is tested.** A posting in Germany stores `europe`, and a rule on
   `emea` matches it. A posting stating only "EMEA" tested against a rule on `europe` gives
   *can't tell*, because an EMEA role may or may not hire in Europe. Storing every containing
   region instead would have made exclude rules fail silently: a German posting would hold
   `{europe, emea}`, and "exclude europe" needs every value to match.
2. **Salary is a range only.** A single figure is not read as a salary (stage-1 item 11: "a
   regular `$X – $Y` range"). That keeps stipends and budgets out. Several ranges that agree on
   currency and period are spanned; ranges that disagree make the salary unknown.
   **Structured salary fields (Lever `salaryRange`, Ashby `compensation`) are not read**, because
   both are empty in every fixture and so untestable. A source definition can add them as
   locators once a board is seen using them.
3. **Full text is kept as pieces** (Lever states it in five places). A keyword is searched in
   each piece, and a phrase does not span two pieces. This also keeps each match's evidence to
   one payload path and one span.
4. **Fetch failures are strict.** A response element without an ID fails the whole source rather
   than being skipped. A malformed response must never mark that source's stored postings
   *no longer listed*. A repeated ID keeps its first occurrence.
5. **Geography reads no city names, and skips ambiguous codes.** "CA" and "IN" are both US state
   abbreviations and country codes, and "Georgia" is both a state and a country, so none of them
   counts from location text. A US state named in full, or by a postal abbreviation that is not
   also a country code ("TX", "NY"), implies the US. Lever's `country` field is an ISO code by
   declaration and is read as one.
6. **Work arrangement and employment type:** the first locator in the definition's order that
   yields a mapped value decides. Otherwise a fallback reads the text: location words for
   arrangement, title words for employment type. A text naming two arrangements gives unknown,
   and no word never means onsite.

## Root amendments (author: "confirmed")

Resolving the shapes concretely exposed two gaps in the stage-1 contracts. Both files are
amended, and the stage-1 record notes both.

- **`link` added to the declared fields.** The page needs a posting's address to send the user
  to it. Every board states one (`absolute_url`, `hostedUrl`, `jobUrl`), but the root's field
  list omitted it. Without it, the assessment records give the host nothing to link to.
- **The any/every rule now names its fields.** The root said that wherever a field holds several
  values, an exclude rule is met only when every value meets it. That is right for
  alternatives (countries, regions, seniority, a salary range) and wrong for values that
  describe the posting together:
  - Lever states department "Engineering" and team "Experience". "Exclude team Experience" would
    then never hide that posting, because "Engineering" does not match.
  - Full text read as several values breaks the same way: an excluded keyword would have to
    appear in every piece.

  Stage-1 item 23 had limited the rule to countries and seniority; the root generalised it when
  the contract was written. The amendment restores what was agreed.

## Findings

**1. The harness has no notion of an interface between trees.** Decomposition is flat: one
contract in, one decision out. Two root contracts resolved separately could each sharpen the
stored-postings shape in a different direction. That is the class of defect run 2 shipped, and
nothing in the harness would notice. Here the shared descriptions were written once and
generated into every contract that uses them, and an assertion checks that both roots carry the
same text. A task with more than one root needs that check in the harness, not in the operator's
care.

**2. The codify test has no size criterion.** Read literally, step 1 ("answerable directly as
deterministic code? → codify") makes the whole assess root a leaf, because none of it is
judgment. It was decomposed anyway. The prompt's "straightforward code" and the README's "small
enough to implement directly" both imply a size bound, and a 300-line leaf is the hardest thing
for codification to write and for verification to check. The prompt should state the bound.

**3. Decomposition caught two intent defects in the root, because it had to write shapes
concretely.** Neither was a satisfiability problem, so the reject gate did not apply. Both are
stage-1 writing errors (an omission, and an over-generalisation of what was agreed). Run 2's
value-space defect went the other way: it passed through every stage because no stage had to
state what a field's values are. Here the declared value spaces forced the issue.

**4. Flatness was not achieved, again.** This ran in the same context as the stage-1 dialog,
and the region and salary resolutions draw directly on it. The subagent-isolation experiment
stays queued.

**5. Flat contracts repeat the shared shapes.** Every contract that touches a stored posting
restates the full posting shape so it can be read alone, which makes the refresh tree about
126 KB. That is the cost of flatness and is acceptable. It is worth knowing before contracts get
larger.

## Deferred to real use (for composition's watch list)

- **Whether each board returns its complete list.** A truncated response would mark real
  postings *no longer listed*. Run 2 fetched all three boards without paginating, but nothing
  has confirmed that Lever's default response is complete for a large board.
- **How often each field comes out unknown on live data**, per board. This is the measure of
  whether the value maps and text readers are good enough. Unknowns are shown by default, so a
  high rate costs attention, not missed postings.

**Prediction unchanged: zero decision points.** Every leaf is declared deterministic.

## Amended at stage 3 (author ratified)

Codification found that `derive_geography` (n8) and `derive_seniority` (n11) promised that a
name or word "denotes" a country or level, which a table can deliver only as far as its entries
reach. The author ratified the narrower contracts: the leaf's table decides. Only those two
behaviors changed in `node-tree-refresh.json`. The parent's contract and glue still hold as
written. See `stage-3-codification.md`.

Composition's watch list gains one item: **table misses and wrong entries on live data**,
meaning names or level words the tables lack (these come out unknown and are shown) and entries
that match something else (a town that shares a country's name, a level word in a phrase the
exceptions lack).
