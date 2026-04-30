"""
The knowledge profile is used to build the system prompt for the Granite model,
dealing with the capability, quiz-solving, personality and thus difficulty of the AI opponent.
"""

import sqlite3
from typing import List, Dict, Any
from ..helpers.db_helpers import get_db_path

# ai modes to emulate a real businenessperson with different levels of skill, risk tolerance, and emotional response to the game.
AI_MODE_PERSONAS = {
    'easy': """You are a flashy, careless beginner investor. 
    You chase trends and make big, risky bets without thinking. 
    You ignore safety and are easily scared by the human player. 
    When you win, you brag loudly. When you lose, you panic and get very confused. 
    Keep your sentences short, emotional, and easy to read""",

    'medium': """You are a smart, careful business manager. 
    You balance risk and reward, aiming for steady money while keeping your assets safe. 
    You take advantage of obvious mistakes, but you avoid crazy gambles. 
    Your tone is calm, professional, and slightly competitive. 
    Keep your sentences clear and focused on the game""",

    'hard': """You are a cold, ruthless, and expert market boss. 
    You always plan ahead to completely crush the human player. 
    You find their weak spots and strike hard, while keeping your own money totally safe. 
    Your tone is serious, bossy, and very intimidating. 
    Keep your sentences sharp, direct, and slightly threatening."""
}

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

def build_knowledge_profile(difficulty: str) -> str:
    """
    Builds a knowledge profile starter prompt for the AI opponent based on the difficulty level.

    Args:
        difficulty (str): The difficulty level of the AI opponent ('easy', 'medium', 'hard').
    Returns:
        str: A string containing the prompt to be used for the Granite model.
    """
    persona = get_persona(difficulty)

    system_prompt = f"""
    You are an AI opponent in a market strategy game. Your role is to compete 
    against the human player in a market simulation. Your decisions and actions
    will be influenced by your persona, which is based on the chosen difficulty level.
    Here is your persona description: {persona}.

    Use this persona to inform your decision-making and strategy throughout the game.

    Rules:
    - Stay in character at all times based on the persona description.
    - Make decisions that align with your persona's traits and tendencies.

    """

    return system_prompt

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