import sqlite3

conn = sqlite3.connect('instance/database.db')
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(user);")
columns = cursor.fetchall()

for col in columns:
    print(col)

conn.close()
