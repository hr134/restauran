import sqlite3
import os

db_path = os.path.join('instance', 'restaurant.db')
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print("Tables found:", [t[0] for t in tables])
    conn.close()
else:
    print("Database not found.")
