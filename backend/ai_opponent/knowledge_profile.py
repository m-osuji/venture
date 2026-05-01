"""
The knowledge profile is used to build the system prompt for the Granite model,
dealing with the capability, quiz-solving, personality and thus difficulty of the AI opponent.
"""

from typing import Any
from ..enums import AIDifficulty, AgentType, GameStage

# ai modes to emulate a real business-person with different levels of skill, risk tolerance, and emotional response.
AI_MODE_PERSONAS = {
    AIDifficulty.EASY: """You are a flashy, careless beginner investor. 
    You chase trends and make big, risky bets without thinking. 
    You ignore safety and are easily scared by the human player. 
    When you win, you brag loudly. When you lose, you panic and get very confused. 
    Keep your sentences short, emotional, and easy to read""",
    AIDifficulty.MEDIUM: """You are a smart, careful business manager. 
    You balance risk and reward, aiming for steady money while keeping your assets safe. 
    You take advantage of obvious mistakes, but you avoid crazy gambles. 
    Your tone is calm, professional, and slightly competitive. 
    Keep your sentences clear and focused on the game""",
    AIDifficulty.HARD: """You are a cold, ruthless, and expert market boss. 
    You always plan ahead to completely crush the human player. 
    You find their weak spots and strike hard, while keeping your own money totally safe. 
    Your tone is serious, bossy, and very intimidating. 
    Keep your sentences sharp, direct, and slightly threatening.""",
}

# AI win rates (base probability of correct answer) based on specific market topics
AI_TOPIC_EXPERTISE = {
    AIDifficulty.EASY: {
        "AI": 0.80,
        "Data Science": 0.60,
        "Cybersecurity": 0.40,
        "Law": 0.20,
        "Education": 0.30,
        "Ethics": 0.10,
        "speed_ms": 8000,
    },
    AIDifficulty.MEDIUM: {
        "AI": 0.60,
        "Data Science": 0.60,
        "Cybersecurity": 0.70,
        "Law": 0.75,
        "Education": 0.80,
        "Ethics": 0.70,
        "speed_ms": 5000,
    },
    AIDifficulty.HARD: {
        "AI": 0.90,
        "Data Science": 0.95,
        "Cybersecurity": 0.95,
        "Law": 0.85,
        "Education": 0.60,
        "Ethics": 0.30,
        "speed_ms": 2500,
    },
}


# def get_attributes(market_id: int) -> Dict[str, Any]:
#     """
#     Fetches the attributes of a given market by its ID.

#     Args:
#         market_id (int): The unique identifier for the market.
#     Returns:
#         Dict[str, Any]: A dictionary containing the market name and its attributes.
#     """
#     # get path to database using helper function
#     db_path = get_db_path()
#     conn = sqlite3.connect(db_path)

#     # set row factory to sqlite3.Row to access columns by name - returning as dictionaries instead of tuples
#     conn.row_factory = sqlite3.Row

#     try:
#         cursor = conn.execute("SELECT * FROM Market WHERE market_id = ?", (market_id,))
#         row = cursor.fetchone()

#         if row is None:
#             raise ValueError(
#                 f"[knowledge_profile] Market with id {market_id} does not exist."
#             )

#         # convert sqlite3.Row to a regular dictionary for easier access
#         return dict(row)

#     except sqlite3.Error as e:
#         raise ValueError(
#             f"[knowledge_profile] Error fetching market data for id {market_id}: {e}"
#         )

#     finally:
#         conn.close()


def get_persona(difficulty: AIDifficulty) -> str:
    """
    Retrieves the persona description for a given difficulty level.

    Args:
        difficulty (AIDifficulty): The difficulty level of the AI opponent ('easy', 'medium', 'hard').
    Returns:
        str: A string describing the persona of the AI opponent for the specified difficulty level.
    """
    persona = AI_MODE_PERSONAS.get(difficulty)

    if persona is None:
        # can change this to default to a medium persona but good to catch bugs for now
        raise ValueError(
            f"[knowledge_profile] Invalid difficulty level: {difficulty}. Choose from one of {list(AI_MODE_PERSONAS.keys())}."
        )

    return persona


def get_quiz_stats(difficulty: AIDifficulty, market_topic: str) -> dict[str, Any]:
    """
    Retrieves the AI's specific expertise and speed for a contested market topic.

    Args:
        difficulty (AIDifficulty): The difficulty level of the AI opponent.
        market_topic (str): The selected topic.
    Returns:
        dict: Dictionary containing the AI's simulated quiz performance metrics
            - 'win_probability' (float): The base probability (0.0 to 1.0) of answering correctly.
            - 'speed_ms' (int): The simulated time taken to answer, in milliseconds.
    """
    profile = AI_TOPIC_EXPERTISE.get(difficulty)
    if profile is None:
        raise ValueError(
            f"[knowledge_profile] Invalid difficulty for quiz stats: {difficulty}."
        )

    # get specific win probability for this topic (fallback to 50% if topic is unknown)
    win_prob = profile.get(market_topic, 0.50)

    return {"win_probability": win_prob, "speed_ms": profile["speed_ms"]}

def build_system_prompt(
    agent_type: AgentType,
    difficulty: AIDifficulty,
    agent_context: dict[str, Any],
    current_stage: GameStage,
    event_context: str = ""
) -> str:
    """
    Builds a targeted system prompt based on which agent is being used and the current game stage.

    Args:
        agent_type (AgentType): Decision Maker, Commentator, or Negotiator.
        difficulty (AIDifficulty): Easy, Medium, or Hard.
        agent_context (dict[str, Any]): The live game state sliced for this specific player.
        current_stage (GameStage): The exact current phase of the game.
        event_context (str, optional): Recent game events or negotiation notes.

    Returns:
        str: The fully formatted system prompt for Granite/Mellea.
    """
    persona = get_persona(difficulty)
    funds = agent_context.get("ip", 0)
    markets = [m.get("name", "Unknown") for m in agent_context.get("owned_markets", [])]

    EXAMPLE_JSON = """
    EXPECTED JSON FORMAT:
    {
    "orders": [
        {"action": "attack", "market": "ExampleMarket", "ip": 10}
      ]
    }
    """

    prompt_lines = [
        persona,
        "\n--- CURRENT GAME STATE ---",
        f"You currently have {funds} Influence Points (IP) to spend.",
        f"You control the following markets: {', '.join(markets) if markets else 'None'}.",
        "--------------------------\n",
    ]

    if agent_type == AgentType.DECISION_MAKER:
        # pass 1: drafting notes for the Plan stage
        if current_stage == GameStage.PLAN:
            prompt_lines.append(
                f"TASK: You are currently in the {current_stage.name} stage.\n"
                "Analyse the board and formulate your INITIAL INTENDED moves (Attack, Defend, or Research).\n"
                "These moves are not yet binding, but will form your strategy going into negotiations.\n"
                f"{EXAMPLE_JSON}"
                "CRITICAL: You must output your decision strictly as a JSON object so the game engine can parse it. "
                "Do not include conversational text."
            )
        # pass 2: locking in decisions for the Orders stage (checking for betrayal)
        else:
            prompt_lines.append(
                f"TASK: You are locking in your final moves for the ORDERS stage.\n"
                f"NEGOTIATION NOTES / RECENT AGREEMENTS: {event_context}\n"
                "Based on the board state and the negotiations that just occurred, decide your final, binding moves.\n"
                "Consider your persona: will you honor your agreements to maintain your Ethical Score, or betray them for strategic gain?\n"
                f"{EXAMPLE_JSON}"
                "CRITICAL: You must output your decision strictly as a JSON object so the game engine can parse it. "
                "Do not include conversational text."
            )

    elif agent_type == AgentType.NEGOTIATOR:
        prompt_lines.append(
            f"TASK: You are currently in the {current_stage.name} stage.\n"
            f"BOARD CONTEXT / RECENT EVENTS: {event_context}\n"
            "Your goal is to propose an alliance, make a threat, or negotiate a trade with the human players.\n"
            "Consider your persona's risk tolerance, your current market ownership, and your intended moves.\n"
            "Keep your message concise, conversational, and directly address the other teams."
        )

    elif agent_type == AgentType.COMMENTATOR:
        prompt_lines.append(
            f"TASK: You are observing the game during the {current_stage.name} stage.\n"
            f"RECENT EVENT: {event_context}\n"
            "Provide a short, in-character taunt, remark, or reaction to this event. "
            "Keep it under 100 words and reference the specific market, stage, or teams involved."
        )

    else:
        # error checking in case of mistype
        raise ValueError(f"[knowledge_profile] Unknown agent_type: {agent_type}.")

    return "\n".join(prompt_lines)


def build_knowledge_profile(difficulty: AIDifficulty) -> str:
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
    print("[knowledge_profile] Testing quiz stats...")

    stats = get_quiz_stats(AIDifficulty.HARD, "Cybersecurity")
    print(f"> Hard AI on Cybersecurity: {stats}")

    # test prompt factory (decision maker in PLAN stage)
    print("\n[knowledge_profile] Testing decison maker (plan stage)...")
    mock_context = {
        "ip": 25,
        "owned_markets": [{"name": "AI"}, {"name": "Data Science"}]
    }
    
    plan_prompt = build_system_prompt(
        agent_type=AgentType.DECISION_MAKER,
        difficulty=AIDifficulty.MEDIUM,
        agent_context=mock_context,
        current_stage=GameStage.PLAN
    )
    print(plan_prompt)

    # test prompt factory (decision maker in Orders stage with betrayal context)
    print("\n[knowledge_profile] Testing decison maker (orders stage)...")
    orders_prompt = build_system_prompt(
        agent_type=AgentType.DECISION_MAKER,
        difficulty=AIDifficulty.HARD,
        agent_context=mock_context,
        current_stage=GameStage.ORDERS,
        event_context="You promised Team Blue that you would not attack the AI market."
    )
    print(orders_prompt)