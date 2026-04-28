"""
Game state definition and transformation layer.

Acts as the single source of truth for structuring, initialising, and mutating the global game state.
Provides core utilities for three specific transformations:
1. Initialization: Building the global state from static database data.
2. Agent Context: Deriving player-specific state dictionaries for AI agents.
3. Frontend Slicing: Generating safe, minimal state views for the client API.
"""

import os
import sqlite3
import json

from uuid import uuid4
from typing import Any
from pathlib import Path

from backend.helpers.db_helpers import get_db_path
from backend.helpers.db_helpers import fetch_all_markets

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# -----------------------------------------
# central game constants and configurations
# -----------------------------------------

DEFAULT_RULES: dict[str, Any] = {
    "attack_cost": 1,
    "defend_cost": 1,
    "research_cost": 2,
    "high_regulation_research_surcharge": 1,
    "high_regulation_threshold": 3.0,
    "maintenance_threshold": 6,
    "maintenance_penalty_per_market": 1,
    "allow_attack_allies": False,
    "forbid_attack_allies": True,
    "max_orders_per_round": 3,
    "primary_action_margin": 0.0,
    "follow_up_action_margin": 1.0,
}

GAME_MODES: dict[str, int] = {"speedrun": 20, "full": 60}

ROOT_DIR = Path(__file__).parent.parent.resolve()
DEFAULT_PATH = ROOT_DIR / "game_state.json"
GAME_STATE_PATH = os.getenv("GAME_STATE_PATH", str(DEFAULT_PATH))

# --------------
# initialisation
# --------------


def init_game_state(
    teams: list[dict[str, Any]], game_mode: str = "speedrun", include_ai: bool = False
) -> dict[str, Any]:
    """
    Build the global in-memory game state from static database data; called once at
    the start of the game.

    Args:
        teams (list[dict]): List of team dictionaries, each with 'id', 'name', 'colour' and 'is_ai' keys.
        game_mode (str): Determine whether the game will be a speedrun (20 min) or full experience (60 min).
        include_ai (bool): Determine whether an AI Opponent is present in this session.

    Returns:
        dict: The initialised global game state dictionary.
    """

    markets = fetch_all_markets()

    # define the list of team-specific state entries (individual dictionaries)
    team_entries = [
        {
            "team_id": t["id"],
            "team_name": t["name"],
            "colour": t["colour"],
            "ip": 0,
            "ethical_score": 1.0,
            "ip_spent_this_turn": 0,
            "is_ai": t.get("is_ai", False),
        }
        for t in teams
    ]

    market_state = {
        str(m["market_id"]): {
            # dynamic fields (updated by engine each round)
            "owner": None,
            "contested": False,
            "supporting_teams": [],
            "allocated_ip": 0,
            "growth_applied": False,
            "research_upgrades": [],
            # derived fields (updated by engine each round)
            "threat": 0.0,
            "enemy_strength_estimate": 0.0,
            # upgrade level tracking
            "production_upgrade_level": 0,
            "regulation_reduction_level": 0,
            "security_upgrade_level": 0,
            "fortification_level": 0,
            "research_level": 0,
            # static reference data from DB (never mutated by engine)
            "_market_id": m["market_id"],
            "_market_name": m["market_name"],
            "_size": m["size"],
            "_regulation_level": m["regulation_level"],
            "_growth_potential": m["growth_potential"],
            "_security_risk": m["security_risk"],
            "_key_topic": m["key_topic"],
        }
        for m in markets
    }

    game_state = {
        "session_uuid": str(uuid4()),
        "status": "IN_PROGRESS",
        "game_mode": game_mode,
        "include_ai": include_ai,
        "current_round": 1,
        "current_stage": "PLAN",
        "current_team_turn": None,
        "team_order": [],
        "rules": DEFAULT_RULES,
        "quickfire_results": [],
        "teams": team_entries,
        "alliances": [],
        "active_synergies": [],
        "market_state": market_state,
        "turn_log": _empty_turn_log(),
    }

    return game_state


def _empty_turn_log() -> dict[str, Any]:
    """
    Helper function to create an fresh turn log structure for each round.

    Returns:
        dict: An empty turn log dictionary with predefined keys.
    """
    return {
        "decisions_confirmed": False,
        "plan_notes": {},
        "declared_moves": {},
        "actual_moves": {},
        "conflicts": [],
        "negotiation_log": [],
    }


# -------------------------------------------------------------
# agent context derivation -
# player-specific dict for decision maker and negotiator agents
# -------------------------------------------------------------


def build_agent_context(game_state: dict[str, Any], team_id: int) -> dict[str, Any]:
    """
    Derive a player-specific context dictionary from the global game state, for AI agents.

    Args:
        game_state (dict): The full, global game state dictionary.
        team_id (int): The ID of the team for which to build the context.

    Returns:
        dict: A filtered dictionary containing only the information relevant to the specified team.
    """

    market_state = game_state.get("market_state", {})
    alliances = game_state.get("alliances", [])
    teams = game_state.get("teams", [])
    rules = game_state.get("rules", DEFAULT_RULES)

    target_team = next((t for t in teams if t["team_id"] == team_id), {})
    current_ip = target_team.get("ip", 0)
    ethical_score = target_team.get("ethical_score", 1.0)


    # TODO: write method!!
    active_alliances = {} # _get_active_alliances_ids(team_id, alliances)

    # derive lists of market ids by ownership status relative to the team
    owned_markets: list[int] = []
    allied_markets: list[int] = []
    enemy_markets: list[int] = []
    neutral_markets: list[int] = []

    for market_id, state in market_state.items():
        owner = state.get("owner")

        if owner == team_id:
            # markets owned by the team itself
            owned_markets.append(market_id)
        elif owner in active_alliances:
            # markets owned by allied teams
            allied_markets.append(market_id)
        elif owner is not None:
            # markets owned by non-allied teams
            enemy_markets.append(market_id)
        else:
            # unowned markets
            neutral_markets.append(market_id)

    # derive the list of markets with active commitments to avoid attack actions
    # i.e. due to alliances or recent negotiations)
    
    # TODO: write method!!
    commitments = {} # _build_commitments(team_id, alliances, market_state)

    avoid_set = set(commitments.get("avoid_attack_markets", []))

    # derive the list of markets that are valid targets for attack actions
    # # i.e. owned by enemies or neutral, excluding any with active commitments to avoid
    attackable_markets = [
        market for market in enemy_markets + neutral_markets if market not in avoid_set
    ]

    # market_states = _extract_market_states(
    #     market_state, owned_markets, enemy_markets, neutral_markets
    # )
    

    # relationship_states = _build_relationship_states(
    #     team_id,
    #     alliances,
    #     market_state,
    #     active_alliances,
    #     game_state.get("current_round", 1),
    # )


    return {
        "current_ip": current_ip,
        "ethical_score": ethical_score,
        "owned_markets": owned_markets,
        "enemy_markets": enemy_markets,
        "neutral_markets": neutral_markets,
        "allied_markets": allied_markets,
        "attackable_markets": attackable_markets,
        # "market_states": market_states,
        # "relationship_states": relationship_states,
        "commitments": commitments,
        "rules": rules,
    }


# 
# TODO: consider moving to db helpers 
# 

def _get_active_alliances(team_id: int, alliances: list[dict[str, Any]]) -> set[int]:
    ally_ids: set[int] = set()
    for alliance in alliances:
        if alliance.get('broken_turn') is not None:
            continue
        members = alliance.get('members') or []
        if team_id in members:
            for member in members:
                if member != team_id:
                    ally_ids.add(member)
    return ally_ids


# -----------------------------------------------------------------
# saving and loading the game state to & from persistent DB storage
# -----------------------------------------------------------------


def save_state(state: dict[str, Any]) -> None:
    """
    Saves the current game state to a JSON file for persistence.

    Args:
        state (dict): The global game state dictionary to be saved.
    """
    with open(GAME_STATE_PATH, "w") as f:
        json.dump(state, f, indent=4)


def load_state() -> dict[str, Any] | None:
    """
    Loads the game state from a JSON file if it exists.

    Returns:
        dict: The loaded game state dictionary, or None if no saved state exists.
    """
    if Path(GAME_STATE_PATH).exists():
        with open(GAME_STATE_PATH, "r") as f:
            return json.load(f)
    return None
