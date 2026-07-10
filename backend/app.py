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
        content = file.read().decode('utf-8')
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
                return_pct = float(row['return'])
                
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
