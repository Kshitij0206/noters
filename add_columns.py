from website import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        # Existing columns
        try:
            conn.execute(text("ALTER TABLE note ADD COLUMN tags TEXT"))
            print("✅ Column 'tags' added.")
        except Exception as e:
            print("⚠️ Could not add 'tags':", e)

        try:
            conn.execute(text("ALTER TABLE note ADD COLUMN is_pinned BOOLEAN DEFAULT 0"))
            print("✅ Column 'is_pinned' added.")
        except Exception as e:
            print("⚠️ Could not add 'is_pinned':", e)

        try:
            conn.execute(text("ALTER TABLE note ADD COLUMN last_updated DATETIME"))
            print("✅ Column 'last_updated' added.")
        except Exception as e:
            print("⚠️ Could not add 'last_updated':", e)

        try:
            conn.execute(text("ALTER TABLE note ADD COLUMN is_completed BOOLEAN DEFAULT 0"))
            print("✅ Column 'is_completed' added.")
        except Exception as e:
            print("⚠️ Could not add 'is_completed':", e)
        
        # New columns for password lock feature
        try:
            conn.execute(text("ALTER TABLE note ADD COLUMN password_hash VARCHAR(128)"))
            print("✅ Column 'password_hash' added.")
        except Exception as e:
            print("⚠️ Could not add 'password_hash':", e)

        try:
            conn.execute(text("ALTER TABLE note ADD COLUMN is_locked BOOLEAN DEFAULT 0"))
            print("✅ Column 'is_locked' added.")
        except Exception as e:
            print("⚠️ Could not add 'is_locked':", e)
        
        # ➕ New column for summary feature
        try:
            conn.execute(text("ALTER TABLE note ADD COLUMN summary TEXT"))
            print("✅ Column 'summary' added.")
        except Exception as e:
            print("⚠️ Could not add 'summary':", e)
