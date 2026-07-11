import io
import csv
from flask import Flask, jsonify, request
from database import init_db, get_connection

app = Flask(__name__)

# Initialize the database on startup
init_db()

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "Backend is running"})

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, type, current_balance, annual_contribution FROM accounts")
    rows = cursor.fetchall()
    conn.close()
    accounts = []
    for row in rows:
        accounts.append({
            "id": row[0],
            "name": row[1],
            "type": row[2],
            "current_balance": row[3],
            "annual_contribution": row[4]
        })
    return jsonify(accounts)

@app.route('/api/accounts', methods=['POST'])
def create_account():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"error": "Name is required"}), 400
    if data.get('type') not in ('post-tax', 'pre-tax'):
        return jsonify({"error": "Type must be 'post-tax' or 'pre-tax'"}), 400
    if data.get('current_balance', 0) < 0:
        return jsonify({"error": "Current balance must be >= 0"}), 400
    if data.get('annual_contribution', 0) < 0:
        return jsonify({"error": "Annual contribution must be >= 0"}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO accounts (name, type, current_balance, annual_contribution) VALUES (?, ?, ?, ?)",
        (data['name'], data['type'], data['current_balance'], data['annual_contribution'])
    )
    conn.commit()
    account_id = cursor.lastrowid
    conn.close()
    return jsonify({"id": account_id, "message": "Account created"}), 201

@app.route('/api/accounts/<int:account_id>', methods=['PUT'])
def update_account(account_id):
    data = request.get_json()
    if not data.get('name'):
        return jsonify({"error": "Name is required"}), 400
    if data.get('type') not in ('post-tax', 'pre-tax'):
        return jsonify({"error": "Type must be 'post-tax' or 'pre-tax'"}), 400
    if data.get('current_balance', 0) < 0:
        return jsonify({"error": "Current balance must be >= 0"}), 400
    if data.get('annual_contribution', 0) < 0:
        return jsonify({"error": "Annual contribution must be >= 0"}), 400
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE accounts SET name = ?, type = ?, current_balance = ?, annual_contribution = ? WHERE id = ?",
        (data['name'], data['type'], data['current_balance'], data['annual_contribution'], account_id)
    )
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Account not found"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "Account updated"})

@app.route('/api/accounts/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Account not found"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "Account deleted"})

@app.route('/api/annual-returns', methods=['GET'])
def get_annual_returns():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT year, return_pct FROM annual_returns ORDER BY year")
    rows = cursor.fetchall()
    conn.close()
    returns = [{"year": r[0], "return_pct": r[1]} for r in rows]
    return jsonify(returns)

@app.route('/api/annual-returns', methods=['POST'])
def upload_annual_returns():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if not file.filename.endswith('.csv'):
        return jsonify({"error": "File must be a CSV"}), 400
        
    try:
        # Use utf-8-sig to automatically strip the Byte Order Mark (BOM) if present
        content = file.read().decode('utf-8-sig')
        stream = io.StringIO(content, newline='')
        reader = csv.DictReader(stream)
        
        conn = get_connection()
        cursor = conn.cursor()
        
        added = 0
        updated = 0
        errors = []
        
        for i, row in enumerate(reader, start=2):
            try:
                year = int(row['year'])
                # Strip '%' sign and whitespace before converting to float
                return_str = row['return'].replace('%', '').strip()
                return_pct = float(return_str)
                
                cursor.execute("SELECT id FROM annual_returns WHERE year = ?", (year,))
                existing = cursor.fetchone()
                
                if existing:
                    cursor.execute("UPDATE annual_returns SET return_pct = ? WHERE year = ?", (return_pct, year))
                    updated += 1
                else:
                    cursor.execute("INSERT INTO annual_returns (year, return_pct) VALUES (?, ?)", (year, return_pct))
                    added += 1
            except (ValueError, KeyError) as e:
                errors.append(f"Row {i}: {str(e)}")
                
        conn.commit()
        conn.close()
        
        return jsonify({
            "message": "Upload successful",
            "added": added,
            "updated": updated,
            "errors": errors
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to process CSV: {str(e)}"}), 500

# --- Scenario CRUD Routes ---

@app.route('/api/scenarios', methods=['GET'])
def get_scenarios():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scenarios")
    rows = cursor.fetchall()
    conn.close()
    
    scenarios = []
    for row in rows:
        scenarios.append({
            "id": row[0],
            "name": row[1],
            "current_age": row[2],
            "retirement_age": row[3],
            "end_age": row[4],
            "expected_expenses_in_retirement": row[5],
            "withdrawal_split_pretax_pct": row[6],
            "inflation_rate_pct": row[7],
            "return_mode": row[8],
            "return_start_year": row[9],
            "return_end_year": row[10],
            "replay_start_year": row[11]
        })
    return jsonify(scenarios)

@app.route('/api/scenarios', methods=['POST'])
def create_scenario():
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()

    # Validation
    if not data.get('name'):
        conn.close()
        return jsonify({"error": "Name is required"}), 400
    
    try:
        current_age = int(data['current_age'])
        retirement_age = int(data['retirement_age'])
        end_age = int(data['end_age'])
        expenses = float(data['expected_expenses_in_retirement'])
        withdrawal_split = float(data['withdrawal_split_pretax_pct'])
        inflation = float(data['inflation_rate_pct'])
        return_mode = data['return_mode']
    except (ValueError, TypeError):
        conn.close()
        return jsonify({"error": "Invalid numeric values for ages, expenses, or rates"}), 400

    if current_age >= retirement_age or retirement_age >= end_age:
        conn.close()
        return jsonify({"error": "Ages must be ordered: current < retirement < end"}), 400
    
    if not (0 <= withdrawal_split <= 100):
        conn.close()
        return jsonify({"error": "Withdrawal split must be between 0 and 100"}), 400
        
    if not (-5 <= inflation <= 20):
        conn.close()
        return jsonify({"error": "Inflation rate must be between -5 and 20"}), 400

    # Validate year ranges against annual_returns
    if return_mode == 'mean_stdev':
        start_year = int(data['return_start_year'])
        end_year = int(data['return_end_year'])
        if start_year > end_year:
            conn.close()
            return jsonify({"error": "Return start year must be <= end year"}), 400
            
        cursor.execute("SELECT MIN(year), MAX(year) FROM annual_returns")
        min_year, max_year = cursor.fetchone()
        
        if min_year is None:
            conn.close()
            return jsonify({"error": "No annual return data available"}), 400
            
        if start_year < min_year or end_year > max_year:
            conn.close()
            return jsonify({"error": f"Return year range must be within {min_year}-{max_year}"}), 400
            
    elif return_mode == 'historical_replay':
        replay_year = int(data['replay_start_year'])
        cursor.execute("SELECT MIN(year), MAX(year) FROM annual_returns")
        min_year, max_year = cursor.fetchone()
        
        if min_year is None:
            conn.close()
            return jsonify({"error": "No annual return data available"}), 400
            
        if replay_year < min_year or replay_year > max_year:
            conn.close()
            return jsonify({"error": f"Replay start year must be within {min_year}-{max_year}"}), 400

    cursor.execute(
        """INSERT INTO scenarios 
           (name, current_age, retirement_age, end_age, expected_expenses_in_retirement, 
            withdrawal_split_pretax_pct, inflation_rate_pct, return_mode, 
            return_start_year, return_end_year, replay_start_year)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data['name'], current_age, retirement_age, end_age, expenses,
            withdrawal_split, inflation, return_mode,
            data.get('return_start_year'), data.get('return_end_year'), data.get('replay_start_year')
        )
    )
    conn.commit()
    scenario_id = cursor.lastrowid
    conn.close()
    return jsonify({"id": scenario_id, "message": "Scenario created"}), 201

@app.route('/api/scenarios/<int:scenario_id>', methods=['PUT'])
def update_scenario(scenario_id):
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()

    # Validation (same as create)
    if not data.get('name'):
        conn.close()
        return jsonify({"error": "Name is required"}), 400
    
    try:
        current_age = int(data['current_age'])
        retirement_age = int(data['retirement_age'])
        end_age = int(data['end_age'])
        expenses = float(data['expected_expenses_in_retirement'])
        withdrawal_split = float(data['withdrawal_split_pretax_pct'])
        inflation = float(data['inflation_rate_pct'])
        return_mode = data['return_mode']
    except (ValueError, TypeError):
        conn.close()
        return jsonify({"error": "Invalid numeric values for ages, expenses, or rates"}), 400

    if current_age >= retirement_age or retirement_age >= end_age:
        conn.close()
        return jsonify({"error": "Ages must be ordered: current < retirement < end"}), 400
    
    if not (0 <= withdrawal_split <= 100):
        conn.close()
        return jsonify({"error": "Withdrawal split must be between 0 and 100"}), 400
        
    if not (-5 <= inflation <= 20):
        conn.close()
        return jsonify({"error": "Inflation rate must be between -5 and 20"}), 400

    if return_mode == 'mean_stdev':
        start_year = int(data['return_start_year'])
        end_year = int(data['return_end_year'])
        if start_year > end_year:
            conn.close()
            return jsonify({"error": "Return start year must be <= end year"}), 400
            
        cursor.execute("SELECT MIN(year), MAX(year) FROM annual_returns")
        min_year, max_year = cursor.fetchone()
        
        if min_year is None:
            conn.close()
            return jsonify({"error": "No annual return data available"}), 400
            
        if start_year < min_year or end_year > max_year:
            conn.close()
            return jsonify({"error": f"Return year range must be within {min_year}-{max_year}"}), 400
            
    elif return_mode == 'historical_replay':
        replay_year = int(data['replay_start_year'])
        cursor.execute("SELECT MIN(year), MAX(year) FROM annual_returns")
        min_year, max_year = cursor.fetchone()
        
        if min_year is None:
            conn.close()
            return jsonify({"error": "No annual return data available"}), 400
            
        if replay_year < min_year or replay_year > max_year:
            conn.close()
            return jsonify({"error": f"Replay start year must be within {min_year}-{max_year}"}), 400

    cursor.execute(
        """UPDATE scenarios SET 
           name = ?, current_age = ?, retirement_age = ?, end_age = ?, 
           expected_expenses_in_retirement = ?, withdrawal_split_pretax_pct = ?, 
           inflation_rate_pct = ?, return_mode = ?, return_start_year = ?, 
           return_end_year = ?, replay_start_year = ?
           WHERE id = ?""",
        (
            data['name'], current_age, retirement_age, end_age, expenses,
            withdrawal_split, inflation, return_mode,
            data.get('return_start_year'), data.get('return_end_year'), data.get('replay_start_year'),
            scenario_id
        )
    )
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Scenario not found"}), 404
        
    conn.commit()
    conn.close()
    return jsonify({"message": "Scenario updated"})

@app.route('/api/scenarios/<int:scenario_id>', methods=['DELETE'])
def delete_scenario(scenario_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Scenario not found"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "Scenario deleted"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
