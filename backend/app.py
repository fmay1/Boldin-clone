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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
