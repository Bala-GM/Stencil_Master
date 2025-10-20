#!/usr/bin/env python3
import os
import sqlite3
import sys
import time
import datetime
import shutil
import waitress
import threading
import webbrowser
from flask import Flask, render_template, request, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = "supersecretkey"

    # ==============================================================
    # 📂 Database & Backup Paths (AppData safe)
    # ==============================================================
    
    BASE_DIR = os.path.join(os.environ["APPDATA"], "Stencil")
    LOCAL_DB = os.path.join(BASE_DIR, "stencil.db")
    BACKUP_DIR = os.path.join(BASE_DIR, "backups")

    os.makedirs(BASE_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)

    # ==============================================================
    # 🗄 Database Helper Functions
    # ==============================================================
    def get_db():
        conn = sqlite3.connect(LOCAL_DB, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db():
        conn = get_db()
        cur = conn.cursor()

        # ---------------- Tables ----------------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS stencil_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fg TEXT, side TEXT, customer TEXT, stencil_no TEXT, rack_no TEXT, location TEXT,
                stencil_mils TEXT, stencil_mils_usl TEXT, stencil_mils_lsl TEXT, stencil_supplier TEXT,
                stencil_pr_no TEXT, date_received TEXT, stencil_validation_dt TEXT, stencil_revalidation_dt TEXT,
                tension_a TEXT, tension_b TEXT, tension_c TEXT, tension_d TEXT, tension_e TEXT, received_by TEXT,
                condition_status TEXT DEFAULT 'ACTIVE',
                production_status TEXT DEFAULT '',
                emp_id TEXT,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

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

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT,
                emp_id TEXT
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS operators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                operator_id TEXT
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS isos_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stencil_no TEXT,
                out_time TIMESTAMP,
                in_time TIMESTAMP,
                remarks TEXT,
                cleaned_ok TEXT,
                dent_ok TEXT,
                mesh_ok TEXT,
                tension_a TEXT,
                tension_b TEXT,
                tension_c TEXT,
                tension_d TEXT,
                tension_e TEXT,
                operator_id TEXT,
                status TEXT,
                cycle_open INTEGER DEFAULT 1
            );
        """)

        # ---------------- Preload Default Users ----------------
        existing = cur.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        if existing == 0:
            users = [("Admin", "adminSRBG", "ADMIN")]
            users += [(f"User{i}", f"User{i}", f"EMP{i:03}") for i in range(1, 21)]
            for u, p, emp in users:
                cur.execute("INSERT INTO users (username, password_hash, emp_id) VALUES (?,?,?)",
                            (u, generate_password_hash(p), emp))

        existing_ops = cur.execute("SELECT COUNT(*) as c FROM operators").fetchone()["c"]
        if existing_ops == 0:
            ops = [(f"OP-USER{i}", f"OP{i:03}") for i in range(1, 21)]
            for uname, opid in ops:
                cur.execute("INSERT INTO operators (username, operator_id) VALUES (?,?)", (uname, opid))

        conn.commit()
        conn.close()
        print(f"✅ Database initialized at {LOCAL_DB}")

    # ==============================================================
    # 💾 Backup System (Weekly)
    # ==============================================================
    def backup_db():
        """Create timestamped .bak copy of the database."""
        if os.path.exists(LOCAL_DB):
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = os.path.join(BACKUP_DIR, f"stencil_{timestamp}.bak")
            shutil.copy2(LOCAL_DB, backup_name)
            print(f"🗄 Backup created at {backup_name}")

    def weekly_backup_job():
        """Background job that runs every week."""
        while True:
            backup_db()
            time.sleep(7 * 24 * 60 * 60)  # 7 days

    def start_backup_thread():
        t = threading.Thread(target=weekly_backup_job, daemon=True)
        t.start()
        print("🕒 Weekly backup thread started")

    # Initialize DB & start backup system
    os.makedirs(BASE_DIR, exist_ok=True)
    init_db()
    start_backup_thread()

    # ==============================================================
    # ⚙️ Existing App Logic
    # ==============================================================
    app.config["DATABASE"] = LOCAL_DB
    app.get_db = get_db

    # --- Your full existing route logic stays here ---
    # ---------------- Utilities ----------------
    SHORT_FIELDS = ["fg","side","customer","stencil_no","rack_no","location"]
    ALL_FIELDS = SHORT_FIELDS + [
        "stencil_mils","stencil_mils_usl","stencil_mils_lsl","stencil_supplier",
        "stencil_pr_no","date_received","stencil_validation_dt","stencil_revalidation_dt",
        "tension_a","tension_b","tension_c","tension_d","tension_e","received_by",
        "condition_status","production_status","emp_id","remarks"
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
        """Validate username & password and return (ok, emp_id)"""
        username = payload.get("username")
        password = payload.get("password")
        if not username or not password:
            return False, None
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        if not row:
            return False, None
        if check_password_hash(row["password_hash"], password):
            return True, row["emp_id"]
        return False, None
    # (Keep all your route and API definitions below this point)
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

    @app.route("/isos")
    def isos():
        return render_template("isos.html")

    # ---------------- EMP API ----------------
    @app.route("/api/login", methods=["POST"])
    def api_login():
        payload = request.get_json(silent=True) or request.form.to_dict()
        ok, emp_id = check_credentials(payload)
        if ok:
            return jsonify({"ok": True, "username": payload["username"], "emp_id": emp_id})
        return jsonify({"ok": False, "error": "Invalid username or password"}), 403
    
    # ---------------- CHANGE EMP API ----------------
    @app.route("/api/change_credentials", methods=["POST"])
    def api_change_credentials():
        payload = request.get_json(silent=True) or request.form.to_dict()
        username = payload.get("username")
        old_pw = payload.get("old_password")
        new_pw = payload.get("new_password")
        new_username = payload.get("new_username")
        new_emp_id = payload.get("new_emp_id")   # 👈 capture new EMP ID

        if not username or not old_pw:
            return jsonify({"ok": False, "error": "Username and old password required"}), 400

        conn = get_db()
        cur = conn.cursor()
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
        if new_emp_id:   # 👈 allow EMP ID change
            updates.append("emp_id=?")
            values.append(new_emp_id)

        if not updates:
            conn.close()
            return jsonify({"ok": False, "error": "Nothing to update"}), 400

        values.append(username)
        cur.execute(f"UPDATE users SET {', '.join(updates)} WHERE username=?", values)
        conn.commit()
        conn.close()

        return jsonify({"ok": True, "message": "Credentials updated"})
    
    # ---------------- OPERATORS API ----------------
    @app.route("/api/operators", methods=["GET"])
    def api_operators():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, username, operator_id FROM operators ORDER BY id")
        rows = cur.fetchall()
        conn.close()

        # Convert to list of dicts
        operators = []
        for row in rows:
            operators.append({
                "id": row["id"],
                "username": row["username"],
                "operator_id": row["operator_id"]
            })
        return jsonify(operators)
    
    # ---------------- CHANGE OPERATOR API ----------------
    @app.route("/api/change_operator", methods=["POST"])
    def api_change_operator():
        payload = request.get_json()
        username = payload.get("username")
        operator_id = payload.get("operator_id")
        new_username = payload.get("new_username")
        new_operator_id = payload.get("new_operator_id")

        if not username or not operator_id:
            return jsonify({"ok": False, "error": "Current username and OP ID required"}), 400

        conn = get_db()
        # ✅ Verify existing operator
        op = conn.execute(
            "SELECT * FROM operators WHERE username=? AND operator_id=?",
            (username, operator_id)
        ).fetchone()

        if not op:
            conn.close()
            return jsonify({"ok": False, "error": "Invalid current operator credentials"}), 403

        # Build update query dynamically
        updates = []
        params = []
        if new_username:
            updates.append("username=?")
            params.append(new_username)
        if new_operator_id:
            updates.append("operator_id=?")
            params.append(new_operator_id)

        if not updates:
            conn.close()
            return jsonify({"ok": False, "error": "No new credentials provided"}), 400

        params.append(op["id"])  # update by operator’s PK
        conn.execute(f"UPDATE operators SET {', '.join(updates)} WHERE id=?", params)
        conn.commit()
        conn.close()

        return jsonify({"ok": True})

    # ---------------- API List ----------------
    @app.route("/api/list")
    def api_list():
        conn = get_db()
        rows = conn.execute(f"""
            SELECT id, {', '.join(SHORT_FIELDS)}, condition_status, production_status
            FROM stencil_list
            WHERE condition_status != 'SCRAP'
            ORDER BY updated_at DESC, id DESC
        """).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    @app.route("/api/received")
    def api_received():
        conn = get_db()
        rows = conn.execute("SELECT * FROM stencil_list ORDER BY updated_at DESC, id DESC").fetchall()
        conn.close()
        return jsonify([row_to_dict(r, ["id"] + ALL_FIELDS) for r in rows])

    @app.route("/api/status")
    def api_status():
        conn = get_db()
        rows = conn.execute("SELECT * FROM stencil_list WHERE condition_status != 'SCRAP' ORDER BY stencil_revalidation_dt ASC").fetchall()
        conn.close()
        return jsonify([row_to_dict(r) for r in rows])

    # ------- ISOS APIs -------
    @app.route("/api/isos_list")
    def api_isos_list():
        conn = get_db()
        rows = conn.execute("""
            SELECT i.id, i.stencil_no, s.fg, s.customer, s.rack_no, s.location,
                i.out_time, i.in_time, i.remarks, i.status, i.operator_id
            FROM isos_cycles i
            JOIN stencil_list s ON i.stencil_no = s.stencil_no
            ORDER BY i.out_time DESC
        """).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    # list of forbidden condition statuses that block ISOS usage
    FORBIDDEN_STATUSES = {
        "MOVE", "REWORK", "SCRAP",
        "REVALIDATION TIME END",
        "RE-VALIDATION NEED TO DONE SOON",
        "STENCIL EOL",
        "STENCIL RE-ORDER SOON"
    }

    def is_stencil_blocked(status: str) -> bool:
        if not status:
            return False
        return status.strip().upper() in FORBIDDEN_STATUSES

    @app.route("/api/isos_lookup/<path:stencil_no>")
    def api_isos_lookup(stencil_no):
        conn = get_db()
        row = conn.execute("SELECT * FROM stencil_list WHERE stencil_no=?", (stencil_no,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"ok": False, "error": f"Stencil not found: {stencil_no}"}), 404
        active = conn.execute("SELECT * FROM isos_cycles WHERE stencil_no=? AND cycle_open=1", (stencil_no,)).fetchone()
        conn.close()
        return jsonify({"ok": True, "stencil": row_to_dict(row), "active_cycle": dict(active) if active else None})

    # ---------------- ISOS OUT ----------------
    @app.route("/api/isos_out", methods=["POST"])
    def api_isos_out():
        payload = request.get_json()
        stencil_no = payload.get("stencil_no")
        operator_id = payload.get("operator_id")

        if not stencil_no or not operator_id:
            return jsonify({"ok": False, "error": "Stencil No and Operator ID required"}), 400

        conn = get_db()
        # ✅ Validate operator_id exists
        op = conn.execute("SELECT * FROM operators WHERE operator_id=?", (operator_id,)).fetchone()
        if not op:
            conn.close()
            return jsonify({"ok": False, "error": "Invalid Operator ID"}), 403

        # Check stencil
        row = conn.execute("SELECT * FROM stencil_list WHERE stencil_no=?", (stencil_no,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"ok": False, "error": "Stencil not found"}), 404

        if is_stencil_blocked(row["condition_status"]):
            conn.close()
            return jsonify({"ok": False, "error": f"Stencil cannot be used (condition_status: {row['condition_status']})"}), 400

        # Ensure not already OUT
        active = conn.execute("SELECT * FROM isos_cycles WHERE stencil_no=? AND cycle_open=1", (stencil_no,)).fetchone()
        if active:
            conn.close()
            return jsonify({"ok": False, "error": "Stencil already OUT, must scan IN first"}), 400

        # Status calc
        cleaned_ok = payload.get("cleaned_ok")
        dent_ok = payload.get("dent_ok")
        mesh_ok = payload.get("mesh_ok")
        tensions = [payload.get(f"tension_{x}") for x in "abcde"]
        remarks = payload.get("remarks")
        status = "OK" if all([cleaned_ok == "OK", dent_ok == "OK", mesh_ok == "OK"]) else "NG"

        # Insert OUT cycle
        conn.execute("""
            INSERT INTO isos_cycles (
                stencil_no, out_time, remarks,
                cleaned_ok, dent_ok, mesh_ok,
                tension_a, tension_b, tension_c, tension_d, tension_e,
                operator_id, status, cycle_open
            ) VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (stencil_no, remarks, cleaned_ok, dent_ok, mesh_ok, *tensions, operator_id, status))

        conn.execute("UPDATE stencil_list SET production_status=? WHERE stencil_no=?", (status, stencil_no))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "status": status})

    # ---------------- ISOS IN ----------------
    @app.route("/api/isos_in", methods=["POST"])
    def api_isos_in():
        payload = request.get_json()
        stencil_no = payload.get("stencil_no")
        operator_id = payload.get("operator_id")

        if not stencil_no or not operator_id:
            return jsonify({"ok": False, "error": "Stencil No and Operator ID required"}), 400

        conn = get_db()
        # ✅ Validate operator_id exists
        op = conn.execute("SELECT * FROM operators WHERE operator_id=?", (operator_id,)).fetchone()
        if not op:
            conn.close()
            return jsonify({"ok": False, "error": "Invalid Operator ID"}), 403

        row = conn.execute("SELECT * FROM stencil_list WHERE stencil_no=?", (stencil_no,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"ok": False, "error": "Stencil not found"}), 404

        if is_stencil_blocked(row["condition_status"]):
            conn.close()
            return jsonify({"ok": False, "error": f"Stencil cannot be returned (condition_status: {row['condition_status']})"}), 400

        active = conn.execute("SELECT * FROM isos_cycles WHERE stencil_no=? AND cycle_open=1", (stencil_no,)).fetchone()
        if not active:
            conn.close()
            return jsonify({"ok": False, "error": "No active OUT cycle for this stencil"}), 400

        # Status calc
        cleaned_ok = payload.get("cleaned_ok")
        dent_ok = payload.get("dent_ok")
        mesh_ok = payload.get("mesh_ok")
        tensions = [payload.get(f"tension_{x}") for x in "abcde"]
        status = "OK" if all([cleaned_ok == "OK", dent_ok == "OK", mesh_ok == "OK"]) else "NG"

        # Update IN cycle
        conn.execute("""
            UPDATE isos_cycles
            SET in_time=CURRENT_TIMESTAMP,
                cleaned_ok=?, dent_ok=?, mesh_ok=?,
                tension_a=?, tension_b=?, tension_c=?, tension_d=?, tension_e=?,
                operator_id=?, status=?, cycle_open=0
            WHERE id=?
        """, (cleaned_ok, dent_ok, mesh_ok, *tensions, operator_id, status, active["id"]))

        conn.execute("UPDATE stencil_list SET production_status=? WHERE stencil_no=?", (status, stencil_no))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "status": status})

    # ------------- Standard CRUD / action APIs -------------
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
        ok, emp_id = check_credentials(payload)
        if not ok:
            return jsonify({"ok": False, "error": "Unauthorized"}), 403

        data = to_upper({k: payload.get(k) for k in ALL_FIELDS})
        data["emp_id"] = emp_id
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
        ok, emp_id = check_credentials(payload)
        if not ok:
            return jsonify({"ok": False, "error": "Unauthorized"}), 403

        conn = get_db()
        cur = conn.cursor()
        old = cur.execute("SELECT * FROM stencil_list WHERE id=?", (stencil_id,)).fetchone()
        if not old:
            conn.close()
            abort(404)

        new_data = to_upper({k: payload.get(k) for k in ALL_FIELDS})
        new_data["emp_id"] = emp_id
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
        ok, emp_id = check_credentials(payload)
        if not ok:
            return jsonify({"ok": False, "error": "Unauthorized"}), 403

        action = payload.get("action", "").upper()
        remarks = payload.get("remarks", "")
        emp = payload.get("emp_id") or emp_id

        if action not in ["MOVE", "REWORK", "SCRAP"]:
            abort(400, "Invalid action")

        conn = get_db()
        cur = conn.cursor()
        # set condition_status for these actions; production_status left untouched
        cur.execute("""
            UPDATE stencil_list
            SET condition_status=?, emp_id=?, remarks=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (action, emp, remarks, stencil_id))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "action": action})

    @app.route("/api/delete/<int:stencil_id>", methods=["POST"])
    def api_delete(stencil_id):
        payload = request.get_json(silent=True) or request.form.to_dict()
        ok, emp_id = check_credentials(payload)
        if not ok:
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
    # ✅ Copy all the route definitions exactly as they are from your current file.

    return app

# ==============================================================
# 🚀 Run the Flask App
# ==============================================================
app = create_app()

if __name__ == "__main__":
    # Run with waitress in production mode
    waitress.serve(app, host="0.0.0.0", port=5005)

#pyinstaller --onefile --name Stencil_Master --add-data "static;static" --add-data "templates;templates" --hidden-import flask --hidden-import flask_sqlalchemy --noconsole --icon=gbicosmt.ico app.py