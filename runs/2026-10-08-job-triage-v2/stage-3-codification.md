# Job-search triage v2 · Stage 3 (codification), 2026-10-08

Input: `node-tree-refresh.json`, `node-tree-assess.json`. Output: `codified-tree-refresh.json`,
`codified-tree-assess.json`, and the leaf sources in `leaves/refresh/` and `leaves/assess/`.
Language: python. Each leaf was written once, from its contract, with no refinement loop.

| tree | id | leaf | lines | determinism | `decide()` |
|---|---|---|---|---|---|
| refresh | n5 | fetch_source | 89 | deterministic | 0 |
| refresh | n7 | read_stated_text | 113 | deterministic | 0 |
| refresh | n8 | derive_geography | 450 | deterministic | 0 |
| refresh | n9 | derive_work_arrangement | 68 | deterministic | 0 |
| refresh | n10 | derive_employment_type | 81 | deterministic | 0 |
| refresh | n11 | derive_seniority | 49 | deterministic | 0 |
| refresh | n12 | derive_salary | 119 | deterministic | 0 |
| refresh | n13 | derive_years_of_experience | 41 | deterministic | 0 |
| refresh | n14 | read_posted_date | 68 | deterministic | 0 |
| refresh | n4 | merge_into_store | 52 | deterministic | 0 |
| assess | n5 | evaluate_rule | 140 | deterministic | 0 |
| assess | n3 | place_postings | 65 | deterministic | 0 |
| assess | n4 | diagnose_rules | 31 | deterministic | 0 |

**13 leaves, all deterministic, zero decision points.** The prediction made at stage 1, and
held through stage 2, survives codification. Run 2 at this stage had one model-call leaf and
46 calls on its live run.

## Mechanical checks run here

These are codification's own output rules, not verification:
- each entry point's parameters are exactly its contract's inputs, in order;
- no leaf calls `decide()` or any model;
- only standard-library imports;
- the network imports (`urllib`) appear only in `fetch_source`, the one leaf whose contract
  declares an effect;
- no `open`, `eval` or `exec`.

No leaf was executed against data; that is stage 4's job.

## Where the judgment went: tables

Item 7 of the interrogator, applied a level down. Each judgment that stage 1 moved "into the
build" now sits in a table in the code, written once and readable by a person:

- **`derive_geography` (n8):** most of its 450 lines are data:
  - ISO 3166 codes, with the names that denote each country alone;
  - US state names and postal abbreviations;
  - Canadian provinces and Australian states (so "New South Wales" is not read as Wales);
  - region names and synonyms;
  - each country's most specific regions.

  Ambiguous names are left out of the table rather than guessed: Georgia, Congo, Korea, Virgin
  Islands.
- **`derive_seniority` (n11):** a table of level words, plus phrases in which a level word is
  not a level ("Chief of Staff", "Staff Accountant", "Lead Generation").
- **`derive_employment_type` (n10):** the title words from the contract. "Contract" counts
  only when it is set off from the role, as in "Designer (Contract)" or "Designer – Contract",
  because "Contracts Manager" names the work, not the terms.

## The finding: two contracts say "denotes", and a table cannot fully deliver that

`derive_geography` counts a name "only when it denotes exactly one country".
`derive_seniority` counts a word only where it "denotes that level". Both phrases are open
language, and a table satisfies them only as far as the table reaches:
- "Staff Pharmacist" would be read as staff level, because that phrase is not in the exception
  list.
- "Lebanon, NH" would add Lebanon as well as the US, because Lebanon is also a town in New
  Hampshire.

By the codification prompt's own rule, a heuristic that passes as deterministic while failing
the behavior on part of the input space is faked determinism. Two remedies were open:

- **A decision point** with the table as its codified fallback. It would have to fire on every
  title and every location, a question on every posting, which defeats the program. In
  practice its fallback *is* the implementation.
- **A narrower contract** that the table satisfies outright: "a name in the leaf's country
  table" and "a word or phrase in the leaf's level table, outside its exception phrases". The
  table's limits become the contract's stated limits, and fixing a miss means editing a table,
  not adding judgment.

**Recommended: the narrower contract.** The tables are build-time judgment, reviewable like the
value maps in source definitions, which is where stage 1 said judgment belongs. Misses go in a
known direction. A name missing from the table comes out unknown, and unknown is shown by
default. A wrong entry comes out as a wrong value, and the only fix is the table, which a live
run will show. Put to the author for ratification.

### Ratified (author: "we'll go with the recommended option show by default")

The narrower contract, with unknowns shown by default. Every rule's `unknowns` already defaults
to `show` (stage 1, item 19), so a name or word missing from a table hides nothing unless the user
sets that rule to hide.

What changed:
- **`derive_geography` (n8):** countries are those named "by an entry in the leaf's country
  table". The table's construction rules (short forms in, names shared with a US state out,
  states imply the US, no cities) are now stated as how the table is built, not as what a name
  denotes. Regions are named "by an entry in the leaf's region table". The contract now states
  both directions of the limit: "a name it lacks gives nothing, even where a reader would
  recognise it, and an entry counts wherever it appears, even where the text means something
  else by it."
- **`derive_seniority` (n11):** levels are those named "by a word or phrase in the leaf's level
  table", with the table's exception phrases giving nothing. "A title is never assigned a level it
  does not name" is gone, because the table cannot keep that promise. In its place: "a level word
  in a phrase its exceptions lack counts as that level ('Staff Pharmacist' gives 'staff')."

Where the edit landed:
- Only these two leaf contracts changed, in `node-tree-refresh.json` and both codified trees.
- The parent, `extract_posting` (n6), keeps its contract and glue. It promises each value is
  "within its field's declared value space or null", and a table value still is.
  *Corrected at stage 4:* n6 also promises a board's value is mapped "only where its meaning
  matches", and so does the root. The narrowed contracts admit the opposite in so many words, so
  that clause no longer follows from the children. See `stage-4-verification.md`, failure C.
- The root contracts never said "denotes", so they are unchanged.
- The code is unchanged: it already was the table. It was re-checked mechanically against the
  narrowed contracts (same parameters, imports and zero `decide()`).
- The examples the new wording names were run once against the code to confirm the contract now
  describes it: "Staff Pharmacist" gives `staff`, and "Lebanon, NH" gives `LB` and `US`. This is a
  check that the wording matches, not verification.

Both narrowings are ratified, so nothing from this stage is left provisional.

`derive_employment_type`, `derive_work_arrangement`, `derive_salary` and
`derive_years_of_experience` do not have this gap: their contracts define their forms closed,
by listed words or a stated shape.

*Corrected at stage 4:* `derive_employment_type` and `derive_years_of_experience` do have this
gap. Each also carries an exclusion clause in open language ("a word naming the subject of the
work gives nothing", "a mention of years that states no requirement is not one"), and execution
found inputs the word lists can't keep out. See `stage-4-verification.md`, failure B.

## Readings verification should judge

1. **Codes in location text are matched upper-case only** (`n8`). The contract says location
   texts are read "whole words, case-insensitive". Read that way, "us", "in", "it" and "no"
   would be read as the US, India, Italy and Norway. The code matches the table's two- and
   three-letter codes in capitals only, so ordinary lower-case words are not read as countries.
   Names are matched case-insensitively, as written. This reading was not part of the
   ratification above, and the narrowed contract still says "case-insensitive".
2. **"Manager" counts from the word** (`n11`). "Product Manager" yields `manager`, because the
   value space is "levels named by title words". "Head of" and "Associate" yield nothing: no
   word in the vocabulary names them.
3. **A stipend range in the same posting makes the salary unknown** (`n12`). It is a second
   statement that disagrees on pay period, and the contract makes disagreeing statements
   unknown. Watch for this on live data.
4. **"Exactly its headers"** (`n5`) is read as no headers beyond the definition's. urllib's
   default `User-Agent` is removed. The transport's own `Host`, `Accept-Encoding` and
   `Connection` cannot be.
5. **Pay period "beside the figures"** (`n12`) is read as within 40 characters on the same
   line, before or after. Two different periods in that window give unknown.

## Flatness, again

Six leaves each carry their own copy of the path reader (`_read_path`), because none may
reference another. Composition nests them verbatim. This time all six are byte-identical
(checked by hash), unlike run 2's two walkers, but nothing enforces that.
