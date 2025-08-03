from website import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:

        # =========================
        # Existing columns for 'note' table
        # =========================
        columns_to_add = [
            ("tags", "TEXT"),
            ("is_pinned", "BOOLEAN DEFAULT 0"),
            ("last_updated", "DATETIME"),
            ("is_completed", "BOOLEAN DEFAULT 0"),
            ("password_hash", "VARCHAR(128)"),
            ("is_locked", "BOOLEAN DEFAULT 0"),
            ("summary", "TEXT"),
            ("title", "TEXT")  # ✅ New column for note title
        ]

        for col_name, col_type in columns_to_add:
            try:
                conn.execute(text(f"ALTER TABLE note ADD COLUMN {col_name} {col_type}"))
                print(f"✅ Column '{col_name}' added.")
            except Exception as e:
                print(f"⚠️ Could not add '{col_name}':", e)

        # =========================
        # Fix for OTP table
        # =========================
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS otp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email VARCHAR(150) NOT NULL,
                    otp VARCHAR(6) NOT NULL,
                    purpose VARCHAR(20) NOT NULL, -- 'signup' or 'reset'
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("✅ Table 'otp' created or already exists.")
        except Exception as e:
            print("⚠️ Could not create 'otp' table:", e)

        try:
            result = conn.execute(text("PRAGMA table_info(otp)")).fetchall()
            columns = [row[1] for row in result]
            if "purpose" not in columns:
                conn.execute(text("ALTER TABLE otp ADD COLUMN purpose VARCHAR(20) DEFAULT 'signup'"))
                print("✅ Column 'purpose' added to 'otp'.")
            else:
                print("ℹ️ Column 'purpose' already exists in 'otp'.")
        except Exception as e:
            print("⚠️ Could not check/add 'purpose' column:", e)
