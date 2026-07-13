# MONTE_CARLO_PLAN.md

A scoped sub-plan for adding Monte Carlo simulation as a third return mode, alongside the existing `mean_stdev` and `historical_replay` modes. Per AGENTS.md, once this feature is built and this document is ready to be dropped from context, any decisions worth remembering long-term should be migrated into PLAN.md's Decisions Log.

**Revision note:** the core engine (Sections 1–4, Build Order steps 1–6) was already implemented before Section 4a (depletion probability) and the 500→1,000 path increase were added. Nothing already built needs to be undone — this is a pure addition on top of data the existing implementation already generates (the floor-at-zero rule and per-path results were already in place; this just adds one more calculation over them). See Build Order steps 8–9 for what's newly needed.

---

## 1. Overview & Goal

Add a `monte_carlo` return mode that generates many randomized simulated paths using **block bootstrap resampling** from the user's actual historical return data — preserving the real, non-normal shape of historical returns (fat tails, crash asymmetry) rather than assuming a fitted statistical distribution. This is distinct from the existing `mean_stdev` mode (which runs one simulation per *actual* historical starting year, a fixed and limited set) — Monte Carlo can generate many more distinct paths from the same underlying data by resampling.

## 2. Core Mechanism

**Block bootstrap, not single-year bootstrap:** each simulated path is built by repeatedly drawing random multi-year "blocks" of *consecutive, real* historical years and concatenating them until the path covers the full projection horizon. This preserves some real sequential structure (a crash followed by an actual historical recovery) that plain single-year resampling would destroy.

**Why not a fitted distribution:** real market returns are fat-tailed and skewed (crashes are sharper and more frequent than a normal distribution predicts). Fitting a normal distribution — especially from a small sample of ~36–56 years — would systematically understate downside risk and add estimation noise on top of an already-mismatched assumption. Block bootstrap only ever produces values that actually happened, avoiding both problems. This also keeps Monte Carlo mode consistent with this app's founding premise: modeling the user's *actual* historical performance, not generic assumptions.

**Block selection: moving (overlapping) block bootstrap.** Any consecutive run of years within the eligible range can become a block — e.g., with 3-year blocks, both "1990-92" and "1991-93" are valid, independently-drawable blocks. This is the statistical standard (Künsch, 1989) and gives far more distinct block options than a non-overlapping partition, which matters given the small sample size.

**Block length:** user-specified per run (a field on the Scenario/Live form, shown only when `return_mode = 'monte_carlo'`), not fixed by the app. No default is prescribed here — the person sets it each time based on what they want to explore.

**Number of paths: 1,000**, fixed. Originally set at 500 as a cautious middle ground given anticipated computation cost — testing showed 500 paths ran almost instantly on real hardware, so this was revised upward to 1,000 for better statistical stability, particularly in the tail percentiles and the depletion-probability metric (Section 4a below), both of which need larger samples to stabilize. Room to increase further later if performance allows.

**Final (leftover) block truncation:** when the projection horizon doesn't divide evenly by the block length, draw one more full-length random block as usual and use only as many of its years as are needed to fill the remainder. This is the standard approach in the moving block bootstrap literature — simpler and statistically cleaner than drawing a separately-calibrated shorter block just for the remainder.

**Year range interacts differently than in mean_stdev mode:** in `mean_stdev` mode, `return_start_year`/`return_end_year` only bound a simulation's *starting* year — the simulation is then free to run using whatever real data follows. For `monte_carlo` mode, the range must bound the **entire block** — every year within a candidate block must fall inside `return_start_year`–`return_end_year`, not just the block's first year. This matters because a block is a short, self-contained chunk (not an open-ended run to the present); without this rule, excluding an era (e.g. the 1970s–80s) could still let a block sneak in a year or two from that era.

## 3. Data Model Additions

**Scenario** gains two new fields, both only relevant when `return_mode = 'monte_carlo'`:
- `block_length_years` (int) — the length of each resampled block, set per scenario/run, same pattern as `return_start_year`/`replay_start_year` already work.
- `return_mode` gains a third valid value: `monte_carlo` (alongside existing `mean_stdev` and `historical_replay`).

`return_start_year`/`return_end_year` are reused (same field names as `mean_stdev` mode), but their semantics differ as described in Section 2 — this should be clearly commented in code, since the same field name means something subtly different depending on `return_mode`.

No new database tables — this reuses the existing `scenarios` table (add the `block_length_years` column) and `annual_returns` table as-is.

## 4. Calculation Methodology

This reuses the **exact same** `_run_monthly_simulation` function already shared between `mean_stdev` and `historical_replay` modes — no duplication. The only difference for `monte_carlo` mode is in how the *sequence of historical years* fed into that function gets constructed, and how the resulting paths get aggregated.

**Step 1 — Determine eligible block starting years.**
Given `block_length_years` = L, a year S is a valid block-starting year only if S, S+1, ..., S+L−1 all exist in `AnnualReturn` AND all fall within `return_start_year`–`return_end_year`. If no valid S exists (e.g. the range is narrower than L), return an error explaining that no valid blocks of that length exist in the selected range.

**Step 2 — Build one random path's year sequence.**
For a single path: repeatedly pick a random eligible S (with replacement — the same block can be picked more than once, even within the same path), append the L consecutive years starting at S to a running sequence of "historical years to use, in order," until the sequence is at least as long as the projection horizon (in years). If the last block would overshoot the horizon, truncate it to only the years actually needed (Section 2).

**Step 3 — Run the simulation for that path.**
Feed this constructed year sequence into the same monthly simulation logic already used by the other two modes (period-based year assignment, growth-then-contribution/withdrawal ordering, the 59.5 rule with pre-tax fallback, floor-at-zero) — except instead of the historical year for period p being `S + p` (a simple increment), it's `year_sequence[p]` (the p-th year in this path's randomly constructed sequence). This is the one real change needed to `_run_monthly_simulation` — everything else about the monthly loop is unchanged.

**Step 4 — Repeat for 1,000 paths, then aggregate per forward year.**
For each forward year offset n, collect the ending balance from all 1,000 paths at that offset (every path reaches every offset — no data-coverage shortfall is possible, since blocks are drawn with replacement). Sort these 1,000 values and read off percentiles directly (empirical, no distributional assumption):
- "50% CI" → 25th and 75th percentile
- "70% CI" → 15th and 85th percentile
- "95% CI" → 2.5th and 97.5th percentile
- Central value → the 50th percentile (median), reported in the existing `mean_balance` field for compatibility with existing frontend code (Results.jsx, Comparisons.jsx, Live.jsx already branch rendering by `return_mode`, so this is a low-risk field reuse rather than a new field name).

**Assumption, flagged:** percentile computation uses linear interpolation between the two nearest ranks (the standard/default method used by most statistical libraries, e.g. `numpy.percentile`'s default) — not nearest-rank or another interpolation scheme. Flag if a different convention is wanted.

**Early pre-tax access warning:** reuses the exact same pattern as `mean_stdev` mode — track how many of the 1,000 paths triggered the pre-59.5 pre-tax fallback, and the earliest age it occurred across all paths, formatted the same way ("In X out of 1,000 simulated paths (Y%), pre-tax funds were accessed before age 59.5...").

**No data-coverage warning needed** for this mode (unlike `mean_stdev`/`historical_replay`) — see Section 2's note on why every path can always reach the full horizon.

## 4a. Probability of Depletion by Age (headline metric)

Percentile dollar bands (Section 4, Step 4) are useful but not the primary output real Monte Carlo retirement tools report — and reusing the CI-band pattern from the other two modes as the default view undersells what this mode is actually good for. Dollar outcomes on the high end are heavily right-skewed (unbounded upside from compounding, compressed downside near the $0 floor), so extreme high-percentile dollar values aren't decision-relevant, while what actually matters — the chance of running out of money — is exactly what percentile bands don't directly answer.

**Compute, for each forward year offset n, the fraction of the 1,000 paths that have already been fully depleted by that age.** A path counts as depleted once its combined (post-tax + pre-tax) balance reaches exactly $0.00 via the existing floor-at-zero rule — and since a depleted path can never recover during retirement (no more contributions, and withdrawals only ever reduce an already-zero balance further, staying at zero), this is a monotonically non-decreasing value as age increases: the probability of depletion by age 70 is always ≥ the probability of depletion by age 65.

**Implementation approach:** track an explicit `ever_depleted` boolean per path (set to `True` the first time combined balance hits exactly $0.00, and never reset), rather than re-deriving depletion status from a balance snapshot alone — this is more robust than relying on exact floating-point equality checks scattered across separate snapshot comparisons. Record this flag's state at each of the same forward year offsets already used for the dollar-based results (Section 4, Step 4), so both metrics stay aligned to the same age points.

**Reported as:** a percentage per age (e.g. "at age 70, 12% of simulated paths have run out of money"), shown as its own chart/line — separate from, and alongside, the existing percentile dollar bands, not replacing them. The percentile bands remain useful as a secondary view of the *magnitude* of outcomes; this metric answers the *probability of failure* question directly.

**Overall success rate** (a single headline number, e.g. "88% success by end_age") is just this same metric read at the final forward year offset — no separate calculation needed.

## 5. Performance / UX Handling

Given the real computation cost (1,000 sequential per-path simulations, each running the full monthly loop for a multi-decade horizon), the Live page, Results page, and Comparisons tab should all show a clear loading state while a Monte Carlo projection is running (reusing existing loading-state patterns already present in these files) — ideally with messaging that sets the expectation this will take longer than the other two modes, rather than looking like it's hung.

**Not required for this pass, but worth knowing:** the simulation loop could be rewritten using `numpy` to process many paths as vectorized array operations instead of nested Python loops, which would meaningfully speed this up. This is a real architectural change to `projection.py`'s core loop, not a small tweak — treat it as its own future decision if 1,000-path Monte Carlo runs turn out to be too slow in practice on this hardware, rather than optimizing preemptively.

## 6. Edge Cases

- No valid block of the requested `block_length_years` exists within `return_start_year`–`return_end_year` → clear error, don't run the simulation (per Step 1).
- `block_length_years` ≤ 0 or larger than the total number of years available in the selected range → validation error.
- Same floor-at-zero, depletion, and pre-tax fallback edge cases as the other two modes — all inherited automatically via the shared `_run_monthly_simulation` function, no new logic needed there.

## 7. Build Order

1. **Backend: block sampling logic.** A new function that, given `return_start_year`, `return_end_year`, `block_length_years`, and the projection horizon, returns one randomly constructed year sequence (Steps 1–2 above). Testable independently of the simulation engine.
2. **Backend: wire into `_run_monthly_simulation`.** Modify the year-assignment logic to accept a pre-built year sequence instead of always computing `S + period_index`, so `mean_stdev`/`historical_replay` (which still use the simple increment) and `monte_carlo` (which uses a random sequence) can share the same function without duplicating the monthly loop.
3. **Backend: run all paths and aggregate into percentiles.** New logic in `calculate_projection` for the `monte_carlo` branch, following Section 4's Steps 3–4. (Originally built running 500 paths; see step 8 for the increase to 1,000.)
4. **Backend: `database.py` schema change.** Add `block_length_years` column to `scenarios`.
5. **Frontend: Scenarios.jsx.** Add `monte_carlo` as a selectable return mode, with the `block_length_years` field shown when selected (reusing `return_start_year`/`return_end_year` fields already present for `mean_stdev`).
6. **Frontend: Results.jsx, Comparisons.jsx, Live.jsx.** Confirm the existing `return_mode`-based conditional rendering (CI columns/lines) correctly handles `monte_carlo` the same way it handles `mean_stdev` — since both modes populate the same field names (`mean_balance`, `ci50_low`, etc.), this should require minimal or no changes, but needs verification.
7. **Verification pass.** Run a Monte Carlo scenario and sanity-check: does the median track reasonably close to the mean_stdev mode's mean for the same inputs? Do the percentile bands look meaningfully wider/more skewed than the z-score-based bands from mean_stdev mode (expected, since block bootstrap preserves fat tails that a normal-distribution assumption smooths away)?

**— Steps 1–7 already implemented; steps 8–9 are the current addition —**

8. **Bump path count from 500 to 1,000.** Update the fixed path count used when running a Monte Carlo projection. No other logic changes.
9. **Add depletion probability calculation and display.** Backend: track `ever_depleted` per path (Section 4a), compute the per-age percentage across all 1,000 paths, include it in the response alongside the existing percentile results. Frontend: Results.jsx, Comparisons.jsx, and Live.jsx each need a new chart/line for this metric when `return_mode = monte_carlo` — shown alongside (not replacing) the existing percentile bands. Consider surfacing the final age's value as a single headline "success rate" number near the top of the results, since that's the single most decision-relevant number this mode produces.

## 8. Acceptance Tests

- [ ] Create a scenario with `return_mode = monte_carlo`, a valid `block_length_years`, and a valid year range — projection runs and returns results without error
- [ ] Try a `block_length_years` larger than the eligible year range — clear validation error, not a crash
- [ ] Confirm results include percentile-based bands (25th/75th, 15th/85th, 2.5th/97.5th) rather than z-score-based bands, for this mode specifically
- [ ] Confirm the reported central value is the median (50th percentile) of the 1,000 paths, not the arithmetic mean
- [ ] Confirm results cover the full projection horizon with no data-coverage warning (unlike mean_stdev mode with a narrow starting-year range)
- [ ] Confirm the early pre-tax access warning appears (with correct count/percentage out of 1,000) when applicable
- [ ] Compare a Monte Carlo scenario's median against a mean_stdev scenario with the same inputs — results should be in the same ballpark, not wildly different, as a sanity check
- [ ] Confirm Results, Comparisons, and Live pages all render Monte Carlo results correctly (chart, table, warnings)
- [ ] Confirm path count is 1,000, not 500
- [ ] Confirm the depletion probability metric is non-decreasing as age increases (never drops after a rise)
- [ ] Confirm the depletion probability at the final age matches a manually-counted "how many of the 1,000 paths ended at $0" check, as a hand-verification
- [ ] Confirm a scenario very unlikely to deplete (e.g. high balance, low expenses) shows a depletion probability near 0% throughout; confirm a scenario very likely to deplete shows it rising well before end_age
