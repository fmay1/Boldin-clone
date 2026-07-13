# PROGRESS.md

**Current state (read this first):** Monte Carlo simulation mode is fully implemented, including 1,000-path block bootstrap, percentile-based confidence intervals, and depletion probability tracking/display across Results, Comparisons, and Live views. All Build Order steps 1-13 and Monte Carlo sub-plan steps 1-9 are complete. Extra income (future income) feature is fully implemented in the Live tab, mirroring existing Scenarios tab functionality — incomes affect projection preview and sync to DB on save.

## How to use this file

- At the start of a new session (especially a new day, or after
  restarting Aider), read this file and PLAN.md before making any
  changes, so you know what's already built and how.
- After completing a Build Order step, or any change worth remembering,
  add an entry below and update "Current state" above.
- If something was implemented differently than PLAN.md describes,
  note it here and explain why — PLAN.md stays as the original plan;
  this file tracks what actually happened.

---

## Log

### [Monte Carlo Sub-plan: Steps 8 & 9] Depletion Probability & Path Count Increase

- **What was implemented:** Increased Monte Carlo simulation path count from 500 to 1,000 for better statistical stability. Added depletion probability calculation (tracking `ever_depleted` per path) and display across `Results.jsx`, `Comparisons.jsx`, and `Live.jsx`. The metric is shown as a separate chart/line and a headline "success rate" percentage.
- **Approach & reasoning:** Reused existing floor-at-zero logic to track depletion. Computed per-age depletion percentage across all 1,000 paths. Frontend conditionally renders the new chart and success rate box when `return_mode === 'monte_carlo'`. No architectural changes needed; purely additive to existing projection and UI code.
- **Deviations from PLAN.md:** none
- **Known issues / TODOs:** none

---

### [Extra Income] Add Extra Income Support to Live Tab

- **What was implemented:** Full extra income (future income) support in the Live tab, matching existing Scenarios tab functionality. Users can now add/edit/remove up to 5 extra incomes per scenario in Live, see them affect the live projection preview, and sync changes back to the DB via "Save Changes to Scenario."
- **Approach & reasoning:** 
  - Backend (`app.py`): Added 2 lines to `preview_projection()` — extract `incomes` from request body and pass it through to `calculate_projection()`. The projection engine already handled incomes correctly; only the preview endpoint was missing the connection.
  - Frontend (`Live.jsx`): Added `incomes`/`originalIncomeIds` state, load incomes in `handleScenarioChange` (mirroring expenditure loading pattern), added Extra Income UI section with Start Age, End Age, Amount, Inflation Adj. checkbox, and Delete button per row, included valid incomes in `handleUpdate` projection payload, and synced income CRUD operations in `handleSave` using the same diffing pattern as expenditures.
  - Handler functions: Added `addIncome`, `updateIncome`, `removeIncome` with a 5-income cap (matching expenditure's 10-expense limit pattern).
- **Deviations from PLAN.md:** none
- **Known issues / TODOs:** No validation on `startAge < endAge` in Live tab (could be added later). The income period is `[start_age, end_age)` — inclusive of start month, exclusive of end month.
