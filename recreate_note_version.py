# fix_versions.py

from website import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    with db.engine.connect() as conn:
        try:
            print("🧹 Deleting orphaned note_version rows...")
            conn.execute(text("DELETE FROM note_version WHERE note_id IS NULL"))
            print("✅ Orphaned rows deleted.")
        except Exception as e:
            print("⚠️ Error while deleting orphans:", e)

        try:
            print("🧱 Recreating note_version table with CASCADE...")
            conn.execute(text("DROP TABLE IF EXISTS note_version"))

            conn.execute(text("""
                CREATE TABLE note_version (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER NOT NULL,
                    version_data TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(note_id) REFERENCES note(id) ON DELETE CASCADE
                )
            """))
            print("✅ Table 'note_version' recreated with proper foreign key.")
        except Exception as e:
            print("❌ Failed to recreate table:", e)
