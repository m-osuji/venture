# handles the capability, quiz-solving and personality of the AI opponent - all tied to the 'difficulty' of the opponent

from typing import List, Dict, Any


AI_MODE_PERSONAS = {
    'easy': '',
    'medium': '',
    'hard': ''
}

EXAMPLE_MARKET_DATA = {
    1: {
        'market_name': 'Healthcare',
        'size': 'Large',
        'regulation_level': 'High',
        'growth_potential': 'Medium',
        'security_risk': 'Low',
        'key_topic': 'Ethics'
    }
}


def get_attributes(market_id: int) -> Dict[str, Any]:
    """
    Fetches the attributes of a given market by its ID.

    Args:
        market_id (int): The unique identifier for the market.
    Returns:
        Dict[str, Any]: A dictionary containing the market name and its attributes. 
    """
    # TODO use an sqlite3 SELECT query to fetch market in dictionary structure 
  
    market = EXAMPLE_MARKET_DATA.get(market_id)

    if not market:
        raise ValueError(f'[decision_maker] Market with ID {market_id} does not exist.')
    
    return market


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
        raise ValueError(f'[decision_maker] Invalid difficulty level: {difficulty}. Choose from one of {list(AI_MODE_PERSONAS.keys())}.')
    
    return persona