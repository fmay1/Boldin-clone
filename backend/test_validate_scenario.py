import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import validate_scenario

def make_cursor(years=range(1990, 2021)):
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE annual_returns (id INTEGER PRIMARY KEY, year INTEGER, return_pct REAL)")
    for y in years:
        cursor.execute("INSERT INTO annual_returns (year, return_pct) VALUES (?, ?)", (y, 5.0))
    conn.commit()
    return conn, cursor

def base_data(**overrides):
    data = {
        "name": "Test",
        "current_age": 46.0,
        "retirement_age": 55.0,
        "end_age": 95,
        "expected_expenses_in_retirement": 50000,
        "withdrawal_split_pretax_pct": 50,
        "inflation_rate_pct": 2.5,
        "return_mode": "mean_stdev",
        "return_start_year": 1990,
        "return_end_year": 2020
    }
    data.update(overrides)
    return data

failures = 0

def check(name, data, expect_error=None, conn=None, cursor=None):
    global failures
    if conn is None:
        conn, cursor = make_cursor()
    parsed, error = validate_scenario(data, cursor)
    if expect_error is None:
        ok = error is None and parsed is not None
        detail = f"parsed={parsed}" if ok else f"unexpected error: {error}"
    else:
        ok = error == expect_error
        detail = f"got error: {error!r}, expected: {expect_error!r}"
    if ok:
        print(f"PASS: {name}")
    else:
        failures += 1
        print(f"FAILED: {name} — {detail}")
    conn.close()

# --- Valid payloads ---

check("valid mean_stdev with end year", base_data())

def check_mean_stdev_no_end_year():
    conn, cursor = make_cursor()
    data = base_data()
    del data["return_end_year"]
    parsed, error = validate_scenario(data, cursor)
    if error is None and parsed["return_end_year"] is None:
        print("PASS: mean_stdev without end year parses end_year as None")
    else:
        global failures
        failures += 1
        print(f"FAILED: mean_stdev without end year — error={error}, parsed_end={parsed and parsed.get('return_end_year')}")
    conn.close()
check_mean_stdev_no_end_year()

check("valid historical_replay", base_data(return_mode="historical_replay", replay_start_year=2000, return_start_year=None, return_end_year=None))
check("valid monte_carlo", base_data(return_mode="monte_carlo", block_length_years=3))

# --- Age validation ---

check("current_age not monthly precision", base_data(current_age=46.3), "Current age must correspond to a whole number of months (e.g., 46.25)")
check("retirement_age not monthly precision", base_data(retirement_age=55.3), "Retirement age must correspond to a whole number of months (e.g., 46.25)")
check("fractional monthly age accepted", base_data(current_age=46.25, retirement_age=55.75))
check("current_age >= retirement_age", base_data(current_age=55.0), "Ages must be ordered: current < retirement < end")
check("retirement_age >= end_age", base_data(end_age=55), "Ages must be ordered: current < retirement < end")

# --- Range validation ---

check("withdrawal_split above 100", base_data(withdrawal_split_pretax_pct=150), "Withdrawal split must be between 0 and 100")
check("inflation above 20", base_data(inflation_rate_pct=25), "Inflation rate must be between -5 and 20")
check("inflation below -5", base_data(inflation_rate_pct=-10), "Inflation rate must be between -5 and 20")

# --- Return mode validation ---

check("unknown return mode rejected", base_data(return_mode="foo"), "Return mode must be one of: mean_stdev, historical_replay, monte_carlo")

# --- Year range validation ---

check("mean_stdev start > end (drift case)", base_data(return_start_year=2020, return_end_year=2010), "Return start year must be <= end year")
check("monte_carlo start > end", base_data(return_mode="monte_carlo", block_length_years=3, return_start_year=2020, return_end_year=2010), "Return start year must be <= end year")
check("start year below min", base_data(return_start_year=1980), "Return year range must be within 1990-2020")
check("end year above max", base_data(return_end_year=2030), "Return year range must be within 1990-2020")
check("replay year out of range", base_data(return_mode="historical_replay", replay_start_year=1980, return_start_year=None, return_end_year=None), "Replay start year must be within 1990-2020")
check("monte_carlo block length zero", base_data(return_mode="monte_carlo", block_length_years=0), "Block length must be > 0")
check("missing return_start_year", {k: v for k, v in base_data().items() if k != "return_start_year"}, "Missing or invalid year field for the selected return mode")
check("non-numeric return_start_year", base_data(return_start_year="abc"), "Missing or invalid year field for the selected return mode")

# --- Missing/invalid core fields ---

check("missing current_age", {k: v for k, v in base_data().items() if k != "current_age"}, "Invalid numeric values for ages, expenses, or rates")
check("non-numeric expenses", base_data(expected_expenses_in_retirement="lots"), "Invalid numeric values for ages, expenses, or rates")

# --- Empty returns table ---

def check_empty_returns():
    global failures
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE annual_returns (id INTEGER PRIMARY KEY, year INTEGER, return_pct REAL)")
    parsed, error = validate_scenario(base_data(), cursor)
    if error == "No annual return data available":
        print("PASS: empty returns table rejected")
    else:
        failures += 1
        print(f"FAILED: empty returns table — got error={error!r}")
    conn.close()
check_empty_returns()

print()
if failures:
    print(f"FAILED: {failures} test(s) failed.")
    sys.exit(1)
print("OK: validate_scenario passes all checks.")
