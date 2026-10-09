# Job-search triage v2 · Stage 1 (interrogator)

**Started** 2026-10-08. Revises run 2's root contract
(`../2026-09-09-job-search-triage/root-contract.json`) into one for a version the author will
actually use, and demo. Not run 3: run 3 stays a fresh task, so the revised stage prompts are
tested on something whose defects are not already known. This run exercises them on a known
task first, including the 2026-10-04 decision seam.

## Task as given

> Turn the job-search triage program into a usable artifact: multi-user in structure, storage
> local for now, demo-able (switch between users to show the separation), with as many
> configurable rule options as the available data supports.

## Carried from run 2 (settled; not re-asked)

1. **Behavior is faithful assessment against stated criteria**, grounded in evidence from the
   posting, not "predicts what I'd want."
2. **The false-negative asymmetry.** A wanted job silently discarded is the costly failure; a
   false positive costs seconds.
3. **Criteria are a configurable input, refined by the user between runs.** The tool is the
   instrument by which "jobs I might want" gets defined; it never learns criteria itself, but
   hands the user refinement material (criteria diagnostics).
4. **Destructive vs. reversible filtering.** Fetch and store everything; filter only on the
   reversible side, and never hide a posting without a recorded reason.
5. **Storage is free** (~16 KB per posting), and the stored postings are the memory.
6. **Sources are data**: a source definition fixes endpoint, envelope, field mappings and date
   format, so the list grows without the contract changing.

## Settled before this stage (2026-10-04 to 2026-10-08 discussion)

7. **No model calls.** The program never calls a model (spec: *The decision seam*). Everything
   in the field inventory is a structured field or text that plain pattern matching reads, so
   the prediction for this run is **zero decision points**.
8. **Multi-user in structure, local storage, basic authentication.** Accounts, sessions and
   per-user access checks live in the host (the local server and page), not in the task's
   contract. The contract is handed one user's profile.
9. **Shared vs. per-user data.** Postings and their extracted fields are shared; each user has
   their own watched sources, rules, and dispositions. Run 2 kept dispositions inside posting
   records; they move to the user.
10. **Rule kinds**, from the field inventory (`../2026-09-09-job-search-triage/fixtures/`,
    three boards): keyword (title or full text); one-of (company, department/team, country,
    work arrangement, employment type); number threshold (salary, years of experience); date
    window; seniority from title words. Each rule acts as require, exclude, or prefer.
11. **Salary is "as stated in a recognisable form."** Where a posting states pay it is a regular
    `$X – $Y` range; where none is found the value is reported as not found, never guessed.
    The narrowed contract replaces run 2's model extraction.
12. **Run 2's defects are in scope:** a declared value space per field (the `remote` collision);
    undated postings surfaced, not dropped; one source failing does not stop the others;
    source definitions can carry request headers.

## Settled in dialog

13. **"Can't tell" handling is a per-rule setting the user controls, defaulting to shown.**
    Author: "users should be able to configure this themselves." Stage 1 accepted with one
    condition that keeps run 2's principle intact: a posting hidden because a rule could not be
    answered carries a reason distinct from one that failed the rule ("hidden: couldn't check
    salary"), so the user can always see how much an unknowns setting is hiding.
14. **Restore defaults, behind a confirmation.** A host feature (the confirmation is UI). Its
    contract consequence: every configurable setting has a declared default. Scope proposed as
    settings only (rules, sources and per-posting marks untouched), with the previous settings
    kept so a restore can be undone; adopted unless the author objects.
15. **Two units: refresh and assess** (A). Author: "those are two distinct operations." Two
    root contracts, two pipeline passes. The stored postings' shape is refresh's output and
    assess's input, so both contracts must state it identically — the interface run 2 got
    wrong.
16. **Prefer rules rank by count; no weights** (B2). Author: weights are appealing but not
    necessary — "if you're so overwhelmed with the number of qualifying posts ... you can
    probably just set more stringent criteria." For prefer rules, can't-tell counts as not met
    (ranking only, nothing hidden), not configurable.
17. **A posting's identity is its source plus the board's posting ID; "no longer listed" is
    exact** (E1). Each board's ID is unique within the board (15 of 15 distinct in each
    fixture; the posting URL embeds it), and run 2 already keyed stored postings on it. A
    stored posting missing from a successful fetch of its source is marked no longer listed,
    with the date first missed; reappearing clears the mark; a failed fetch marks nothing.
    Adopted unless the author objects.
18. **Re-posts: no link, no flag.** A role posted once per region is separate postings, kept
    separate (4 of Linear's 15 sampled titles, 2 of GitLab's). A re-posted role gets a new ID,
    and nothing in the data links it to the old one. Stage 1 proposed a factual
    same-company, same-title flag; the author declined: "it's probably possible for an
    entirely new/different job post to have the same title." Re-posts arrive as new postings,
    a known limitation as in run 2.

19. **Per-user marks** (C): viewed, saved, applied, hidden by you. "New" means not yet viewed
    by this user. Hidden by you wins over everything, is listed with that reason, and is
    reversible. Saved keeps a posting shown even when a rule would hide it (C1, author: yes),
    with the rule's verdict still visible. Applied postings stay shown, marked.
20. **Declared value spaces** (D). A board's value maps into a field's space only where its
    meaning matches; otherwise the field is unknown, with the board's raw value kept.
    - Text as stated: title, location, department/team, full text. Company: from the source.
    - Country: country codes where stated or clearly derivable, else unknown.
    - Work arrangement: remote / hybrid / onsite / unknown.
    - Employment type: full-time / part-time / contract / temporary / internship / unknown
      (Lever's "Permanent" states nothing about hours: unknown).
    - Seniority, from title words; no seniority word means unknown, not mid-level.
    - Salary: minimum, maximum, currency, pay period, where stated in a recognisable form. No
      currency conversion; a different currency or period from the rule's is can't-tell. A bare
      `$` counts as USD when the posting's country is the US (D1, author: yes).
    - Years of experience: the minimum stated ("5+ years" gives 5), else unknown.
    - Posted date: a date, or undated.
21. **Source failures and undated postings** (E; author: "E works"). Refresh reports each
    source's outcome; a failure affects no other source and keeps that source's earlier
    postings. Undated postings are stored and shown, marked "no posting date", and are
    can't-tell under date-window rules.

22. **Unstated pay period** (item-7 check). Every salary in the samples is a yearly range
    that never says so. Stage 1 proposed reading an unstated period as yearly from 10,000 up;
    the author rejected it ("we shouldn't assume a monthly salary over 10k is an annual
    salary") and set the floor at the full-time yearly equivalent of the minimum wage: for
    USD, $7.25 × 2,080 hours = $15,080, the US federal minimum. Below the floor the period is
    unknown. The floor varies by place, so it is data rather than code: a table keyed by
    currency, since the figures it is compared with are in that currency. A currency without
    an entry gets no inference. Author assumes US-based users for now.

23. **Judgment settled now** (item-7 check; author: "1-4 look good").
    - Several values in one field (countries, seniority) are alternatives: a
      require or prefer rule is met when any value meets it; an exclude rule only when every
      value does. Several values can only make hiding rarer.
    - Regions sit beside countries. A country implies its region; a region never implies a
      country, so "country is US" on a "North America" posting is can't-tell.
    - Keyword tests are case-insensitive on whole words or phrases; a trailing `*` matches any
      word ending.
    - Two dates for rules: the board's posted date, and first seen (when refresh first stored
      the posting). Linear lists postings published in 2021 that are still open.

# STAGE 1 COMPLETE — 2026-10-08

Author: "contracts look good, go ahead." Two root contracts, the handoff to decomposition:

- [`root-contract-refresh.json`](root-contract-refresh.json): fetch and extract, shared by all
  users, networked.
- [`root-contract-assess.json`](root-contract-assess.json): one user's rules and marks over the
  stored postings, pure computation.

The stored-postings shape is refresh's output and assess's input, and its description is the
same text in both contracts (checked when the files were written). Accounts, sessions, the
page, and restore-defaults' confirmation and undo belong to the host, built outside the
pipeline.

**Prediction: zero decision points** in both. Every field is structured data or text that
plain pattern matching reads. Stages 3 and 5 test this.

## How the contract moved

- **Run 2's single contract split in two** (item 15): fetching is user-independent; assessing
  is per user.
- **Run 2's recency input dropped.** Boards return every open posting and storage is free, so
  refresh stores everything; date limits became rules over posted and first-seen dates.
- **Run 2's model extraction gone.** Each field gained a declared value space (the `remote`
  defect), salary narrowed to "stated in a recognisable form," and the judgments that would
  otherwise recur each run were settled as rules (items 22, 23).
- **New outputs:** a per-source report (failure isolation), listing status, and per-rule
  diagnostics extended to count what each unknowns setting hides.

## Added while writing the contracts (flagged to the author)

- **Listing status is a one-of rule field**, so closed postings can be excluded. With no such
  rule they stay shown, flagged; the default is unchanged, only an option was added.
- **A salary range counts as several values** under item 23's rule, so "at least 100,000" is
  met by a 90,000–120,000 range and "exclude at most 50,000" hides only a range wholly at or
  below it.
- **A final tie-break by source and posting ID**, so the order is fully determined.
- **A stored posting refetched keeps its first-seen date** while its payload and extraction
  are replaced by the latest version.

## Amendments proposed by stage 2 (author: "confirmed")

Found on 2026-10-08 while decomposition resolved the shapes concretely; both root files are
amended. See `stage-2-decomposition.md`, *Root amendments*.

- **`link` added to the declared fields.** The root omitted the posting's address, which the
  page needs.
- **The any/every rule names its fields:** countries, regions, seniority and a salary's range.
  Item 23 agreed it for alternatives only; the root generalised it to every field with several
  values, which would stop "exclude team X" from ever hiding a posting that also names a
  department.

## Decisions the author made against stage-1 recommendation

- **Pay floor** (item 22): stage 1 proposed 10,000; the author rejected reading a monthly
  figure over 10,000 as yearly and set the floor at the minimum wage's full-time yearly
  equivalent, per currency.
- **Re-post flag** (item 18): declined; a matching title does not mean the same job.

## Observations for the deferred interrogator-refinement pass

- **Pre-filled proposals let the author answer by reaction.** C, D and E were settled in one
  line ("yes to C1, yes to D1, E works") because each came with a proposal and one question.
- **Item 7 earned its place on first use.** Asking what would still need deciding each run
  produced five rules; the author corrected one with a better-grounded rule than stage 1's,
  which is the dialog working as intended.
- **The author's questions were answered from the fixtures, not from memory.** "Is there a
  unique identifier?" was checked against all three boards' samples before answering, which
  also surfaced the per-region duplicates the answer turned on.
