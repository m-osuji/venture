from pathlib import Path
import sqlite3

ROOT_DIR = Path(__file__).parent.parent.resolve()
DB_PATH = ROOT_DIR / 'database' / 'db.db'

def get_db_path() -> str:
    """
    Get the file path to the SQLite database.

    Returns:
        str: The absolute file path to the database as a String.
    """
    return str(DB_PATH)


def fetch_all(query: str, params: tuple = ()) -> list[sqlite3.Row]:
    """
    Execute a SQL query and return all rows as sqlite3.Row objects.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()


def fetch_all_markets() -> list[dict]:
    """
    Fetch every market record from the database as dictionaries.
    """
    rows = fetch_all("SELECT * FROM Market")
    return [dict(row) for row in rows]
