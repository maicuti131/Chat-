# server.py
from flask import Flask, request, jsonify, g
import sqlite3
import os
import uuid
import time
from functools import wraps

DB = 'control.db'
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "admintoken123")  # đổi cho an toàn

app = Flask(__name__)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript('''
    CREATE TABLE IF NOT EXISTS clients (
      id TEXT PRIMARY KEY,
      token TEXT,
      created_at REAL
    );
    CREATE TABLE IF NOT EXISTS tasks (
      id TEXT PRIMARY KEY,
      client_id TEXT,
      command TEXT,
      status TEXT,
      created_at REAL,
      result TEXT
    );
    ''')
    db.commit()

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization","")
        if auth != f"Bearer {ADMIN_TOKEN}":
            return jsonify({"error":"forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper

@app.before_first_request
def before_first():
    init_db()

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json() or {}
    client_id = data.get("client_id") or str(uuid.uuid4())
    token = str(uuid.uuid4())
    db = get_db()
    db.execute("INSERT OR REPLACE INTO clients (id, token, created_at) VALUES (?, ?, ?)",
               (client_id, token, time.time()))
    db.commit()
    return jsonify({"client_id": client_id, "token": token})

@app.route('/tasks', methods=['GET'])
def get_tasks():
    token = request.headers.get("Authorization","").replace("Bearer ","")
    db = get_db()
    row = db.execute("SELECT id FROM clients WHERE token=?", (token,)).fetchone()
    if not row:
        return jsonify({"error":"unauthorized"}), 401
    client_id = row['id']
    # fetch next pending task
    task = db.execute("SELECT * FROM tasks WHERE client_id=? AND status='pending' ORDER BY created_at LIMIT 1",
                      (client_id,)).fetchone()
    if not task:
        return jsonify({"task": None})
    # mark as running
    db.execute("UPDATE tasks SET status='running' WHERE id=?", (task['id'],))
    db.commit()
    return jsonify({"task": {"id": task['id'], "command": task['command']}})

@app.route('/result', methods=['POST'])
def post_result():
    token = request.headers.get("Authorization","").replace("Bearer ","")
    db = get_db()
    row = db.execute("SELECT id FROM clients WHERE token=?", (token,)).fetchone()
    if not row:
        return jsonify({"error":"unauthorized"}), 401
    client_id = row['id']
    data = request.get_json() or {}
    task_id = data.get("task_id")
    result = data.get("result","")
    db.execute("UPDATE tasks SET status='done', result=?, created_at=created_at WHERE id=? AND client_id=?",
               (result, task_id, client_id))
    db.commit()
    return jsonify({"ok": True})

@app.route('/enqueue', methods=['POST'])
@require_admin
def enqueue():
    data = request.get_json() or {}
    client_id = data.get("client_id")
    command = data.get("command")
    if not client_id or not command:
        return jsonify({"error":"client_id and command required"}), 400
    task_id = str(uuid.uuid4())
    db = get_db()
    db.execute("INSERT INTO tasks (id, client_id, command, status, created_at) VALUES (?, ?, ?, 'pending', ?)",
               (task_id, client_id, command, time.time()))
    db.commit()
    return jsonify({"task_id": task_id})

@app.route('/clients', methods=['GET'])
@require_admin
def list_clients():
    db = get_db()
    rows = db.execute("SELECT id, created_at FROM clients").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route('/task/<task_id>', methods=['GET'])
@require_admin
def get_task(task_id):
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        return jsonify({"error":"not found"}), 404
    return jsonify(dict(row))

if __name__ == '__main__':
    # chạy dev server (production: dùng gunicorn/nginx)
    app.run(host='0.0.0.0', port=5000, debug=True)
