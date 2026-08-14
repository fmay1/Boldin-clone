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

VALID_RETURN_MODES = ('mean_stdev', 'historical_replay', 'monte_carlo')

def validate_scenario(data, cursor):
    """
    Validates the scenario parameters shared by the create, update, and
    preview endpoints. Returns (parsed, None) if valid, or (None,
    error_message) if not. `parsed` holds the type-coerced values the
    endpoints use in their SQL. `name` is checked by callers that persist,
    since preview doesn't save.
    """
    try:
        current_age = float(data['current_age'])
        retirement_age = float(data['retirement_age'])
        end_age = int(data['end_age'])
        expenses = float(data['expected_expenses_in_retirement'])
        withdrawal_split = float(data['withdrawal_split_pretax_pct'])
        inflation = float(data['inflation_rate_pct'])
        return_mode = data['return_mode']
    except (ValueError, TypeError, KeyError):
        return None, "Invalid numeric values for ages, expenses, or rates"

    # Validate monthly precision for current_age and retirement_age
    if abs((current_age * 12) - round(current_age * 12)) > 1e-9:
        return None, "Current age must correspond to a whole number of months (e.g., 46.25)"
    if abs((retirement_age * 12) - round(retirement_age * 12)) > 1e-9:
        return None, "Retirement age must correspond to a whole number of months (e.g., 46.25)"

    if current_age >= retirement_age or retirement_age >= end_age:
        return None, "Ages must be ordered: current < retirement < end"

    if not (0 <= withdrawal_split <= 100):
        return None, "Withdrawal split must be between 0 and 100"

    if not (-5 <= inflation <= 20):
        return None, "Inflation rate must be between -5 and 20"

    if return_mode not in VALID_RETURN_MODES:
        return None, "Return mode must be one of: mean_stdev, historical_replay, monte_carlo"

    cursor.execute("SELECT MIN(year), MAX(year) FROM annual_returns")
    min_year, max_year = cursor.fetchone()

    if min_year is None:
        return None, "No annual return data available"

    parsed = {
        "current_age": current_age,
        "retirement_age": retirement_age,
        "end_age": end_age,
        "expenses": expenses,
        "withdrawal_split": withdrawal_split,
        "inflation": inflation,
        "return_mode": return_mode,
        "return_start_year": None,
        "return_end_year": None,
        "replay_start_year": None,
        "block_length_years": None
    }

    try:
        if return_mode in ('mean_stdev', 'monte_carlo'):
            start_year = int(data['return_start_year'])
            end_year = int(data['return_end_year']) if data.get('return_end_year') is not None else None
            if end_year is not None and start_year > end_year:
                return None, "Return start year must be <= end year"
            if start_year < min_year or (end_year is not None and end_year > max_year):
                return None, f"Return year range must be within {min_year}-{max_year}"
            parsed["return_start_year"] = start_year
            parsed["return_end_year"] = end_year
            if return_mode == 'monte_carlo':
                block_len = int(data['block_length_years'])
                if block_len <= 0:
                    return None, "Block length must be > 0"
                parsed["block_length_years"] = block_len
        elif return_mode == 'historical_replay':
            replay_year = int(data['replay_start_year'])
            if replay_year < min_year or replay_year > max_year:
                return None, f"Replay start year must be within {min_year}-{max_year}"
            parsed["replay_start_year"] = replay_year
    except (ValueError, TypeError, KeyError):
        return None, "Missing or invalid year field for the selected return mode"

    return parsed, None

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

    parsed, error = validate_scenario(data, cursor)
    if error:
        conn.close()
        return jsonify({"error": error}), 400

    cursor.execute(
        """INSERT INTO scenarios
           (name, current_age, retirement_age, end_age, expected_expenses_in_retirement,
            withdrawal_split_pretax_pct, inflation_rate_pct, return_mode,
            return_start_year, return_end_year, replay_start_year, block_length_years)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data['name'], parsed["current_age"], parsed["retirement_age"], parsed["end_age"], parsed["expenses"],
            parsed["withdrawal_split"], parsed["inflation"], parsed["return_mode"],
            parsed["return_start_year"], parsed["return_end_year"], parsed["replay_start_year"],
            parsed["block_length_years"]
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

    # Validation (shared with create and preview)
    if not data.get('name'):
        conn.close()
        return jsonify({"error": "Name is required"}), 400

    parsed, error = validate_scenario(data, cursor)
    if error:
        conn.close()
        return jsonify({"error": error}), 400

    cursor.execute(
        """UPDATE scenarios SET
           name = ?, current_age = ?, retirement_age = ?, end_age = ?,
           expected_expenses_in_retirement = ?, withdrawal_split_pretax_pct = ?,
           inflation_rate_pct = ?, return_mode = ?, return_start_year = ?,
           return_end_year = ?, replay_start_year = ?, block_length_years = ?
           WHERE id = ?""",
        (
            data['name'], parsed["current_age"], parsed["retirement_age"], parsed["end_age"], parsed["expenses"],
            parsed["withdrawal_split"], parsed["inflation"], parsed["return_mode"],
            parsed["return_start_year"], parsed["return_end_year"], parsed["replay_start_year"],
            parsed["block_length_years"],
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

# --- Scenario Income Routes ---

@app.route('/api/scenarios/<int:scenario_id>/incomes', methods=['POST'])
def create_income(scenario_id):
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check scenario exists and get current_age and end_age
    cursor.execute("SELECT current_age, end_age FROM scenarios WHERE id = ?", (scenario_id,))
    scenario = cursor.fetchone()
    if not scenario:
        conn.close()
        return jsonify({"error": "Scenario not found"}), 404
        
    current_age = scenario[0]
    scenario_end_age = scenario[1]
    
    start_age = data.get('start_age')
    end_age = data.get('end_age')
    amount = data.get('amount')
    inflation_adjusted = data.get('inflation_adjusted', 0)
    
    if start_age is None or end_age is None or amount is None:
        conn.close()
        return jsonify({"error": "Start age, end age, and amount are required"}), 400
        
    try:
        start_age = float(start_age)
        end_age = float(end_age)
        amount = float(amount)
    except (ValueError, TypeError):
        conn.close()
        return jsonify({"error": "Invalid numeric values"}), 400
        
    if amount <= 0:
        conn.close()
        return jsonify({"error": "Amount must be > 0"}), 400
        
    if start_age >= end_age:
        conn.close()
        return jsonify({"error": "Start age must be < end age"}), 400
        
    if start_age < current_age:
        conn.close()
        return jsonify({"error": "Start age must be >= current_age of the scenario"}), 400
        
    if end_age > scenario_end_age:
        conn.close()
        return jsonify({"error": "End age must be <= end_age of the scenario"}), 400
        
    cursor.execute(
        "INSERT INTO scenario_incomes (scenario_id, start_age, end_age, amount, inflation_adjusted) VALUES (?, ?, ?, ?, ?)",
        (scenario_id, start_age, end_age, amount, 1 if inflation_adjusted else 0)
    )
    conn.commit()
    inc_id = cursor.lastrowid
    conn.close()
    return jsonify({"id": inc_id, "message": "Income created"}), 201

@app.route('/api/scenarios/<int:scenario_id>/incomes/<int:iid>', methods=['PUT'])
def update_income(scenario_id, iid):
    data = request.get_json()
    conn = get_connection()
    cursor = conn.cursor()
    
    # Check if income belongs to scenario
    cursor.execute("SELECT start_age, end_age, amount FROM scenario_incomes WHERE id = ? AND scenario_id = ?", (iid, scenario_id))
    inc = cursor.fetchone()
    if not inc:
        conn.close()
        return jsonify({"error": "Income not found or does not belong to this scenario"}), 404
        
    # Get scenario current_age and end_age
    cursor.execute("SELECT current_age, end_age FROM scenarios WHERE id = ?", (scenario_id,))
    scenario = cursor.fetchone()
    current_age = scenario[0]
    scenario_end_age = scenario[1]
    
    start_age = data.get('start_age')
    end_age = data.get('end_age')
    amount = data.get('amount')
    inflation_adjusted = data.get('inflation_adjusted', 0)
    
    if start_age is None or end_age is None or amount is None:
        conn.close()
        return jsonify({"error": "Start age, end age, and amount are required"}), 400
        
    try:
        start_age = float(start_age)
        end_age = float(end_age)
        amount = float(amount)
    except (ValueError, TypeError):
        conn.close()
        return jsonify({"error": "Invalid numeric values"}), 400
        
    if amount <= 0:
        conn.close()
        return jsonify({"error": "Amount must be > 0"}), 400
        
    if start_age >= end_age:
        conn.close()
        return jsonify({"error": "Start age must be < end age"}), 400
        
    if start_age < current_age:
        conn.close()
        return jsonify({"error": "Start age must be >= current_age of the scenario"}), 400
        
    if end_age > scenario_end_age:
        conn.close()
        return jsonify({"error": "End age must be <= end_age of the scenario"}), 400
        
    cursor.execute(
        "UPDATE scenario_incomes SET start_age = ?, end_age = ?, amount = ?, inflation_adjusted = ? WHERE id = ? AND scenario_id = ?",
        (start_age, end_age, amount, 1 if inflation_adjusted else 0, iid, scenario_id)
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "Income updated"})

@app.route('/api/scenarios/<int:scenario_id>/incomes/<int:iid>', methods=['DELETE'])
def delete_income(scenario_id, iid):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scenario_incomes WHERE id = ? AND scenario_id = ?", (iid, scenario_id))
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"error": "Income not found or does not belong to this scenario"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": "Income deleted"})

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

    # Validation (shared with create and update)
    parsed, error = validate_scenario(data, cursor)
    if error:
        conn.close()
        return jsonify({"error": error}), 400

    conn.close()
    
    accounts_list = [dict(a) for a in accounts]
    returns_list = [dict(r) for r in annual_returns]
    expenditures = data.get('expenditures') or []
    incomes = data.get('incomes') or []
    
    result = calculate_projection(data, accounts_list, returns_list, expenditures, incomes)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
