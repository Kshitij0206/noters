# add_columns.py

from website import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
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
