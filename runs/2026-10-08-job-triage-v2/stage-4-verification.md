# Job-search triage v2 · Stage 4 (verification), 2026-10-08

Input: `codified-tree-refresh.json`, `codified-tree-assess.json`. Output: `verified-tree-refresh.json`,
`verified-tree-assess.json`, every check in `verify/all-checks.json`, the harness in `verify/`
(`python3 verify/run_all.py` reruns it). Each unit was checked alone: a leaf as its code against
its contract, an internal node as its glue against its contract given its children's contracts.

**199 checks, 195 executed (97%), 4 static. 10 failures, 0 deferred. 11 of 19 units pass.**

Of the 195 executed checks, 57 are the harness reading each unit's code (surface, closure, seam,
glue_determinism, wiring, pattern). The other 138 ran the unit's own code:
- **Leaves** ran on the 45 saved fixture postings from run 2 (Greenhouse, Lever, Ashby) for
  typical input, on hand-built cases for each clause, and on shapes unlike either to test for
  overfitting.
- **`fetch_source`** ran against a local HTTP server.
- **Glue** ran against stub children that keep their contracts and record how they were called.

The 4 static checks are the assume-guarantee arguments, which are reasoning over contracts.

| tree | id | unit | name | verdict | checks | fails |
|---|---|---|---|---|---|---|
| refresh | n1 | node | (root) | **fail** | 6 | 1 |
| refresh | n2 | node | fetch_sources | pass | 6 | 0 |
| refresh | n5 | leaf | fetch_source | pass | 15 | 0 |
| refresh | n3 | node | extract_fetched | pass | 5 | 0 |
| refresh | n6 | node | extract_posting | **fail** | 7 | 1 |
| refresh | n7 | leaf | read_stated_text | **fail** | 15 | 1 |
| refresh | n8 | leaf | derive_geography | **fail** | 26 | 3 |
| refresh | n9 | leaf | derive_work_arrangement | pass | 8 | 0 |
| refresh | n10 | leaf | derive_employment_type | **fail** | 9 | 1 |
| refresh | n11 | leaf | derive_seniority | pass | 8 | 0 |
| refresh | n12 | leaf | derive_salary | **fail** | 25 | 1 |
| refresh | n13 | leaf | derive_years_of_experience | **fail** | 8 | 1 |
| refresh | n14 | leaf | read_posted_date | pass | 8 | 0 |
| refresh | n4 | leaf | merge_into_store | pass | 9 | 0 |
| assess | n1 | node | (root) | **fail** | 6 | 1 |
| assess | n2 | node | evaluate_rules | pass | 5 | 0 |
| assess | n5 | leaf | evaluate_rule | pass | 16 | 0 |
| assess | n3 | leaf | place_postings | pass | 11 | 0 |
| assess | n4 | leaf | diagnose_rules | pass | 6 | 0 |

**Claim audit: 13 of 13 leaves clean.** No leaf calls `decide()` or a model, and every leaf is
claimed deterministic. **Nothing is deferred.** The protocol allows deferral only for decision
points (whether an answer is right, how often a fallback fires), and this program has none.

Four of my own test expectations were wrong on first run and were corrected before this record:
- a list path in the duplicate-ID case;
- a missing-`id_path` case that failed before it reached the ID;
- the shown order in `place_postings`, where e and f tie and key order puts e first;
- an exclude rule over regions [europe, emea], which the contract makes can't-tell.

In each case the leaf was right.

## The failures, by kind

### A. The code departs from its contract (re-codify)

- **`read_stated_text` (n7): whitespace split across inline tags.** `<p>Hello <b> world</b></p>`
  becomes "Hello  world", with two spaces. The contract says whitespace runs are collapsed. The
  cause is that the converter collapses each chunk of text separately, then joins the chunks. No
  fixture piece is affected.
- **`derive_geography` (n8): spans at a countries locator.** Spans are offsets into the raw
  value, but the evidence shape says they index "the text as converted to plain text". The two
  differ only when a locator value has extra whitespace.
- **`derive_salary` (n12): two statements side by side.** Take "$4,000 - $5,000 per month or
  $50,000 - $60,000 per year". Each statement's 40-character window reaches the other's period,
  so both come out with pay_period null. Being equal, they "agree" and combine into 4,000–60,000
  with an unknown period. Read as "beside", the periods disagree and the contract gives null.
  The harm downstream is small: a salary rule gets can't tell either way.

### B. Open language that a table can't deliver (the stage 3 finding, twice more)

- **`derive_employment_type` (n10).** The contract says "a word naming the subject of the work
  gives nothing", but only "Contract" is guarded. The leaf reads:
  - "Internship Program Manager" and "Intern Recruiter" as internship;
  - "Temporary Housing Coordinator" as temporary;
  - "Full-Time Equivalent Planning Analyst" as full-time.
- **`derive_years_of_experience` (n13).** The contract says "a mention of years that states no
  requirement is not one". The leaf reads:
  - "fully remote for at least 3 years" as 3;
  - "10+ years of history with us" as 10;
  - "In 2 years you will gain experience" as 2. Here the code's "N years … experience" form is
    looser than the contract's "N years of … experience" because it doesn't require "of".

Stage 3 said these two contracts "define their forms closed, by listed words or a stated shape",
so they lacked n8 and n11's gap. That was wrong. Each also carries an exclusion clause in open
language, which a word list meets only as far as its exceptions reach. Execution found both.

In the same family, n8 has two places where its contract and its table disagree:
- **"European Union".** The contract's own example says a countries-locator value of
  "European Union" "names neither one country nor a region" and is kept with value null. The
  region table maps it to `europe`. Ashby states it on every EU posting.
- **Reading 1.** The contract reads location texts "case-insensitive". The leaf matches codes in
  capitals only, so "remote - us" gives nothing.

In both, the code is arguably the better behavior and the contract wording is what's off.

### C. Contracts between the leaves and the root drop root clauses (re-decompose)

The glue passes everything run against stubs: order, multiplicity and dataflow are as wired. The
failures are in what the intermediate contracts promise.

- **Refresh root (n1).** The root states two clauses that `extract_fetched` (n3) doesn't carry:
  - "a board's value being mapped into a value space only where its meaning matches";
  - the salary clause: a bare $ is USD only for a US-only posting, and an unstated period is
    yearly only at or above the pay floor.

  n3 promises "the extraction of its payload under its own source's definition and the pay-floor
  table", plus the field shapes. The leaves keep both clauses, but a different `extract_fetched`
  that met its own contract could break the root without any local check noticing.
- **Assess root (n1).** `evaluate_rules` (n2) promises "each the verdict of that rule on that
  posting at the current date" and the verdict's shape. It doesn't carry any of the root's rules
  for what a verdict is:
  - can't tell exactly when unknown or not comparable;
  - any/every over alternatives;
  - whole-word keywords;
  - within-days.

  Only `evaluate_rule`, one level below, states them.
- **`extract_posting` (n6).** It promises mapping "only where its meaning matches". The narrowed
  geography and seniority contracts ratified at stage 3 say outright that a table entry counts
  "even where the text means something else" and that "Staff Pharmacist" gives `staff`, so the
  clause can't be derived from the children. The stage 3 record said the narrowing left n6's
  contract holding. That missed this clause, which the root states too. **This is my error,
  caught here.**

**Framework finding: a clause-carry check belongs in decomposition.** Two of the three are an
iterative node naming its child's result ("the verdict of that rule", "the extraction of its
payload") without restating what that result must satisfy. A flat parent can't see the
grandchild's contract, so the root's clause falls through. Stage 2's harness checked that the
shared interface is identical across trees. It did not check that every clause of a parent's
behavior is derivable from its children's contracts, which is assume-guarantee run at
decomposition time. Verification is where it was caught, by reading, not execution.

## The five readings stage 3 asked about

1. **Codes in capitals only (n8): fails the letter of the contract.** The contract says
   case-insensitive. The leaf's reading avoids "us", "in", "it" and "no" being read as countries.
   Recommended: amend the contract to the code's reading.
2. **"Manager" counts from the word; "Head of" and "Associate" give nothing (n11): passes.**
   The table decides, per the narrowed contract.
3. **A stipend range makes the salary unknown (n12): passes.** Disagreeing statements give null,
   as the contract says. A funding range ("raised $20 - 30M") does the same: it has a salary
   statement's form. Both go on the watch list.
4. **"Exactly its headers" (n5): passes.** The server received the definition's headers plus
   only the transport's Host, Accept-Encoding and Connection. With no headers defined there is no
   default User-Agent.
5. **A 40-character window for "beside the figures" (n12): passes for one statement, fails for
   two side by side.** See failure A.

Judged within the contracts and recorded as readings:
- urllib follows a redirect, so a 302 means two requests;
- an ID of "" counts as no ID;
- US$ and C$ are read as USD and CAD;
- in "$50-60k" the k applies to both figures.

## Choices for the author

| unit | failure | recommendation |
|---|---|---|
| n7 | whitespace across inline tags | **re-codify**: collapse whitespace after joining the text |
| n8 | spans into raw locator values | **re-codify**: convert the value as plain text before scanning |
| n8 | "European Union" example vs the table | **amend the contract's example**: the region table decides, and EU lies within Europe. The other way is to drop the table entry |
| n8 | reading 1, case | **amend the contract**: names case-insensitive, codes in capitals only |
| n10 | subject-of-work words count | **narrow like n8 and n11**: the leaf's word table decides, with listed exception phrases. Re-codifying with more exceptions can never be complete |
| n12 | adjacent statements share a window | **re-codify**: each statement's window stops at its neighbour |
| n13 | non-requirement mentions count | **narrow** so the forms decide, and **re-codify** the "N years … experience" form to require "of" (also accepting "N years' experience") |
| n6 + root | "only where its meaning matches" | **amend** to what the program does: board values are mapped only through the definition's values maps, and text is read only through the leaf tables, which decide. This touches the root contract, so the author confirms |
| refresh n1 | n3 drops the salary and mapping clauses | **re-decompose**: n3 and n6 restate both |
| assess n1 | n2 drops the verdict rules | **re-decompose**: n2 restates them |

All are small: wording edits in five contracts, and code changes in four leaves (n7, n8, n12, n13).

## Watch list for composition

Nothing is deferred. These are the questions only live data answers:
- **Whether each board returns its complete list**, especially Lever (from stage 2).
- **The unknown rate per field per board** (from stage 2).
- **Salary collisions**: stipends and funding ranges both make the salary unknown.
- **Table misses and wrong entries** (from stage 3).
- **Redirects**: the transport follows them, so a board that moves still fetches.

---

## Fix pass: every failure resolved, 2026-10-08

The author's decision: "yes, apply all the recommended fixes and re-verify". Every fix was the
recommended one, and none adds a decision point.

**Re-verified: 201 checks, 197 executed (98%), 4 static. 0 failures, 0 deferred. 19 of 19 units
pass.** The claim audit is still clean: 13 of 13 leaves are deterministic with zero `decide()`.

What changed:
- **Contracts.** Behaviors changed in the refresh root, n3, n6, n8, n10, n13 and assess n2. No
  glue changed, and `evaluate_rule`'s text is identical. Recorded in `stage-1-interrogation.md`
  for the root and `stage-2-decomposition.md` for the rest.
- **Code.** n7, n8, n10, n12 and n13 were re-codified, as recorded in `stage-3-codification.md`.

**Checks were regenerated, not replayed.** Eight checks asserted on wording or behavior that the
amended contracts changed, and each was rewritten against the new contract. Two more are new:
- n8: "European Union" now gives europe, and "Worldwide" gives null.
- n8: two- and three-letter names count only in capitals, longer names in any case.
- n8, new: an html-format locator's spans index its converted text.
- n10: exception phrases give nothing, and "Intern Coordinator" still gives internship, as the
  narrowed contract says.
- n12: side-by-side statements get month and year.
- n12, new: a period does not reach a farther statement.
- n13: the forms decide, so "at least 3 years" counts, but "in 2 years you will gain experience"
  doesn't.
- The three static node checks now test that n3, n6 and assess n2 state the carried clauses in
  the root's words, and that n6's children deliver them.

With the two new checks, the total went from 199 to 201.

**On real input nothing moved.** For n7, n8, n10, n12 and n13, the old and new code give
identical outputs on all 45 fixture postings. The failures were real but confined to inputs the
fixtures don't contain, which is why hand-built cases found them.

The watch list for composition is unchanged.
