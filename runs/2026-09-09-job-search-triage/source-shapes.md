# Source shapes — evidence for decomposition

Live samples pulled 2026-09-21 from three public ATS job-board APIs. All three are
unauthenticated, documented, and intended to be consumed. Trimmed to 15 postings each
in `fixtures/`; re-fetch commands below.

**OLMIS is not a source of postings.** It is the Oregon Employment Department Research
Division's labor market *information* system (now branded QualityInfo, at olmis.org /
olmis.com): occupation and wage profiles, QCEW industry employment, career paths. One of
its tools draws on Help Wanted OnLine data, but that is *aggregate statistics derived from*
postings, not individual postings. It answers "what does this occupation pay in Oregon,"
never "who is hiring." Actual Oregon postings live in iMatchSkills / WorkSource Oregon,
which exposes no documented public API. See "Oregon-local sources" below.

## The three shapes

| | Greenhouse | Ashby | Lever |
|---|---|---|---|
| endpoint | `boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true` | `api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true` | `api.lever.co/v0/postings/{slug}?mode=json` |
| envelope | `{jobs:[...], meta}` | `{jobs:[...], apiVersion}` | bare top-level **array** |
| title field | `title` | `title` | **`text`** |
| date | `first_published`, ISO-8601 w/ offset | `publishedAt`, ISO-8601 Z | `createdAt`, **epoch milliseconds** |
| location | `location.name`, free text (`"Remote, Bangalore"`) | `location` + `secondaryLocations` + `address` | `categories.location` + `categories.allLocations` + `country` |
| remote | **absent** | `isRemote` (boolean) + `workplaceType` | `workplaceType` |
| description | `content` — HTML-escaped HTML, **no plain variant** | `descriptionHtml` *and* `descriptionPlain` | `descriptionPlain`, `descriptionBodyPlain`, `additionalPlain` |
| compensation | **absent** | `compensation` object (frequently empty) | `salaryRange` (sometimes) |
| pagination | none — whole board in one call | none | none |

Sizes: GitLab 206 postings / 3.2 MB with content (~15.7 KB per posting). Ashby and Lever
comparable. No provider required a second per-job detail fetch — the earlier worry about
list-then-detail does not apply to these three, though it may to others.

## What this confirms, empirically

**Storage is free, as assumed.** ~16 KB per posting means 5,000 postings is about 80 MB.
The contract's "fetch everything, filter non-destructively" rests on a real number now.

**Three-valued criteria are necessary, not a nicety.** Take one criterion — "is this
remote?" On Ashby it is a boolean field. On Lever it is a different field with different
values. On Greenhouse it is *not in the data at all* and has to be read out of free-text
location or prose. One criterion, three answerability levels, across sources that are all
in scope simultaneously. Satisfied / not satisfied / not-answerable is forced by the data.

**Extraction should be field-mapping first, seam second.** This is new and it sharpens the
contract's sole `ai()` leaf. Where a source already carries a field (`isRemote`), extraction
is deterministic mapping and costs no model call. Where it does not (Greenhouse remoteness,
every provider's salary), the seam fires. So seam load varies per source per field, and the
cheapest correct design pays the model *only* for what the source failed to state. That is
the author's leftover-reasoning test applied one level down, and codification should be held
to it.

**Sources-as-data is validated.** A source definition has to carry: endpoint template, the
envelope path to the posting list, per-field mappings into the common schema, and a date
format. That is the author's "ruleset" idea, now grounded in three real divergences rather
than imagined ones.

## Oregon-local sources — open

These three are company-by-company boards; they are a fine test substrate but not a way to
see Oregon's labor market. Two real options, neither resolved:

- **USAJOBS** — documented public REST API (`GET /api/Search`, `data.usajobs.gov`), free,
  location-filterable, federal roles only. Requires an API key, which is a free email
  signup the author has to do; it cannot be done for them.
- **NLx (National Labor Exchange)** — NASWA/DirectEmployers nonprofit aggregating state job
  banks and corporate career sites, unduplicated, refreshed daily; all 50 states participate,
  so Oregon's state job bank postings flow into it. API access exists via the NLx Research
  Hub but is aimed at agencies and researchers, so it likely needs a data agreement.

## Re-fetch

```sh
curl -s "https://boards-api.greenhouse.io/v1/boards/gitlab/jobs?content=true"
curl -s "https://api.ashbyhq.com/posting-api/job-board/linear?includeCompensation=true"
curl -s "https://api.lever.co/v0/postings/spotify?mode=json"
```

Board slugs are per-company and must be supplied; there is no discovery endpoint. Probing
found `sentry` (Greenhouse) and `box` (Lever) return 404 — a slug is a guess until tried.
