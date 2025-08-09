from website import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        
        # --- Check existing columns for 'note' ---
        result = conn.execute(text("PRAGMA table_info(note)")).fetchall()
        note_cols = [row[1] for row in result]

        columns_to_add = [
            ("tags", "TEXT"),
            ("is_pinned", "BOOLEAN DEFAULT 0"),
            ("last_updated", "DATETIME"),
            ("is_completed", "BOOLEAN DEFAULT 0"),
            ("password_hash", "VARCHAR(128)"),
            ("is_locked", "BOOLEAN DEFAULT 0"),
            ("summary", "TEXT"),
            ("title", "TEXT"),
            ("bg_color", "VARCHAR(50) DEFAULT 'default'")
        ]

        for col_name, col_type in columns_to_add:
            if col_name not in note_cols:
                try:
                    conn.execute(text(f"ALTER TABLE note ADD COLUMN {col_name} {col_type}"))
                    print(f"✅ Column '{col_name}' added to 'note'.")
                except Exception as e:
                    print(f"⚠️ Could not add '{col_name}' to 'note':", e)
            else:
                print(f"ℹ️ Column '{col_name}' already exists in 'note'.")

        # --- Create 'otp' table and check purpose column ---
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS otp (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email VARCHAR(150) NOT NULL,
                    otp VARCHAR(6) NOT NULL,
                    purpose VARCHAR(20) NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("✅ Table 'otp' created or already exists.")
        except Exception as e:
            print("⚠️ Could not create 'otp' table:", e)

        try:
            result = conn.execute(text("PRAGMA table_info(otp)")).fetchall()
            otp_cols = [row[1] for row in result]
            if "purpose" not in otp_cols:
                conn.execute(text("ALTER TABLE otp ADD COLUMN purpose VARCHAR(20) DEFAULT 'signup'"))
                print("✅ Column 'purpose' added to 'otp'.")
            else:
                print("ℹ️ Column 'purpose' already exists in 'otp'.")
        except Exception as e:
            print("⚠️ Could not check/add 'purpose' column:", e)

        # --- Check existing columns for 'user' ---
        result = conn.execute(text("PRAGMA table_info(user)")).fetchall()
        user_cols = [row[1] for row in result]

        if "created_at" not in user_cols:
            try:
                conn.execute(text("ALTER TABLE user ADD COLUMN created_at DATETIME"))
                print("✅ Column 'created_at' added to 'user'.")
            except Exception as e:
                print("⚠️ Could not add 'created_at' to 'user':", e)
        else:
            print("ℹ️ Column 'created_at' already exists in 'user'.")

        try:
            conn.execute(text("UPDATE user SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
            print("✅ Existing users' created_at set to current timestamp.")
        except Exception as e:
            print("⚠️ Could not update 'created_at' values:", e)

        # Check if username exists
        if "username" not in user_cols:
            try:
                conn.execute(text("ALTER TABLE user ADD COLUMN username VARCHAR(150)"))
                print("✅ Column 'username' added to 'user' (without UNIQUE constraint).")
            except Exception as e:
                print("⚠️ Could not add 'username' to 'user':", e)
        else:
            print("ℹ️ Column 'username' already exists in 'user'.")

            try:
                conn.execute(text("""
                    UPDATE user SET username = SUBSTR(email, 1, INSTR(email, '@') - 1) WHERE username IS NULL
                """))
                print("✅ Existing users' usernames populated from email.")
            except Exception as e:
                print("⚠️ Could not update 'username' values:", e)
        if "profile_pic_url" not in user_cols:
            try:
                conn.execute(text("ALTER TABLE user ADD COLUMN profile_pic_url VARCHAR(255);"))
                print("✅ Column 'profile_pic_url' added to 'user'.")
            except Exception as e:
                print("⚠️ Could not add 'profile_pic_url' to 'user':", e)
        else:
            print("ℹ️ Column 'profile_pic_url' already exists in 'user'.")

