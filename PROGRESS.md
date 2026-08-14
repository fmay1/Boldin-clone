# PROGRESS.md

**Current state (read this first):** Monte Carlo simulation mode is fully implemented, including 1,000-path block bootstrap, percentile-based confidence intervals, and depletion probability tracking/display across Results, Comparisons, and Live views. All Build Order steps 1-13 and Monte Carlo sub-plan steps 1-9 are complete. Extra income (future income) feature is fully implemented in the Live tab, mirroring existing Scenarios tab functionality — incomes affect projection preview and sync to DB on save. The Live tab's 5-income cap has been removed so incomes are uncapped in both tabs, matching PLAN.md step 14. Scenario input validation is consolidated in a shared `validate_scenario()` function in app.py, used by the create, update, and preview endpoints.

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

### [Refactor] Shared validate_scenario() for create/update/preview

- **What was implemented:** Extracted the ~60 lines of duplicated scenario validation from the create, update, and preview endpoints in `app.py` into one `validate_scenario()` function (plus a `VALID_RETURN_MODES` constant). All three endpoints call it, and their SQL now uses the type-coerced values it returns. Added `backend/test_validate_scenario.py` (24 cases, plain-Python style matching the existing tests) and verified all three endpoints end-to-end via Flask's test client against a throwaway database.
- **Behavior changes (all strict improvements):** (1) Unknown `return_mode` on create/update previously hit the SQLite CHECK constraint → unhandled → 500; now a 400 with a clear message. (2) Missing core fields (e.g. `current_age`) on create/update previously 500'd; now a 400. (3) `return_start_year > return_end_year` on the preview endpoint was previously caught deep in `calculate_projection` with a different message; now caught at the API layer with the same message as create/update.
- **Approach & reasoning:** The duplication had already caused drift twice — the Decisions Log records the preview endpoint missing the monthly-precision check, and a pre-refactor audit found preview had no start>end year check at all. One function means a rule change is one edit. The `name` check stays in create/update (preview doesn't persist). Existing error message strings kept verbatim since the frontend displays them.
- **Deviations from PLAN.md:** none
- **Known issues / TODOs:** Frontend validation copies (Scenarios.jsx/Live.jsx) deliberately left alone — they're a UX layer; the backend is the enforcement layer.

---

### [Fix] Remove Live tab's 5-income cap

- **What was implemented:** Removed the 5-income cap from the Live tab (`Live.jsx` — deleted the guard in `addIncome` and the `disabled` state on the "+ Add Income" button). Incomes are now uncapped in both the Scenarios and Live tabs.
- **Approach & reasoning:** PLAN.md step 14 explicitly says "no hard limit on count" for incomes; the 5-cap was an implementation choice in the Live tab (copied from the expenditure pattern) that the backend never enforced. The expenditure cap of 10 is unchanged — it is specified in PLAN.md step 11 and is consistent in both tabs.
- **Deviations from PLAN.md:** none — this brings the code back in line with the plan.
- **Known issues / TODOs:** none

---

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
