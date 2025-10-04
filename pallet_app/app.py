#!/usr/bin/env python3
import os
import sqlite3
import threading
import webbrowser
from flask import Flask, render_template, request, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY="dev",
        DATABASE=os.path.join(app.instance_path, "pallet.db"),
    )

    os.makedirs(app.instance_path, exist_ok=True)

    # ---------------- DB helpers ----------------
    def get_db():
        conn = sqlite3.connect(app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db():
        conn = get_db()
        cur = conn.cursor()

        # main pallet table with two status columns
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pallet_list (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fg TEXT, customer TEXT, pallet_no TEXT, pallet_qty TEXT, rack_no TEXT, location TEXT,
                pallet_supplier TEXT,
                pallet_pr_no TEXT, date_received TEXT, pallet_validation_dt TEXT, pallet_revalidation_dt TEXT,
                received_by TEXT,
                condition_status TEXT DEFAULT 'ACTIVE',
                production_status TEXT DEFAULT '',
                emp_id TEXT,
                remarks TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # history table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pallet_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pallet_id INTEGER,
                changed_column TEXT,
                old_value TEXT,
                new_value TEXT,
                changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pallet_id) REFERENCES pallet_list (id)
            );
        """)

        # users table (login users who can change condition_status etc.)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password_hash TEXT,
                emp_id TEXT
            );
        """)

        # operators table (for ISOS / production operators)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS operators (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                operator_id TEXT
            );
        """)

        # ISOS cycles (Out / In cycles)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS isos_cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pallet_no TEXT,
                out_time TIMESTAMP,
                in_time TIMESTAMP,
                remarks TEXT,
                cleaned_ok TEXT,
                dent_ok TEXT,
                mesh_ok TEXT,
                operator_id TEXT,   -- ✅ replaced emp_id with operator_id
                status TEXT,
                cycle_open INTEGER DEFAULT 1
            );
        """)

        # Preload default users if table empty
        existing = cur.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
        if existing == 0:
            # Admin + User1..User20, each with emp_id
            users = [("Admin", "adminSRBG", "ADMIN")]
            users += [(f"User{i}", f"User{i}", f"EMP{i:03}") for i in range(1, 21)]
            for u, p, emp in users:
                cur.execute("INSERT INTO users (username, password_hash, emp_id) VALUES (?,?,?)",
                            (u, generate_password_hash(p), emp))

        # Preload operators if table empty (OP-USER1..OP-USER20 with operator ids OP1..OP20).
        existing_ops = cur.execute("SELECT COUNT(*) as c FROM operators").fetchone()["c"]
        if existing_ops == 0:
            ops = [(f"OP-USER{i}", f"OP{i:03}") for i in range(1, 21)]
            for uname, opid in ops:
                cur.execute("INSERT INTO operators (username, operator_id) VALUES (?,?)", (uname, opid))

        conn.commit()
        conn.close()

    with app.app_context():
        init_db()

    # ---------------- Utilities ----------------
    SHORT_FIELDS = ["fg","customer","pallet_no","pallet_qty","rack_no","location"]
    ALL_FIELDS = SHORT_FIELDS + [
        "pallet_supplier",
        "pallet_pr_no","date_received","pallet_validation_dt","pallet_revalidation_dt",
        "received_by",
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
            FROM pallet_list
            WHERE condition_status != 'SCRAP'
            ORDER BY updated_at DESC, id DESC
        """).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    @app.route("/api/received")
    def api_received():
        conn = get_db()
        rows = conn.execute("SELECT * FROM pallet_list ORDER BY updated_at DESC, id DESC").fetchall()
        conn.close()
        return jsonify([row_to_dict(r, ["id"] + ALL_FIELDS) for r in rows])

    @app.route("/api/status")
    def api_status():
        conn = get_db()
        rows = conn.execute("SELECT * FROM pallet_list WHERE condition_status != 'SCRAP' ORDER BY pallet_revalidation_dt ASC").fetchall()
        conn.close()
        return jsonify([row_to_dict(r) for r in rows])

    # ------- ISOS APIs -------
    @app.route("/api/isos_list")
    def api_isos_list():
        conn = get_db()
        rows = conn.execute("""
            SELECT i.id, i.pallet_no, s.fg, s.customer, s.rack_no, s.location,
                i.out_time, i.in_time, i.remarks, i.status, i.operator_id
            FROM isos_cycles i
            JOIN pallet_list s ON i.pallet_no = s.pallet_no
            ORDER BY i.out_time DESC
        """).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])

    # list of forbidden condition statuses that block ISOS usage
    FORBIDDEN_STATUSES = {
        "MOVE", "REWORK", "SCRAP",
        "REVALIDATION TIME END",
        "RE-VALIDATION NEED TO DONE SOON"
    }

    def is_pallet_blocked(status: str) -> bool:
        if not status:
            return False
        return status.strip().upper() in FORBIDDEN_STATUSES

    @app.route("/api/isos_lookup/<path:pallet_no>")
    def api_isos_lookup(pallet_no):
        conn = get_db()
        row = conn.execute("SELECT * FROM pallet_list WHERE pallet_no=?", (pallet_no,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"ok": False, "error": f"Pallet not found: {pallet_no}"}), 404
        active = conn.execute("SELECT * FROM isos_cycles WHERE pallet_no=? AND cycle_open=1", (pallet_no,)).fetchone()
        conn.close()
        return jsonify({"ok": True, "pallet": row_to_dict(row), "active_cycle": dict(active) if active else None})

    # ---------------- ISOS OUT ----------------
    @app.route("/api/isos_out", methods=["POST"])
    def api_isos_out():
        payload = request.get_json()
        pallet_no = payload.get("pallet_no")
        operator_id = payload.get("operator_id")

        if not pallet_no or not operator_id:
            return jsonify({"ok": False, "error": "pallet No and Operator ID required"}), 400

        conn = get_db()
        # ✅ Validate operator_id exists
        op = conn.execute("SELECT * FROM operators WHERE operator_id=?", (operator_id,)).fetchone()
        if not op:
            conn.close()
            return jsonify({"ok": False, "error": "Invalid Operator ID"}), 403

        # Check pallet
        row = conn.execute("SELECT * FROM pallet_list WHERE pallet_no=?", (pallet_no,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"ok": False, "error": "pallet not found"}), 404

        if is_pallet_blocked(row["condition_status"]):
            conn.close()
            return jsonify({"ok": False, "error": f"pallet cannot be used (condition_status: {row['condition_status']})"}), 400

        # Ensure not already OUT
        active = conn.execute("SELECT * FROM isos_cycles WHERE pallet_no=? AND cycle_open=1", (pallet_no,)).fetchone()
        if active:
            conn.close()
            return jsonify({"ok": False, "error": "pallet already OUT, must scan IN first"}), 400

        # Status calc
        cleaned_ok = payload.get("cleaned_ok")
        dent_ok = payload.get("dent_ok")
        mesh_ok = payload.get("mesh_ok")
        remarks = payload.get("remarks")
        status = "OK" if all([cleaned_ok == "OK", dent_ok == "OK", mesh_ok == "OK"]) else "NG"

        # Insert OUT cycle
        conn.execute("""
            INSERT INTO isos_cycles (
                pallet_no, out_time, remarks,
                cleaned_ok, dent_ok, mesh_ok,
                operator_id, status, cycle_open
            ) VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, 1)
        """, (pallet_no, remarks, cleaned_ok, dent_ok, mesh_ok, operator_id, status))

        conn.execute("UPDATE pallet_list SET production_status=? WHERE pallet_no=?", (status, pallet_no))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "status": status})

    # ---------------- ISOS IN ----------------
    @app.route("/api/isos_in", methods=["POST"])
    def api_isos_in():
        payload = request.get_json()
        pallet_no = payload.get("pallet_no")
        operator_id = payload.get("operator_id")

        if not pallet_no or not operator_id:
            return jsonify({"ok": False, "error": "pallet No and Operator ID required"}), 400

        conn = get_db()
        # ✅ Validate operator_id exists
        op = conn.execute("SELECT * FROM operators WHERE operator_id=?", (operator_id,)).fetchone()
        if not op:
            conn.close()
            return jsonify({"ok": False, "error": "Invalid Operator ID"}), 403

        row = conn.execute("SELECT * FROM pallet_list WHERE pallet_no=?", (pallet_no,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"ok": False, "error": "pallet not found"}), 404

        if is_pallet_blocked(row["condition_status"]):
            conn.close()
            return jsonify({"ok": False, "error": f"pallet cannot be returned (condition_status: {row['condition_status']})"}), 400

        active = conn.execute("SELECT * FROM isos_cycles WHERE pallet_no=? AND cycle_open=1", (pallet_no,)).fetchone()
        if not active:
            conn.close()
            return jsonify({"ok": False, "error": "No active OUT cycle for this pallet"}), 400

        # Status calc
        cleaned_ok = payload.get("cleaned_ok")
        dent_ok = payload.get("dent_ok")
        mesh_ok = payload.get("mesh_ok")
        status = "OK" if all([cleaned_ok == "OK", dent_ok == "OK", mesh_ok == "OK"]) else "NG"

        # Update IN cycle
        conn.execute("""
            UPDATE isos_cycles
            SET in_time=CURRENT_TIMESTAMP,
                cleaned_ok=?, dent_ok=?, mesh_ok=?,
                operator_id=?, status=?, cycle_open=0
            WHERE id=?
        """, (cleaned_ok, dent_ok, mesh_ok, operator_id, status, active["id"]))

        conn.execute("UPDATE pallet_list SET production_status=? WHERE pallet_no=?", (status, pallet_no))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "status": status})

    # ------------- Standard CRUD / action APIs -------------
    @app.route("/api/get/<int:pallet_id>")
    def api_get(pallet_id):
        conn = get_db()
        row = conn.execute("SELECT * FROM pallet_list WHERE id=?", (pallet_id,)).fetchone()
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
            INSERT INTO pallet_list ({', '.join(ALL_FIELDS)})
            VALUES ({', '.join(['?'] * len(ALL_FIELDS))})
        """, [data.get(k) for k in ALL_FIELDS])
        new_id = cur.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "id": new_id})

    @app.route("/api/update/<int:pallet_id>", methods=["POST"])
    def api_update(pallet_id):
        payload = request.get_json(silent=True) or request.form.to_dict()
        ok, emp_id = check_credentials(payload)
        if not ok:
            return jsonify({"ok": False, "error": "Unauthorized"}), 403

        conn = get_db()
        cur = conn.cursor()
        old = cur.execute("SELECT * FROM pallet_list WHERE id=?", (pallet_id,)).fetchone()
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
                changes.append((pallet_id, f, old_val, new_val))

        if changes:
            cur.executemany("""
                INSERT INTO pallet_history (pallet_id, changed_column, old_value, new_value)
                VALUES (?,?,?,?)
            """, changes)
            set_clause = ", ".join([f"{f}=?" for f in ALL_FIELDS]) + ", updated_at=CURRENT_TIMESTAMP"
            values = [new_data.get(f) for f in ALL_FIELDS] + [pallet_id]
            cur.execute(f"UPDATE pallet_list SET {set_clause} WHERE id=?", values)

        conn.commit()
        conn.close()
        return jsonify({"ok": True, "changes": len(changes)})

    @app.route("/api/action/<int:pallet_id>", methods=["POST"])
    def api_action(pallet_id):
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
            UPDATE pallet_list
            SET condition_status=?, emp_id=?, remarks=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
        """, (action, emp, remarks, pallet_id))
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "action": action})

    @app.route("/api/delete/<int:pallet_id>", methods=["POST"])
    def api_delete(pallet_id):
        payload = request.get_json(silent=True) or request.form.to_dict()
        ok, emp_id = check_credentials(payload)
        if not ok:
            return jsonify({"ok": False, "error": "Unauthorized"}), 403
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM pallet_list WHERE id=?", (pallet_id,))
        cur.execute("DELETE FROM pallet_history WHERE pallet_id=?", (pallet_id,))
        conn.commit()
        conn.close()
        return jsonify({"ok": True})

    @app.route("/api/history/<int:pallet_id>")
    def api_history(pallet_id):
        column = request.args.get("column")
        conn = get_db()
        cur = conn.cursor()
        if column and column != "all":
            cur.execute("""
                SELECT changed_at, changed_column, old_value, new_value
                FROM pallet_history
                WHERE pallet_id = ? AND changed_column = ?
                ORDER BY changed_at DESC, id DESC
            """, (pallet_id, column))
        else:
            cur.execute("""
                SELECT changed_at, changed_column, old_value, new_value
                FROM pallet_history
                WHERE pallet_id = ?
                ORDER BY changed_at DESC, id DESC
            """, (pallet_id,))
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify(rows)

    return app

# ---- Create and run ----
app = create_app()

def open_browser():
    try:
        webbrowser.open("http://127.0.0.1:5006/")
    except Exception:
        pass

if __name__ == "__main__":
    threading.Timer(1.5, open_browser).start()
    app.run(debug=True, port=5006)

#pyinstaller --onefile --name Pallet_Master --add-data "static;static" --add-data "templates;templates" --hidden-import flask --hidden-import flask_sqlalchemy --noconsole --icon=gbicosmt.ico app.py