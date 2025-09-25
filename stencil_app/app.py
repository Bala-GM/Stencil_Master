#!/usr/bin/env python3
import os
import sys
import sqlite3
import threading
import webbrowser
from flask import Flask, render_template, request, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder="templates", static_folder="static")

# ✅ Define a dynamic, safe location for the DB file
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)  # Running from PyInstaller exe
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Development mode

    VAR_DIR = os.path.join(BASE_DIR, "var", "app-instance")
    os.makedirs(VAR_DIR, exist_ok=True)

    DB_FILE = os.path.join(VAR_DIR, "stencil.db")

    # ✅ Store into Flask config
    app.config.update(
        SECRET_KEY="dev",
        DATABASE=DB_FILE,
    )

    # ---------------- DB helpers ----------------
    def get_db():
        conn = sqlite3.connect(app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db():
        conn = get_db()
        cur = conn.cursor()
        # main stencil table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stencil_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fg TEXT, side TEXT, customer TEXT, stencil_no TEXT, rack_no TEXT, location TEXT,
                stencil_mils TEXT, stencil_mils_usl TEXT, stencil_mils_lsl TEXT, stencil_supplier TEXT,
                stencil_pr_no TEXT, date_received TEXT, stencil_validation_dt TEXT, stencil_revalidation_dt TEXT,
                tension_a TEXT, tension_b TEXT, tension_c TEXT, tension_d TEXT, tension_e TEXT, received_by TEXT,
                status TEXT DEFAULT 'ACTIVE',
                emp_id TEXT,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # history table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stencil_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stencil_id INTEGER,
                changed_column TEXT,
                old_value TEXT,
                new_value TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (stencil_id) REFERENCES stencil_list (id)
            );
        """)
        # users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT
            );
        """)
        # Preload default users if table empty
        existing = cur.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        if existing == 0:
            users = [("Admin", "adminSRBG")] + [(f"User{i}", f"User{i}") for i in range(1, 21)]
            for u, p in users:
                cur.execute("INSERT INTO users (username, password_hash) VALUES (?,?)",
                            (u, generate_password_hash(p)))
        conn.commit()
        conn.close()

    with app.app_context():
        init_db()

    # ---------------- Utilities ----------------
    SHORT_FIELDS = ["fg","side","customer","stencil_no","rack_no","location"]
    ALL_FIELDS = SHORT_FIELDS + [
        "stencil_mils","stencil_mils_usl","stencil_mils_lsl","stencil_supplier",
        "stencil_pr_no","date_received","stencil_validation_dt","stencil_revalidation_dt",
        "tension_a","tension_b","tension_c","tension_d","tension_e","received_by",
        "status","emp_id","remarks"
    ]

    def to_upper(d: dict):
        out = {}
        for k, v in d.items():
            out[k] = "" if v is None else str(v).strip().upper()
        return out

    def row_to_dict(row, fields=None):
        if row is None:
            return None
        if fields is None:
            fields = ["id"] + ALL_FIELDS
        return {k: row[k] for k in fields if (k == "id" or k in row.keys())}

    def check_credentials(payload):
        """Validate username & password against hashed DB values"""
        username = payload.get("username")
        password = payload.get("password")
        if not username or not password:
            return False
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        if not row:
            return False
        return check_password_hash(row["password_hash"], password)

    # ---------------- Pages ----------------
    @app.route("/")
    def home():
        return render_template("home.html")

    @app.route("/received")
    def received():
        return render_template("received.html")

    @app.route("/status")
    def status():
        return render_template("status.html")

    # ---------------- API ----------------
    @app.route("/api/login", methods=["POST"])
    def api_login():
        payload = request.get_json(silent=True) or request.form.to_dict()
        if check_credentials(payload):
            return jsonify({"ok": True, "username": payload["username"]})
        return jsonify({"ok": False, "error": "Invalid username or password"}), 403

    @app.route("/api/change_credentials", methods=["POST"])
    def api_change_credentials():
        """Allow user to change username and/or password"""
        payload = request.get_json(silent=True) or request.form.to_dict()
        username = payload.get("username")
        old_pw = payload.get("old_password")
        new_pw = payload.get("new_password")
        new_username = payload.get("new_username")

        if not username or not old_pw:
            return jsonify({"ok": False, "error": "Username and old password required"}), 400

        conn = get_db()
        cur = conn.cursor()

        # Verify old credentials
        row = cur.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row or not check_password_hash(row["password_hash"], old_pw):
            conn.close()
            return jsonify({"ok": False, "error": "Invalid username or old password"}), 403

        updates = []
        values = []

        if new_username:
            updates.append("username=?")
            values.append(new_username)
        if new_pw:
            updates.append("password_hash=?")
            values.append(generate_password_hash(new_pw))

        if not updates:
            conn.close()
            return jsonify({"ok": False, "error": "Nothing to update"}), 400

        values.append(username)  # WHERE old username
        cur.execute(f"UPDATE users SET {', '.join(updates)} WHERE username=?", values)

        conn.commit()
        conn.close()

        return jsonify({
            "ok": True,
            "message": f"Updated {'username and password' if new_username and new_pw else 'username' if new_username else 'password'} successfully"
        })

    @app.route("/api/list")
    def api_list():
        conn = get_db()
        rows = conn.execute(f"""
            SELECT id, {', '.join(SHORT_FIELDS)}, status
            FROM stencil_list
            WHERE status != 'SCRAP'
            ORDER BY updated_at DESC, id DESC
        """).fetchall()
        conn.close()
        data = [{"id": r["id"], **{f: r[f] for f in SHORT_FIELDS}, "status": r["status"]} for r in rows]
        return jsonify(data)

    @app.route("/api/received")
    def api_received():
        conn = get_db()
        rows = conn.execute("SELECT * FROM stencil_list ORDER BY updated_at DESC, id DESC").fetchall()
        conn.close()
        data = [row_to_dict(r, ["id"] + ALL_FIELDS) for r in rows]
        return jsonify(data)

    @app.route("/api/status")
    def api_status():
        conn = get_db()
        rows = conn.execute("SELECT * FROM stencil_list WHERE status != 'SCRAP' ORDER BY stencil_revalidation_dt ASC").fetchall()
        conn.close()
        data = [row_to_dict(r) for r in rows]
        return jsonify(data)

    @app.route("/api/get/<int:stencil_id>")
    def api_get(stencil_id):
        conn = get_db()
        row = conn.execute("SELECT * FROM stencil_list WHERE id=?", (stencil_id,)).fetchone()
        conn.close()
        if not row:
            abort(404)
        return jsonify(row_to_dict(row, ["id"] + ALL_FIELDS))

    @app.route("/api/add", methods=["POST"])
    def api_add():
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not check_credentials(payload):
            return jsonify({"ok": False, "error": "Unauthorized"}), 403

        data = to_upper({k: payload.get(k) for k in ALL_FIELDS})
        conn = get_db()
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO stencil_list ({', '.join(ALL_FIELDS)})
            VALUES ({', '.join(['?'] * len(ALL_FIELDS))})
        """, [data.get(k) for k in ALL_FIELDS])
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "id": new_id})

    @app.route("/api/update/<int:stencil_id>", methods=["POST"])
    def api_update(stencil_id):
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not check_credentials(payload):
            return jsonify({"ok": False, "error": "Unauthorized"}), 403

        conn = get_db()
        cur = conn.cursor()
        old = cur.execute("SELECT * FROM stencil_list WHERE id=?", (stencil_id,)).fetchone()
        if not old:
            conn.close()
            abort(404)

        new_data = to_upper({k: payload.get(k) for k in ALL_FIELDS})
        changes = []
        for f in ALL_FIELDS:
            old_val = (old[f] or "").strip()
            new_val = (new_data.get(f) or "").strip()
            if old_val != new_val:
                changes.append((stencil_id, f, old_val, new_val))

        if changes:
            cur.executemany("""
                INSERT INTO stencil_history (stencil_id, changed_column, old_value, new_value)
                VALUES (?,?,?,?)
            """, changes)
            set_clause = ", ".join([f"{f}=?" for f in ALL_FIELDS]) + ", updated_at=CURRENT_TIMESTAMP"
            values = [new_data.get(f) for f in ALL_FIELDS] + [stencil_id]
            cur.execute(f"UPDATE stencil_list SET {set_clause} WHERE id=?", values)

        conn.commit()
        conn.close()
        return jsonify({"ok": True, "changes": len(changes)})

    @app.route("/api/action/<int:stencil_id>", methods=["POST"])
    def api_action(stencil_id):
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not check_credentials(payload):
            return jsonify({"ok": False, "error": "Unauthorized"}), 403

        action = payload.get("action", "").upper()
        remarks = payload.get("remarks", "")
        emp_id = payload.get("emp_id", "")

        if action not in ["MOVE", "REWORK", "SCRAP"]:
            abort(400, "Invalid action")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            UPDATE stencil_list 
            SET status=?, emp_id=?, remarks=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (action, emp_id, remarks, stencil_id))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "action": action})

    @app.route("/api/delete/<int:stencil_id>", methods=["POST"])
    def api_delete(stencil_id):
        payload = request.get_json(silent=True) or request.form.to_dict()
        if not check_credentials(payload):
            return jsonify({"ok": False, "error": "Unauthorized"}), 403

        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM stencil_list WHERE id=?", (stencil_id,))
        cur.execute("DELETE FROM stencil_history WHERE stencil_id=?", (stencil_id,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    @app.route("/api/history/<int:stencil_id>")
    def api_history(stencil_id):
        column = request.args.get("column")
        conn = get_db()
        cur = conn.cursor()
        if column and column != "all":
            cur.execute("""
                SELECT changed_at, changed_column, old_value, new_value
                FROM stencil_history
                WHERE stencil_id = ? AND changed_column = ?
                ORDER BY changed_at DESC, id DESC
            """, (stencil_id, column))
        else:
            cur.execute("""
                SELECT changed_at, changed_column, old_value, new_value
                FROM stencil_history
                WHERE stencil_id = ?
                ORDER BY changed_at DESC, id DESC
            """, (stencil_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify(rows)
    
# ✅ Auto-launch in browser
def open_browser():
    webbrowser.open("http://127.0.0.1:5005/")

if __name__ == "__main__":
    init_db()
    threading.Timer(1.5, open_browser).start()
    app.run(debug=True, port=5005)

#pyinstaller --onefile --name Stencil_Master --add-data "static;static" --add-data "templates;templates" --add-data "var/app-instance/stencil.db;var/app-instance" --hidden-import flask --hidden-import flask_sqlalchemy --noconsole --icon=smt-stencils.ico app.py