import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'retirement_planner.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('post-tax', 'pre-tax')),
            current_balance REAL NOT NULL CHECK(current_balance >= 0),
            annual_contribution REAL NOT NULL CHECK(annual_contribution >= 0)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            current_age REAL NOT NULL,
            retirement_age REAL NOT NULL,
            end_age INTEGER NOT NULL,
            expected_expenses_in_retirement REAL NOT NULL,
            withdrawal_split_pretax_pct REAL NOT NULL CHECK(withdrawal_split_pretax_pct >= 0 AND withdrawal_split_pretax_pct <= 100),
            inflation_rate_pct REAL NOT NULL CHECK(inflation_rate_pct >= -5 AND inflation_rate_pct <= 20),
            return_mode TEXT NOT NULL CHECK(return_mode IN ('mean_stdev', 'historical_replay')),
            return_start_year INTEGER,
            return_end_year INTEGER,
            replay_start_year INTEGER
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS annual_returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER UNIQUE NOT NULL,
            return_pct REAL NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scenario_expenditures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
            amount REAL NOT NULL CHECK(amount > 0),
            age REAL NOT NULL,
            inflation_adjusted INTEGER NOT NULL DEFAULT 0
        )
    ''')
    
    conn.commit()
    conn.close()
