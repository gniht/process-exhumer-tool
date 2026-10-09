# Job-search triage v2 · Stage 5 (composition), 2026-10-08

Input: `verified-tree-refresh.json` and `verified-tree-assess.json`. The gate was clear: 19 of 19
units pass, and the deferred list is empty, so this run's watch list is the five items from
stage 4.

Output, two programs, **the deliverable**:

| program | lines | node functions | needs |
|---|---|---|---|
| **`job_triage_refresh.py`** | 1,369 | 14 | network access to the boards |
| **`job_triage_assess.py`** | 303 | 5 | nothing |

Each is a single file using only the standard library, with JSON on stdin and JSON on stdout.
**Neither calls a model, and neither has a decision point,** so neither carries a decision
runtime or reads a stored-answers file. Everything else from the run is in `live/`, and
`final-tree-*.json` carry the run on their root results. `compose.py` is the assembler.

```
python3 job_triage_refresh.py < refresh-input.json > refresh-output.json
python3 job_triage_assess.py  < assess-input.json  > assess-output.json
```

## Assembly found two defects before the run counted

**1. A reject: `fetch_source` (n5) had two candidate entry points.** Composition identifies the
entry point as the one function taking exactly the contract's inputs. n5 also had a private
`_fetch(source)`. The three stages each had their own rule:
- **codification** allows private helpers;
- **verification's** surface check counted only public functions;
- **composition** counts every function.

The reject names codification, so n5 was re-codified: the helper now takes `endpoint, headers`
and behavior is unchanged. Verification's surface check now applies composition's rule. Run
against the stage 4 code, it would have failed n5. Re-verified: 201 checks, 0 failures.

**2. Composition's own mechanic corrupted `derive_geography`.** The prompt nests each leaf's code
"verbatim, indented one level". Indenting every line also indents the lines inside a multi-line
string. n8's country table is one, so every table line gained four leading spaces and the table
parsed into nonsense: in the assembled program, "CA" read as the US and "United States of
America" as "".

The first live run didn't crash. It produced plausible-looking output with wrong countries, which
the whole-output shape check caught: 111 problems, including the empty string, which is outside
the value space. A side-by-side run of the program's function and the verified leaf on the same
posting showed the cause. That output was discarded.

The fix is in the assembler, which composition owns:
- **String-aware indentation:** a line that continues a multi-line string is never indented.
- **An identity check:** every nested leaf and glue block must be, as an AST, exactly the code
  that was verified. The naive build fails it.
- **Stage 4's leaf checks re-run against the assembled programs:** 126 of 127 pass. The
  shortened-timeout check needs a module constant that nesting turns into a local, so it runs
  only on the tree's code. A naive build stops these checks at n8.

Both defects are in the mechanics *between* stages, which no single stage's checks covered. See
**Framework findings** below.

## The live runs, 2026-10-08

Inputs in `live/`:
- **`sources.json`**: the real source definitions, covered below.
- **`pay_floors.json`**: `{USD: 15080}` only. You set the floor for US-based users, and I won't
  guess minimum wages elsewhere. A salary in another currency with no stated period stays unknown.
- **`users.json`**: two demo users.

Large inputs and outputs, including the 13 MB stores, are left out of git by `live/.gitignore`.

| run | store in | result |
|---|---|---|
| refresh 1 | empty | 330 postings stored (GitLab 220, Spotify 79, Linear 31). The nonexistent board failed alone: `HTTP 404`. About 3 seconds. |
| refresh 2 | run 1's | 0 new, 0 removed, every first-seen date kept, all 330 re-extracted identically |
| refresh 3 | 45 postings saved 2026-09-21 (run 2's fixtures), extracted by this program | **8 marked no longer listed** since 2026-10-08 (5 GitLab, 3 Spotify), real takedowns. The 37 still listed kept first-seen 2026-09-21. 338 stored. |
| assess demo-a | refresh 3's | 338 watched, 66 shown, 272 hidden |
| assess demo-b | refresh 3's | 113 watched (Spotify and Linear), 13 shown, 100 hidden |

**Checked mechanically against the outputs:**
- **Refresh:** every stored posting's 14 fields against the declared value spaces and evidence
  shape: 330 × 14, **0 problems**.
- **Assess:** nine root clauses, and all nine hold for both users:
  - each watched posting appears exactly once;
  - verdicts come in rule order;
  - can't tell occurs exactly when the tested value is unknown;
  - both orderings hold;
  - hidden-by-you holds;
  - saved overrides the rules;
  - the flags are right;
  - the diagnostics totals add up.

Assess gives identical output on a rerun.

The demo users' rules and marks are mine, chosen to exercise every test, action and mark. **They
are not your rules.** A run with your own rules is still to come.

## The real source definitions (`live/sources.json`)

All three use the boards' public posting APIs. Choices worth your review, since a values map is
where build-time judgment about meaning lives:

- **Ashby (Linear):**
  - `User-Agent: job-triage/2 (personal job search)`. Ashby answers with no User-Agent or this
    one, and refuses urllib's default (run 2's 403). v2 sends no default, so this header is
    courtesy, not a fix.
  - `workplaceType` is mapped: Remote, Hybrid, OnSite.
  - **`isRemote` is deliberately not used.** It is `true` on all 31 postings, including the 3
    Hybrid ones, so it doesn't mean fully remote.
- **Lever (Spotify):**
  - `workplaceType` is mapped.
  - `commitment` "Full Time Contractor" maps to contract.
  - **"Permanent" is left unmapped**, because permanent says nothing about hours. That leaves
    employment type unknown on 77 of 79 Spotify postings, all shown by default. **One question
    for you below.**
  - "Short Term" is left unmapped: it could be contract or temporary.
- **Greenhouse (GitLab):** no structured work arrangement or employment type. Work arrangement
  comes from location words ("Remote, …"). The office names are read as location text.

## The watch list, settled

1. **Whether each board returns its complete list:** confirmed for two of three.
   - **Lever:** paging with `skip`/`limit` returns exactly the default's 79 postings.
   - **Greenhouse:** 220 listed, equal to its own `meta.total`.
   - **Ashby:** 31; the API has no paging and no count to compare against.
2. **The unknown rate per field per board** (from `live/watch-1.json`):
   - **Always known** on all three: title, link, company, location, department/team, full text
     and posted date.
   - **Employment type** is unknown on 218 of 220 GitLab postings (Greenhouse has no such field
     and titles rarely say) and 77 of 79 Spotify ("Permanent").
   - **Seniority** is unknown on about a third of titles, ones without a level word: "Backend
     Engineer II", "Account Executive", "Product Engineer".
   - **Salary** is unknown on all 31 Linear postings (Linear publishes none), 59 of 79 Spotify
     and 116 of 220 GitLab.
   - **Years** is unknown on 193 of 220 GitLab.
   - **Countries** is unknown on 8 of 31 Linear (its EU postings: region only), 5 of 220 GitLab
     and 0 of 79 Spotify.

   Every unknown is shown by default.
3. **Salary collisions: none observed.** No stipend or funding ranges appeared. There are 124
   salaries in all:
   - 120 are USD yearly;
   - 4 are GitLab's Polish zloty ranges ("272,000 - 408,000 PLN"), whose period stays unknown
     because PLN has no pay floor, as designed.
4. **Table misses and wrong entries:** no wrong entries found.
   - All 28 distinct country matches from text are correct ("KSA" is Saudi Arabia, "NY" the US).
   - Only one location names no geography at all: plain "Remote".
   - One exception phrase did its job: "Chief of Staff, CRO" is not read as staff level. No title
     hit an employment-type exception.
   - Misses, which come out unknown and are shown: "II", "Intermediate", "Fixed-Term".
5. **Redirects:** none of the three endpoints redirects.

## Differential check across boards

- **Countries, structured vs. text:** Spotify's `country` field and Linear's `addressCountry`
  never disagree with the countries their location text names. Where the text names none (city
  names like "Toronto" aren't read), the structured field fills the gap.
- **Work arrangement:** GitLab's comes from location words, Spotify's and Linear's from
  structured fields. They can't be cross-checked: Spotify's and Linear's location texts never
  contain an arrangement word. GitLab's 24 unknowns are all Bangalore office postings with no
  arrangement word, which correctly come out unknown, not "onsite".
- **Posted date has two bases, by contract.** Greenhouse dates are read as written in their own
  offset (US Eastern); Lever's and Ashby's are UTC. So 19 of 220 GitLab dates fall a day earlier
  than UTC would put them. It's at most one day, and within-days rules barely notice, but it is
  the one place a shared field name doesn't mean quite the same thing.

## Realized decision load and the residue

**Zero.** There's no `decide()` call anywhere, so no pending questions and an **empty residue**.
For comparison, run 2's program made 46 model calls on its live run. The build-time judgment
this program needs lives where you can read and edit it:
- the source definitions' values maps above;
- the leaf tables of countries, regions, level words, employment words and year forms.

## Questions for you

1. **Should Lever's "Permanent" map to full-time?** It's Spotify's standard posting type. Mapping
   it makes employment type known on 71 more postings, at the cost of assuming permanent means
   full-time.
2. **Pay floors beyond USD**, whenever you want salaries in other currencies read as yearly
   without a stated period. It needs each country's minimum wage, so it's yours to set.

## Framework findings

1. **Composition's "verbatim, indented one level" changes code that has multi-line strings.**
   The prompt should say:
   - indent code lines, never a string's continuation lines;
   - confirm each nested unit is AST-identical to the verified one;
   - re-run the leaf checks against the assembled program.

   Silent corruption at assembly is the worst kind, because everything upstream passed.
2. **Three stages, three entry-point rules.** Codification, verification and composition should
   share one rule. The simplest is codification's prompt saying a helper may not take exactly the
   entry point's parameter list, with verification applying composition's rule (done here, in the
   harness).
3. **A whole-output shape check belongs in every live run.** It's cheap and mechanical, and it
   caught the corrupted build that looked fine at a glance.

## Verdict

**Would a non-technical observer say the framework did what it was supposed to? Yes, this time
for the program as well as the pipeline.** Two standalone programs:
- fetch three real job boards in about 3 seconds;
- keep a memory that notices postings taken down;
- show each user a different, ordered list from the same store, with a reason for every hidden
  posting;
- never call a model and never ask a question at run time.

Run 2's silent false negative (remote jobs judged not remote) can't recur, because every field
now has a declared value space. The defect this stage did find was in the pipeline's own
assembly step, and the checks added here found it before it reached a user.

**This assessment is judgment, from the checks and observations above.**

Next is the host, built outside the pipeline: a local server and page, basic authentication,
switching users, and restore defaults with a confirmation popup. It calls these two programs.
