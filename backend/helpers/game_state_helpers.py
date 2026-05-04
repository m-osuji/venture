"""
Helper functions to manage global game state (including initialisation,
mutation,and extraction of relevant slices for agents and frontend).
"""

import os
import json

from uuid import uuid4
from typing import Any
from pathlib import Path

from enums import GameStage, SessionStatus

from helpers.db_helpers import get_db_path
from helpers.db_helpers import fetch_all_markets

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
            # static reference data from DB (never mutated by engine, as shown by underscore)
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
        "status": SessionStatus.IN_PROGRESS,
        "game_mode": game_mode,
        "include_ai": include_ai,
        "current_round": 1,
        "current_stage": GameStage.PLAN,
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


# -----------------------
# market state extraction
# -----------------------


def _cast_market_keys(market_state: dict[str, Any]) -> dict[int, Any]:
    """
    Casts the market_state keys from strings (due to JSON serialisation) back to integers.

    Args:
        market_state (dict): The original market_state dictionary with string keys.

    Returns:
        dict: The market_state dictionary with integer keys.
    """
    return {int(k): v for k, v in market_state.items()}


def _extract_market_states(
    market_state: dict[int, Any],
    owned_markets: list[int],
    enemy_markets: list[int],
    neutral_markets: list[int],
) -> dict[int, dict[str, Any]]:
    """
    Extracts and structures state information for markets relevant to the team,
    including dynamic fields from the game engine and static data from the DB.

    Args:
        market_state (dict): The full market_state dictionary from the global game state.
        owned_markets (list): List of market IDs owned by the team.
        enemy_markets (list): List of market IDs owned by enemy teams.
        neutral_markets (list): List of market IDs that are unowned.

    Returns:
        dict: A dictionary (keyed by market ID) containing the state information for each relevant market.
    """
    # only extract states for markets that are owned by the team, owned by enemies, or neutral
    relevant_ids = set(owned_markets + enemy_markets + neutral_markets)

    # structure the extracted info into a consistent format for the agent context
    result: dict[int, dict[str, Any]] = {}

    for market_id, state in market_state.items():
        if market_id not in relevant_ids:
            continue

        result[market_id] = {
            "allocated_ip": int(state.get("allocated_ip", 0)),
            "reallocatable_ip": int(state.get("allocated_ip", 0)),
            "threat": float(state.get("threat", 0.0)),
            "enemy_strength_estimate": float(state.get("enemy_strength_estimate", 0.0)),
            "research_level": int(state.get("research_level", 0)),
            "research_upgrades": state.get("research_upgrades") or [],
            "production_upgrade_level": int(state.get("production_upgrade_level", 0)),
            "regulation_reduction_level": int(
                state.get("regulation_reduction_level", 0)
            ),
            "security_upgrade_level": int(state.get("security_upgrade_level", 0)),
            "fortification_level": int(state.get("fortification_level", 0)),
        }

    return result


# -------------------------------------------------------------
# agent context derivation -
# player-specific dict for decision maker and negotiator agents
# -------------------------------------------------------------


def build_agent_context(game_state: dict[str, Any], team_id: int) -> dict[str, Any]:
    """
    Derive a player-specific context dictionary from the global game state, for AI agents.

    Args:
        game_state (dict): The full, global game state dictionary.
        team_id (int): The ID of the team to build the context for.

    Returns:
        dict: A filtered dictionary containing only the information relevant to the specified team.
    """
    market_state = game_state.get("market_state", {})
    # cast market_state stringified keys back to integers for easier handling in agent logic
    market_state = _cast_market_keys(market_state)
    alliances = game_state.get("alliances", [])
    teams = game_state.get("teams", [])
    rules = game_state.get("rules", DEFAULT_RULES)

    target_team = next((t for t in teams if t["team_id"] == team_id), {})
    current_ip = target_team.get("ip", 0)
    ethical_score = target_team.get("ethical_score", 1.0)

    active_alliances = _get_active_alliances(team_id, alliances)

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
    commitments = _build_commitments(team_id, alliances, market_state)

    avoid_set = set(commitments.get("avoid_attack_markets", []))

    # derive the list of markets that are valid targets for attack actions
    # # i.e. owned by enemies or neutral, excluding any with active commitments to avoid
    attackable_markets = [
        market for market in enemy_markets + neutral_markets if market not in avoid_set
    ]

    # derive the states for all markets, including data from DB and dynamic fields from the game engine
    market_states = _extract_market_states(
        market_state, owned_markets, enemy_markets, neutral_markets
    )

    relationship_states = _build_relationship_states(
        team_id,
        alliances,
        market_state,
        active_alliances,
        game_state.get("current_round", 1),
    )

    return {
        "current_ip": current_ip,
        "ethical_score": ethical_score,
        "owned_markets": owned_markets,
        "enemy_markets": enemy_markets,
        "neutral_markets": neutral_markets,
        "allied_markets": allied_markets,
        "attackable_markets": attackable_markets,
        "market_states": market_states,
        "relationship_states": relationship_states,
        "commitments": commitments,
        "rules": rules,
    }


# ----------------------------------------------------------
#  functions for deriving active alliances and market states
# ----------------------------------------------------------


def _get_active_alliances(team_id: int, alliances: list[dict[str, Any]]) -> set[int]:
    """
    Derives the set of active (i.e. not yet broken) ally team IDs for the specified team.

    Args:
        team_id (int): The ID of the team whose active alliances will be found.
        alliances (list[dict]): List of alliance dictionaries from the game state.

    Returns:
        set[int]: Set of team IDs that are active allies of the specified team.
    """
    ally_ids: set[int] = set()
    for alliance in alliances:
        # only consider alliances that are still active (unbroken)
        if alliance.get("broken_turn") is not None:
            continue

        members = alliance.get("members") or []
        if team_id in members:
            for member in members:
                if member != team_id:
                    # add to the set of active allies
                    ally_ids.add(member)
    return ally_ids


def _build_commitments(
    team_id: int,
    alliances: list[dict],
    market_state: dict[int, Any],
) -> dict[str, list[int]]:
    """
    Derives commitments from active alliances, assuming that markets owned by
    active allies or shared as part of an active alliance should be avoided as attack targets.

    Args:
        team_id (int): The ID of the team for which commitments are being derived.
        alliances (list[dict]): List of alliance dictionaries from the game state.
        market_state (dict): The full market_state dictionary from the global game state.

    Returns:
        dict: A dictionary containing lists of market IDs that should be avoided as attack targets due to active commitments.
    """
    # markets owned by active allies should be avoided as attack targets
    avoid_attack_markets: list[int] = []
    # markets that are shared as part of an active alliance should be avoided as attack targets
    protected_markets: list[int] = []

    for alliance in alliances:
        if alliance.get("broken_turn") is not None:
            continue
        members = alliance.get("members") or []
        if team_id not in members:
            continue

        for market_id, state in market_state.items():
            owner = state.get("owner")
            if owner in members and owner != team_id:
                avoid_attack_markets.append(market_id)

        shared = alliance.get("shared_market")
        if shared:
            protected_markets.append(shared)

    return {
        "avoid_attack_markets": list(set(avoid_attack_markets)),
        "protected_markets": list(set(protected_markets)),
    }


def _build_relationship_states(
    team_id: int,
    alliances: list[dict],
    market_state: dict[int, Any],
    active_ally_team_ids: set[int],
    current_round: int,
) -> dict[int, dict[str, Any]]:
    """
    Derives relationship states (trust, cooperation) for markets owned by active allies.

    Args:
        team_id (int): The ID of the team to derive relationship states for.
        alliances (list[dict]): List of alliance dictionaries from the game state.
        market_state (dict): The full market_state dictionary from the global game state.
        active_ally_team_ids (set[int]): Team IDs that are allied with the specific team.
        current_round (int): The current round number, used to calculate alliance duration.

    Returns:
        dict: A dictionary (keyed by market ID) containing relationship information for markets owned by active allies.
    """
    relationship_states: dict[int, dict[str, Any]] = {}

    for alliance in alliances:
        if alliance.get("broken_turn") is not None:
            continue
        members = alliance.get("members") or []
        if team_id not in members:
            continue

        formed_turn = int(alliance.get("formed_turn") or 1)
        # turns the alliance has been active for; proxy for relationship strength and trust
        alliance_turns = max(1, current_round - formed_turn + 1)

        for market_id, state in market_state.items():
            owner = state.get("owner")
            if owner not in active_ally_team_ids:
                continue

            relationship_states[market_id] = {
                "alliance_turns": alliance_turns,
                "trust": 0.7,  # TODO: wire to ally team's ethical_score
            }

    return relationship_states


# -------------------------------------------------
# functions to faciliate displaying on the frontend
# -------------------------------------------------


def _get_frontend_states(game_state: dict[str, Any]) -> dict[str, Any]:
    """
    Extracts information needed for sanitised frontend display from the global game state.

    Args:
        game_state (dict): The global game state dictionary.

    Returns:
        dict: A dictionary containing frontend-relevant information, avoiding exposure of sensitive information.
    """
    teams = game_state.get("teams") or []
    market_state = game_state.get("market_state") or {}
    # cast market_state stringified keys back to integers for easier handling in frontend logic
    market_state = _cast_market_keys(market_state)
    status = game_state.get("status", SessionStatus.IN_PROGRESS)

    stage_int = game_state.get("current_stage", GameStage.PLAN)
    # ensure frontend has readable string version of game stage
    stage_str = GameStage(stage_int).name if stage_int in GameStage._value2member_map_ else "UNKNOWN"

    return {
        "session_uuid": game_state.get("session_uuid"),
        "status": status,
        "game_mode": game_state.get("game_mode"),
        "current_round": game_state.get("current_round", 1),
        "current_stage": stage_str,
        "current_team_turn": game_state.get("current_team_turn"),
        "team_order": game_state.get("team_order", []),
        "teams": [
            {
                "team_id": t["team_id"],
                "team_name": t["team_name"],
                "colour": t["colour"],
                "ip": t["ip"],
                "ip_spent_this_turn": t.get("ip_spent_this_turn", 0),
                # ethical score hidden until game end
                "ethical_score": (
                    t["ethical_score"] if status == SessionStatus.FINISHED else None
                ),
                "is_ai": t.get("is_ai", False),
            }
            for t in teams
        ],
        "market_state": {
            market_id: {
                "owner": state.get("owner"),
                "contested": state.get("contested", False),
                "colour": _get_owner_colour(state.get("owner"), teams),
                "market_name": state.get("_market_name"),
                "size": state.get("_size"),
                "research_upgrades": state.get("research_upgrades", []),
            }
            for market_id, state in market_state.items()
        },
        "leaderboard": _build_leaderboard(game_state),
        "active_synergies": game_state.get("active_synergies", []),
        "alliances": [
            {
                "alliance_id": a["alliance_id"],
                "members": a["members"],
                "type": a["type"],
                "formed_turn": a["formed_turn"],
                "broken_turn": a.get("broken_turn"),
            }
            for a in (game_state.get("alliances") or [])
        ],
        "plan_notes": game_state.get("turn_log", {}).get("plan_notes", {}),
    }


def _build_leaderboard(game_state: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Builds a leaderboard from current game state, sorted by IP then markets controlled (descending).

    Args:
        game_state (dict): The global game state dictionary.

    Returns:
        list[dict]: A list of team dictionaries sorted by IP, each containing team_id, team_name, ip, and colour.
    """
    teams = game_state.get("teams") or []
    market_state = game_state.get("market_state") or {}
    status = game_state.get("status", "IN_PROGRESS")

    markets_per_team: dict[str, int] = {}
    for state in market_state.values():
        owner = state.get("owner")
        if owner:
            markets_per_team[owner] = markets_per_team.get(owner, 0) + 1

    entries = [
        {
            "team_id": t["team_id"],
            "team_name": t["team_name"],
            "colour": t["colour"],
            "ip": t["ip"],
            "markets_controlled": markets_per_team.get(t["team_id"], 0),
            "ethical_score": t["ethical_score"] if status == "FINISHED" else None,
        }
        for t in teams
    ]

    return sorted(
        entries,
        key=lambda e: (e["ip"], e["markets_controlled"]),
        reverse=True,
    )


def _get_owner_colour(owner_id: int | None, teams: list[dict]) -> str | None:
    """
    Get the colour for the team that owns a market, or None if neutral.

    Args:
        owner_id: The ID of the market owner, or None if unowned.
        teams: The list of team dictionaries from the game state.
    Returns:
         The hex colour string of the owning team, or None if the market is unowned.
    """
    if not owner_id:
        return None
    team = next((t for t in teams if t["team_id"] == owner_id), None)
    return team["colour"] if team else None


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


if __name__ == "__main__":

    # localised import just for testing the generation of an initial game state JSON file, to avoid circular imports with the agent context building functions
    import pprint

    print("> game_state_helpers : intialising game state...")

    initial_state = init_game_state(
        teams=[
            {"id": 1, "name": "Reds", "colour": "#FF0000"},
            {"id": 2, "name": "Blues", "colour": "#0000FF"},
            {"id": 3, "name": "Greens", "colour": "#00FF00"},
        ],
        game_mode="speedrun",
        include_ai=True,
    )

    save_state(initial_state)
    print("> game_state_helpers: saved to json file.")

    loaded = load_state()

    if loaded is not None:
        print("> game_state_helpers: loaded from json file.")
        frontend_view = _get_frontend_states(loaded)
        pprint.pprint(frontend_view)
    else:
        print("> game_state_helpers: no saved state found.")
