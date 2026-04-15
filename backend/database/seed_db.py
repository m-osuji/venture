import sqlite3
from helpers.db_helpers import get_db_path

def seed_db_markets():
    print("[seed_db] Seeding the database with market data..")
    
    db_path = get_db_path()
    print(f"[seed_db] Connecting to database at: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # delete existing data to avoid duplicates when re-seeding
    cursor.execute("DELETE FROM Market;")

    markets = [
        (1, 'Healthcare', 'Large', 'High', 'Medium', 'Low', 'Ethics'),
    ]

    # insert sample market data
    cursor.executemany("""
        INSERT INTO Market (market_id, market_name, size, regulation_level, growth_potential, security_risk, key_topic)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, markets)

    # commit changes and close the connection
    conn.commit()
    conn.close()
    print("[seed_db] Database seeding complete! querying is now possible")

if __name__ == "__main__":
    seed_db_markets()