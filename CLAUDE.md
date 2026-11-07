# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Constella AI draws a store's sales as a network of product types (`item_tag`): which are bought
together (lift, co-orders), which bridge others, which form communities. A chat answers questions
about the network the graph currently shows, and every figure in an answer is traceable to a tool
call. `README.md` covers the product and the user-facing behaviour in full.

## Commands

Run from the repo root (`make help` lists everything). The uv project lives in `backend/`, not
the root.

```bash
make install     # uv sync, npm install, prek hooks, creates backend/.env from .env.example
make migrate     # creates the campaign tables (app/infra/sql/schema/*.sql); safe to re-run
make backend     # FastAPI dev server on :8000 (uv run --env-file .env fastapi dev app/main.py)
make frontend    # Vite on :5173, proxies /api to :8000
make test        # backend unit tests — no database or API key needed
make lint        # prek run --all-files: ruff check --fix, ruff format, sqlfluff fix+lint, whitespace
make build       # frontend: tsc && vite build (the only frontend type-check)
```

Single test: `cd backend && uv run pytest tests/test_reviewer.py::test_name -q`
(pytest's `testpaths` is `tests`, so evals are never picked up by plain `pytest`).

Evals call the model (costs money) and need `OPENAI_API_KEY`; most also need `TEST_DATABASE_URL`:
`make golden` (regenerates `evals/data/invoice.csv` with a fixed seed, **drops and refills** the
test DB's `invoice` table, rebuilds `golden.json`), then `make eval`, `eval-analyst`,
`eval-router`, `eval-scientist`, `eval-writer`. Most run through `deepeval test run`;
`eval-router` is plain pytest. Never point `TEST_DATABASE_URL` at the real database.

Ruff: line length 100, rules `E F I UP B SIM`. SQL in `app/infra/sql/` is linted by sqlfluff
(`backend/.sqlfluff`).

## Architecture

```
frontend (React 19 + Vite + Tailwind 4) ──/api──▶ backend (FastAPI) ──▶ Postgres `invoice` (read-only)
                                                      └──▶ OpenAI Agents SDK (`agents` package)
```

### Data layer (`app/infra/data.py`)
- `load_network(days, segment)` runs the named queries in `app/infra/sql/*.sql` (loaded by file
  name via `query(name, params)`) over a **read-only** connection and builds items, pairs (above
  a min co-order threshold scaled to the scope), lift, communities and bridges with networkx.
- It is `@lru_cache`d per scope: the data is assumed not to change while the server runs.
  `load_catalog` / `load_bundles` are cached the same way.
- Campaign store: `app/infra/store.py` is the only module that writes (`campaign`,
  `campaign_pilot`); `data.py` stays read-only. A campaign saved from an AI proposal keeps a copy
  of it in `source_proposal`. The rules a campaign must keep are code in `app/campaigns.py`.
- `GET /api/network` and every agent tool read this same function, so what the agent says about a
  scope and what the graph draws for it cannot disagree. Keep it that way: tools must not query
  the DB with their own thresholds.

### Agent versions (`app/versions/`, picked by `AGENT_VERSION` in `main.chosen()`)
- `v1`: prompt-only baseline (network summarised into the prompt), for evals.
- `v2`: the analyst with tools → reviewer → optional scientist chart. `v2.Answer` extends the
  analyst's `Reply`.
- `v3` (default): `router → analyst (reviewed) → strategist (reviewed, if planned) → writer`, plus
  `scientist` if the router planned a chart. `v3.Answer` extends `v2.Answer`. The analyst is
  shared unchanged with v2, so v2 and v3 give the same answer to a factual question.
- Follow-ups: `/api/ask*` takes an optional `history` (`app/roles/conversation.py`; the app sends
  its last 3 turns). v3's router, analyst and strategist read it; v1/v2 ignore it. It is never
  reviewer context: an earlier answer's figures must be looked up again.

### The ledger — the core invariant
- `app/tools/lookups.py` defines `Run` (segments, `ignored` types, `ledger`) as the Agents SDK run
  context and the `TOOLS` list. Every tool call goes through `record()`, which appends an entry
  `{"id": "L1", tool, args, result}` and returns the result tagged with its `ledger_id`.
- The model never writes SQL and must never compute a figure: each figure in a reply cites a
  ledger id.
- `app/roles/reviewer.py` is **code, not a model**: it checks each cited figure is in the cited
  ledger result, every number in the text came from the question or a tool, and every item/pair
  is on the graph. A failed review sends the reply back to the analyst once with notes.
- The strategist's campaigns are likewise checked in code (types on the graph, discount in range,
  real segment, not in `ignored`); the writer only writes slogans for campaigns that passed.
- The scientist never types numbers: it picks a chart type and points it at one ledger entry.
- Tools return `{"error": ...}` (e.g. unknown segment with closest spellings) so the model can call
  again, rather than raising.

### Streaming and progress
- `POST /api/ask/stream` returns NDJSON: `{"step": ...}` lines, then one `{"answer": ...}` or
  `{"error": ...}`. The frontend parser is `frontend/src/api.ts`.
- `app/infra/progress.py` uses a `ContextVar` listener so roles/tools call `progress.step(...)`
  without knowing whether anyone listens; tools run in worker threads, so `main.ask_stream`
  forwards events with `loop.call_soon_threadsafe`.

### Frontend
- `src/types.ts` hand-mirrors the backend's response shapes (network and `Answer`); update it when
  changing a Pydantic answer model or the network dict.
- `src/graph/` renders the network and toolbar (period, segment, view, line width); `src/chat/`
  renders answers, citations, ledger, review verdict, charts and progress. The chat sends the
  graph's current filters, the user's ignored types and the recent turns with each question.

## Conventions
- Tests in `backend/tests/` must run without a database or API key: they build networks/ledgers
  inline (see `tests/test_reviewer.py`) rather than calling Postgres or the model.
- Commits follow `type(CAI-N): message` with the Linear ticket id; branches are `feat/CAI-N`.
- Docstrings and comments explain *why* in plain prose; match that style.
