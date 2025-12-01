import sqlite3
import pandas as pd
from tkinter import Tk, filedialog, messagebox

def import_excel_to_stencil_db():
    # Choose Excel file
    Tk().withdraw()
    excel_path = filedialog.askopenfilename(
        title="Select Excel File",
        filetypes=[("Excel Files", "*.xlsx *.xls")]
    )
    if not excel_path:
        messagebox.showwarning("No file selected", "Please select an Excel file.")
        return

    # Choose database
    db_path = filedialog.askopenfilename(
        title="Select stencil.db File",
        filetypes=[("SQLite Database", "*.db")]
    )
    if not db_path:
        messagebox.showwarning("No DB selected", "Please select a database file.")
        return

    # Read Excel
    df = pd.read_excel(excel_path)

    # Convert all string values to uppercase and strip spaces
    df = df.map(lambda x: str(x).upper().strip() if isinstance(x, str) else x)

    # Convert all Timestamp/datetime to string (YYYY-MM-DD)
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")

    # Expected columns (must match stencil_list schema)
    expected_cols = [
        "ID", "FG", "SIDE", "CUSTOMER", "STENCIL_NO", "RACK_NO", "LOCATION",
        "STENCIL_MILS", "STENCIL_MILS_USL", "STENCIL_MILS_LSL", "STENCIL_SUPPLIER",
        "STENCIL_PR_NO", "DATE_RECEIVED", "STENCIL_VALIDATION_DT", "STENCIL_REVALIDATION_DT",
        "TENSION_A", "TENSION_B", "TENSION_C", "TENSION_D", "TENSION_E", "RECEIVED_BY",
        "CONDITION_STATUS", "PRODUCTION_STATUS", "EMP_ID", "REMARKS"
    ]
    missing_cols = [c for c in expected_cols if c not in df.columns]
    if missing_cols:
        messagebox.showerror("Column mismatch", f"Missing columns: {', '.join(missing_cols)}")
        return

    # Connect DB
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    updated, inserted, skipped = 0, 0, 0

    for i, row in df.iterrows():
        try:
            row_data = {k: row[k] for k in expected_cols}
            record_id = int(row_data["ID"]) if not pd.isna(row_data["ID"]) else None

            # Ensure safe data conversion
            for k, v in row_data.items():
                if isinstance(v, pd.Timestamp):
                    row_data[k] = v.strftime("%Y-%m-%d")
                elif isinstance(v, float) and pd.isna(v):
                    row_data[k] = None

            if record_id is not None:
                # Check if record exists
                cur.execute("SELECT COUNT(*) FROM stencil_list WHERE id = ?", (record_id,))
                exists = cur.fetchone()[0]

                if exists:
                    # Update existing record
                    cur.execute("""
                        UPDATE stencil_list SET
                            fg=?, side=?, customer=?, stencil_no=?, rack_no=?, location=?,
                            stencil_mils=?, stencil_mils_usl=?, stencil_mils_lsl=?, stencil_supplier=?,
                            stencil_pr_no=?, date_received=?, stencil_validation_dt=?, stencil_revalidation_dt=?,
                            tension_a=?, tension_b=?, tension_c=?, tension_d=?, tension_e=?, received_by=?,
                            condition_status=?, production_status=?, emp_id=?, remarks=?, updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                    """, (
                        row_data["FG"], row_data["SIDE"], row_data["CUSTOMER"], row_data["STENCIL_NO"],
                        row_data["RACK_NO"], row_data["LOCATION"], row_data["STENCIL_MILS"],
                        row_data["STENCIL_MILS_USL"], row_data["STENCIL_MILS_LSL"], row_data["STENCIL_SUPPLIER"],
                        row_data["STENCIL_PR_NO"], row_data["DATE_RECEIVED"], row_data["STENCIL_VALIDATION_DT"],
                        row_data["STENCIL_REVALIDATION_DT"], row_data["TENSION_A"], row_data["TENSION_B"],
                        row_data["TENSION_C"], row_data["TENSION_D"], row_data["TENSION_E"], row_data["RECEIVED_BY"],
                        row_data["CONDITION_STATUS"], row_data["PRODUCTION_STATUS"],
                        row_data["EMP_ID"], row_data["REMARKS"], record_id
                    ))
                    updated += 1
                    print(f"✅ Updated ID {record_id} (Row {i+2})")

                else:
                    # Insert new record
                    cur.execute("""
                        INSERT INTO stencil_list (
                            id, fg, side, customer, stencil_no, rack_no, location,
                            stencil_mils, stencil_mils_usl, stencil_mils_lsl, stencil_supplier,
                            stencil_pr_no, date_received, stencil_validation_dt, stencil_revalidation_dt,
                            tension_a, tension_b, tension_c, tension_d, tension_e, received_by,
                            condition_status, production_status, emp_id, remarks
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record_id, row_data["FG"], row_data["SIDE"], row_data["CUSTOMER"], row_data["STENCIL_NO"],
                        row_data["RACK_NO"], row_data["LOCATION"], row_data["STENCIL_MILS"], row_data["STENCIL_MILS_USL"],
                        row_data["STENCIL_MILS_LSL"], row_data["STENCIL_SUPPLIER"], row_data["STENCIL_PR_NO"],
                        row_data["DATE_RECEIVED"], row_data["STENCIL_VALIDATION_DT"], row_data["STENCIL_REVALIDATION_DT"],
                        row_data["TENSION_A"], row_data["TENSION_B"], row_data["TENSION_C"], row_data["TENSION_D"],
                        row_data["TENSION_E"], row_data["RECEIVED_BY"], row_data["CONDITION_STATUS"],
                        row_data["PRODUCTION_STATUS"], row_data["EMP_ID"], row_data["REMARKS"]
                    ))
                    inserted += 1
                    print(f"🆕 Inserted ID {record_id} (Row {i+2})")
            else:
                skipped += 1
                print(f"⚠️ Skipped Row {i+2}: No valid ID")

        except Exception as e:
            print(f"❌ Error on Row {i+2}: {e}")
            skipped += 1

    conn.commit()
    conn.close()

    summary = f"✅ Updated: {updated}\n🆕 Inserted: {inserted}\n⚠️ Skipped: {skipped}"
    messagebox.showinfo("Import Complete", summary)
    print("\n" + summary)

if __name__ == "__main__":
    import_excel_to_stencil_db()
