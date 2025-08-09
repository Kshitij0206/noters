    try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS note_order (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (note_id) REFERENCES note(id),
                    FOREIGN KEY (user_id) REFERENCES user(id)
                )
            """))
            print("✅ Table 'note_order' created or already exists.")
        except Exception as e:
            print("⚠️ Could not create 'note_order' table:", e)
