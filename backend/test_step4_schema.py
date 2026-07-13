import sys
import os
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import init_db, DB_PATH

def test_step4_schema():
    # Initialize DB to ensure schema is up to date
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check 1: block_length_years column exists
    cursor.execute('PRAGMA table_info(scenarios)')
    cols = [row[1] for row in cursor.fetchall()]
    if 'block_length_years' not in cols:
        print("FAILED: Missing block_length_years column!")
        sys.exit(1)
        
    # Check 2: return_mode constraint includes 'monte_carlo'
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='scenarios'")
    schema = cursor.fetchone()[0]
    if 'monte_carlo' not in schema:
        print("FAILED: return_mode check constraint not updated!")
        sys.exit(1)
        
    conn.close()
    print("OK: Step 4 verified: block_length_years added and return_mode constraint updated.")

if __name__ == '__main__':
    test_step4_schema()
