# PLAN.md

**What I'm building:** A Boldin clone that uses my own historical return data to allow me to exhaustively plan for retirement — not only the period before retirement, but also the period during retirement.

**What this project is meant to teach me:** This project is less about teaching and more about creating something I would actually use. It's scoped primarily around app architecture (frontend/backend separation, API design, data flow, file organization), since I already understand the finance concepts involved.

**Explicit constraints:** None beyond what's captured in this plan.

---

## 1. Overview

- App name: Personal Retirement Assistant
- One-sentence description: A Boldin clone that uses my own historical return data to allow me to exhaustively plan for retirement — not only the period before retirement, but also the period during retirement.
- Concept(s) this reinforces: Application architecture — specifically, how a frontend and backend are separated and communicate, and how data flows through a growing app.

## 2. Learning Boundary

This project should primarily teach:

- How a frontend and backend are separated and communicate (API calls), applied at a larger scale than past exercises
- How application data flows from user input → backend logic → storage → back to the UI
- How a growing app stays organized (file/module structure) as features accumulate

Things the AI should avoid introducing unless explicitly approved:

- Authentication / user accounts (single-user app, no login needed)
- ORMs (raw SQL is fine — SQL already familiar from a past project)
- Async/background job patterns
- Dependency injection or other enterprise-y abstractions
- WebSockets / real-time sync
- Microservices or multi-service architecture
- Local LLM integration and account/bank linking (deliberately deferred — see Section 13)

## 3. Core Features (MVP)

- User can enter multiple accounts (name, type — post-tax/pre-tax, current balance)
- User can enter current age and planned retirement age
- User can specify annual contribution amounts, split by account (applied until retirement age)
- User can input their own historical annual return data (1970–present or whatever range is uploaded), applied uniformly across the whole portfolio (single shared investment strategy)
- User can set a withdrawal rule: before age 59.5, draw from post-tax accounts only; after 59.5, draw by a fixed percentage split (pre-tax/post-tax) that the user specifies
- User can choose a return calculation mode per scenario:
  - **Mean/stdev mode** (rolling-window historical simulation): select a range of eligible starting years; for each one, simulate the full projection using actual sequential historical returns from that starting point forward; then, for each forward year, take the mean and standard deviation across all simulations that reached that year, and show confidence bands from those. Full methodology in Section 4a.
  - **Historical replay mode**: select a single starting year; replay that one actual historical sequence of returns forward in order
- App runs a year-by-year projection of account balances from now through an end age (e.g. 95), using the selected return mode
- Retirement expenses are entered as a flat annual number (today's dollars) and adjusted for inflation each year using a per-scenario inflation rate
- If projected funds are depleted before end_age, balance floors at zero and a "funds depleted at age X" flag is shown
- User can create and compare multiple scenarios side by side (e.g. retire at 55 vs. 57), each with its own ages, expenses, withdrawal split, inflation rate, and return mode — but sharing the same set of accounts
- Results shown as a chart and/or table of balances over time per scenario

## 4. Data Model

**Account**
- Purpose: Represents one of the user's real financial accounts.
- Fields: `id`, `name` (text), `type` (post-tax | pre-tax), `current_balance` (number), `annual_contribution` (number, applied until retirement)
- Relationships: None (shared across all scenarios, not owned by any one scenario)
- Validation rules: `name` required, non-empty; `current_balance` ≥ 0; `annual_contribution` ≥ 0

**Scenario**
- Purpose: Represents one retirement plan variant (e.g. "Retire at 55") that can be compared against others.
- Fields: `id`, `name`, `current_age` (int), `retirement_age` (int), `end_age` (int), `expected_expenses_in_retirement` (number, annual, today's dollars), `withdrawal_split_pretax_pct` (0–100), `inflation_rate_pct` (number), `return_mode` (mean_stdev | historical_replay), `return_start_year` (int, required when return_mode = mean_stdev — the minimum year allowed as a simulation's starting year), `return_end_year` (int, optional when return_mode = mean_stdev — the maximum year allowed as a simulation's starting year; if left blank, defaults to the most recent year present in AnnualReturn data at calculation time), `replay_start_year` (int, used when return_mode = historical_replay — the single starting year for that one replayed sequence)
- Relationships: None (all scenarios share the same Account records; a scenario doesn't own its own copy of accounts)
- Validation rules: `current_age` < `retirement_age` < `end_age`, all positive integers; `withdrawal_split_pretax_pct` between 0–100; `inflation_rate_pct` within a sane range (e.g. -5 to 20, to catch typos); `return_start_year`, `return_end_year` (if provided), and `replay_start_year` must fall within years actually present in AnnualReturn data; if both `return_start_year` and `return_end_year` are provided, `return_start_year` ≤ `return_end_year`

## 4a. Mean/Stdev Return Mode — Calculation Methodology

This is a rolling-window historical simulation, not a simple flat-average projection. It must be implemented exactly as follows, since it needs to match the user's existing spreadsheet:

**Step 1 — Determine eligible starting years.**
Let `last_data_year` = the most recent year present in `AnnualReturn`. Eligible starting years are every year S in `AnnualReturn` where `return_start_year` ≤ S ≤ (`return_end_year` if set, otherwise `last_data_year`).

**Step 2 — Run one simulation per eligible starting year.**
For each eligible starting year S:
- Initialize simulation balances from the scenario's current accounts, tracked as two running subtotals: post-tax and pre-tax (both needed separately because of the withdrawal rule below; both grow at the same rate since one return series applies to the whole portfolio).
- Let `years_until_retirement` = `retirement_age` − `current_age`, and `projection_horizon` = `end_age` − `current_age`.
- For each forward year offset n = 1, 2, 3, ... up to `projection_horizon`:
  1. The historical year this offset maps to for this simulation is `S + n − 1`. If that year is greater than `last_data_year`, this simulation stops here — it has no data to continue, and does not contribute to offset n or any later offset.
  2. **Contribution/withdrawal is applied first, before growth:**
     - If n ≤ `years_until_retirement` (pre-retirement): add each account's `annual_contribution` to the matching (post-tax/pre-tax) subtotal.
     - If n > `years_until_retirement` (post-retirement): calculate that year's withdrawal need as `expected_expenses_in_retirement` inflated by `inflation_rate_pct`, compounded for n years. If the age at this offset (`current_age + n`) is under 59.5, withdraw the full amount from the post-tax subtotal only. If 59.5 or over, split the withdrawal between subtotals per `withdrawal_split_pretax_pct`. If a subtotal is insufficient, floor it at zero rather than going negative (see Section 10).
  3. **Then apply growth:** grow both subtotals by that year's actual historical return (`return_pct` for year `S + n − 1` in `AnnualReturn`).
  4. Record the combined (post-tax + pre-tax) ending balance for this simulation at offset n.

**Step 3 — Aggregate across simulations, per forward year.**
For each offset n = 1 to `projection_horizon`:
- Collect the ending balance at offset n from every simulation that had enough data to reach it (i.e., every eligible S where `S + n − 1` ≤ `last_data_year`).
- Compute the mean and standard deviation of that set of balances.
- Compute confidence bands using z-scores (standard values, assumed unless corrected): 50% CI ≈ mean ± 0.674×stdev, 70% CI ≈ mean ± 1.036×stdev, 95% CI ≈ mean ± 1.96×stdev.

**Step 4 — Handle insufficient data.**
If, for some offsets near the end of `projection_horizon`, no simulation has enough data to reach that far, the app should: (a) show a warning before/alongside the results explaining that the selected starting-year range doesn't cover the full projection horizon, and (b) still render the chart/table for whatever offsets do have at least one simulation, rather than blocking the whole result.

**AnnualReturn**
- Purpose: Stores the user's actual historical annual returns for their investment strategy, uploaded via CSV.
- Fields: `id`, `year` (int), `return_pct` (number, e.g. 8.4)
- Relationships: None (global, shared across all accounts/scenarios — one uniform return series)
- Validation rules: `year` unique (no duplicates — CSV re-upload overwrites existing years rather than duplicating); `return_pct` no hard bound (legitimately can be very negative or positive)

No `ProjectionResult` entity — year-by-year projection results are always calculated fresh by the backend when a scenario is viewed, never stored, since return-methodology inputs are expected to change frequently and stored results would go stale.

**CSV upload format** (for AnnualReturn): two columns, `year` and `return`, with a header row (e.g. `1970,8.4`).

## 5. Assumptions

- Single user — no multi-user support, no login
- Desktop-first for v1 — not actively designed for mobile, but built as a standard web app (React frontend + Flask API) so mobile support could be added later via responsive design work, without an architectural rewrite
- Local network only — backend and (later) local LLM run on the user's own machines, not exposed to the internet
- Currency is USD
- All dollar amounts entered in today's (real) dollars; inflation applied only to retirement expenses via `inflation_rate_pct`
- Historical returns and account balances are updated manually (CSV upload / manual entry) — no live account syncing in v1
- All accounts are invested in the same strategy — one global return series applies uniformly to the whole portfolio, not per-account

## 6. Storage & Persistence

- Where does data live? SQLite — a single database file on disk (e.g. `retirement_planner.db`). No separate database server process.
- Tables (mirroring Section 4 directly):
  - `accounts`: `id`, `name`, `type`, `current_balance`, `annual_contribution`
  - `scenarios`: `id`, `name`, `current_age`, `retirement_age`, `end_age`, `expected_expenses_in_retirement`, `withdrawal_split_pretax_pct`, `inflation_rate_pct`, `return_mode`, `return_start_year`, `return_end_year`, `replay_start_year`
  - `annual_returns`: `id`, `year`, `return_pct`
- No browser storage (localStorage) used for persistent data — only React state for in-session UI.

## 6a. What's Not Tracked in Git

Given this stack (Python/Flask, React, SQLite), the following should never be committed — set up in `.gitignore` during Build Order Step 1, not added reactively later:

- **Python artifacts**: `__pycache__/`, `*.pyc`, virtual environment folder (`.venv/` or `venv/`) — regenerated locally, not source
- **React/Node artifacts**: `node_modules/`, build output (`build/` or `dist/`) — regenerated from `package.json`
- **The SQLite database file** (`retirement_planner.db`) — this holds real personal financial data (actual balances, actual projections), not just build output; it must never enter git history, even in a private repo
- **Uploaded CSVs**, if saved to disk (e.g. an `uploads/` folder) — same reason: real financial data
- **Env/secrets files** (`.env`) — nothing needs one yet, but excluded preemptively since the future local LLM connector (Section 13) will likely need a config value (e.g. a local server URL) that shouldn't be hardcoded into tracked files
- **OS files**: `.DS_Store`, `Thumbs.db`

## 7. Architecture

- **Backend** (Python):
  - `app.py` / `server.py` — API entry point, routes
  - `database.py` — SQLite connection + raw SQL queries (no ORM)
  - `projection.py` — core calculation engine: contribution/withdrawal logic, mean/stdev and historical-replay return modes. Deliberately isolated so the withdrawal rule (currently a fixed percentage split) can be swapped for real tax-optimized logic later without touching the rest of the app.
  - `models.py` (optional) — plain data structures matching Section 4's entities, not an ORM
- **Frontend** (React):
  - Accounts view (add/edit/delete accounts)
  - Scenarios view (create/edit/delete scenarios, select scenarios for comparison)
  - Results view (charts via Recharts, tables, confidence bands, depletion flags)
- **Data flow**: Frontend sends account/scenario data to backend via API → backend saves to SQLite. When viewing results, frontend requests a projection → backend runs `projection.py` fresh using current DB data → returns computed year-by-year results → frontend renders as chart/table. Nothing is computed client-side except UI state.

## 8. Tech Stack

- **Python** — backend language
- **Flask** — lightweight API framework; avoids async/validation patterns not yet needed
- **SQLite** (via Python's built-in `sqlite3` module) — database, single file, no server to manage
- **React** — frontend UI framework; supports the charting/comparison UI needs and reinforces frontend/backend separation
- **Recharts** — charting library, integrates natively with React
- **Python's built-in `csv` module** — parsing the historical returns upload

## 9. Key User Flows

**Flow 1: Adding an account**
1. Open the app, land on an "Accounts" page (empty on first use)
2. Click "Add Account," enter name, type (post-tax/pre-tax), current balance, annual contribution
3. Save — appears in a list of accounts, editable/deletable

**Flow 2: Uploading historical returns**
1. Go to "Historical Returns" page
2. Upload CSV (`year`, `return` columns, with header row)
3. App merges new data into `annual_returns`: new years are added, existing years are overwritten with the new value
4. Confirmation shown (e.g. "Loaded X years, range Y–Z; N years updated, M years added") plus a simple preview table to sanity check

**Flow 3: Creating a scenario**
1. Go to "Scenarios" page, click "New Scenario"
2. Enter: name, current age, retirement age, end age, expected retirement expenses, withdrawal split %, inflation rate %, and return mode (mean/stdev with a year range, or historical replay with a start year)
3. Save — scenario appears in a list

**Flow 4: Viewing/comparing results**
1. From the Scenarios list, select one or more scenarios to view
2. App calls the backend, which runs the projection fresh for each selected scenario. For mean/stdev mode, this means running the full rolling-window simulation described in Section 4a (one simulation per eligible starting year, aggregated per forward year into mean + confidence bands). For historical replay mode, it means the single replayed sequence. Either way: contributions until retirement → withdrawals after, per the 59.5 rule and account type.
2a. If mean/stdev mode can't cover the full projection horizon with available data, a warning is shown alongside the results (see Section 4a, Step 4), and the chart/table simply stops wherever data runs out.
3. Results shown as a chart (balance over time, one line per scenario) and a table
4. If mean/stdev mode, chart also shows a shaded confidence band
5. Contributions stop and withdrawals begin automatically once `retirement_age` is reached, driven by the projection logic (not stored as separate account data)

## 10. Edge Cases & Error Handling

- CSV upload with malformed rows (missing value, non-numeric return/year) → reject those rows individually, show which rows failed and why, still process valid rows
- CSV upload with duplicate years → overwrite existing value with the new one (per Flow 2)
- Scenario with `current_age` ≥ `retirement_age`, or `retirement_age` ≥ `end_age` → validation error, not saved
- No accounts exist yet when viewing a projection → clear message directing user to add an account, not a blank/broken chart
- No historical return data uploaded yet when viewing a projection → clear message, not a silent failure or crash
- Selected year range (mean/stdev mode) or replay start year (historical replay mode) falls outside years present in `annual_returns` → validation error stating the valid available range
- `return_start_year` > `return_end_year` (mean/stdev mode, when both are provided) → validation error, not saved
- Mean/stdev mode: no eligible starting year has enough historical data to cover the full projection horizon (`end_age` − `current_age` years) → warn before/alongside results, then still show the chart/table for whatever forward years do have at least one simulation reaching them (per Section 4a, Step 4)
- `withdrawal_split_pretax_pct` outside 0–100 → validation error
- Funds depleted before `end_age` → balance floors at zero for remaining years, with a "funds depleted at age X" flag shown in results

## 11. Simplicity Rules

Unless there's a specific, stated reason otherwise:

- Use the fewest moving parts that solve the problem.
- Avoid introducing new libraries.
- Avoid abstractions before they're needed.
- Prefer explicit code over clever code.
- Prefer one straightforward implementation over a generic or reusable one.

## 12. Out of Scope (For This Build)

- Local LLM chat integration (later milestone)
- Bank/brokerage account linking (later milestone)
- Tax-bracket-aware / truly tax-optimized withdrawal ordering (v1 uses a fixed pre/post-tax percentage split instead)
- Social Security income modeling
- Multiple account types beyond post-tax/pre-tax, e.g. Roth
- Healthcare/Medicare cost modeling
- Roth conversion strategy optimized against ACA subsidy cliffs
- Full Monte Carlo simulation with percentile distributions (v1 uses mean/stdev and historical replay instead)
- Authentication/multi-user support
- Mobile-optimized layout (addable later, not built now)
- Live/automatic data sync — all data entry (accounts, returns) is manual/CSV-based in v1

## 13. Future Ideas

- Local LLM integration (Qwen models on a separate machine) to ask questions about the plan
- Bank/brokerage account linking for automatic balance updates
- Tax-bracket-aware withdrawal optimization (replacing the fixed percentage split)
- Social Security timing/amount modeling
- Roth account support and Roth conversion strategy
- Roth conversion optimization against ACA subsidy cliffs, before Medicare eligibility
- Healthcare/Medicare cost modeling
- Full Monte Carlo simulation (many randomized simulated paths, percentile-based outcomes) as an alternative/addition to mean/stdev and historical-replay modes
- Long-term care and estate planning modeling
- Mobile-responsive layout
- Historical-replay mode enhancements (e.g. replaying arbitrary custom stretches, not just "from year X forward")

## 14. Build Order

1. **Project scaffolding** — Flask backend serving a basic API, React frontend that can talk to it (a simple round trip), SQLite database file created with the `accounts`, `scenarios`, `annual_returns` tables (empty, per Section 6 schema). Includes a `.gitignore` set up from the start (see Section 6a) — not added later once something's already been committed by accident. Proves frontend, backend, and database are wired together correctly; nothing functional yet.
2. **Accounts CRUD** — Backend API routes to create/read/update/delete `Account` records; React "Accounts" page to add, view, edit, delete accounts, with Section 4 validation rules enforced. Basic, reasonable styling included (not bare HTML, not a full design pass).
3. **Historical returns upload** — Backend route to accept CSV upload, parse it, merge into `annual_returns` (overwrite on duplicate year), with malformed-row handling per Section 10. React "Historical Returns" page with upload UI and confirmation/preview table. Basic styling included.
4. **Scenario CRUD** — Backend API routes for `Scenario` records; React "Scenarios" page to create/edit/delete scenarios with all Section 4 fields, validation rules enforced (age ordering, percentage bounds, year range must exist in `annual_returns`). Basic styling included.
5. **Core projection engine (mean/stdev mode only)** — `projection.py` logic implementing the full rolling-window historical simulation from Section 4a: one simulation per eligible starting year, contributions/withdrawals applied before growth each year, aggregated per forward year into mean + z-score confidence bands (50%/70%/95%). Floors at zero on depletion, flags depletion age, warns if data can't cover the full projection horizon. Exposed via backend API route; not yet wired to frontend (backend only, no UI styling concerns).
6. **Results view (single scenario, mean/stdev mode)** — React "Results" page calling the projection API for one scenario, rendering a chart (Recharts, with confidence band) and a table. Basic styling included.
7. **Historical replay mode** — Add the second return calculation mode to `projection.py` (replay actual historical sequence from a chosen start year), selectable per scenario, reflected in the Results view.
8. **Multi-scenario comparison** — Extend the Results view to select multiple scenarios and see them overlaid/side-by-side (chart + table). Basic styling included.
9. **Final visual consistency pass** — Lighter than a full redo: unify colors/typography/spacing across all pages, refine chart presentation, address inconsistencies now that everything exists together, to meet the "looks like real retirement software" bar from Section 3.

## 15. Open Questions

None currently — everything raised during planning was resolved into a decision rather than deliberately deferred. Add here if something genuinely open comes up later.

## 16. Decisions Log

- Dropped "expected income until retirement" as a field — contributions are entered directly per account, so income isn't needed by the projection math. Income may return if/when tax or ACA-subsidy features are built, since those need actual income, not just savings rate.
- Withdrawal logic (fixed pre/post-tax split) deliberately isolated in its own function/module so it can be swapped for real tax-optimized logic later without touching the rest of the app.
- Chose SQLite over a heavier database (Postgres/MySQL) — single-user, local-only app doesn't need a running database server.
- Chose React over plain HTML/JS — driven by charting/comparison UI needs and reinforcing the frontend/backend separation that's this project's core learning goal.
- Chose Flask over FastAPI — avoids introducing async/validation patterns not yet needed (Section 2 boundary).
- Chose "bake in basic styling per step" over "separate final polish pass" — better fits small, reviewable steps, especially important for a local model doing the implementation (smaller diffs are easier to get right than one large multi-file restyle).
- Return methodology (mean/stdev vs. historical replay) made a per-scenario setting, not global, so different comparison scenarios can use different assumptions.
- No `ProjectionResult` storage entity — results always computed fresh, since return-methodology inputs are expected to change frequently.
- Pulled multiple accounts and scenario comparison forward into MVP (originally Tier 2) since they're core to actual usability for someone near retirement.
- Deferred true tax-optimized withdrawal ordering to Tier 2/3, in favor of a fixed, user-specified pre/post-tax percentage split for v1 (isolated for easy future replacement).
- Deferred full Monte Carlo simulation to Tier 2/3, in favor of two simpler v1 modes: mean/stdev-based projection with a confidence band, and historical replay of an actual return sequence.
- Replaced the originally-planned "single flat mean return + stdev of annual returns" calculation with a rolling-window historical simulation (Section 4a), to match the user's existing spreadsheet methodology: one simulation per eligible historical starting year, aggregated per forward year into a mean and confidence bands.
- `return_end_year` (max eligible starting year, mean/stdev mode) made optional, defaulting to the most recent uploaded data year, since the primary use case is excluding old years (e.g. the 1970s/80s), not excluding recent ones.
- Contribution/withdrawal is applied before that year's growth, not after — matches the user's spreadsheet convention.
- Withdrawals are calculated and applied once per year (at the start, before growth), even though real-world withdrawals happen bi-monthly — annual return data doesn't support meaningful sub-year timing, so bi-monthly withdrawal timing was simplified away for v1 (noted here in case it's revisited later).
- Confidence interval z-scores (0.674 / 1.036 / 1.96 for 50%/70%/95% CI) are an assumption based on standard statistical convention for a normal distribution — not explicitly confirmed against the user's spreadsheet formulas, so worth double-checking against actual output once built.

## 17. Success Criteria

- Can enter real accounts and get a projection that matches a hand-calculation for at least one simple case
- Can compare at least two realistic scenarios (e.g. different retirement ages) and get a clear read on which leaves the user better off / whether funds last through `end_age`
- Can switch between mean/stdev and historical replay return modes and see results change in an intuitively sensible way
- Can explain, in own words, how the frontend, backend, and database pieces fit together
- *(Longer-term, not v1)*: once Tier 2/3 features exist, the app fully replaces the user's spreadsheet for real retirement decisions

## 18. Acceptance Tests

- [ ] Add an account with name, type, balance, contribution — it appears in the Accounts list
- [ ] Edit an account's balance — change is saved and reflected
- [ ] Delete an account — it's removed from the list
- [ ] Upload a valid CSV of historical returns — years load correctly, confirmation shows correct count/range
- [ ] Re-upload a CSV with an overlapping year — that year's value is overwritten, others untouched
- [ ] Upload a CSV with a malformed row — that row is rejected with a clear message, valid rows still load
- [ ] Create a scenario with valid ages/expenses/withdrawal split/inflation rate/return mode — it saves and appears in the Scenarios list
- [ ] Try to create a scenario where `retirement_age` ≤ `current_age` — rejected with a clear validation message
- [ ] View results for a single scenario in mean/stdev mode — chart shows a projected line with a confidence band, table shows year-by-year balances
- [ ] View results for a scenario in historical replay mode — chart reflects the actual replayed sequence of returns
- [ ] Compare two scenarios side by side — both appear correctly, distinguishable from each other
- [ ] Set up a scenario deliberately designed to deplete funds early — balance floors at zero, "funds depleted at age X" is shown
- [ ] Try to view a projection with no accounts entered — clear message shown, not a crash/blank screen
- [ ] Try to view a projection with no historical return data uploaded — clear message shown, not a crash
- [ ] For a scenario in mean/stdev mode, manually hand-calculate the mean and stdev at year 1 (a small, checkable case) and confirm the app's output matches
- [ ] Set `return_start_year` close to the most recent data year with a long projection horizon — confirm the app warns that not all years are covered, and still shows results through whatever years are covered
- [ ] Leave `return_end_year` blank in mean/stdev mode — confirm it defaults to the most recent uploaded year rather than erroring

## 19. What I Should Be Able to Explain Afterward

- How the frontend (React) and backend (Flask API) are separated, and how they communicate — what a request/response actually looks like going from a button click to a database write and back
- How data flows: user input → API call → backend logic (`projection.py`) → SQLite → back to the UI as a chart/table
- Why the projection is calculated fresh each time instead of stored, and what that tradeoff means
- Why the withdrawal logic is isolated in its own function — what "keeping a seam" for future changes actually buys
- The overall file/module structure and what belongs where, well enough to know where to go to change something specific (e.g. "I want to tweak how contributions are applied" → `projection.py`)
