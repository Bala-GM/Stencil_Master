import sqlite3
import pandas as pd
from tkinter import Tk, filedialog, messagebox

def import_excel_to_pallet_db():
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
        title="Select pallet.db File",
        filetypes=[("SQLite Database", "*.db")]
    )
    if not db_path:
        messagebox.showwarning("No DB selected", "Please select a database file.")
        return

    # Read Excel
    df = pd.read_excel(excel_path)

    # Convert all string values to uppercase
    df = df.map(lambda x: str(x).upper().strip() if isinstance(x, str) else x)

    # Convert all Timestamp/datetime to string (YYYY-MM-DD)
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%d")

    # Expected columns
    expected_cols = [
        "ID", "FG", "CUSTOMER", "PALLET_NO", "PALLET_QTY", "RACK_NO", "LOCATION",
        "PALLET_SUPPLIER", "SUPPLIER_PRT_NO", "DATE_RECEIVED",
        "PALLET_VALIDATION_DT", "PALLET_REVALIDATION_DT", "RECEIVED_BY",
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

            # Ensure all data types are strings or None
            for k, v in row_data.items():
                if isinstance(v, pd.Timestamp):
                    row_data[k] = v.strftime("%Y-%m-%d")
                elif isinstance(v, float) and pd.isna(v):
                    row_data[k] = None

            if record_id is not None:
                # Check if record exists
                cur.execute("SELECT COUNT(*) FROM pallet_list WHERE id = ?", (record_id,))
                exists = cur.fetchone()[0]

                if exists:
                    cur.execute("""
                        UPDATE pallet_list SET
                            fg=?, customer=?, pallet_no=?, pallet_qty=?, rack_no=?, location=?,
                            pallet_supplier=?, supplier_prt_no=?, date_received=?, pallet_validation_dt=?,
                            pallet_revalidation_dt=?, received_by=?, condition_status=?, production_status=?,
                            emp_id=?, remarks=?, updated_at=CURRENT_TIMESTAMP
                        WHERE id=?
                    """, (
                        row_data["FG"], row_data["CUSTOMER"], row_data["PALLET_NO"], row_data["PALLET_QTY"],
                        row_data["RACK_NO"], row_data["LOCATION"], row_data["PALLET_SUPPLIER"],
                        row_data["SUPPLIER_PRT_NO"], row_data["DATE_RECEIVED"], row_data["PALLET_VALIDATION_DT"],
                        row_data["PALLET_REVALIDATION_DT"], row_data["RECEIVED_BY"],
                        row_data["CONDITION_STATUS"], row_data["PRODUCTION_STATUS"],
                        row_data["EMP_ID"], row_data["REMARKS"], record_id
                    ))
                    updated += 1
                    print(f"✅ Updated ID {record_id} (Row {i+2})")

                else:
                    # Insert new record
                    cur.execute("""
                        INSERT INTO pallet_list (
                            id, fg, customer, pallet_no, pallet_qty, rack_no, location,
                            pallet_supplier, supplier_prt_no, date_received, pallet_validation_dt,
                            pallet_revalidation_dt, received_by, condition_status, production_status,
                            emp_id, remarks
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        record_id, row_data["FG"], row_data["CUSTOMER"], row_data["PALLET_NO"],
                        row_data["PALLET_QTY"], row_data["RACK_NO"], row_data["LOCATION"],
                        row_data["PALLET_SUPPLIER"], row_data["SUPPLIER_PRT_NO"], row_data["DATE_RECEIVED"],
                        row_data["PALLET_VALIDATION_DT"], row_data["PALLET_REVALIDATION_DT"],
                        row_data["RECEIVED_BY"], row_data["CONDITION_STATUS"],
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
    import_excel_to_pallet_db()
