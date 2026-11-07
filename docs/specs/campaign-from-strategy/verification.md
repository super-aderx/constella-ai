# Campaign from strategy: end-to-end verification

Requirements: ./requirements.md · Technical plan: ./tech-plan.md · Ticket: CAI-9

## Summary

- **Date:** 2026-11-07.
- **Verified:** `main` at `910bb7f` (CAI-7 backend, PR #7, and CAI-8 wizard, PR #8, both merged).
- **Result:** every requirement acceptance criterion that is still in scope (AC1–AC15) passes
  end to end. So do the three database checks of CAI-9 and every edge case in the requirements.
  One edge case passes as an accepted deviation (a type that is not in the catalog is flagged on
  Save, not before Next). No integration bugs were found.

The run used the real app, the real API and a real Postgres. Only the chat answer was canned, so
no model was called (see *Environment*). Every save was checked in SQL.

## Environment

| Part | What was used |
|---|---|
| Database | Docker `postgres:17-alpine` (PostgreSQL 17.11), container `cai9-pg`, port 55432. Throwaway: removed after the run. Never the real `DATABASE_URL`. |
| Data | `backend/evals/data/invoice.sql` and `invoice.csv` (3,319 lines, 13 product types, 4 segments, one county `高雄市`). This is the eval sample, not the production catalog. |
| Schema | `python -m app.infra.migrate`, run twice. Both runs exited 0 and the second changed nothing. The result was `campaign` and `campaign_pilot` as in the tech plan's data model, with `source_proposal jsonb` and no `proposal_id`. |
| API | `main` backend, `fastapi run app/main.py --port 8100` against `cai9-pg`. |
| App | `main` frontend, `vite --port 5180`; the browser sent `/api` to port 8100. |
| Browser | Chrome, driven by Playwright (which answered `/api/ask/stream` itself and forwarded the rest of `/api` to :8100). Every step can also be done by hand; see *How to repeat by hand*. |
| Chat answer | Canned (`/api/ask/stream` answered by the test) so that no model is called. Everything after the answer (the wizard, the endpoints, the store and Postgres) is real. |

The canned answer is one NDJSON line, the shape `/api/ask/stream` ends with. This is the exact
line the run used (save it as `answer.ndjson`):

```json
{"answer": {"text": "Here are campaign options.", "items": [], "pairs": [], "review": null, "strategy": {"text": "Options built on the network.", "campaigns": [{"name": "Morning set", "basis": "proven", "items": ["鮮乳", "吐司"], "discount_percent": 15, "audience": "忠誠客戶", "reason": "Milk and toast share 120 baskets.", "slogans": [{"text": "Rise and dine", "pun": null}]}, {"name": "Snack night", "basis": "potential", "items": ["洋芋片", "可樂"], "discount_percent": 10, "audience": null, "reason": "Chips and cola could sell together.", "slogans": []}], "figures": []}}}
```

For the catalog edge case only, the run used the same line with a third proposal appended to
`strategy.campaigns` (save it as `answer-catalog.ndjson`):

```json
{"answer": {"text": "Here are campaign options.", "items": [], "pairs": [], "review": null, "strategy": {"text": "Options built on the network.", "campaigns": [{"name": "Morning set", "basis": "proven", "items": ["鮮乳", "吐司"], "discount_percent": 15, "audience": "忠誠客戶", "reason": "Milk and toast share 120 baskets.", "slogans": [{"text": "Rise and dine", "pun": null}]}, {"name": "Snack night", "basis": "potential", "items": ["洋芋片", "可樂"], "discount_percent": 10, "audience": null, "reason": "Chips and cola could sell together.", "slogans": []}, {"name": "Unknown type set", "basis": "potential", "items": ["鮮乳", "不存在的類別"], "discount_percent": 20, "audience": null, "reason": "A proposal naming a type that is not in the catalog.", "slogans": []}], "figures": []}}}
```

"Morning set" stands in for the requirements' "Tea time bundle / Wholesale" example. "Snack night"
has no segment and no slogans, which is how a proposal looks when it did not pass the strategist's
check. The sample has no "teapot", so AC3's typo is `洋芋皮`, a typo for the type `洋芋片`.

## How to repeat by hand

**Never use `make migrate` or `make backend` for this.** Both read `backend/.env`, which points at
the real database. Ports 8000 and 5173 are left free for normal development: the API runs on 8100
and the app on 5181.

**1. Throwaway database** (from `backend/`). The migration runs twice; the second run must leave
the schema unchanged.

```bash
export CAI9_DB=postgresql://postgres:pw@localhost:55432/postgres
docker run -d --rm --name cai9-pg -e POSTGRES_PASSWORD=pw -p 55432:5432 postgres:17-alpine
docker cp evals/data/invoice.sql cai9-pg:/tmp/ && docker cp evals/data/invoice.csv cai9-pg:/tmp/
docker exec cai9-pg psql -U postgres -f /tmp/invoice.sql
docker exec cai9-pg psql -U postgres -c "\copy invoice FROM '/tmp/invoice.csv' CSV HEADER"   # COPY 3319

DATABASE_URL=$CAI9_DB uv run python -m app.infra.migrate          # "Applied campaigns.sql"
docker exec cai9-pg pg_dump -U postgres --schema-only -t campaign -t campaign_pilot | grep -v '^\\\(un\)\?restrict' > /tmp/schema-1.sql
DATABASE_URL=$CAI9_DB uv run python -m app.infra.migrate          # again: exits 0
docker exec cai9-pg pg_dump -U postgres --schema-only -t campaign -t campaign_pilot | grep -v '^\\\(un\)\?restrict' > /tmp/schema-2.sql
diff /tmp/schema-1.sql /tmp/schema-2.sql && echo "second run changed nothing"
```

`pg_dump` writes a random `\restrict` token in each dump, so those lines are left out of the
comparison. In this run the two dumps were otherwise identical.

**2. The API** on that database (from `backend/`):

```bash
DATABASE_URL=$CAI9_DB OPENAI_API_KEY=unused uv run fastapi run app/main.py --port 8100
```

**3. The app**, serving the canned answer. Put the two answer files above and this Vite config,
`vite.cai9.mjs`, in one folder outside the repo (here `~/cai9/`):

```js
// Serves the canned chat answer and forwards every other /api call to the API on :8100.
import { readFileSync } from "node:fs"
import { createRequire } from "node:module"
import { dirname, join } from "node:path"
import { fileURLToPath, pathToFileURL } from "node:url"

// This file lives outside the repo, so the app's plugins are found from frontend/, where Vite runs.
const fromApp = createRequire(join(process.cwd(), "package.json"))
const load = async (name) => (await import(pathToFileURL(fromApp.resolve(name)).href)).default
const [react, tailwindcss] = await Promise.all([load("@vitejs/plugin-react"), load("@tailwindcss/vite")])

const here = dirname(fileURLToPath(import.meta.url))
const canned = {
  name: "canned-answer",
  configureServer(server) {
    server.middlewares.use("/api/ask/stream", (_req, res) => {
      res.setHeader("Content-Type", "application/x-ndjson")
      res.end(readFileSync(join(here, process.env.CANNED ?? "answer.ndjson")))
    })
  },
}

export default {
  root: process.cwd(),
  plugins: [canned, react(), tailwindcss()],
  server: { proxy: { "/api": "http://localhost:8100" } },
}
```

Then, from `frontend/`:

```bash
npx vite --config ~/cai9/vite.cai9.mjs --port 5181 --strictPort
# for the catalog edge case, restart it with the third proposal:
CANNED=answer-catalog.ndjson npx vite --config ~/cai9/vite.cai9.mjs --port 5181 --strictPort
```

Open http://localhost:5181 and ask anything: the answer is always the canned one. This route was
itself checked in a plain browser session (a save, a 500 during an outage, and a 201 on retry).

**4. After each save, the row it stored:**

```bash
docker exec cai9-pg psql -U postgres -x -c "SELECT * FROM campaign c LEFT JOIN campaign_pilot p ON p.campaign_id = c.id ORDER BY c.created_at DESC LIMIT 1;"
```

**5. The database outage for AC14.** Run the first command with the wizard on Review, click Save,
check the error, then run the second command and click Save again:

```bash
docker exec cai9-pg psql -U postgres -d template1 -c "ALTER DATABASE postgres ALLOW_CONNECTIONS false"
docker exec cai9-pg psql -U postgres -d template1 -c "ALTER DATABASE postgres ALLOW_CONNECTIONS true"
```

**6. Clean up:** stop Vite and the API, then `docker stop cai9-pg` (it was started with `--rm`, so
the data goes with it).

Then follow the *What was done* column below, in order. The dates are fixed (campaigns in
December 2026, pilots in November 2026), so they are valid only until 2026-11-12. On a later run,
move them all by the same number of days.

## Results

| AC | What was done | Result | Evidence |
|---|---|---|---|
| AC1 | Asked for campaigns; the answer showed both proposals. | PASS | Each card has its own "Add as campaign" button, including "Snack night", which has no slogans. Screenshot 01. |
| AC2 | Clicked "Add as campaign" on "Morning set". | PASS | A centered window opened on Step 1. Title "Morning set", strategy = the proposal's reason, chips 鮮乳 and 吐司 labelled Type, discount 15, segment 忠誠客戶, both dates empty, "All counties". Screenshot 02. |
| AC3 | Typed `洋芋皮` in Products. | PASS | 洋芋片 appeared labelled "Type", with SKUs labelled "Product". ↓ and Enter added `厚切洋芋片 大包`; a clicked `原味洋芋片` was removed with its ×; `zzzzqq` showed "No products match 'zzzzqq'". Screenshot 03. |
| AC4 | Clicked Next with no start date. | PASS | Stayed on Step 1 with "Required." under "Starts on" (`aria-invalid="true"`). Screenshot 04. |
| AC5 | Set the dates to 2026-12-01 … 2026-12-11, then tried discounts 0, 101 and 12.5, then 100. | PASS | Each of 0, 101 and 12.5 kept Next on Step 1 with "Enter a whole number from 1 to 100."; 100 moved to Step 2. Then went back, set 15 and picked county 高雄市 ("1 selected"). |
| AC6 | On "Snack night", switched the pilot on, filled its dates, switched it off, then Next. | PASS | Review showed "No pilot" and "All customers". The stored row has no pilot (E2). Screenshot 08. |
| AC7 | Pilot on, size 100, then Next. | PASS | Stayed on Step 2 with "Enter a whole number from 1 to 99." |
| AC8 | Campaign start 2026-12-01, pilot end 2026-12-01, then Next. | PASS | Stayed on Step 2 with "Pilot must end before the campaign starts." Screenshot 05. Then set pilot 2026-11-12 … 2026-11-17 at 10 %, 10 % off, and switched auto-start on. |
| AC9 | On Review, clicked Back twice. | PASS | On Step 1 the title, discount, both dates, "1 selected" county and the SKU chip were unchanged, and Step 2 kept the pilot's end date. |
| AC10 | Opened Review. | PASS | It showed every value in words: the title, strategy, three products, "15% off", "Dec 1, 2026 – Dec 11, 2026", 忠誠客戶, 高雄市, and for the pilot "10% of the audience", "Nov 12, 2026 – Nov 17, 2026", "10% off" and "When the pilot passes: start the campaign automatically". Screenshot 06. |
| AC11 | Clicked Save. | PASS | The window closed, "Campaign saved" showed, and only this card reads "Saved ✓" (screenshot 07). The stored row matches the review value for value, and `source_proposal` is the clicked proposal's six fields without its slogans (E1). |
| AC12 | Opened "Morning set" again, edited the title, pressed Esc. | PASS | "Discard this campaign draft?" appeared. Cancel kept the window and "Changed title"; a second Esc with OK closed it. The campaign count did not change. |
| AC13 | Opened "Snack night" again (it reads "Saved ✓") and clicked Save. | PASS | "You already saved a campaign from this proposal. Save another?" appeared. Cancel sent nothing; OK stored a second, separate row (E3). |
| AC14 | Made the database refuse connections (`ALTER DATABASE postgres ALLOW_CONNECTIONS false`), then clicked Save. | PASS | The API logged `OperationalError … not currently accepting connections` and answered 500. The window stayed on Review with every value, showed "Could not save the campaign. Try again. The values are locked because the last attempt may have been saved." and disabled Back; the card still read "Add as campaign" and no row was stored (screenshot 09). After connections were allowed again, Save resent the same request and stored exactly one row (E5). |
| AC15 | After a page reload, double-clicked Save on a new "Morning set" draft. | PASS | One POST was sent and one row exists for its token (E4). |
| AC16 | — | Dropped | Conversion is not measured (decision D4, 2026-11-07). |

### CAI-9 database checks

| Check | Result | Evidence |
|---|---|---|
| A campaign saved with a pilot matches every value on the review step, with `status = 'scheduled'`, and `source_proposal` matches the clicked proposal. | PASS | E1, compared with screenshot 06 and the AC10 row above. |
| A double-click on Save stores exactly one row for that `client_token`. | PASS | E4. |
| The same proposal saved twice on purpose gives two rows with the same `source_proposal`. | PASS | E3: two tokens, identical `source_proposal`. |

## Edge cases

| Edge case (requirements) | Result | Evidence |
|---|---|---|
| A proposal with no segment starts with the segment empty (all customers). | PASS | "Snack night" opened with "All customers" and was stored with `segment` NULL (E2). |
| A proposed type that is no longer in the catalog is flagged and must be removed before Next. | PASS (accepted deviation) | The tech plan accepts flagging it on Save instead of before Next (*Risks*: the catalog does not change while the server runs). With "Unknown type set", Save got the server's 422, the wizard went to Step 1 and marked the chip "不存在的類別 is not in the catalog.", and no row was stored. After removing the chip, Save stored the campaign with `item_types = {鮮乳}`. `source_proposal` still records both proposed types (E6, screenshot 11). |
| A fuzzy search with no matches shows "No products match '<query>'". | PASS | AC3. |
| A failed save keeps the window on Review with every value, shows an error and allows a retry; no "Saved ✓". | PASS | AC14. The values are also locked until the retry is answered, as decided in the PR #8 review. |
| A double-click on Save stores one campaign. | PASS | AC15, E4. |
| A pilot switched off after its fields were filled is not saved; Review shows "No pilot". | PASS | AC6, E2: no `campaign_pilot` row. |
| Campaign dates moved after the pilot was set: Step 2 shows the error and Save is blocked until it is fixed. | PASS | With a valid pilot (ends 2026-11-17) and Review reached, went back and moved the campaign start to 2026-11-15. Next on Step 1 led to Step 2, where Next showed "Pilot must end before the campaign starts." No request was sent (screenshot 10). Review cannot be reached again until the pilot is fixed, which blocks Save. |
| A page reload may reset "Saved ✓"; the database stays the source of truth. | PASS | After a reload and a new answer, no card read "Saved ✓", and the campaign count was unchanged. |

## Issues found

None. No fix was needed and no new issue was proposed.

## Checks

| Command | Result |
|---|---|
| `make test` (no `DATABASE_URL` or `OPENAI_API_KEY` set) | 173 passed |
| `make lint` (and its hooks on this file) | every hook passed |
| `make build` | passed (tsc and vite build) |

No dependency manifest or lockfile changed.

## Evidence

The SQL was run with `psql` in `cai9-pg` right after the save it checks. E7 is the whole table at
the end of the run. A later check of the by-hand route (*How to repeat by hand*) added a seventh
row, "By-hand check", which is not part of the run.

**E1: "Morning set" with a pilot (AC11, CAI-9 check 1)**

```
SELECT * FROM campaign c LEFT JOIN campaign_pilot p ON p.campaign_id = c.id ORDER BY c.created_at DESC LIMIT 1;
-[ RECORD 1 ]----+---------------------------------------------------------------------------------------------------------------
id               | d28aafab-9dfd-4a4e-b513-17b3a9210470
source_proposal  | {"name": "Morning set", "basis": "proven", "items": ["鮮乳", "吐司"], "reason": "Milk and toast share 120 baskets.", "audience": "忠誠客戶", "discount_percent": 15}
client_token     | 1711fa9e-9ab4-4903-a92c-3780f529383f
status           | scheduled
title            | Morning set
strategy         | Milk and toast share 120 baskets.
item_types       | {鮮乳,吐司}
products         | {"厚切洋芋片 大包"}
discount_percent | 15
starts_on        | 2026-12-01
ends_on          | 2026-12-11
segment          | 忠誠客戶
counties         | {高雄市}
created_at       | 2026-11-07 13:33:17.818241+00
campaign_id      | d28aafab-9dfd-4a4e-b513-17b3a9210470
audience_percent | 10
starts_on        | 2026-11-12
ends_on          | 2026-11-17
discount_percent | 10
auto_start       | t
```

The review step showed (screenshot 06) and the row holds:

| Field on Review | Shown | Stored |
|---|---|---|
| Title | Morning set | `title` Morning set |
| Strategy | Milk and toast share 120 baskets. | `strategy` same |
| Products | 鮮乳 Type, 吐司 Type, 厚切洋芋片 大包 Product | `item_types` {鮮乳,吐司}, `products` {厚切洋芋片 大包} |
| Discount | 15% off | `discount_percent` 15 |
| Dates | Dec 1, 2026 – Dec 11, 2026 | `starts_on` 2026-12-01, `ends_on` 2026-12-11 |
| Customers | 忠誠客戶 | `segment` 忠誠客戶 |
| Counties | 高雄市 | `counties` {高雄市} |
| Pilot | 10% of the audience | `audience_percent` 10 |
| | Nov 12, 2026 – Nov 17, 2026 | `starts_on` 2026-11-12, `ends_on` 2026-11-17 |
| | 10% off | `discount_percent` 10 |
| | When the pilot passes: start the campaign automatically | `auto_start` t |
| (status) | | `status` scheduled |

**E2: "Snack night", pilot filled then switched off (AC6)**

```
-[ RECORD 1 ]----+---------------------------------------------------------------------------------------------------------------
id               | 9ea6af48-9dd4-43dd-8b37-f9e11f3b4e19
source_proposal  | {"name": "Snack night", "basis": "potential", "items": ["洋芋片", "可樂"], "reason": "Chips and cola could sell together.", "audience": null, "discount_percent": 10}
client_token     | ac097bdf-3264-4110-84fd-42460a82bf36
status           | scheduled
title            | Snack night
strategy         | Chips and cola could sell together.
item_types       | {洋芋片,可樂}
products         | {}
discount_percent | 10
starts_on        | 2026-12-05
ends_on          | 2026-12-20
segment          |
counties         | {}
created_at       | 2026-11-07 13:33:18.436539+00
campaign_id      |
audience_percent |
starts_on        |
ends_on          |
discount_percent |
auto_start       |
```

The pilot columns are empty because there is no `campaign_pilot` row.

**E3: the same proposal saved twice (AC13, CAI-9 check 3)**

```
SELECT client_token, created_at, source_proposal FROM campaign WHERE title = 'Snack night' ORDER BY created_at;
             client_token             |          created_at           | source_proposal
--------------------------------------+-------------------------------+--------------------------------------------------------------------------------------------------------------------------------
 ac097bdf-3264-4110-84fd-42460a82bf36 | 2026-11-07 13:33:18.436539+00 | {"name": "Snack night", "basis": "potential", "items": ["洋芋片", "可樂"], "reason": "Chips and cola could sell together.", "audience": null, "discount_percent": 10}
 4a20887b-94ba-4a71-a084-f1a1a87cc209 | 2026-11-07 13:33:19.451493+00 | {"name": "Snack night", "basis": "potential", "items": ["洋芋片", "可樂"], "reason": "Chips and cola could sell together.", "audience": null, "discount_percent": 10}
(2 rows)
```

**E4: double-click on Save (AC15, CAI-9 check 2)**

```
SELECT COUNT(*) AS rows_for_token FROM campaign WHERE client_token = '932bc8ec-f4d0-4874-a120-dc66742230d3';
 rows_for_token
----------------
              1
(1 row)
```

One POST was sent for this draft.

**E5: retry after the database refused connections (AC14)**

```
SELECT title, client_token, created_at FROM campaign WHERE client_token = '89501c7c-8471-4554-8fc7-07bbfa60bb49';
        title         |             client_token             |          created_at
----------------------+--------------------------------------+-------------------------------
 Snack night (outage) | 89501c7c-8471-4554-8fc7-07bbfa60bb49 | 2026-11-07 13:33:22.329361+00
(1 row)
```

While the database refused connections the count for this token was 0. Both POSTs (the failed
one and the retry) had the same body. The API log showed:

```
ERROR:root:Could not read what a campaign is checked against
psycopg.OperationalError: connection failed: … FATAL:  database "postgres" is not currently accepting connections
"POST /api/campaigns HTTP/1.1" 500 Internal Server Error
"POST /api/campaigns HTTP/1.1" 201 Created
```

**E6: a proposed type that is not in the catalog (edge case)**

```
SELECT title, item_types, source_proposal->'items' AS proposed_items FROM campaign WHERE client_token = 'd9170ba5-157d-4781-97d3-3f447cdb27c9';
      title       | item_types |      proposed_items
------------------+------------+--------------------------
 Unknown type set | {鮮乳}     | ["鮮乳", "不存在的類別"]
(1 row)
```

Before the chip was removed, Save got `422` and the count for this token was 0.

**E7: every campaign stored in the run**

```
           title            |  status   |  item_types   |      products       | discount_percent | starts_on  |  ends_on   | segment  | counties | pilots
----------------------------+-----------+---------------+---------------------+------------------+------------+------------+----------+----------+--------
 Morning set                | scheduled | {鮮乳,吐司}   | {"厚切洋芋片 大包"} |               15 | 2026-12-01 | 2026-12-11 | 忠誠客戶 | {高雄市} |      1
 Snack night                | scheduled | {洋芋片,可樂} | {}                  |               10 | 2026-12-05 | 2026-12-20 |          | {}       |      0
 Snack night                | scheduled | {洋芋片,可樂} | {}                  |               10 | 2026-12-05 | 2026-12-20 |          | {}       |      0
 Morning set (double-click) | scheduled | {鮮乳,吐司}   | {}                  |               15 | 2026-12-15 | 2026-12-25 | 忠誠客戶 | {}       |      0
 Snack night (outage)       | scheduled | {洋芋片,可樂} | {}                  |               10 | 2026-12-06 | 2026-12-21 |          | {}       |      0
 Unknown type set           | scheduled | {鮮乳}        | {}                  |               20 | 2026-12-02 | 2026-12-12 |          | {}       |      0
(6 rows)
```

Six saves gave six rows: no duplicates from the double-click or the retry, and nothing from the
discarded draft (AC12), the cancelled re-save (AC13) or the rejected saves (AC14, E6).

## Screenshots

Taken during the run. They are not committed; they are attached to the CAI-9 pull request.

| # | File | Shows |
|---|---|---|
| 01 | `01-answer-two-proposals.png` | The answer with a button on each proposal (AC1) |
| 02 | `02-step1-prefilled.png` | Step 1 prefilled from "Morning set" (AC2) |
| 03 | `03-search-typo.png` | Search results for `洋芋皮`, labelled Type and Product (AC3) |
| 04 | `04-required-start.png` | "Required." under the start date (AC4) |
| 05 | `05-pilot-overlap.png` | "Pilot must end before the campaign starts." (AC8) |
| 06 | `06-review-with-pilot.png` | Review with every value, pilot and auto-start (AC10, E1) |
| 07 | `07-saved-toast.png` | "Campaign saved" and "Saved ✓" on one card (AC11) |
| 08 | `08-review-no-pilot.png` | Review with "No pilot" (AC6) |
| 09 | `09-save-failed-locked.png` | The save error with Back locked (AC14). The toast behind is from the save just before. |
| 10 | `10-dates-moved-after-pilot.png` | Step 2 blocking after the campaign start moved (edge case) |
| 11 | `11-type-not-in-catalog.png` | The server's catalog error on the chip (edge case) |
