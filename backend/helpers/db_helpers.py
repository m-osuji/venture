from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.resolve()
DB_PATH = ROOT_DIR / 'database' / 'db.db'

def get_db_path() -> str:
    """
    Get the file path to the SQLite database.

    Returns:
        str: The absolute file path to the database as a String.
    """
    return str(DB_PATH)