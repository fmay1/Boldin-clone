from flask import Flask, jsonify
from database import init_db

app = Flask(__name__)

# Initialize the database on startup
init_db()

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "Backend is running"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
