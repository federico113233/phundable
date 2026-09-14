# Phundable — grant & funding finder for charities

A bilingual (FR/EN) web app that helps charities find funding they're actually
eligible for, understand *why* they match, and generate their application
documents.

One onboarding → a transparent 1–10 compatibility score against 5 funding
families → the individual funders inside each → a guided application walkthrough
→ six `.docx` documents pre-filled from the charity's own answers.

Built on the Phenix brand kit in the parent folder (Ambit, `#F74039`, `#310200`).

---

## Run it

```bash
cd app-grants
.venv/bin/python server/server.py
```

Open **http://localhost:8010**.

The app opens on a **landing page** explaining what it does, with a call to action
that starts the onboarding. Once a charity completes onboarding, the landing page
also offers a "continue to my results" link, and the header gains dashboard nav.

To reset to a clean first-run state (useful before a demo):

```bash
rm -f server/data/profile.json
find server/data/generated -name '*.docx' -delete
```

The virtualenv and its one dependency (`python-docx`) are already installed.
To rebuild from scratch:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

---

## Two audiences

The landing page serves both sides of the marketplace: charities use the product free,
and companies pay to be listed.

- **Charities** — onboarding, scores, application guidance, generated documents. Free.
- **Companies** — a listing on the platform so their programme reaches charities that
  genuinely match it, and so the applications they receive are already eligible and
  complete. **Pricing is quoted per organisation** (it depends on size and how many
  programmes they list), so no figure is hardcoded anywhere; `#/for-companies` collects
  a quote request including organisation size. **The form takes no payment or card details.**

### Partner funders

Paying funders are listed in `server/data/partners.json` — deliberately separate from
`funders.enriched.json`, which `tools/enrich.py` rewrites wholesale and would otherwise
destroy commercial data on every re-run. `catalog.py` merges them in at load time.

Partners get a logo, a badge, a sliding ribbon on the landing page, and a count on the
dashboard. **They do not get a better score.** `scoring.py` contains zero references to
`is_partner`, `partner_logo` or `partner_name`, so paying cannot move a compatibility
number — the guarantee is structural, not a convention. Charities are told this in plain
language on every partner's page. In the current data, partner scores range from 5.2 to
8.6 and several non-partners outrank them.

To add a partner: drop a logo in `public/assets/partners/`, add an entry to
`partners.json`, and run `.venv/bin/python tools/trim_logos.py` to normalise the image.

## Demoing the charity side

The onboarding form has a **demo filler** above the wizard: three one-click sample
charities, chosen to score differently so the engine can be seen to discriminate
rather than just emit a number.

| Sample | Profile | Scores highest on |
|---|---|---|
| Aide alimentaire | Les Paniers Solidaires — Occitanie, 380k, ESUS + food-aid accreditation, local experience | French grants 9.1 |
| Jeunesse & insertion | Horizon Jeunes — Île-de-France, 850k, youth accreditation, national experience | Corporate 9.7 |
| Environnement | Terre Vivante — multi-region + EU, 2.1M, 45% co-financing, EU experience | EU grants 7.7 (the highest of the three) |

Clicking a sample **replaces** the whole profile, so switching never leaves stale
values behind. Samples live in `public/js/samples.js`; every value is validated
against `server/config/onboarding_fields.json`.

## Demo data and the internal pipeline

`#/admin` is an **internal commercial view**: active listings (paying partners) plus the
inbound quote-request pipeline, with KPIs and status per request. It is deliberately
**not linked from the public navigation and has no login** — it is a prototype surface.
Do not deploy it publicly as-is.

Seed or reset the demo pipeline:

```bash
.venv/bin/python tools/seed_demo.py          # 8 realistic quote requests
.venv/bin/python tools/seed_demo.py --clear  # empty the pipeline
```

Requests submitted through the public form at `#/for-companies` enter the same pipeline
with status `new`, so the whole loop is demonstrable live.

**The seeded company names are fictional.** Stating that a real business requested a quote
would be a false claim about that business, and email domains use `example.com` so nothing
can reach a real inbox by accident.

> Note on the partner list: the seven funders in `partners.json` are **real foundations**
> presented as paying partners for demonstration purposes. That is fine in a prototype, but
> it is a claim about real organisations — replace it with genuine customers, or label it as
> illustrative, before showing this publicly.

## How it works

### Scoring is deterministic — the LLM never touches it

A charity deciding where to spend three weeks of unpaid effort deserves a score
it can interrogate. `server/scoring.py` is pure Python: six dimensions, weighted
per category, every number returned with the reason it was produced.

| Dimension | Measures |
|---|---|
| `theme` | overlap between the charity's cause areas and the funder's priorities |
| `geo` | whether the charity's regions are covered |
| `eligibility` | hard gates: legal status, accreditations, minimum age |
| `capacity` | co-financing, English reporting, audited accounts, admin burden vs experience |
| `size` | amount sought vs the funder's range (skipped when undisclosed) |
| `timing` | rolling / annual / periodic / one-off |

Design decisions worth knowing:

- **Hard-gate failure caps the score at 3/10** with the exact blocking reason —
  never a silent low number.
- **Per-category weights**: EU grants weight `capacity` at 0.40; corporate
  funding weights `theme` at 0.38. The five families behave differently because
  they *are* different.
- **Unknown never reads as excellent.** A funder that publishes no eligibility
  conditions scores 0.72 on that dimension, not 1.0 — we couldn't verify a match,
  so we don't claim one. Dimensions that don't apply are dropped and their weight
  redistributed, so a funder is never punished for what it doesn't publish.
- **Research confidence tempers the result**: a `low`-confidence record is scaled
  to 0.82 so it can't present as a verified 9/10.
- **Category score = quality × depth.** One strong match is a lead; five is a
  strategy. Depth saturates at 5 eligible options.

### The LLM does two jobs, both offline of scoring

1. **Enrichment** (`tools/enrich.py`) — a one-time pass that parses the prose
   source CSV into structured, comparable fields *and* translates it to French.
2. **Document drafting** (`server/docgen.py`) — writes the cover letter, project
   summary and eligibility narrative.

Both are told, explicitly and repeatedly, to use only supplied facts, never to
invent a figure or merge two facts into one claim. Every generated document
carries a review notice, and only documents whose prose actually came from the
model say "AI-assisted".

If Groq is unreachable or rate-limited, documents still generate from templates
with a visible banner. **A live demo never hard-fails.**

---

## Updating the funding database

Replace `server/data/funders.source.csv` (UTF-8, same columns), then:

```bash
.venv/bin/python tools/enrich.py          # only rows that changed
.venv/bin/python tools/enrich.py --all    # re-do everything
```

Enrichment is content-hashed, so re-running after editing three rows costs three
API calls, not 48. The running server picks up the new file without a restart.

**Free-tier rate limits are tight** — a full 48-row run takes ~15 minutes with
back-off. The script waits out HTTP 429 using the provider's own `retry-after`.

### Changing the onboarding questions

Everything lives in `server/config/onboarding_fields.json` — bilingual labels,
field types, options, validation. The wizard, the scoring inputs and the document
templates all read from it. Change that one file; nothing else needs editing.

---

## Layout

```
app-grants/
├── server/
│   ├── server.py       HTTP + JSON API (stdlib only)
│   ├── scoring.py      deterministic rule engine
│   ├── catalog.py      catalogue loading, link normalisation, profile storage
│   ├── llm.py          Groq client: model autodetect, 429 back-off, fallback
│   ├── docgen.py       .docx generation (python-docx)
│   ├── config/onboarding_fields.json
│   ├── .env            GROQ_API_KEY (gitignored)
│   └── data/
│       ├── funders.source.csv      your research (the input)
│       ├── funders.enriched.json   structured + translated (generated)
│       ├── profile.json            the charity's saved profile
│       └── generated/              produced .docx files
├── public/             SPA: hash routing, no build step
│   ├── js/{app,i18n,api,dom}.js + js/views/*.js   (routing lives in app.js)
│   ├── i18n/{en,fr}.json
│   └── css/styles.css
└── tools/enrich.py
```

### API

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | catalogue counts, profile presence, LLM status |
| `GET /api/config/onboarding` | field definitions |
| `GET` / `POST /api/profile` | read / save the charity profile |
| `GET /api/categories` | 5 families with scores and counts |
| `GET /api/categories/<id>` | scored opportunities inside one family |
| `GET /api/opportunities/<id>` | full record + score breakdown + doc list |
| `POST /api/documents/<type>` | generate a document |
| `GET /api/documents/<file>` | download the `.docx` |

---

## Robustness

Audited end to end. The behaviours below are deliberate and covered by the audit:

- **Scoring never raises.** Profile data arrives from a browser and may be any JSON
  type. `scoring.py` coerces everything through `_as_list` / `_as_number`; verified
  against 9 malformed profiles x 48 funders x every category with zero failures.
- **Profiles are validated and whitelisted on save.** `POST /api/profile` type-checks
  every field against `onboarding_fields.json` (types, ranges, allowed option values)
  and persists only declared keys, so a tampered client cannot inject fields.
- **No path traversal.** Document downloads go through `os.path.basename`; unknown
  static paths fall back to `index.html`. `server/.env` is not reachable over HTTP.
- **No XSS surface.** All view rendering goes through `el()`, which appends text
  nodes; there is no `innerHTML` path for funder or profile data.
- **Documents degrade gracefully.** If the LLM is unavailable the document is still
  produced from templates, flagged `ai_used: false`, with the reason printed in the
  document footer.
- **Template documents never claim AI authorship**, and AI documents always carry a
  review notice.

## Known limits

- **The source data rarely states hard criteria.** Across 48 records:
  co-financing % appears in 0, English requirements in 0, minimum org age in 1,
  and a usable funding amount in 8. Eligibility gating is therefore softer than
  the engine can support. Adding `min_org_age_years`, `cofinancing_required_pct`
  and `requires_english` columns to the source CSV would sharpen scoring more
  than any code change.
- **Administrative complexity is largely unmeasured** — the extractor rated 46/48
  "medium". EU grants are set to "high" from the category, since that one is
  reliable domain knowledge rather than a guess.
- **Funder content is machine-translated** into French from English source text.
  Good, but worth a human pass before anything client-facing.
- **Single profile, no accounts** — one charity per installation, by design.
- `.env` holds a real API key. It is gitignored; rotate it when the prototype
  is done.
