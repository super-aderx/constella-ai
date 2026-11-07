# Campaign from strategy — Breakdown

Tech plan: ./tech-plan.md
Last updated: 2026-11-07

> **Changed 2026-11-07 (CAI-7):** proposals are not stored and conversion is not measured. I1 no
> longer stores proposals or adds `proposal_id`. A campaign keeps a copy of its proposal in
> `source_proposal`. I2 keys its button on the proposal's position and sends `source_proposal`.
> I3 drops the conversion query. FR14 / AC16 are dropped from the requirements.

## Overview

There are 3 issues in 2 waves. The backend (I1) and the frontend (I2) share no files, and the tech
plan's *Interfaces & contracts* pins every shape between them. So they start together in wave 0,
with no separate contracts issue. I3 is a short end-to-end check against a real database once both
are merged.

- Parallelism: 2 issues at once.
- Critical path: I1 or I2, then I3.

## Waves
- Wave 0: I1, I2 (parallel)
- Wave 1: I3

## Coverage
| Requirement | Issues |
|---|---|
| FR1 / AC1 | I2 (button) |
| FR2 / AC9 | I2 |
| FR3 / AC4, AC5 | I1 (server rules, counties), I2 (fields, client rules) |
| FR4 / AC2 | I2 |
| FR5 / AC3 | I1 (search), I2 (picker) |
| FR6 / AC6, AC7 | I1, I2 |
| FR7 / AC8 | I1, I2 |
| FR8 | I2 |
| FR9 / AC10 | I2 |
| FR10 / AC11 | I1, I3 |
| FR11 | I2 |
| FR12 / AC12 | I2 |
| FR13 / AC13 | I2, I3 |
| Edge: save fails / AC14 | I1 (500), I2 |
| Edge: double-click / AC15 | I1 (`client_token`), I2 (disable), I3 |

## Issue graph
```json
{
  "feature": "campaign-from-strategy",
  "issues": [
    {"id": "I1", "title": "Backend: store campaigns, product search", "depends_on": [], "touches": [
      "backend/app/infra/sql/", "backend/app/infra/migrate.py", "backend/app/infra/store.py",
      "backend/app/campaigns.py", "backend/app/products.py", "backend/app/main.py",
      "backend/tests/", "backend/.env.example", "Makefile", "README.md", "CLAUDE.md",
      "docs/specs/campaign-from-strategy/"]},
    {"id": "I2", "title": "Frontend: Add-as-campaign wizard in the chat", "depends_on": [], "touches": [
      "frontend/src/types.ts", "frontend/src/api.ts", "frontend/src/campaign/",
      "frontend/src/chat/AnswerCard.tsx", "frontend/src/chat/Chat.tsx"]},
    {"id": "I3", "title": "End-to-end verification against a real database", "depends_on": ["I1", "I2"], "touches": [
      "docs/specs/campaign-from-strategy/verification.md"]}
  ]
}
```

## Issues

### I1: Backend: store campaigns, product search — CAI-7
- **Wave:** 0 · **Depends on:** — · **Estimate:** L
- **Why:**
  - The saved campaign must really be in the database (FR10, AC11), with a copy of the AI
    proposal it came from.
  - The server is the authoritative check of every rule (FR3, FR6, FR7).
  - Product search must tolerate typos (FR5, AC3).
- **Scope:**
  1. **Schema and migration.**
     - Write `backend/app/infra/sql/schema/campaigns.sql` exactly as in the tech plan's
       *Data model*: `campaign` (with `source_proposal JSONB`) and `campaign_pilot`, with
       `IF NOT EXISTS`, passing sqlfluff.
     - `backend/app/infra/migrate.py` runs every `sql/schema/*.sql` in name order, in one
       transaction, on a writable connection to `DATABASE_URL`.
     - Add a Makefile target `migrate` that runs
       `cd backend && uv run --env-file .env python -m app.infra.migrate`.
     - In `.env.example`, note that the DB user needs CREATE for `make migrate`, and INSERT and
       SELECT on the campaign tables.
     - In `README.md` and `CLAUDE.md`, note that the API now writes these two tables. `data.py`
       stays read-only.
  2. **Models** in `backend/app/campaigns.py`: `ProductRef`, `Pilot`, `CampaignDraft` and
     `SavedCampaign`, as in the tech plan, with `source_proposal: strategist.Campaign | None`, and
     these limits:
     - title ≤ 200, strategy ≤ 4000
     - `StrictInt` discount 1–100, pilot percent 1–99
     - `date` fields, and `UUID` ids
  3. **Rules:** `draft_problems(draft, catalog, segments, counties, today)` in the same file. It is
     pure and returns *every* broken rule as `(loc, msg)`, with exactly the loc and msg values in the
     tech plan's 422 table. A product of kind `"type"` must be a catalog key. One of kind
     `"product"` must be in some catalog value list. `source_proposal` is not checked.
  4. **Store** in `backend/app/infra/store.py`. It is the only module that writes, and it uses named
     SQL files in `app/infra/sql/`.
     - `save_campaign(draft) -> (SavedCampaign, created)`:
       - Run `INSERT ... ON CONFLICT (client_token) DO NOTHING RETURNING`.
       - If nothing comes back, return the existing row and its pilot with `created=False`.
       - Otherwise insert the `campaign_pilot` row when there is a pilot.
       - Split `products` by kind into `item_types` and `products`. The response rebuilds them,
         types first.
     - `load_counties()`: cached, read-only, distinct non-null
       `invoice.county`, sorted.
     - Keep the row ↔ model mapping in pure helpers so it can be tested without a database.
  5. **Search** in `backend/app/products.py`: `search_products(q, limit) -> list[ProductHit]`.
     - It scores catalog types (`load_catalog()` keys) and products (its values) with
       `app.tools.search.score`, keeping those at `GOOD_ENOUGH` or above (`search.best` returns
       bare names, so it would lose each hit's kind and type).
     - On ties, types come first, then names alphabetically. Blank `q` → `[]`.
     - Time it on a catalog of 20,000 names. If it takes more than 150 ms, add a cheap pre-filter.
  6. **Endpoints** in `backend/app/main.py`:
     - `GET /api/campaign-options` → `{segments, counties}`.
     - `GET /api/products/search?q=&limit=` with `limit` from 1 to 50, default 20.
     - `POST /api/campaigns`:
       1. `draft_problems` returns problems → 422 in FastAPI's `detail` shape, with
          `type:"campaign_rule"` and `"body"`-prefixed `loc`.
       2. Otherwise → 201 if created, 200 on a repeated `client_token`.
       3. A database error → log it and return 500.
  7. **Docs:** update the three files in `docs/specs/campaign-from-strategy/` for the decision
     above.
- **Out of scope:** all frontend work (I2). Storing proposals, proposal ids, and `/api/ask*`.
- **Contract:** the tech plan's *Data model* and *Interfaces & contracts*: endpoint paths, JSON
  field names, status codes, the 422 shape and its messages. I2 builds against these, so do not
  change them without updating the tech plan.
- **Files:** see `touches`.
- **Acceptance criteria:**
  - Given an empty database, when `make migrate` runs twice, then the two tables exist and the
    second run succeeds.
  - Given a draft with campaign start 2026-12-01, pilot end 2026-12-01 and two other broken rules,
    then `draft_problems` returns all three, including
    `(("pilot","ends_on"), "Pilot must end before the campaign starts.")`. A valid draft returns
    `[]`.
  - Given a catalog `{"teapot": ["blue teapot"]}`, when searching "teapto", then the type "teapot"
    comes first, and "blue tea" finds the product with `type: "teapot"`.
  - Given a valid POST, with the store patched to report created or existing, then the response is
    201 or 200 with a `SavedCampaign`, including the same `source_proposal`. A rule problem gives
    422 with `detail[0].loc == ["body","pilot","ends_on"]`. A store exception gives 500.
- **How to verify:** `make test lint`. All the new tests run without a database or an API key, as
  the repo's convention requires: they build catalogs and drafts inline and monkeypatch the store.
  Then run `make migrate` against a scratch database.

### I2: Frontend: Add-as-campaign wizard in the chat — CAI-8
- **Wave:** 0 · **Depends on:** — · **Estimate:** L
- **Why:** this is the user-facing flow. It covers the button on each proposal (FR1), the 3-step
  modal (FR2), prefill (FR4), the fields and product search (FR3, FR5), the pilot (FR6), blocking
  Next on errors (FR7, FR8), review (FR9), the save confirmation (FR11), the discard guard (FR12)
  and the repeat-save warning (FR13).
- **Scope:**
  1. **Types and API** in `src/types.ts` and `src/api.ts`, as in the tech plan:
     - `ProductRef`, `ProductHit`, `CampaignOptions`, `PilotDraft`, `CampaignDraft` (with
       `source_proposal: Campaign | null`) and `SavedCampaign`. `Campaign` is unchanged.
     - `getCampaignOptions()`, a cached promise like `getNetwork`.
     - `searchProducts(q, signal)`.
     - `saveCampaign(draft)`, which throws `CampaignError { fields, message }`. On a 422, `fields`
       maps `loc` (with `"body"` dropped, joined by `.`) to `msg`. On anything else, `fields` is
       null and the message is "Could not save the campaign. Try again."
  2. **Logic** in `src/campaign/validate.ts` and `src/campaign/draft.ts`. These are pure, with no
     React.
     - `stepErrors(step, draft, today)` mirrors the server's rules and messages for steps 1 and 2.
       Step 3 is both together. Catalog membership is left to the server.
     - `fromProposal`: title ← name, strategy ← reason, products ← items as `kind:"type"`,
       discount ← discount_percent, segment ← audience. Dates and counties start empty, the pilot
       is off with `auto_start:false`, `client_token` comes from `crypto.randomUUID()`, and
       `source_proposal` is the proposal itself.
     - `toRequest` trims the text and sends `pilot: null` when the pilot is off.
     - `isDirty` compares two drafts, ignoring the token.
  3. **Step 1** (`CampaignStep`, `ProductPicker`):
     - The fields are title, strategy, products, discount %, start and end dates, segment (with
       "All customers" = null) and counties (a checkbox list summarised as "All counties" or
       "N selected").
     - The picker's search is debounced by 200 ms, aborts stale requests, and works from the
       keyboard (↑/↓/Enter/Esc). Hits are labelled "Type" or "Product". With no hits it shows
       "No products match '<q>'".
     - Selected products are removable chips. Server errors for a single product mark its chip.
  4. **Step 2** (`PilotStep`):
     - The "Run a pilot first" switch is off by default. Turning it on shows the audience % (1–99),
       dates, discount, and the switch "When the pilot passes: start the campaign automatically"
       (off = hold for approval).
     - Turning the pilot off keeps the typed values but sends no pilot.
  5. **Step 3** (`ReviewStep`): every value, read-only and in words. For example: "All customers",
     "All counties", "15% off", "No pilot", "Hold for my approval when the pilot passes".
  6. **Shell** (`CampaignWizard`):
     - A native `<dialog>` with `showModal()`, centered and about 640 px wide, with the step
       indicator "1 Campaign · 2 Pilot · 3 Review".
     - Next runs `stepErrors` and shows errors under their fields, with `aria-invalid`. Back keeps
       all values.
     - **Saving:**
       - Save is disabled while pending.
       - If `alreadySaved > 0`, it first asks "You already saved a campaign from this proposal.
         Save another?".
       - Field errors from a 422 jump to the first step that has one.
       - Other failures show the message and keep everything.
     - **Closing:** X, Esc (the `cancel` event) and a click on the backdrop ask "Discard this
       campaign draft?" when `isDirty`.
  7. **Chat:**
     - In `AnswerCard`'s `Campaigns`, every card shows "Add as campaign", or "Saved ✓" once it has
       been saved. The button stays clickable.
     - A proposal is keyed by its position in the answer (answer index and campaign index).
       `Chat` holds `saved: Record<proposalKey, number>`, the open proposal, and a "Campaign
       saved" toast (`role="status"`, hidden after 4 s).
  - Use the existing Tailwind tokens and the `chip` style, and add no new dependencies.
- **Out of scope:** all backend work (I1). Until I1 merges, develop against the tech plan's contract.
  A temporary mock in `api.ts` behind `import.meta.env.DEV` is fine, but remove it before merging.
- **Contract:** the tech plan's *Interfaces & contracts*: JSON shapes, endpoints, the 422 `loc`
  values and their messages, and the component props.
- **Files:** see `touches`.
- **Acceptance criteria:**
  - Given a strategy answer with 2 proposals, then each has its own button. Clicking a button opens the prefilled Step 1 with empty dates and
    counties (AC1, AC2).
  - Given Step 1 with no start date, or a discount of 0, 101 or 12.5, then Next stays put and shows
    the field error. A discount of 100 is allowed (AC4, AC5).
  - Given the pilot is on with size 100, or with a pilot end on or after the campaign start, then
    Next shows the matching error. With the pilot off, Review shows "No pilot" (AC6, AC7, AC8).
  - Given Step 3, when Back is clicked twice, then Step 1 has every value unchanged. Esc on an
    edited draft asks to discard (AC9, AC12).
  - Given a successful save, then the dialog closes, the toast shows, and the button reads
    "Saved ✓". A second save warns first. A failed save keeps the dialog and its values. A
    double-click sends one request (AC11, AC13, AC14, AC15).
- **How to verify:** `make build`. Then by hand in `make frontend` against the ACs, using the mock
  or I1's backend. There is no frontend test runner, per tech-plan decision D10.

### I3: End-to-end verification against a real database — CAI-9
- **Wave:** 1 · **Depends on:** I1, I2 · **Estimate:** S
- **Why:** I1 and I2 were each tested alone. Only a real run proves that the saved row matches the
  review screen, which is the database check the user plans to do (AC11, AC13, AC15).
- **Scope:**
  - Run `make migrate`, then `make backend` and `make frontend`.
  - Walk AC1–AC15 in the browser. After each save, check it with
    `SELECT * FROM campaign c LEFT JOIN campaign_pilot p ON p.campaign_id = c.id ORDER BY c.created_at DESC LIMIT 1;`
  - Record the results in `docs/specs/campaign-from-strategy/verification.md`.
  - Fix small integration bugs in place, and file anything larger as a new issue.
- **Out of scope:** new features.
- **Files:** see `touches`.
- **Acceptance criteria:**
  - Given a saved campaign with a pilot, then the `campaign` and `campaign_pilot` rows match every
    value on the review step, with `status = 'scheduled'` and `source_proposal` holding the
    proposal it came from (AC11).
  - Given a double-click on Save, then exactly one row exists for that `client_token` (AC15). The
    same proposal saved twice on purpose gives two rows with the same `source_proposal` (AC13).
- **How to verify:** `verification.md` lists AC1–AC15 with their results, and `make test lint build`
  passes.
