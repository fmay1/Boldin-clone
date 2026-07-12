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
- Fields: `id`, `name`, `current_age` (decimal, monthly precision — e.g. 46.25 means 3 months into age 46), `retirement_age` (decimal, monthly precision, same convention), `end_age` (int — whole years only, since precision here doesn't matter), `expected_expenses_in_retirement` (number, annual, today's dollars), `withdrawal_split_pretax_pct` (0–100), `inflation_rate_pct` (number), `return_mode` (mean_stdev | historical_replay), `return_start_year` (int, required when return_mode = mean_stdev — the minimum year allowed as a simulation's starting year), `return_end_year` (int, optional when return_mode = mean_stdev — the maximum year allowed as a simulation's starting year; if left blank, defaults to the most recent year present in AnnualReturn data at calculation time), `replay_start_year` (int, used when return_mode = historical_replay — the single starting year for that one replayed sequence)
- Relationships: None (all scenarios share the same Account records; a scenario doesn't own its own copy of accounts)
- Validation rules: `current_age` < `retirement_age` < `end_age`; `current_age` and `retirement_age` must be a whole number or a whole number plus a multiple of 1/12 (i.e., snap to monthly precision — reject values like 46.3 that don't correspond to a whole month); `end_age` a positive integer; `withdrawal_split_pretax_pct` between 0–100; `inflation_rate_pct` within a sane range (e.g. -5 to 20, to catch typos); `return_start_year`, `return_end_year` (if provided), and `replay_start_year` must fall within years actually present in AnnualReturn data; if both `return_start_year` and `return_end_year` are provided, `return_start_year` ≤ `return_end_year`

## 4a. Return Mode Calculation Methodology

This is a rolling-window historical simulation, not a simple flat-average projection. **The per-simulation mechanics in Step 2 are shared by both `mean_stdev` and `historical_replay` modes — they must be implemented as one function, not duplicated.** The only difference between the two modes is Step 1 (how many starting years are eligible) and Step 3 (whether results get aggregated across multiple simulations, or just returned as-is from the single simulation). This must be implemented exactly as follows, since it needs to match the user's existing spreadsheet:

**Step 1 — Determine eligible starting year(s).**
- `mean_stdev` mode: let `last_data_year` = the most recent year present in `AnnualReturn`. Eligible starting years are every year S in `AnnualReturn` where `return_start_year` ≤ S ≤ (`return_end_year` if set, otherwise `last_data_year`).
- `historical_replay` mode: there is exactly one "eligible starting year" — `replay_start_year`. Everything in Step 2 runs identically for this one year; Step 3's aggregation is skipped (a single simulation has no mean/stdev/CI to compute — the result IS the simulation's own trajectory).

**Step 2 — Run one simulation per eligible starting year.**
For each eligible starting year S:
- Initialize simulation balances from the scenario's current accounts, tracked as two running subtotals: post-tax and pre-tax (both needed separately because of the withdrawal rule below; both grow at the same rate since one return series applies to the whole portfolio).
- **Define the reporting periods.** If `current_age` is a whole number, every period is 12 months and the first period aligns naturally. If `current_age` has a fractional part (monthly precision), the first period is shorter — `first_period_months = round((1 − (current_age mod 1)) × 12)` — covering only the months remaining until the next whole age; every period after that is a full 12 months, until the projection horizon (`(end_age − current_age) × 12` total months) is reached (the final period may be shorter than 12 months if the horizon doesn't divide evenly).
- **Critical: one historical year per period, not per raw elapsed month.** The historical year for period index p (0-indexed: p=0 is the first period) is `S + p`. This must NOT be computed as `S + floor(elapsed_months / 12)` using raw month count from the start — when the first period is shorter than 12 months (fractional `current_age`), that raw-month-count approach causes two different periods to blend parts of two different calendar years' returns into one reporting period, producing incorrect (and visibly nonsensical — e.g. a supposed "2008 return" period that's actually part-2007/part-2008) results. Each period must be assigned exactly one historical year, applied for that period's full length (whether 6, 12, or some other number of months), regardless of how many raw months have elapsed since the start.
- If period p's historical year (`S + p`) is greater than `last_data_year`, this simulation stops here — it has no data to continue, and does not contribute to this period or any later one.
- Retirement timing: `retirement_month` = round((`retirement_age` − `current_age`) × 12), counted as elapsed months from the start (this is unaffected by the period-year-assignment fix above — it's still just a month count).
- For each period p, and for each month within that period:
  1. **Convert that period's single annual return to a monthly rate:** `monthly_rate = (1 + return_pct/100)^(1/12) − 1`, using `return_pct` for historical year `S + p`. This is the geometric conversion — compounding this rate 12 times reproduces the actual annual return exactly (not a simple divide-by-12 approximation). This same monthly_rate is used for every month within period p, however many months that is.
  2. **Determine this month's phase:** using the running elapsed-month count (across all periods so far, call it m), if m ≤ `retirement_month`, this month is pre-retirement (contribution); otherwise it's post-retirement (withdrawal). This is evaluated fresh every month, which is what allows retirement to fall mid-period.
  3. **If pre-retirement:** `monthly_contribution_posttax` = sum of post-tax accounts' `annual_contribution` ÷ 12; `monthly_contribution_pretax` = sum of pre-tax accounts' `annual_contribution` ÷ 12.
     **If post-retirement:** calculate the current year's total withdrawal need as `expected_expenses_in_retirement` inflated by `inflation_rate_pct`, compounded for `m / 12` years (fractional years elapsed since the start of the projection — inflation compounds continuously, not in yearly steps), then divide by 12 for `monthly_withdrawal_need`. Whether post-tax-only or split applies is determined this month using the fractional age at this point (`current_age + m/12`) compared to 59.5.
  4. **Apply growth first (end-of-month convention), then the month's contribution/withdrawal:**
     - Grow both subtotals (post-tax, pre-tax) by `monthly_rate`.
     - If pre-retirement: add `monthly_contribution_posttax` / `monthly_contribution_pretax` to the matching subtotal.
     - If post-retirement: apply `monthly_withdrawal_need` — if the fractional age this month is under 59.5, withdraw from post-tax only, **unless post-tax can't cover it that month — in that case, take everything post-tax has, pull the remaining shortfall from pre-tax, and mark this simulation as having had "early pre-tax access" starting at this month's age.** If 59.5 or over, split `monthly_withdrawal_need` per `withdrawal_split_pretax_pct`. If the combined total is insufficient to cover the month's withdrawal, floor both subtotals at zero (see Section 10).
- At the end of each period p, record the combined (post-tax + pre-tax) balance as this simulation's result for forward year offset `n = p + 1`.

**Assumption, flagged for confirmation:** contributions and withdrawals use the same monthly timing convention (growth first, then contribution/withdrawal, each month) for consistency — correct if the spreadsheet's Excel `FV` formula uses the same timing for both; flag if contributions actually use different timing than withdrawals.

**Step 3 — Aggregate across simulations, per forward year (mean_stdev mode only).**
For each offset n = 1 to `projection_horizon`:
- Collect the ending balance at offset n from every simulation that had enough data to reach it (i.e., every eligible S where `S + n − 1` ≤ `last_data_year`).
- Compute the mean and standard deviation of that set of balances.
- Compute confidence bands using z-scores (standard values, assumed unless corrected): 50% CI ≈ mean ± 0.674×stdev, 70% CI ≈ mean ± 1.036×stdev, 95% CI ≈ mean ± 1.96×stdev.

**Step 4 — Handle insufficient data (mean_stdev mode only).**
A minimum of **5 simulations** is required to report a data point for a given forward year offset — fewer than that is too small a sample to trust (and a sample of 1 makes standard deviation mathematically undefined, since it divides by `n − 1`). For any offset where fewer than 5 simulations have enough data to reach it, treat it the same as having *no* data: (a) show a warning before/alongside the results explaining that the selected starting-year range only supports results through a certain age, and (b) stop the chart/table there — don't attempt to compute or display a mean/stdev/CI from fewer than 5 simulations, and never let an empty or too-small simulation set silently produce a `NaN`, zero, or other garbage value that reaches the frontend. (`historical_replay` mode has only one simulation by definition — this minimum doesn't apply; it simply stops wherever that one simulation runs out of data, per Step 2, with a warning noting the cutoff age.)

**Step 5 — Warn on early pre-tax access (both modes).**
If any simulation triggered the pre-59.5 pre-tax fallback (Step 2, part 4), show a separate warning noting this happened, including the earliest age at which it occurred (across all simulations, for mean_stdev mode; for the single simulation, in replay mode). This is distinct from the depletion warning and the data-coverage warning — it's flagging a real-world consideration (early-withdrawal penalties/tax treatment aren't modeled in v1), not an error.

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
  - Scenarios view (create/edit/delete scenarios, select scenarios to view or compare)
  - Results view (single scenario at a time — charts via Recharts, tables, confidence bands for mean/stdev mode, depletion/warning flags)
  - Comparisons view (multiple scenarios overlaid — means only, no confidence bands or table detail, so mean_stdev and historical_replay scenarios can be compared side by side on equal footing)
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

**Flow 4: Viewing a single scenario's full results**
1. From the Scenarios list, select one scenario to view
2. App calls the backend, which runs the projection fresh. For mean/stdev mode, this means running the full rolling-window simulation described in Section 4a (one simulation per eligible starting year, aggregated per forward year into mean + confidence bands). For historical replay mode, it means the single replayed sequence. Either way: contributions until retirement → withdrawals after, per the 59.5 rule and account type.
2a. If mean/stdev mode can't cover the full projection horizon with available data, a warning is shown alongside the results (see Section 4a, Step 4), and the chart/table simply stops wherever data runs out.
3. Results shown as a chart (balance over time) and a table
4. If mean/stdev mode, chart also shows a shaded confidence band; historical replay mode shows a single line only (no band, since there's nothing to aggregate)
5. Contributions stop and withdrawals begin automatically once `retirement_age` is reached, driven by the projection logic (not stored as separate account data)

**Flow 5: Comparing multiple scenarios**
1. From the Scenarios list, select two or more scenarios (any mix of mean_stdev and historical_replay) to compare
2. App calls the backend for each selected scenario's projection, same underlying calculation as Flow 4
3. Results shown as a single chart with one **mean-only** line per scenario, overlaid — no confidence bands, no table, regardless of each scenario's return mode. This keeps mean_stdev and historical_replay scenarios visually comparable on equal footing, since only historical_replay's single-line data exists for both.
4. Any warnings from the underlying calculation (data-coverage cutoff, depletion, early pre-tax access) are still shown per scenario, just without the full CI/table detail — comparisons is a simplified view, not a simplified warning system.
5. For full detail on any one scenario shown in the comparison, the user returns to Flow 4's single-scenario Results view for that scenario.

## 10. Edge Cases & Error Handling

- CSV upload with malformed rows (missing value, non-numeric return/year) → reject those rows individually, show which rows failed and why, still process valid rows
- CSV upload with duplicate years → overwrite existing value with the new one (per Flow 2)
- Scenario with `current_age` ≥ `retirement_age`, or `retirement_age` ≥ `end_age` → validation error, not saved
- No accounts exist yet when viewing a projection → clear message directing user to add an account, not a blank/broken chart
- No historical return data uploaded yet when viewing a projection → clear message, not a silent failure or crash
- Selected year range (mean/stdev mode) or replay start year (historical replay mode) falls outside years present in `annual_returns` → validation error stating the valid available range
- `return_start_year` > `return_end_year` (mean/stdev mode, when both are provided) → validation error, not saved
- Mean/stdev mode: fewer than 5 eligible starting years have enough historical data to reach a given forward year offset → treat as insufficient data for that offset onward; warn before/alongside results stating the max age covered, and stop the chart/table there rather than computing statistics from too small (or empty) a sample (per Section 4a, Step 4)
- Pre-59.5 withdrawal need exceeds available post-tax balance → pull the shortfall from pre-tax instead of leaving expenses unmet, and warn that early pre-tax access occurred (per Section 4a, Step 5) — this is separate from full depletion and shouldn't be silent
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

**Near-term (worth tackling right after MVP is complete, not a distant idea):**
- Interactive controls (sliders/dials) directly on the Results page to tweak scenario parameters (retirement age, expenses, withdrawal split, etc.) and see results update live, instead of having to go back to the Scenarios tab, edit, save, and return. Needs real design decisions before building: whether a live tweak is a temporary preview or auto-saves, how the backend avoids being hammered on every drag event (debouncing), and whether it applies to one scenario or all displayed ones at once.

**Longer-term / more speculative:**
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
8. **Comparisons tab** — New, separate frontend view (not an extension of the Results page). Lets you select multiple scenarios (any mix of mean_stdev/historical_replay) and see them overlaid on one chart as mean-only lines, per Flow 5 — no confidence bands, no table. Per-scenario warnings (data-coverage cutoff, depletion, early pre-tax access) still shown. The single-scenario Results view (step 6) is left untouched, keeping full CI/table detail for one scenario at a time. Basic styling included.
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
- Discovered after building step 5: the original pre-59.5 withdrawal rule (100% from post-tax, no fallback) could silently leave expenses unmet once post-tax ran dry, letting pre-tax compound untouched and producing a misleadingly rising balance. Fixed by adding a fallback: if post-tax can't cover the full pre-59.5 withdrawal, pull the shortfall from pre-tax and warn that early pre-tax access occurred. This is a deliberate simplification — real-world early withdrawal penalties/tax treatment on that pulled amount are not modeled in v1 (see Section 12).
- Discovered after building step 5: at the tail end of the projection horizon, the number of simulations contributing to each forward-year aggregate shrinks (fewer starting years have enough data to reach far-future offsets), eventually reaching 1 or 0 simulations. A sample of 1 makes standard deviation mathematically undefined (divides by n−1=0), and a sample of 0 was producing garbage/NaN values instead of being excluded. Fixed by requiring a minimum of 5 simulations to report a data point for a given offset; fewer than that is treated the same as "no data" (per Section 4a, Step 4), stopping the chart/warning there instead of silently displaying statistically meaningless or broken values.
- Discovered after building step 5: comparing app output to the user's spreadsheet revealed a large (~$700K by age 56) discrepancy in projected balances during retirement. Root cause: the original annual lump-sum withdrawal timing (full year's withdrawal taken upfront, forfeiting a full year of growth on that money) differs meaningfully from the spreadsheet's monthly withdrawal timing via Excel's FV function, which keeps most of the balance invested for most of each month. Fixed by switching both contributions and withdrawals to monthly compounding: annual returns are converted to a monthly rate via `(1 + annual_return)^(1/12) − 1`, and each month applies growth first, then that month's contribution/withdrawal (matching the spreadsheet's FV "type = 0" convention). This is a meaningfully more complex calculation than the original annual version — see Section 4a for the full monthly mechanics.
- After switching to monthly compounding, a further discrepancy remained (app ~$4.4M vs. spreadsheet ~$5.1M for the same 6-year window). Verified via an independent reference implementation (run against the real CSV, outside the app's own code) that the app correctly matched the spec as written — ruling out an app bug. Traced the remaining gap to the monthly rate conversion formula: the user's spreadsheet likely uses the simpler `r/12` (nominal rate), while the app uses the geometric `(1+r)^(1/12) − 1`. Confirmed via testing that `r/12` reproduces the spreadsheet's numbers closely. Decision: **keep the geometric conversion** — it's the only one that reproduces the exact real historical annual return when compounded 12 times, which matters for an app whose core premise is fidelity to actual historical performance (`r/12` systematically overstates long-run compounding relative to what really happened). This means the app's numbers will not exactly match the existing spreadsheet going forward, and that's an accepted, deliberate tradeoff — not a bug.
- Added support for fractional `current_age`/`retirement_age` (monthly precision, e.g. 46.25) since a short pre-retirement window makes whole-year rounding meaningfully inaccurate. This required restructuring Section 4a's Step 2 from a year-then-month nested loop into a single month-based loop, with the contribution/withdrawal phase (and the 59.5 withdrawal-source check) re-evaluated every month instead of once per year — this is what allows retirement to fall mid-year. `end_age` stays a whole number, since horizon-level precision doesn't matter the same way.
- Discovered that `historical_replay` mode's numbers had drifted out of sync with `mean_stdev` mode's — while `mean_stdev` had been repeatedly fixed (monthly compounding, geometric rate conversion, pre-59.5 fallback, fractional retirement age), `historical_replay` likely wasn't updated alongside it, suggesting it was implemented as a separate code path rather than sharing logic. Restructured Section 4a to make explicit that both modes must share the exact same per-simulation function (Step 2) — the only difference between them is Step 1 (one starting year vs. many) and Step 3 (whether results get aggregated). This should prevent the two modes from drifting apart again in the future; the app's code needs a corresponding refactor so `historical_replay` calls the same simulation function as `mean_stdev`, rather than a separate implementation.
- Found (and fixed in the spec) a real bug affecting any simulation with a fractional `current_age`: historical years were being assigned to months using raw elapsed-month count (`S + floor(elapsed_months / 12)`), which only works cleanly when every period is exactly 12 months. With a fractional `current_age` (short first period), this caused two different calendar years' returns to blend within a single reporting period — verified independently against the real CSV, producing visibly nonsensical results (e.g. a "2008 return" period that was actually part-2007/part-2008, masking the real 2008 crash). Fixed by assigning exactly one historical year per reporting *period* (`S + period_index`), regardless of that period's length — the first period may be shorter than 12 months, but it still gets exactly one historical year's return, applied for however many months that period spans.
- Split "viewing results" into two separate frontend views instead of one extended Results page: a single-scenario Results view (full detail — confidence bands for mean_stdev, table) and a separate Comparisons view (multiple scenarios overlaid, mean-only lines, no bands/table). Reason: mean_stdev scenarios produce confidence-band data that historical_replay scenarios don't have, so a unified comparison view would need to handle two different data shapes awkwardly. Showing means only in Comparisons sidesteps that entirely, at the cost of losing CI detail when comparing — full detail is still available by returning to the single-scenario Results view.
- Considered skipping multi-scenario comparison (Build Order step 8) in favor of relying on the not-yet-built live-dial interaction (see Future Ideas) instead. Decided against it: comparison (seeing multiple full trajectories at once) and live single-scenario tweaking solve different problems, and comparison was deliberately pulled into MVP early on specifically because it's core to a near-retirement decision — skipping it would reverse that earlier decision without a strong enough reason. Comparison (step 8) proceeds as planned.

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
- [ ] Compare two scenarios side by side in the Comparisons tab — both appear as mean-only lines, distinguishable from each other, no CI bands shown
- [ ] Compare one mean_stdev scenario against one historical_replay scenario in the Comparisons tab — both display correctly on equal footing (mean-only), despite having different underlying data shapes
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
