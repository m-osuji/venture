import sqlite3

conn = sqlite3.connect("db.db")

# used to create a seed file which recreates the db for deployment
with open("seed.sql", "w", encoding="utf-8") as f:
    for line in conn.iterdump():
        f.write(line + "\n")

conn.close()
print("Done")