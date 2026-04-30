"""
Helper functions to manage global game state (including initialisation,
mutation,and extraction of relevant slices for agents and frontend).
"""

import os
import json
from collections import defaultdict
from copy import deepcopy

from uuid import uuid4
from typing import Any
from pathlib import Path

from backend.enums import GameStage, SessionStatus

from backend.helpers.db_helpers import fetch_all_markets
from backend.helpers.db_helpers import fetch_all

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

SIZE_IP_VALUES: dict[str, int] = {
    "small": 1,
    "medium": 2,
    "large": 3,
    "very large": 4,
}

ENUM_SCORE_VALUES: dict[str, float] = {
    "small": 1.0,
    "medium": 2.0,
    "large": 3.0,
    "very large": 4.0,
    "low": 1.0,
    "high": 3.0,
    "very high": 4.0,
}

SYNERGY_OPERATOR_VALUES: dict[str, int] = {
    "plus_two": 2,
    "plus_one": 1,
    "minus_one": -1,
    "ignore_one": 0,
}

RESEARCH_OPTION_TO_LEVEL_FIELD: dict[str, str] = {
    "increase_production": "production_upgrade_level",
    "reduce_regulation_burden": "regulation_reduction_level",
    "improve_security": "security_upgrade_level",
    "fortify_market": "fortification_level",
}

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
        "round_history": [],
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
        "prepared_moves": {},
        "conflicts": [],
        "pending_research": [],
        "negotiation_log": [],
        "resolution_applied": False,
    }


# ------------------------------
# round-state mutation helpers
# ------------------------------


def set_team_order(game_state: dict[str, Any], team_order: list[int]) -> dict[str, Any]:
    """
    Stores the team turn order after the quickfire stage or manual setup.
    """
    expected_team_ids = sorted(_all_team_ids(game_state))
    provided_ids = [int(team_id) for team_id in team_order]

    if sorted(provided_ids) != expected_team_ids or len(set(provided_ids)) != len(provided_ids):
        raise ValueError(
            f"[gameplay_helpers] team_order must contain each team exactly once. "
            f"Expected {expected_team_ids}, got {provided_ids}."
        )

    game_state["team_order"] = provided_ids
    game_state["current_team_turn"] = provided_ids[0] if provided_ids else None
    return game_state


def submit_plan_notes(game_state: dict[str, Any], team_id: int, notes: Any) -> dict[str, Any]:
    """
    Record a team's private planning notes for the current round.
    """
    _require_stage(game_state, GameStage.PLAN)
    _get_team_entry(game_state, team_id)

    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    turn_log.setdefault("plan_notes", {})[str(team_id)] = notes
    return game_state


def submit_declared_moves(
    game_state: dict[str, Any], team_id: int, moves: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Record the moves a team verbally signalled during negotiation.
    """
    _require_stage(game_state, GameStage.NEGOTIATE)
    _get_team_entry(game_state, team_id)

    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    turn_log.setdefault("declared_moves", {})[str(team_id)] = _normalise_moves(moves)
    return game_state


def append_negotiation_entry(game_state: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
    """
    Append a structured negotiation log entry for the current round.
    """
    _require_stage(game_state, GameStage.NEGOTIATE)

    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    turn_log.setdefault("negotiation_log", []).append(dict(entry))
    return game_state


def submit_actual_moves(
    game_state: dict[str, Any], team_id: int, moves: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Store the binding orders a team wants to execute during the ORDERS stage.
    """
    _require_stage(game_state, GameStage.ORDERS)
    _get_team_entry(game_state, team_id)

    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    turn_log.setdefault("actual_moves", {})[str(team_id)] = _normalise_moves(moves)
    return game_state


def advance_stage(game_state: dict[str, Any], force: bool = False) -> dict[str, Any]:
    """
    Advance the global game state to the next round stage.

    The transition PLAN -> NEGOTIATE requires all teams to submit plan notes unless
    force=True.
    The transition ORDERS -> RESOLVE prepares attacks, defend allocations, and
    pending research.
    The transition RESOLVE -> UPDATE requires conflicts to be resolved unless
    force=True.
    The transition UPDATE -> PLAN applies end-of-round updates and starts the next
    round.
    """
    current_stage = GameStage(int(game_state.get("current_stage", GameStage.PLAN)))

    if current_stage == GameStage.PLAN:
        missing = _missing_submissions(game_state, "plan_notes")
        if missing and not force:
            raise ValueError(
                f"[gameplay_helpers] Cannot leave PLAN stage; missing notes for teams {missing}."
            )
        game_state["current_stage"] = GameStage.NEGOTIATE
        return game_state

    if current_stage == GameStage.NEGOTIATE:
        game_state["current_stage"] = GameStage.ORDERS
        return game_state

    if current_stage == GameStage.ORDERS:
        missing = _missing_submissions(game_state, "actual_moves")
        if missing and not force:
            raise ValueError(
                f"[gameplay_helpers] Cannot leave ORDERS stage; missing orders for teams {missing}."
            )
        prepare_resolution_state(game_state)
        game_state["current_stage"] = GameStage.RESOLVE
        return game_state

    if current_stage == GameStage.RESOLVE:
        unresolved = [
            conflict
            for conflict in game_state.get("turn_log", {}).get("conflicts", [])
            if conflict.get("status") != "resolved"
        ]
        if unresolved and not force:
            unresolved_ids = [int(conflict["market_id"]) for conflict in unresolved]
            raise ValueError(
                f"[gameplay_helpers] Cannot leave RESOLVE stage; unresolved conflicts remain for markets {unresolved_ids}."
            )
        game_state["current_stage"] = GameStage.UPDATE
        return game_state

    apply_round_update(game_state)
    return game_state


def prepare_resolution_state(game_state: dict[str, Any]) -> dict[str, Any]:
    """
    Validate submitted orders and convert them into conflict / update data that
    the quiz resolver and update stage can consume.
    """
    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    market_state = game_state.get("market_state", {})
    rules = game_state.get("rules", DEFAULT_RULES)

    _reset_resolution_fields(game_state)

    turn_log["prepared_moves"] = {}
    turn_log["conflicts"] = []
    turn_log["pending_research"] = []
    turn_log["resolution_applied"] = False
    turn_log["decisions_confirmed"] = False

    attacks_by_market: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for team in game_state.get("teams", []):
        team["ip_spent_this_turn"] = 0

    for team_id in _all_team_ids(game_state):
        team = _get_team_entry(game_state, team_id)
        moves = turn_log.get("actual_moves", {}).get(str(team_id), [])
        prepared_moves = _normalise_moves(moves)

        max_orders = int(rules.get("max_orders_per_round", 3))
        if len(prepared_moves) > max_orders:
            raise ValueError(
                f"[gameplay_helpers] Team {team_id} submitted {len(prepared_moves)} orders; limit is {max_orders}."
            )

        available_current_ip = int(team.get("ip", 0))
        spent_current_ip = 0

        for move in prepared_moves:
            action_type = move["action_type"]

            if action_type == "hold":
                continue

            if _uses_shared_ip(move):
                if available_current_ip < move["ip_spent"]:
                    raise ValueError(
                        f"[gameplay_helpers] Team {team_id} cannot afford order {move}; available current_ip={available_current_ip}."
                    )
                available_current_ip -= move["ip_spent"]
                spent_current_ip += move["ip_spent"]

            if action_type == "attack":
                _validate_attack_move(game_state, team_id, move)
                attacks_by_market[int(move["target_market_id"])].append(
                    {"team_id": team_id, **move}
                )
            elif action_type == "defend":
                _apply_defend_move(game_state, team_id, move)
            elif action_type == "research":
                _validate_research_move(game_state, team_id, move)
                turn_log["pending_research"].append({"team_id": team_id, **move})
            else:
                raise ValueError(
                    f"[gameplay_helpers] Unsupported action_type '{action_type}' in order {move}."
                )

        team["ip"] = available_current_ip
        team["ip_spent_this_turn"] = spent_current_ip
        turn_log["prepared_moves"][str(team_id)] = prepared_moves

    turn_log["conflicts"] = _build_conflict_entries(game_state, attacks_by_market)
    turn_log["decisions_confirmed"] = True

    for conflict in turn_log["conflicts"]:
        market_id = int(conflict["market_id"])
        state = market_state[str(market_id)]
        state["contested"] = True
        state["supporting_teams"] = list(conflict["attacker_team_ids"])

    return game_state


def apply_resolution_outcomes(
    game_state: dict[str, Any], outcomes: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Apply attack resolution outcomes after quiz results are known.
    """
    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    market_state = game_state.get("market_state", {})
    conflicts = {
        int(conflict["market_id"]): conflict for conflict in turn_log.get("conflicts", [])
    }

    for outcome in outcomes:
        market_id = int(outcome["market_id"])
        if market_id not in conflicts:
            raise ValueError(
                f"[gameplay_helpers] No prepared conflict exists for market {market_id}."
            )

        conflict = conflicts[market_id]
        winner_team_id = outcome.get("winner_team_id")
        winner_team_id = int(winner_team_id) if winner_team_id is not None else None

        if winner_team_id is not None:
            _get_team_entry(game_state, winner_team_id)
            market_state[str(market_id)]["owner"] = winner_team_id

        market_state[str(market_id)]["contested"] = False
        market_state[str(market_id)]["supporting_teams"] = []

        conflict["winner_team_id"] = winner_team_id
        conflict["status"] = "resolved"
        conflict["resolution_notes"] = outcome.get("resolution_notes")

    if not turn_log.get("conflicts"):
        turn_log["resolution_applied"] = True
    else:
        turn_log["resolution_applied"] = all(
            conflict.get("status") == "resolved" for conflict in turn_log["conflicts"]
        )

    return game_state


def apply_round_update(game_state: dict[str, Any]) -> dict[str, Any]:
    """
    Apply non-conflict order effects, refresh derived values, distribute income,
    apply maintenance, and advance to the next round.
    """
    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    current_round = int(game_state.get("current_round", 1))

    game_state.setdefault("round_history", []).append(
        {"round": current_round, "turn_log": deepcopy(turn_log)}
    )

    _apply_research_upgrades(game_state)
    _refresh_active_synergies(game_state)
    _distribute_income(game_state)
    _apply_maintenance(game_state)
    _refresh_market_estimates(game_state)

    for team in game_state.get("teams", []):
        team["ip_spent_this_turn"] = 0

    game_state["current_round"] = current_round + 1
    game_state["current_stage"] = GameStage.PLAN
    team_order = game_state.get("team_order") or []
    game_state["current_team_turn"] = team_order[0] if team_order else None
    game_state["turn_log"] = _empty_turn_log()

    return game_state


# --------------------
# mutation internals
# --------------------


def _all_team_ids(game_state: dict[str, Any]) -> list[int]:
    return [int(team["team_id"]) for team in (game_state.get("teams") or [])]


def _get_team_entry(game_state: dict[str, Any], team_id: int) -> dict[str, Any]:
    for team in game_state.get("teams", []):
        if int(team["team_id"]) == int(team_id):
            return team
    raise ValueError(f"[gameplay_helpers] Unknown team_id {team_id}.")


def _require_stage(game_state: dict[str, Any], expected_stage: GameStage) -> None:
    current_stage = GameStage(int(game_state.get("current_stage", GameStage.PLAN)))
    if current_stage != expected_stage:
        raise ValueError(
            f"[gameplay_helpers] Expected stage {expected_stage.name}, got {current_stage.name}."
        )


def _missing_submissions(game_state: dict[str, Any], field_name: str) -> list[int]:
    submissions = game_state.get("turn_log", {}).get(field_name, {}) or {}
    return [
        team_id
        for team_id in _all_team_ids(game_state)
        if str(team_id) not in submissions
    ]


def _normalise_moves(moves: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not moves:
        return []

    normalised: list[dict[str, Any]] = []
    for raw_move in moves:
        metadata = raw_move.get("metadata") or {}
        normalised.append(
            {
                "action_type": str(raw_move.get("action_type", "hold")).strip().lower(),
                "target_market_id": _optional_int(raw_move.get("target_market_id")),
                "source_market_id": _optional_int(raw_move.get("source_market_id")),
                "ip_spent": int(raw_move.get("ip_spent", 0)),
                "metadata": dict(metadata),
            }
        )
    return normalised


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _market_entry(game_state: dict[str, Any], market_id: int) -> dict[str, Any]:
    try:
        return game_state["market_state"][str(int(market_id))]
    except KeyError as exc:
        raise ValueError(f"[gameplay_helpers] Unknown market_id {market_id}.") from exc


def _reset_resolution_fields(game_state: dict[str, Any]) -> None:
    for state in (game_state.get("market_state") or {}).values():
        state["contested"] = False
        state["supporting_teams"] = []


def _uses_shared_ip(move: dict[str, Any]) -> bool:
    return str(move.get("metadata", {}).get("resource_pool", "current_ip")) != "market_ip"


def _validate_attack_move(game_state: dict[str, Any], team_id: int, move: dict[str, Any]) -> None:
    target_market_id = move.get("target_market_id")
    if target_market_id is None:
        raise ValueError(f"[gameplay_helpers] Attack order missing target_market_id: {move}")

    target_state = _market_entry(game_state, target_market_id)
    owner = target_state.get("owner")
    if owner == team_id:
        raise ValueError(
            f"[gameplay_helpers] Team {team_id} cannot attack its own market {target_market_id}."
        )

    if move["ip_spent"] <= 0:
        raise ValueError(f"[gameplay_helpers] Attack order must spend positive IP: {move}")

    if owner is None:
        return

    if not _can_attack_team(game_state, team_id, int(owner)):
        raise ValueError(
            f"[gameplay_helpers] Team {team_id} cannot attack allied/protected market {target_market_id}."
        )


def _apply_defend_move(game_state: dict[str, Any], team_id: int, move: dict[str, Any]) -> None:
    target_market_id = move.get("target_market_id")
    if target_market_id is None:
        raise ValueError(f"[gameplay_helpers] Defend order missing target_market_id: {move}")

    target_state = _market_entry(game_state, target_market_id)
    if target_state.get("owner") != team_id:
        raise ValueError(
            f"[gameplay_helpers] Team {team_id} can only defend its own markets. Invalid target {target_market_id}."
        )

    if move["ip_spent"] <= 0:
        raise ValueError(f"[gameplay_helpers] Defend order must spend positive IP: {move}")

    if _uses_shared_ip(move):
        target_state["allocated_ip"] = int(target_state.get("allocated_ip", 0)) + move["ip_spent"]
        return

    source_market_id = move.get("source_market_id")
    if source_market_id is None:
        raise ValueError(
            f"[gameplay_helpers] Reallocation defend order requires source_market_id: {move}"
        )

    source_state = _market_entry(game_state, source_market_id)
    if source_state.get("owner") != team_id:
        raise ValueError(
            f"[gameplay_helpers] Team {team_id} can only reallocate from its own markets. Invalid source {source_market_id}."
        )

    source_available = int(source_state.get("allocated_ip", 0))
    if source_available < move["ip_spent"]:
        raise ValueError(
            f"[gameplay_helpers] Cannot reallocate {move['ip_spent']} IP from market {source_market_id}; only {source_available} allocated."
        )

    source_state["allocated_ip"] = source_available - move["ip_spent"]
    target_state["allocated_ip"] = int(target_state.get("allocated_ip", 0)) + move["ip_spent"]


def _validate_research_move(
    game_state: dict[str, Any], team_id: int, move: dict[str, Any]
) -> None:
    target_market_id = move.get("target_market_id")
    if target_market_id is None:
        raise ValueError(f"[gameplay_helpers] Research order missing target_market_id: {move}")

    target_state = _market_entry(game_state, target_market_id)
    if target_state.get("owner") != team_id:
        raise ValueError(
            f"[gameplay_helpers] Team {team_id} can only research its own markets. Invalid target {target_market_id}."
        )

    option = str(move.get("metadata", {}).get("research_option", "")).strip().lower()
    if option not in RESEARCH_OPTION_TO_LEVEL_FIELD:
        raise ValueError(
            f"[gameplay_helpers] Unknown research_option '{option}' for order {move}."
        )

    expected_cost = _get_research_cost_from_state(game_state, target_market_id)
    if int(move["ip_spent"]) != expected_cost:
        raise ValueError(
            f"[gameplay_helpers] Research on market {target_market_id} costs {expected_cost} IP, received {move['ip_spent']}."
        )


def _can_attack_team(game_state: dict[str, Any], attacker_team_id: int, defender_team_id: int) -> bool:
    rules = game_state.get("rules", DEFAULT_RULES)
    if not bool(rules.get("forbid_attack_allies", True)):
        return True

    active_allies = _get_active_alliances(attacker_team_id, game_state.get("alliances", []))
    return defender_team_id not in active_allies


def _build_conflict_entries(
    game_state: dict[str, Any], attacks_by_market: dict[int, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []

    for market_id, orders in attacks_by_market.items():
        state = _market_entry(game_state, market_id)
        defender_team_id = state.get("owner")
        attacker_team_ids = sorted({int(order["team_id"]) for order in orders})

        if defender_team_id is None and len(attacker_team_ids) == 1:
            conflict_type = "neutral_capture"
        elif defender_team_id is None:
            conflict_type = "neutral_contested"
        elif len(attacker_team_ids) == 1:
            conflict_type = "attack_vs_owner"
        else:
            conflict_type = "multi_attack"

        conflicts.append(
            {
                "market_id": market_id,
                "market_name": state.get("_market_name"),
                "quiz_topic": state.get("_key_topic"),
                "conflict_type": conflict_type,
                "defender_team_id": defender_team_id,
                "attacker_team_ids": attacker_team_ids,
                "attack_orders": orders,
                "defender_strength_estimate": _estimate_market_defense_strength(state),
                "status": "pending",
                "winner_team_id": None,
            }
        )

    return sorted(conflicts, key=lambda conflict: int(conflict["market_id"]))


def _get_research_cost_from_state(game_state: dict[str, Any], market_id: int) -> int:
    rules = game_state.get("rules", DEFAULT_RULES)
    state = _market_entry(game_state, market_id)

    base_cost = int(rules.get("research_cost", 2))
    threshold = float(rules.get("high_regulation_threshold", 3.0))
    surcharge = int(rules.get("high_regulation_research_surcharge", 1))

    regulation_score = _enum_score(state.get("_regulation_level"))
    if regulation_score >= threshold:
        return base_cost + surcharge
    return base_cost


def _apply_research_upgrades(game_state: dict[str, Any]) -> None:
    turn_log = game_state.get("turn_log", {}) or {}
    for move in turn_log.get("pending_research", []):
        market_id = int(move["target_market_id"])
        state = _market_entry(game_state, market_id)
        option = str(move.get("metadata", {}).get("research_option", "")).strip().lower()
        level_field = RESEARCH_OPTION_TO_LEVEL_FIELD[option]

        state[level_field] = int(state.get(level_field, 0)) + 1
        state["research_level"] = int(state.get("research_level", 0)) + 1
        upgrades = list(state.get("research_upgrades") or [])
        upgrades.append(option)
        state["research_upgrades"] = upgrades


def _refresh_active_synergies(game_state: dict[str, Any]) -> None:
    synergies = fetch_all(
        "SELECT market1, market2, bonus_type, bonus_value FROM Synergy"
    )
    market_state = game_state.get("market_state", {}) or {}
    active: list[dict[str, Any]] = []

    for row in synergies:
        market1 = str(int(row["market1"]))
        market2 = str(int(row["market2"]))
        state1 = market_state.get(market1)
        state2 = market_state.get(market2)
        if state1 is None or state2 is None:
            continue

        owner = state1.get("owner")
        if owner is None or owner != state2.get("owner"):
            continue

        active.append(
            {
                "team_id": owner,
                "market1": int(row["market1"]),
                "market2": int(row["market2"]),
                "bonus_type": row["bonus_type"],
                "bonus_value": row["bonus_value"],
            }
        )

    game_state["active_synergies"] = active


def _distribute_income(game_state: dict[str, Any]) -> None:
    market_state = game_state.get("market_state", {}) or {}
    bonus_ip_by_team: dict[int, int] = defaultdict(int)

    for synergy in game_state.get("active_synergies", []) or []:
        if str(synergy.get("bonus_type", "")).strip().lower() != "ip":
            continue
        bonus_ip_by_team[int(synergy["team_id"])] += SYNERGY_OPERATOR_VALUES.get(
            str(synergy.get("bonus_value", "")).strip().lower(), 0
        )

    for team in game_state.get("teams", []):
        team_id = int(team["team_id"])
        owned_market_income = sum(
            _market_income(state)
            for state in market_state.values()
            if state.get("owner") == team_id
        )
        team["ip"] = int(team.get("ip", 0)) + owned_market_income + bonus_ip_by_team[team_id]


def _apply_maintenance(game_state: dict[str, Any]) -> None:
    market_state = game_state.get("market_state", {}) or {}
    rules = game_state.get("rules", DEFAULT_RULES)
    threshold = int(rules.get("maintenance_threshold", 6))
    penalty_per_market = int(rules.get("maintenance_penalty_per_market", 1))

    for team in game_state.get("teams", []):
        team_id = int(team["team_id"])
        owned_count = sum(1 for state in market_state.values() if state.get("owner") == team_id)
        excess = max(0, owned_count - threshold)
        penalty = excess * penalty_per_market
        team["ip"] = max(0, int(team.get("ip", 0)) - penalty)


def _refresh_market_estimates(game_state: dict[str, Any]) -> None:
    market_state = game_state.get("market_state", {}) or {}
    recent_conflicts = {
        int(conflict["market_id"]): conflict
        for conflict in (game_state.get("round_history", [])[-1]["turn_log"].get("conflicts", [])
                         if game_state.get("round_history") else [])
    }

    for market_id_str, state in market_state.items():
        conflict = recent_conflicts.get(int(market_id_str))
        defense_strength = _estimate_market_defense_strength(state)
        state["enemy_strength_estimate"] = defense_strength

        if state.get("owner") is None:
            state["threat"] = 0.0
        elif conflict is None:
            state["threat"] = 0.15
        else:
            total_attack_ip = sum(int(order.get("ip_spent", 0)) for order in conflict.get("attack_orders", []))
            attacker_count = len(conflict.get("attacker_team_ids", []))
            state["threat"] = min(1.0, 0.2 + (0.1 * attacker_count) + (0.08 * total_attack_ip))

        state["contested"] = False
        state["supporting_teams"] = []


def _market_income(state: dict[str, Any]) -> int:
    size_key = str(state.get("_size", "")).strip().lower()
    base_income = SIZE_IP_VALUES.get(size_key, 1)
    production_bonus = int(state.get("production_upgrade_level", 0))
    return base_income + production_bonus


def _estimate_market_defense_strength(state: dict[str, Any]) -> float:
    allocated_ip = float(state.get("allocated_ip", 0))
    fortification = float(state.get("fortification_level", 0))
    regulation_level = max(
        0.0,
        _enum_score(state.get("_regulation_level")) - float(state.get("regulation_reduction_level", 0)),
    )
    security_level = max(
        0.0,
        _enum_score(state.get("_security_risk")) - float(state.get("security_upgrade_level", 0)),
    )

    regulation_bonus = max(0.0, regulation_level - 1.0)
    security_penalty = max(0.0, security_level - 1.0)

    return max(0.0, allocated_ip + fortification + regulation_bonus - security_penalty)


def _enum_score(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return ENUM_SCORE_VALUES.get(str(value).strip().lower(), 0.0)
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


def get_frontend_state(game_state: dict[str, Any]) -> dict[str, Any]:
    """
    Public wrapper for the sanitised frontend view of the current session state.
    """
    return _get_frontend_states(game_state)


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

    print("> gameplay_helpers : intialising game state...")

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
    print("> gameplay_helpers: saved to json file.")

    loaded = load_state()

    if loaded is not None:
        print("> gameplay_helpers: loaded from json file.")
        frontend_view = _get_frontend_states(loaded)
        pprint.pprint(frontend_view)
    else:
        print("> gameplay_helpers: no saved state found.")

