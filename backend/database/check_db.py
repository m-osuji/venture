import sqlite3
from helpers.db_helpers import get_db_path

# conn = sqlite3.connect('db.db') # Adjust path if needed
# cursor = conn.cursor()

# # get list of all tables in the database
# cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
# tables = cursor.fetchall()
# print(f"[check_db] Tables in db: {tables}")

# if tables:
#     table_name = tables[0][0] # get the first table name from the list
#     cursor.execute(f"PRAGMA table_info({table_name});")
#     columns = cursor.fetchall()
    
#     print(f"\nschema for table '{table_name}':")
#     for col in columns:
#         print(f"- column name: {col[1]} | data type: {col[2]}")

# conn.close()

DB_PATH = get_db_path()

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# specifically query the Market table
cursor.execute("PRAGMA table_info(Market);")
columns = cursor.fetchall()

print("[check_db] Schema for table 'Market':")
for col in columns:
    print(f"- column name: {col[1]:<15} | data type: {col[2]}")

conn.close()