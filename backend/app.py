import io
import csv
from flask import Flask, jsonify, request
from database import init_db, get_connection
from projection import run_projection, calculate_projection

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
    
    scenarios = []
    for row in rows:
        scenario_id = row[0]
        cursor.execute("SELECT id, amount, age, inflation_adjusted FROM scenario_expenditures WHERE scenario_id = ?", (scenario_id,))
        exp_rows = cursor.fetchall()
        expenditures = [{"id": e[0], "amount": e[1], "age": e[2], "inflation_adjusted": e[3]} for e in exp_rows]
        
        cursor.execute("SELECT id, start_age, end_age, amount, inflation_adjusted FROM scenario_incomes WHERE scenario_id = ?", (scenario_id,))
        inc_rows = cursor.fetchall()
        incomes = [{"id": i[0], "start_age": i[1], "end_age": i[2], "amount": i[3], "inflation_adjusted": i[4]} for i in inc_rows]
        
        scenarios.append({
            "id": scenario_id,
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
            "replay_start_year": row[11],
            "block_length_years": row[12],
            "expenditures": expenditures,
            "incomes": incomes
        })
    conn.close()
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
        current_age = float(data['current_age'])
        retirement_age = float(data['retirement_age'])
        end_age = int(data['end_age'])
        expenses = float(data['expected_expenses_in_retirement'])
        withdrawal_split = float(data['withdrawal_split_pretax_pct'])
        inflation = float(data['inflation_rate_pct'])
        return_mode = data['return_mode']
    except (ValueError, TypeError):
        conn.close()
        return jsonify({"error": "Invalid numeric values for ages, expenses, or rates"}), 400

    # Validate monthly precision for current_age and retirement_age
    if abs((current_age * 12) - round(current_age * 12)) > 1e-9:
        conn.close()
        return jsonify({"error": "Current age must correspond to a whole number of months (e.g., 46.25)"}), 400
    if abs((retirement_age * 12) - round(retirement_age * 12)) > 1e-9:
        conn.close()
        return jsonify({"error": "Retirement age must correspond to a whole number of months (e.g., 46.25)"}), 400

    if current_age >= retirement_age or retirement_age >= end_age:
        conn.close()
        return jsonify({"error": "Ages must be ordered: current < retirement < end"}), 400
    
    if not (0 <= withdrawal_split <= 100):
        conn.close()
        return jsonify({"error": "Withdrawal split must be between 0 and 100"}), 400
        
    if not (-5 <= inflation <= 20):
        conn.close()
        return jsonify({"error": "Inflation rate must be between -5 and 20"}), 400

    try:
        if return_mode == 'mean_stdev':
            start_year = int(data['return_start_year'])
            end_year = int(data['return_end_year']) if data.get('return_end_year') is not None else None
            if start_year is not None and end_year is not None and start_year > end_year:
                conn.close()
                return jsonify({"error": "Return start year must be <= end year"}), 400
                
            cursor.execute("SELECT MIN(year), MAX(year) FROM annual_returns")
            min_year, max_year = cursor.fetchone()
            
            if min_year is None:
                conn.close()
                return jsonify({"error": "No annual return data available"}), 400
                
            if start_year < min_year or (end_year is not None and end_year > max_year):
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
                
        elif return_mode == 'monte_carlo':
            start_year = int(data['return_start_year'])
            end_year = int(data['return_end_year']) if data.get('return_end_year') is not None else None
            block_len = int(data['block_length_years'])
            if start_year is not None and end_year is not None and start_year > end_year:
                conn.close()
                return jsonify({"error": "Return start year must be <= end year"}), 400
            if block_len <= 0:
                conn.close()
                return jsonify({"error": "Block length must be > 0"}), 400
                
            cursor.execute("SELECT MIN(year), MAX(year) FROM annual_returns")
            min_year, max_year = cursor.fetchone()
            
            if min_year is None:
                conn.close()
                return jsonify({"error": "No annual return data available"}), 400
                
            if start_year < min_year or (end_year is not None and end_year > max_year):
                conn.close()
                return jsonify({"error": f"Return year range must be within {min_year}-{max_year}"}), 400
    except (ValueError, TypeError, KeyError):
        conn.close()
        return jsonify({"error": "Missing or invalid year field for the selected return mode"}), 400

    cursor.execute(
        """INSERT INTO scenarios 
           (name, current_age, retirement_age, end_age, expected_expenses_in_retirement, 
            withdrawal_split_pretax_pct, inflation_rate_pct, return_mode, 
            return_start_year, return_end_year, replay_start_year, block_length_years)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data['name'], current_age, retirement_age, end_age, expenses,
            withdrawal_split, inflation, return_mode,
            data.get('return_start_year'), data.get('return_end_year'), data.get('replay_start_year'),
            data.get('block_length_years')
        )
    )
    conn.commit()
    scenario_id = cursor.lastrowid
    
    # Copy expenditures if requested
    if data.get('copy_expenditures') is True and data.get('source_scenario_id'):
        source_id = data['source_scenario_id']
        cursor.execute("SELECT amount, age, inflation_adjusted FROM scenario_expenditures WHERE scenario_id = ?", (source_id,))
        source_exps = cursor.fetchall()
        for exp in source_exps:
            cursor.execute(
                "INSERT INTO scenario_expenditures (scenario_id, amount, age, inflation_adjusted) VALUES (?, ?, ?, ?)",
                (scenario_id, exp[0], exp[1], exp[2])
            )
        conn.commit()
        
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
        current_age = float(data['current_age'])
        retirement_age = float(data['retirement_age'])
        end_age = int(data['end_age'])
        expenses = float(data['expected_expenses_in_retirement'])
        withdrawal_split = float(data['withdrawal_split_pretax_pct'])
        inflation = float(data['inflation_rate_pct'])
        return_mode = data['return_mode']
    except (ValueError, TypeError):
        conn.close()
        return jsonify({"error": "Invalid numeric values for ages, expenses, or rates"}), 400

    # Validate monthly precision for current_age and retirement_age
    if abs((current_age * 12) - round(current_age * 12)) > 1e-9:
        conn.close()
        return jsonify({"error": "Current age must correspond to a whole number of months (e.g., 46.25)"}), 400
    if abs((retirement_age * 12) - round(retirement_age * 12)) > 1e-9:
        conn.close()
        return jsonify({"error": "Retirement age must correspond to a whole number of months (e.g., 46.25)"}), 400

    if current_age >= retirement_age or retirement_age >= end_age:
        conn.close()
        return jsonify({"error": "Ages must be ordered: current < retirement < end"}), 400
    
    if not (0 <= withdrawal_split <= 100):
        conn.close()
        return jsonify({"error": "Withdrawal split must be between 0 and 100"}), 400
        
    if not (-5 <= inflation <= 20):
        conn.close()
        return jsonify({"error": "Inflation rate must be between -5 and 20"}), 400

    try:
        if return_mode == 'mean_stdev':
            start_year = int(data['return_start_year'])
            end_year = int(data['return_end_year']) if data.get('return_end_year') is not None else None
            if start_year is not None and end_year is not None and start_year > end_year:
                conn.close()
                return jsonify({"error": "Return start year must be <= end year"}), 400
                
            cursor.execute("SELECT MIN(year), MAX(year) FROM annual_returns")
            min_year, max_year = cursor.fetchone()
            
            if min_year is None:
                conn.close()
                return jsonify({"error": "No annual return data available"}), 400
                
            if start_year < min_year or (end_year is not None and end_year > max_year):
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
                
        elif return_mode == 'monte_carlo':
            start_year = int(data['return_start_year'])
            end_year = int(data['return_end_year']) if data.get('return_end_year') is not None else None
            block_len = int(data['block_length_years'])
            if start_year is not None and end_year is not None and start_year > end_year:
                conn.close()
                return jsonify({"error": "Return start year must be <= end year"}), 400
            if block_len <= 0:
                conn.close()
                return jsonify({"error": "Block length must be > 0"}), 400
                
            cursor.execute("SELECT MIN(year), MAX(year) FROM annual_returns")
            min_year, max_year = cursor.fetchone()
            
            if min_year is None:
                conn.close()
                return jsonify({"error": "No annual return data available"}), 400
                
            if start_year < min_year or (end_year is not None and end_year > max_year):
                conn.close()
                return jsonify({"error": f"Return year range must be within {min_year}-{max_year}"}), 400
    except (ValueError, TypeError, KeyError):
        conn.close()
        return jsonify({"error": "Missing or invalid year field for the selected return mode"}), 400

    cursor.execute(
        """UPDATE scenarios SET 
           name = ?, current_age = ?, retirement_age = ?, end_age = ?, 
           expected_expenses_in_retirement = ?, withdrawal_split_pretax_pct = ?, 
           inflation_rate_pct = ?, return_mode = ?, return_start_year = ?, 
           return_end_year = ?, replay_start_year = ?, block_length_years = ?
           WHERE id = ?""",
        (
            data['name'], current_age, retirement_age, end_age, expenses,
            withdrawal_split, inflation, return_mode,
            data.get('return_start_year'), data.get('return_end_year'), data.get('replay_start_year'),
            data.get('block_length_years'),
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

# --- Scenario Expenditure Routes ---

@app.route('/api/scenarios/<int:scenario_id>/expenditures', methods=['POST'])
def create_expenditure(scenario_id):
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check scenario exists and get current_age
    cursor.execute("SELECT current_age FROM scenarios WHERE id = ?", (scenario_id,))
    scenario = cursor.fetchone()
    if not scenario:
        conn.close()
        return jsonify({"error": "Scenario not found"}), 404
        
    current_age = scenario[0]
    
    # Check count of existing expenditures
    cursor.execute("SELECT COUNT(*) FROM scenario_expenditures WHERE scenario_id = ?", (scenario_id,))
    count = cursor.fetchone()[0]
    if count >= 10:
        conn.close()
        return jsonify({"error": "Maximum of 10 expenditures per scenario reached"}), 400
        
    amount = data.get('amount')
    age = data.get('age')
    inflation_adjusted = data.get('inflation_adjusted', 0)
    
    if amount is None or age is None:
        conn.close()
        return jsonify({"error": "Amount and age are required"}), 400
        
    try:
        amount = float(amount)
        age = float(age)
    except (ValueError, TypeError):
        conn.close()
        return jsonify({"error": "Invalid numeric values"}), 400
        
    if amount <= 0:
        conn.close()
        return jsonify({"error": "Amount must be > 0"}), 400
        
    if age < current_age:
        conn.close()
        return jsonify({"error": "Age must be >= current_age of the scenario"}), 400
        
    cursor.execute(
        "INSERT INTO scenario_expenditures (scenario_id, amount, age, inflation_adjusted) VALUES (?, ?, ?, ?)",
        (scenario_id, amount, age, 1 if inflation_adjusted else 0)
    )
    conn.commit()
    exp_id = cursor.lastrowid
    conn.close()
    return jsonify({"id": exp_id, "message": "Expenditure created"}), 201

@app.route('/api/scenarios/<int:scenario_id>/expenditures/<int:eid>', methods=['PUT'])
def update_expenditure(scenario_id, eid):
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if expenditure belongs to scenario
    cursor.execute("SELECT amount, age FROM scenario_expenditures WHERE id = ? AND scenario_id = ?", (eid, scenario_id))
    exp = cursor.fetchone()
    if not exp:
        conn.close()
        return jsonify({"error": "Expenditure not found or does not belong to this scenario"}), 404
        
    # Get scenario current_age
    cursor.execute("SELECT current_age FROM scenarios WHERE id = ?", (scenario_id,))
    current_age = cursor.fetchone()[0]
    
    amount = data.get('amount')
    age = data.get('age')
    inflation_adjusted = data.get('inflation_adjusted', 0)
    
    if amount is None or age is None:
        conn.close()
        return jsonify({"error": "Amount and age are required"}), 400
        
    try:
        amount = float(amount)
        age = float(age)
    except (ValueError, TypeError):
        conn.close()
        return jsonify({"error": "Invalid numeric values"}), 400
        
    if amount <= 0:
        conn.close()
        return jsonify({"error": "Amount must be > 0"}), 400
        
    if age < current_age:
        conn.close()
        return jsonify({"error": "Age must be >= current_age of the scenario"}), 400
        
    cursor.execute(
        "UPDATE scenario_expenditures SET amount = ?, age = ?, inflation_adjusted = ? WHERE id = ? AND scenario_id = ?",
        (amount, age, 1 if inflation_adjusted else 0, eid, scenario_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Expenditure updated"})

@app.route('/api/scenarios/<int:scenario_id>/expenditures/<int:eid>', methods=['DELETE'])
def delete_expenditure(scenario_id, eid):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scenario_expenditures WHERE id = ? AND scenario_id = ?", (eid, scenario_id))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Expenditure not found or does not belong to this scenario"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "Expenditure deleted"})

# --- Projection Route ---

@app.route('/api/projection/<int:scenario_id>', methods=['GET'])
def get_projection(scenario_id):
    result = run_projection(scenario_id)
    if isinstance(result, tuple):
        return jsonify(result[0]), result[1]
    return jsonify(result)

@app.route('/api/projection/preview', methods=['POST'])
def preview_projection():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
        
    # Basic validation
    try:
        current_age = float(data['current_age'])
        retirement_age = float(data['retirement_age'])
        end_age = int(data['end_age'])
        expenses = float(data['expected_expenses_in_retirement'])
        withdrawal_split = float(data['withdrawal_split_pretax_pct'])
        inflation = float(data['inflation_rate_pct'])
        return_mode = data['return_mode']
    except (ValueError, TypeError, KeyError):
        return jsonify({"error": "Invalid numeric values or missing fields"}), 400

    # Validate monthly precision for current_age and retirement_age
    if abs((current_age * 12) - round(current_age * 12)) > 1e-9:
        return jsonify({"error": "Current age must correspond to a whole number of months (e.g., 46.25)"}), 400
    if abs((retirement_age * 12) - round(retirement_age * 12)) > 1e-9:
        return jsonify({"error": "Retirement age must correspond to a whole number of months (e.g., 46.25)"}), 400

    if current_age >= retirement_age or retirement_age >= end_age:
        return jsonify({"error": "Ages must be ordered: current < retirement < end"}), 400
    if not (0 <= withdrawal_split <= 100):
        return jsonify({"error": "Withdrawal split must be between 0 and 100"}), 400
    if not (-5 <= inflation <= 20):
        return jsonify({"error": "Inflation rate must be between -5 and 20"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts")
    accounts = cursor.fetchall()
    if not accounts:
        conn.close()
        return jsonify({"error": "No accounts found."}), 400
        
    cursor.execute("SELECT year, return_pct FROM annual_returns ORDER BY year")
    annual_returns = cursor.fetchall()
    if not annual_returns:
        conn.close()
        return jsonify({"error": "No annual return data found."}), 400
        
    min_year, max_year = cursor.execute("SELECT MIN(year), MAX(year) FROM annual_returns").fetchone()
    
    try:
        if return_mode == 'mean_stdev':
            start_year = int(data['return_start_year'])
            end_year = int(data['return_end_year']) if data.get('return_end_year') else max_year
            if start_year < min_year or end_year > max_year:
                conn.close()
                return jsonify({"error": f"Return year range must be within {min_year}-{max_year}"}), 400
        elif return_mode == 'historical_replay':
            replay_year = int(data['replay_start_year'])
            if replay_year < min_year or replay_year > max_year:
                conn.close()
                return jsonify({"error": f"Replay start year must be within {min_year}-{max_year}"}), 400
        elif return_mode == 'monte_carlo':
            start_year = int(data['return_start_year'])
            end_year = int(data['return_end_year']) if data.get('return_end_year') else max_year
            block_len = int(data['block_length_years'])
            if start_year < min_year or end_year > max_year:
                conn.close()
                return jsonify({"error": f"Return year range must be within {min_year}-{max_year}"}), 400
            if block_len <= 0:
                conn.close()
                return jsonify({"error": "Block length must be > 0"}), 400
    except (ValueError, TypeError, KeyError):
        conn.close()
        return jsonify({"error": "Missing or invalid year field for the selected return mode"}), 400
            
    conn.close()
    
    accounts_list = [dict(a) for a in accounts]
    returns_list = [dict(r) for r in annual_returns]
    expenditures = data.get('expenditures') or []
    
    result = calculate_projection(data, accounts_list, returns_list, expenditures)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
