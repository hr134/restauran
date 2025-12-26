import sqlite3
import os

db_path = os.path.join('instance', 'restaurant.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(user)")
columns = [column[1] for column in cursor.fetchall()]
print("Columns in 'user' table:", columns)
conn.close()
