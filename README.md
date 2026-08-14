# Personal Retirement Assistant (Boldin-clone)

A single-user, local-only retirement planning web app. It projects your
account balances from now through an end age (e.g. 95) using **your own
historical return data** (uploaded as CSV) rather than generic market
assumptions, so you can exhaustively plan both the pre-retirement and
retirement periods.

## What it does

- **Accounts** — enter your real accounts (post-tax / pre-tax, current
  balance, annual contribution). Accounts are shared across all scenarios.
- **Historical returns** — upload a CSV of annual returns (`year,return`
  columns, header row). Re-uploads overwrite existing years.
- **Scenarios** — create multiple plan variants (e.g. "Retire at 55" vs
  "Retire at 57") with their own ages, retirement expenses, inflation rate,
  withdrawal split, return mode, planned large expenditures, and future
  income streams.
- **Projections** — a month-by-month simulation per scenario:
  contributions until retirement age, withdrawals after. Before 59.5,
  withdrawals come from post-tax accounts only (with a pre-tax fallback and
  warning if post-tax runs short); after 59.5, they follow your chosen
  pre-tax/post-tax split. Balances floor at zero, with a
  "funds depleted at age X" flag.
- **Three return modes** (chosen per scenario):
  - `mean_stdev` — one simulation per eligible historical starting year,
    aggregated per forward year into a mean with 50/70/95% confidence bands
  - `historical_replay` — one actual historical return sequence replayed
    forward from a chosen start year
  - `monte_carlo` — 1,000 randomized paths built by block-bootstrap
    resampling of your real returns, with percentile bands plus a
    probability-of-depletion chart and overall success rate
- **Pages** — Accounts, Historical Returns, Scenarios, Results (single
  scenario, full detail), Comparisons (multiple scenarios overlaid,
  mean-only lines), and Live (tweak a saved scenario's fields and preview
  results without saving).

## Tech stack

- **Backend:** Python + Flask (raw SQL, no ORM), SQLite database
- **Frontend:** React + Recharts, built with Vite
- No authentication, no internet exposure — everything runs on your machine

## Running the app

Prerequisites: Python and Node.js installed.

1. One-time setup: run `install.bat` (installs Flask and the frontend
   dependencies), or manually:
   - `pip install -r backend/requirements.txt`
   - `cd frontend && npm install`
2. Start: run `start.bat`, which opens the backend
   (`http://localhost:5000`) and the frontend dev server
   (`http://localhost:3001`) in separate windows and opens the app in your
   browser. Leave both windows open while using the app.
3. Or manually, in two terminals:
   - `python backend/app.py`
   - `cd frontend && npm run dev`
4. Open `http://localhost:3001`. "Backend Status: Backend is running"
   confirms the two halves are connected.

## Project layout

```
backend/
  app.py           Flask API: all routes, validation, CSV upload
  database.py      SQLite connection + schema
  projection.py    The calculation engine (all three return modes)
  test_*.py        Ad-hoc tests for the projection engine
frontend/
  src/
    App.jsx        Navigation + backend status
    Accounts.jsx   Accounts page
    HistoricalReturns.jsx  CSV upload page
    Scenarios.jsx  Scenario create/edit/delete
    Results.jsx    Single-scenario results (bands, table, warnings)
    Comparisons.jsx  Multi-scenario overlay (mean-only)
    Live.jsx       Tweak-and-preview page
Returns.csv        Historical return data (year, return)
retirement_planner.db   SQLite database — created on first run, git-ignored
```

## Data & privacy

All data lives in `retirement_planner.db` (SQLite, in this folder). It
contains real personal financial data, so it is git-ignored and never
committed. Projections are always computed fresh from the current database
state — results are never stored.

## Documentation

- `PLAN.md` — the full plan: data model, calculation methodology
  (Section 4a), user flows, edge cases, and the Decisions Log
- `PROGRESS.md` — what has actually been built and how (read this first in
  a new session)
- `MONTE_CARLO_PLAN.md` — the sub-plan for the Monte Carlo mode
- `AGENTS.md` — how AI coding agents should work on this project
