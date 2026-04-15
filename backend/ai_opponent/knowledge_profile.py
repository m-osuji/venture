# handles the capability, quiz-solving and personality of the AI opponent - all tied to the 'difficulty' of the opponent

import sqlite3
from typing import List, Dict, Any
from ..helpers.db_helpers import get_db_path


AI_MODE_PERSONAS = {
    'easy': '',
    'medium': '',
    'hard': ''
}

# EXAMPLE_MARKET_DATA = {
#     1: {
#         'market_name': 'Healthcare',
#         'size': 'Large',
#         'regulation_level': 'High',
#         'growth_potential': 'Medium',
#         'security_risk': 'Low',
#         'key_topic': 'Ethics'
#     }
# }

def get_attributes(market_id: int) -> Dict[str, Any]:
    """
    Fetches the attributes of a given market by its ID.

    Args:
        market_id (int): The unique identifier for the market.
    Returns:
        Dict[str, Any]: A dictionary containing the market name and its attributes. 
    """
    # get path to database using helper function
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)

    # set row factory to sqlite3.Row to access columns by name - returning as dictionaries instead of tuples
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.execute('SELECT * FROM Market WHERE market_id = ?', (market_id,))
        row = cursor.fetchone()

        if row is None:
            raise ValueError(f'[knowledge_profile] Market with id {market_id} does not exist.')

        # convert sqlite3.Row to a regular dictionary for easier access
        return dict(row)

    except sqlite3.Error as e:
        raise ValueError(f'[knowledge_profile] Error fetching market data for id {market_id}: {e}')
    
    finally:
        conn.close()

def get_persona(difficulty: str) -> str:
    """
    Retrieves the persona description for a given difficulty level.

    Args:
        difficulty (str): The difficulty level of the AI opponent ('easy', 'medium', 'hard'). 
    Returns:
        str: A string describing the persona of the AI opponent for the specified difficulty level.
    """
    persona = AI_MODE_PERSONAS.get(difficulty)

    if persona is None:
        # can change this to default to a medium persona but good to catch bugs for now
        raise ValueError(f'[knowledge_profile] Invalid difficulty level: {difficulty}. Choose from one of {list(AI_MODE_PERSONAS.keys())}.')
    
    return persona

if __name__ == "__main__":
    # example usage
    MARKET_ID = 1
    DIFFICULTY = 'medium'

    try:   
        attributes = get_attributes(MARKET_ID)
        print(f'[knowledge_profile] Market attributes for market id {MARKET_ID}: {attributes}' )

    except ValueError as e:
        print(f"[knowledge_profile] Error: {e}")
    
    
    persona = get_persona(DIFFICULTY)
    print(f"[knowledge_profile] Persona for difficulty '{DIFFICULTY}': {persona}")