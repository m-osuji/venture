"""
Helper functions for database interactions.
"""
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
    Executes a SQL query and returns all results as a list of sqlite3.Row objects.

    Args:
        query (str): The SQL query to execute.
        params (tuple): Optional parameters to pass.

    Returns:
        list[sqlite3.Row]: List of rows returned by the query.
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        return conn.execute(query, params).fetchall()
    finally:
        conn.close()

def fetch_one(query: str, params: tuple = ()) -> sqlite3.Row | None:
    """
    Executes a SQL query and returns a single result as a sqlite3.Row object.
    
    Args:  
        query (str): The SQL query to execute.
        params (tuple): Optional parameters to pass,
    Returns:
        sqlite3.Row | None: Single row returned by the query, or None if no results. 
    """
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        return conn.execute(query, params).fetchone()
    finally:
        conn.close()

def fetch_all_markets() -> list[dict]:
    """
    Fetches all market records from the database and returns them as a list of dictionaries.
    
    Returns:
        list[dict]: A list of dictionaries, each representing a market record
    """
    rows = fetch_all('SELECT * FROM Market')
    return [dict(row) for row in rows]

def fetch_market_by_id(market_id: int) -> dict | None:
    """
    Fetches a single market record by its ID and returns it as a dictionary.

    Args:
        market_id (int): The unique identifier for the market.     
    Returns:
        dict | None: A dictionary representing the market record, or None if not found.
    """
    row = fetch_one('SELECT * FROM Market WHERE market_id = ?', (market_id,))
    return dict(row) if row else None

def fetch_questions(topic=None, difficulty=None):
    """
    Fetch questions from the Question table.
    Optionally filter by topic and/or difficulty_level.
    Returns a list of dicts matching the quiz_helpers data contract.
    """
    query = "SELECT * FROM Question WHERE 1=1"
    params = []

    if topic is not None:
        query += " AND topic = ?"
        params.append(topic)
    if difficulty is not None:
        query += " AND difficulty_level = ?"
        params.append(difficulty)

    return fetch_all(query, params)