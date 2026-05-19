"""
Helper functions to manage global game state (including initialisation,
mutation,and extraction of relevant slices for agents and frontend).
"""

import os
import json
import re
from collections import defaultdict
from copy import deepcopy

from uuid import uuid4
from typing import Any
from pathlib import Path

from backend.enums import GameStage, SessionStatus

from backend.helpers.db_helpers import fetch_all_markets
from backend.helpers.db_helpers import fetch_all
from backend.helpers import quiz_helpers

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
    "max_rounds": None,
    "session_minutes": None,
}

GAME_MODES: dict[str, int] = {"speedrun": 20, "full": 60}
DEFAULT_ROUND_MINUTES = 5

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
        "rules": _build_rules_for_game_mode(game_mode),
        "quickfire_results": [],
        "requested_stop": False,
        "game_over_reason": None,
        "finished_round": None,
        "winner_team_id": None,
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
        "plan_allocations": {},
        "declared_moves": {},
        "alliance_offers": [],
        "actual_moves": {},
        "prepared_moves": {},
        "conflicts": [],
        "active_quizzes": [],
        "quiz_results": {},
        "resolution_outcomes": [],
        "pending_research": [],
        "negotiation_log": [],
        "ethical_events": [],
        "ethical_adjustments": {},
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


def configure_opening_setup(
    game_state: dict[str, Any],
    team_order: list[int],
    opening_assignments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Apply the opening tournament outcome to a fresh session.

    This persists the initial turn order, assigns starting markets, and seeds each
    owning team with opening reserve IP equal to the income of the markets they
    drafted.
    """
    _require_stage(game_state, GameStage.PLAN)
    set_team_order(game_state, team_order)

    assignments = opening_assignments or []
    market_state = game_state.get("market_state", {}) or {}

    for state in market_state.values():
        state["owner"] = None
        state["allocated_ip"] = 0
        state["contested"] = False
        state["supporting_teams"] = []

    for team in game_state.get("teams", []):
        team["ip"] = 0
        team["ip_spent_this_turn"] = 0

    used_market_ids: set[int] = set()
    for assignment in assignments:
        team_id = int(assignment["team_id"])
        _get_team_entry(game_state, team_id)

        market_id = _resolve_opening_market_id(
            game_state,
            market_id=assignment.get("market_id"),
            market_slug=assignment.get("market_slug"),
            used_market_ids=used_market_ids,
        )
        market_entry = _market_entry(game_state, market_id)
        market_entry["owner"] = team_id
        used_market_ids.add(market_id)

    for team in game_state.get("teams", []):
        team_id = int(team["team_id"])
        team["ip"] = sum(
            _market_income(state)
            for state in market_state.values()
            if int(state.get("owner") or 0) == team_id
        )

    game_state["active_synergies"] = []
    _refresh_market_estimates(game_state)
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


def submit_plan_allocations(
    game_state: dict[str, Any], team_id: int, allocations: list[dict[str, Any]] | None
) -> dict[str, Any]:
    """
    Record one team's planning-stage IP allocations into owned markets.

    The latest submission replaces any previous PLAN allocations from that same
    team for the current round, refunding the prior allocation back to team IP
    before applying the new one.
    """
    _require_stage(game_state, GameStage.PLAN)
    team = _get_team_entry(game_state, team_id)
    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    allocation_store = turn_log.setdefault("plan_allocations", {})
    market_state = game_state.get("market_state", {}) or {}

    prior_allocations = allocation_store.get(str(team_id), []) or []
    _refund_plan_allocations(team, market_state, prior_allocations)

    normalised_allocations = _normalise_plan_allocations(allocations)
    total_ip = sum(entry["ip_allocated"] for entry in normalised_allocations)
    available_ip = int(team.get("ip", 0))
    if total_ip > available_ip:
        raise ValueError(
            f"[gameplay_helpers] Team {team_id} cannot allocate {total_ip} IP during PLAN; "
            f"only {available_ip} IP available."
        )

    for allocation in normalised_allocations:
        market_id = allocation["market_id"]
        market_entry = _market_entry(game_state, market_id)
        if market_entry.get("owner") != int(team_id):
            raise ValueError(
                f"[gameplay_helpers] Team {team_id} can only allocate IP to owned markets. "
                f"Market {market_id} is not owned by that team."
            )

    for allocation in normalised_allocations:
        market_entry = _market_entry(game_state, allocation["market_id"])
        market_entry["allocated_ip"] = int(market_entry.get("allocated_ip", 0)) + allocation["ip_allocated"]

    team["ip"] = available_ip - total_ip
    allocation_store[str(team_id)] = normalised_allocations
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


def propose_alliance(
    game_state: dict[str, Any],
    proposer_team_id: int,
    recipient_team_id: int,
    *,
    alliance_type: str = "alliance",
    protected_markets: list[int] | None = None,
    notes: Any = None,
) -> dict[str, Any]:
    """
    Create a pending bilateral alliance offer during the NEGOTIATE stage.
    """
    _require_stage(game_state, GameStage.NEGOTIATE)
    _get_team_entry(game_state, proposer_team_id)
    _get_team_entry(game_state, recipient_team_id)

    if int(proposer_team_id) == int(recipient_team_id):
        raise ValueError("[gameplay_helpers] A team cannot propose an alliance to itself.")

    protected_market_ids = _normalise_market_id_list(protected_markets)

    for market_id in protected_market_ids:
        _market_entry(game_state, market_id)

    if _find_active_alliance_between(game_state, proposer_team_id, recipient_team_id) is not None:
        raise ValueError(
            f"[gameplay_helpers] Teams {proposer_team_id} and {recipient_team_id} already have an active alliance."
        )

    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    offers = turn_log.setdefault("alliance_offers", [])

    if _find_pending_offer_between(offers, proposer_team_id, recipient_team_id) is not None:
        raise ValueError(
            f"[gameplay_helpers] Teams {proposer_team_id} and {recipient_team_id} already have a pending alliance offer this round."
        )

    current_round = int(game_state.get("current_round", 1))
    offer_id = f"offer_{uuid4().hex[:10]}"
    offer = {
        "offer_id": offer_id,
        "proposer_team_id": int(proposer_team_id),
        "recipient_team_id": int(recipient_team_id),
        "members": sorted([int(proposer_team_id), int(recipient_team_id)]),
        "type": str(alliance_type or "alliance").strip().lower(),
        "protected_markets": protected_market_ids,
        "notes": notes,
        "status": "pending",
        "proposed_turn": current_round,
        "resolved_turn": None,
        "resolved_by_team_id": None,
        "rejection_reason": None,
        "alliance_id": None,
    }
    offers.append(offer)

    append_negotiation_entry(
        game_state,
        {
            "entry_type": "alliance_offer",
            "offer_id": offer_id,
            "proposer_team_id": int(proposer_team_id),
            "recipient_team_id": int(recipient_team_id),
            "protected_markets": list(protected_market_ids),
        },
    )
    return offer


def accept_alliance_offer(
    game_state: dict[str, Any], offer_id: str, responder_team_id: int
) -> dict[str, Any]:
    """
    Accept a pending alliance offer and create an active alliance entry.
    """
    _require_stage(game_state, GameStage.NEGOTIATE)
    _get_team_entry(game_state, responder_team_id)

    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    offer = _get_alliance_offer(turn_log, offer_id)
    if offer["status"] != "pending":
        raise ValueError(
            f"[gameplay_helpers] Alliance offer {offer_id} is already {offer['status']}."
        )

    if int(offer["recipient_team_id"]) != int(responder_team_id):
        raise ValueError(
            f"[gameplay_helpers] Only team {offer['recipient_team_id']} can accept alliance offer {offer_id}."
        )

    members = [int(member) for member in (offer.get("members") or [])]
    if _find_active_alliance_between(game_state, members[0], members[1]) is not None:
        raise ValueError(
            f"[gameplay_helpers] Teams {members[0]} and {members[1]} already have an active alliance."
        )

    current_round = int(game_state.get("current_round", 1))
    alliance_id = f"alliance_{uuid4().hex[:10]}"
    alliance = {
        "alliance_id": alliance_id,
        "members": members,
        "type": offer.get("type", "alliance"),
        "formed_turn": current_round,
        "protected_markets": list(offer.get("protected_markets") or []),
        "notes": offer.get("notes"),
        "source_offer_id": offer_id,
        "status": "active",
        "broken_turn": None,
        "broken_by_team_id": None,
        "broken_reason": None,
    }

    offer["status"] = "accepted"
    offer["resolved_turn"] = current_round
    offer["resolved_by_team_id"] = int(responder_team_id)
    offer["alliance_id"] = alliance_id
    game_state.setdefault("alliances", []).append(alliance)

    append_negotiation_entry(
        game_state,
        {
            "entry_type": "alliance_accepted",
            "offer_id": offer_id,
            "alliance_id": alliance_id,
            "members": members,
            "accepted_by_team_id": int(responder_team_id),
        },
    )
    return alliance


def reject_alliance_offer(
    game_state: dict[str, Any],
    offer_id: str,
    responder_team_id: int,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    """
    Reject a pending alliance offer during the NEGOTIATE stage.
    """
    _require_stage(game_state, GameStage.NEGOTIATE)
    _get_team_entry(game_state, responder_team_id)

    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    offer = _get_alliance_offer(turn_log, offer_id)
    if offer["status"] != "pending":
        raise ValueError(
            f"[gameplay_helpers] Alliance offer {offer_id} is already {offer['status']}."
        )

    if int(offer["recipient_team_id"]) != int(responder_team_id):
        raise ValueError(
            f"[gameplay_helpers] Only team {offer['recipient_team_id']} can reject alliance offer {offer_id}."
        )

    offer["status"] = "rejected"
    offer["resolved_turn"] = int(game_state.get("current_round", 1))
    offer["resolved_by_team_id"] = int(responder_team_id)
    offer["rejection_reason"] = reason

    append_negotiation_entry(
        game_state,
        {
            "entry_type": "alliance_rejected",
            "offer_id": offer_id,
            "rejected_by_team_id": int(responder_team_id),
            "reason": reason,
        },
    )
    return offer


def break_alliance(
    game_state: dict[str, Any],
    alliance_id: str,
    acting_team_id: int,
    *,
    reason: str = "manual_break",
) -> dict[str, Any]:
    """
    Explicitly end an active alliance during the NEGOTIATE stage.

    This is treated as an open diplomatic action rather than an attack-based betrayal.
    """
    _require_stage(game_state, GameStage.NEGOTIATE)
    _get_team_entry(game_state, acting_team_id)

    alliance = _get_alliance_by_id(game_state, alliance_id)
    members = {int(member) for member in (alliance.get("members") or [])}
    if int(acting_team_id) not in members:
        raise ValueError(
            f"[gameplay_helpers] Team {acting_team_id} is not a member of alliance {alliance_id}."
        )
    if alliance.get("broken_turn") is not None:
        raise ValueError(f"[gameplay_helpers] Alliance {alliance_id} is already broken.")

    alliance["broken_turn"] = int(game_state.get("current_round", 1))
    alliance["broken_by_team_id"] = int(acting_team_id)
    alliance["broken_reason"] = str(reason)
    alliance["status"] = "broken"

    append_negotiation_entry(
        game_state,
        {
            "entry_type": "alliance_broken",
            "alliance_id": alliance_id,
            "members": sorted(members),
            "broken_by_team_id": int(acting_team_id),
            "reason": str(reason),
        },
    )
    return alliance


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


def start_resolution_quizzes(
    game_state: dict[str, Any], used_question_ids: list[int] | None = None
) -> dict[str, Any]:
    """
    Build and store internal quiz payloads for the conflicts prepared this round.
    """
    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    conflicts = turn_log.get("conflicts", []) or []

    if not conflicts:
        turn_log["active_quizzes"] = []
        return game_state

    turn_log["active_quizzes"] = quiz_helpers.build_quizzes_for_pending_conflicts(
        game_state,
        used_question_ids=used_question_ids,
    )
    return game_state


def submit_quiz_results(
    game_state: dict[str, Any], market_id: int, team_results: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Store quiz answers or score summaries for one conflict during the RESOLVE stage.
    """
    _require_stage(game_state, GameStage.RESOLVE)

    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    quiz = _get_active_quiz(turn_log, market_id)
    participant_team_ids = {int(team_id) for team_id in quiz.get("participant_team_ids", [])}
    time_limit_ms = int(quiz.get("time_limit_ms", 30_000))

    normalised_results: list[dict[str, Any]] = []
    for raw_result in team_results:
        if raw_result.get("team_id") is None:
            raise ValueError(
                f"[gameplay_helpers] Quiz result for market {market_id} is missing team_id."
            )

        team_id = int(raw_result["team_id"])
        if team_id not in participant_team_ids:
            raise ValueError(
                f"[gameplay_helpers] Team {team_id} is not a participant in quiz market {market_id}."
            )

        normalised_result = deepcopy(raw_result)
        normalised_result["team_id"] = team_id

        if not normalised_result.get("questions"):
            normalised_result["questions"] = deepcopy(quiz.get("questions", []))

        if "answers" in normalised_result and normalised_result["answers"] is not None:
            normalised_result["answers"] = [
                {
                    "question_id": int(answer["question_id"]),
                    "selected_option": answer.get("selected_option"),
                    "response_time_ms": int(answer.get("response_time_ms", time_limit_ms)),
                }
                for answer in normalised_result["answers"]
                if answer.get("question_id") is not None
            ]

        if "total_response_time_ms" in normalised_result:
            normalised_result["total_response_time_ms"] = int(
                normalised_result["total_response_time_ms"]
            )

        normalised_results.append(normalised_result)

    turn_log.setdefault("quiz_results", {})[str(int(market_id))] = {
        "market_id": int(market_id),
        "team_results": normalised_results,
    }
    return game_state


def resolve_pending_quizzes(game_state: dict[str, Any], force: bool = False) -> dict[str, Any]:
    """
    Resolve stored quiz results into market outcomes and apply them to the game state.
    """
    _require_stage(game_state, GameStage.RESOLVE)

    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    active_quizzes = turn_log.get("active_quizzes", []) or []

    if not active_quizzes:
        turn_log["resolution_outcomes"] = []
        if not turn_log.get("conflicts"):
            turn_log["resolution_applied"] = True
        return game_state

    missing_results = _missing_quiz_results(game_state)
    if missing_results and not force:
        raise ValueError(
            f"[gameplay_helpers] Cannot resolve quizzes; missing quiz results for markets {missing_results}."
        )

    quiz_results = list((turn_log.get("quiz_results") or {}).values())
    if force:
        recorded_market_ids = {int(result["market_id"]) for result in quiz_results}
        for quiz in active_quizzes:
            market_id = int(quiz["market_id"])
            if market_id in recorded_market_ids:
                continue
            quiz_results.append({"market_id": market_id, "team_results": []})

    outcomes = quiz_helpers.build_resolution_outcomes_from_quiz(game_state, quiz_results)
    turn_log["resolution_outcomes"] = outcomes
    apply_resolution_outcomes(game_state, outcomes)
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
    if _is_finished_status(game_state.get("status")):
        raise ValueError("[gameplay_helpers] Cannot advance a finished game.")

    current_stage = GameStage(int(game_state.get("current_stage", GameStage.PLAN)))

    if current_stage == GameStage.PLAN:
        missing = _missing_plan_submissions(game_state)
        if missing and not force:
            raise ValueError(
                f"[gameplay_helpers] Cannot leave PLAN stage; missing plan submissions for teams {missing}."
            )
        game_state["current_stage"] = GameStage.NEGOTIATE
        return game_state

    if current_stage == GameStage.NEGOTIATE:
        pending_offer_ids = _pending_alliance_offer_ids(game_state)
        if pending_offer_ids and not force:
            raise ValueError(
                f"[gameplay_helpers] Cannot leave NEGOTIATE stage; unresolved alliance offers remain: {pending_offer_ids}."
            )
        _expire_pending_alliance_offers(game_state)
        game_state["current_stage"] = GameStage.ORDERS
        return game_state

    if current_stage == GameStage.ORDERS:
        missing = _missing_submissions(game_state, "actual_moves")
        if missing and not force:
            raise ValueError(
                f"[gameplay_helpers] Cannot leave ORDERS stage; missing orders for teams {missing}."
            )
        prepare_resolution_state(game_state)
        start_resolution_quizzes(game_state)
        game_state["current_stage"] = GameStage.RESOLVE
        return game_state

    if current_stage == GameStage.RESOLVE:
        missing_quiz_results = _missing_quiz_results(game_state)
        if (
            game_state.get("turn_log", {}).get("conflicts")
            and not game_state.get("turn_log", {}).get("resolution_applied", False)
            and (not missing_quiz_results or force)
        ):
            resolve_pending_quizzes(game_state, force=force)

        unresolved = [
            conflict
            for conflict in game_state.get("turn_log", {}).get("conflicts", [])
            if conflict.get("status") != "resolved"
        ]
        if unresolved and not force:
            if missing_quiz_results:
                raise ValueError(
                    f"[gameplay_helpers] Cannot leave RESOLVE stage; missing quiz results for markets {missing_quiz_results}."
                )
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
    turn_log["active_quizzes"] = []
    turn_log["quiz_results"] = {}
    turn_log["resolution_outcomes"] = []
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

    start_resolution_quizzes(game_state)
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

    _apply_ethical_scoring(game_state)

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

    finish_reason = _get_game_finish_reason(game_state, current_round)
    if finish_reason is not None:
        _finalise_game(game_state, current_round, finish_reason)
        return game_state

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


def _build_rules_for_game_mode(game_mode: str) -> dict[str, Any]:
    rules = dict(DEFAULT_RULES)
    mode_key = str(game_mode or "speedrun").strip().lower()
    session_minutes = int(GAME_MODES.get(mode_key, GAME_MODES["speedrun"]))

    rules["session_minutes"] = session_minutes
    rules["max_rounds"] = max(1, session_minutes // DEFAULT_ROUND_MINUTES)
    return rules


def _is_finished_status(status: Any) -> bool:
    if isinstance(status, SessionStatus):
        return status == SessionStatus.FINISHED
    return str(status or "").strip().upper() == SessionStatus.FINISHED.value


def _status_value(status: Any) -> str:
    if isinstance(status, SessionStatus):
        return status.value
    text = str(status or "").strip().upper()
    return text or SessionStatus.IN_PROGRESS.value


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


def _missing_plan_submissions(game_state: dict[str, Any]) -> list[int]:
    turn_log = game_state.get("turn_log", {}) or {}
    notes = turn_log.get("plan_notes", {}) or {}
    allocations = turn_log.get("plan_allocations", {}) or {}
    return [
        team_id
        for team_id in _all_team_ids(game_state)
        if str(team_id) not in notes and str(team_id) not in allocations
    ]


def _missing_quiz_results(game_state: dict[str, Any]) -> list[int]:
    turn_log = game_state.get("turn_log", {}) or {}
    active_quizzes = turn_log.get("active_quizzes", []) or []
    recorded_results = turn_log.get("quiz_results", {}) or {}
    return [
        int(quiz["market_id"])
        for quiz in active_quizzes
        if str(int(quiz["market_id"])) not in recorded_results
    ]


def _pending_alliance_offer_ids(game_state: dict[str, Any]) -> list[str]:
    turn_log = game_state.get("turn_log", {}) or {}
    offers = turn_log.get("alliance_offers", []) or []
    return [
        str(offer["offer_id"])
        for offer in offers
        if str(offer.get("status", "pending")).strip().lower() == "pending"
    ]


def _expire_pending_alliance_offers(game_state: dict[str, Any]) -> None:
    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    current_round = int(game_state.get("current_round", 1))

    for offer in turn_log.get("alliance_offers", []) or []:
        if str(offer.get("status", "pending")).strip().lower() != "pending":
            continue
        offer["status"] = "expired"
        offer["resolved_turn"] = current_round
        offer["resolved_by_team_id"] = None

        append_negotiation_entry(
            game_state,
            {
                "entry_type": "alliance_offer_expired",
                "offer_id": offer["offer_id"],
                "members": list(offer.get("members") or []),
            },
        )


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


def _normalise_plan_allocations(
    allocations: list[dict[str, Any]] | None,
) -> list[dict[str, int]]:
    if not allocations:
        return []

    aggregated: dict[int, int] = defaultdict(int)
    for raw_allocation in allocations:
        market_id = _optional_int(
            raw_allocation.get("market_id", raw_allocation.get("target_market_id"))
        )
        if market_id is None:
            raise ValueError(
                f"[gameplay_helpers] Plan allocation missing market_id/target_market_id: {raw_allocation}"
            )

        ip_allocated_raw = raw_allocation.get(
            "ip_allocated",
            raw_allocation.get("ip", raw_allocation.get("amount", 0)),
        )
        ip_allocated = int(ip_allocated_raw)
        if ip_allocated < 0:
            raise ValueError(
                f"[gameplay_helpers] Plan allocation cannot be negative: {raw_allocation}"
            )
        if ip_allocated == 0:
            continue

        aggregated[int(market_id)] += ip_allocated

    return [
        {"market_id": market_id, "ip_allocated": ip_allocated}
        for market_id, ip_allocated in sorted(aggregated.items())
    ]


def _refund_plan_allocations(
    team: dict[str, Any],
    market_state: dict[str, Any],
    prior_allocations: list[dict[str, Any]] | None,
) -> None:
    if not prior_allocations:
        return

    refunded_total = 0
    for allocation in prior_allocations:
        market_id = int(allocation["market_id"])
        ip_allocated = int(allocation.get("ip_allocated", 0))
        if ip_allocated <= 0:
            continue

        state_entry = market_state.get(str(market_id))
        if state_entry is not None:
            state_entry["allocated_ip"] = max(
                0,
                int(state_entry.get("allocated_ip", 0)) - ip_allocated,
            )
        refunded_total += ip_allocated

    team["ip"] = int(team.get("ip", 0)) + refunded_total


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _normalise_market_id_list(values: list[int] | None) -> list[int]:
    if not values:
        return []

    seen: set[int] = set()
    ordered: list[int] = []
    for value in values:
        market_id = int(value)
        if market_id in seen:
            continue
        seen.add(market_id)
        ordered.append(market_id)
    return ordered


def _get_alliance_offer(turn_log: dict[str, Any], offer_id: str) -> dict[str, Any]:
    target_offer_id = str(offer_id)
    for offer in turn_log.get("alliance_offers", []) or []:
        if str(offer.get("offer_id")) == target_offer_id:
            return offer
    raise ValueError(f"[gameplay_helpers] Unknown alliance offer_id {offer_id}.")


def _find_pending_offer_between(
    offers: list[dict[str, Any]], team_a_id: int, team_b_id: int
) -> dict[str, Any] | None:
    target_members = {int(team_a_id), int(team_b_id)}
    for offer in offers:
        members = {int(member) for member in (offer.get("members") or [])}
        if members != target_members:
            continue
        if str(offer.get("status", "pending")).strip().lower() == "pending":
            return offer
    return None


def _find_active_alliance_between(
    game_state: dict[str, Any], team_a_id: int, team_b_id: int
) -> dict[str, Any] | None:
    target_members = {int(team_a_id), int(team_b_id)}
    for alliance in game_state.get("alliances", []) or []:
        members = {int(member) for member in (alliance.get("members") or [])}
        if members != target_members:
            continue
        if alliance.get("broken_turn") is not None:
            continue
        return alliance
    return None


def _get_alliance_by_id(game_state: dict[str, Any], alliance_id: str) -> dict[str, Any]:
    target_alliance_id = str(alliance_id)
    for alliance in game_state.get("alliances", []) or []:
        if str(alliance.get("alliance_id")) == target_alliance_id:
            return alliance
    raise ValueError(f"[gameplay_helpers] Unknown alliance_id {alliance_id}.")


def _market_entry(game_state: dict[str, Any], market_id: int) -> dict[str, Any]:
    try:
        return game_state["market_state"][str(int(market_id))]
    except KeyError as exc:
        raise ValueError(f"[gameplay_helpers] Unknown market_id {market_id}.") from exc


def _slugify_market_name(value: Any) -> str:
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", str(value or "").lower().replace("&", "and")))


def _resolve_opening_market_id(
    game_state: dict[str, Any],
    *,
    market_id: Any = None,
    market_slug: Any = None,
    used_market_ids: set[int] | None = None,
) -> int:
    if market_id is not None:
        resolved_market_id = int(market_id)
        _market_entry(game_state, resolved_market_id)
        return resolved_market_id

    slug = _slugify_market_name(market_slug)
    if not slug:
        raise ValueError("[gameplay_helpers] Opening setup assignment requires market_id or market_slug.")

    taken = used_market_ids or set()
    for key, state in (game_state.get("market_state") or {}).items():
        resolved_market_id = int(key)
        if resolved_market_id in taken:
            continue
        if _slugify_market_name(state.get("_market_name")) == slug:
            return resolved_market_id

    raise ValueError(f"[gameplay_helpers] Could not resolve opening market slug '{slug}'.")


def _get_active_quiz(turn_log: dict[str, Any], market_id: int) -> dict[str, Any]:
    target_market_id = int(market_id)
    for quiz in turn_log.get("active_quizzes", []) or []:
        if int(quiz["market_id"]) == target_market_id:
            return quiz
    raise ValueError(
        f"[gameplay_helpers] No active quiz exists for market {target_market_id}."
    )


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
        if _attack_breaks_alliance(move):
            return
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


def _get_game_finish_reason(game_state: dict[str, Any], completed_round: int) -> str | None:
    if bool(game_state.get("requested_stop")):
        return "requested_stop"

    rules = game_state.get("rules", {}) or {}
    max_rounds = rules.get("max_rounds")
    if max_rounds not in (None, "", 0):
        if int(completed_round) >= int(max_rounds):
            return "max_rounds_reached"

    return None


def _finalise_game(game_state: dict[str, Any], completed_round: int, reason: str) -> None:
    game_state["status"] = SessionStatus.FINISHED
    game_state["current_stage"] = GameStage.UPDATE
    game_state["current_team_turn"] = None
    game_state["current_round"] = completed_round
    game_state["requested_stop"] = False
    game_state["game_over_reason"] = str(reason)
    game_state["finished_round"] = int(completed_round)
    leaderboard = _build_leaderboard(game_state)
    winner_team_id = leaderboard[0]["team_id"] if leaderboard else None
    game_state["winner_team_id"] = winner_team_id


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


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, float(value)))


def _apply_ethical_scoring(game_state: dict[str, Any]) -> None:
    """
    Evaluate ethical penalties for this round before the turn log is archived.
    """
    turn_log = game_state.setdefault("turn_log", _empty_turn_log())
    actual_moves_by_team = turn_log.get("actual_moves", {}) or {}
    declared_moves_by_team = turn_log.get("declared_moves", {}) or {}
    plan_notes_by_team = turn_log.get("plan_notes", {}) or {}

    events: list[dict[str, Any]] = []
    penalty_by_team: dict[int, float] = defaultdict(float)

    for team_id in _all_team_ids(game_state):
        actual_moves = _normalise_moves(actual_moves_by_team.get(str(team_id), []))
        declared_moves = _normalise_moves(declared_moves_by_team.get(str(team_id), []))
        plan_notes = plan_notes_by_team.get(str(team_id))

        plan_penalty, plan_event = _evaluate_plan_note_alignment(
            team_id,
            plan_notes,
            actual_moves,
        )
        if plan_penalty > 0.0:
            penalty_by_team[team_id] += plan_penalty
            events.append(plan_event)

        declared_penalty, declared_event = _evaluate_declared_move_alignment(
            team_id,
            declared_moves,
            actual_moves,
        )
        if declared_penalty > 0.0:
            penalty_by_team[team_id] += declared_penalty
            events.append(declared_event)

        betrayal_penalty, betrayal_events = _apply_alliance_betrayal_penalties(
            game_state,
            team_id,
            actual_moves,
        )
        if betrayal_penalty > 0.0:
            penalty_by_team[team_id] += betrayal_penalty
            events.extend(betrayal_events)

    adjustments: dict[str, dict[str, float]] = {}
    for team in game_state.get("teams", []):
        team_id = int(team["team_id"])
        starting_score = _clamp(float(team.get("ethical_score", 1.0)), 0.0, 1.0)
        penalty = min(0.95, round(float(penalty_by_team.get(team_id, 0.0)), 4))
        ending_score = _clamp(starting_score - penalty, 0.0, 1.0)
        team["ethical_score"] = ending_score

        adjustments[str(team_id)] = {
            "starting_score": round(starting_score, 4),
            "penalty": penalty,
            "ending_score": round(ending_score, 4),
        }

    turn_log["ethical_events"] = events
    turn_log["ethical_adjustments"] = adjustments


def _evaluate_plan_note_alignment(
    team_id: int,
    notes: Any,
    actual_moves: list[dict[str, Any]],
) -> tuple[float, dict[str, Any] | None]:
    if notes in (None, "", []):
        return 0.0, None

    action_hint = _normalise_note_action(notes)
    planned_targets = _extract_note_market_ids(notes)
    actual_non_hold_moves = [move for move in actual_moves if move["action_type"] != "hold"]
    actual_attack_moves = [move for move in actual_moves if move["action_type"] == "attack"]
    actual_targets = {
        int(move["target_market_id"])
        for move in actual_non_hold_moves
        if move.get("target_market_id") is not None
    }

    penalty = 0.0
    reasons: list[str] = []

    if action_hint == "hold" and actual_non_hold_moves:
        penalty += 0.05
        reasons.append("planned to hold but executed non-hold actions")
    elif action_hint == "defend" and actual_attack_moves:
        penalty += 0.06
        reasons.append("planned to defend but launched an attack")
    elif action_hint == "research" and any(
        move["action_type"] != "research" for move in actual_non_hold_moves
    ):
        penalty += 0.05
        reasons.append("planned to research but changed action type")
    elif action_hint == "attack" and not actual_attack_moves:
        penalty += 0.04
        reasons.append("planned to attack but did not submit an attack")

    unexpected_targets = sorted(actual_targets - planned_targets) if planned_targets else []
    if unexpected_targets:
        penalty += min(0.06, 0.03 * len(unexpected_targets))
        reasons.append(f"used unexpected targets {unexpected_targets}")

    penalty = min(0.12, round(penalty, 4))
    if penalty <= 0.0:
        return 0.0, None

    return penalty, {
        "team_id": team_id,
        "category": "plan_mismatch",
        "penalty": penalty,
        "summary": "; ".join(reasons),
    }


def _evaluate_declared_move_alignment(
    team_id: int,
    declared_moves: list[dict[str, Any]],
    actual_moves: list[dict[str, Any]],
) -> tuple[float, dict[str, Any] | None]:
    if not declared_moves:
        return 0.0, None

    declared_counts = _build_move_signature_counts(declared_moves)
    actual_counts = _build_move_signature_counts(actual_moves)

    missing_signatures = {
        signature: count
        for signature, count in declared_counts.items()
        if actual_counts.get(signature, 0) < count
    }
    surprise_signatures = {
        signature: count
        for signature, count in actual_counts.items()
        if declared_counts.get(signature, 0) < count
    }

    mismatch_count = 0
    for signature, count in missing_signatures.items():
        mismatch_count += count - actual_counts.get(signature, 0)
    for signature, count in surprise_signatures.items():
        mismatch_count += count - declared_counts.get(signature, 0)

    penalty = min(0.12, round(0.03 * mismatch_count, 4))
    if penalty <= 0.0:
        return 0.0, None

    return penalty, {
        "team_id": team_id,
        "category": "negotiation_mismatch",
        "penalty": penalty,
        "summary": (
            f"{mismatch_count} declared-vs-actual move mismatch(es) detected"
        ),
        "details": {
            "missing_moves": [str(signature) for signature in missing_signatures],
            "surprise_moves": [str(signature) for signature in surprise_signatures],
        },
    }


def _apply_alliance_betrayal_penalties(
    game_state: dict[str, Any],
    attacker_team_id: int,
    actual_moves: list[dict[str, Any]],
) -> tuple[float, list[dict[str, Any]]]:
    alliances = game_state.get("alliances", []) or []
    current_round = int(game_state.get("current_round", 1))
    total_penalty = 0.0
    events: list[dict[str, Any]] = []
    broken_alliance_ids: set[str] = set()

    for move in actual_moves:
        if move["action_type"] != "attack" or move.get("target_market_id") is None:
            continue

        target_state = _market_entry(game_state, int(move["target_market_id"]))
        defender_team_id = _optional_int(target_state.get("owner"))
        if defender_team_id is None:
            continue

        for index, alliance in enumerate(alliances):
            if alliance.get("broken_turn") is not None:
                continue

            members = {int(member) for member in (alliance.get("members") or [])}
            if attacker_team_id not in members or defender_team_id not in members:
                continue

            alliance_turns = max(
                1,
                current_round - int(alliance.get("formed_turn") or current_round) + 1,
            )
            protected_markets = set(
                _normalise_market_id_list(alliance.get("protected_markets") or [])
            )

            penalty = 0.12 + min(0.18, 0.03 * alliance_turns)
            if int(move["target_market_id"]) in protected_markets:
                penalty += 0.05
            if _attack_breaks_alliance(move):
                penalty += 0.03
            penalty = round(min(0.4, penalty), 4)

            total_penalty += penalty
            alliance_id = str(alliance.get("alliance_id") or f"alliance_{index}")
            if alliance_id not in broken_alliance_ids:
                alliance["broken_turn"] = current_round
                alliance["broken_by_team_id"] = attacker_team_id
                alliance["broken_reason"] = "attack"
                broken_alliance_ids.add(alliance_id)

            events.append(
                {
                    "team_id": attacker_team_id,
                    "category": "alliance_betrayal",
                    "penalty": penalty,
                    "summary": (
                        f"Attacked allied market {move['target_market_id']} owned by team "
                        f"{defender_team_id} after {alliance_turns} round(s) of alliance."
                    ),
                    "details": {
                        "alliance_id": alliance_id,
                        "target_market_id": int(move["target_market_id"]),
                        "defender_team_id": defender_team_id,
                        "alliance_turns": alliance_turns,
                        "protected_markets": sorted(protected_markets),
                    },
                }
            )

    return round(min(0.9, total_penalty), 4), events


def _normalise_note_action(notes: Any) -> str | None:
    if isinstance(notes, dict):
        candidates = [
            notes.get("planned_action"),
            notes.get("action_type"),
            notes.get("intent"),
            notes.get("stance"),
        ]
        for candidate in candidates:
            action = _normalise_note_action(candidate)
            if action:
                return action
        return None

    text = str(notes or "").strip().lower()
    if not text:
        return None
    if "hold" in text or "wait" in text:
        return "hold"
    if "defend" in text or "protect" in text:
        return "defend"
    if "research" in text or "upgrade" in text:
        return "research"
    if "attack" in text or "capture" in text:
        return "attack"
    return None


def _extract_note_market_ids(notes: Any) -> set[int]:
    if isinstance(notes, dict):
        market_ids: set[int] = set()
        for key in (
            "target_market_id",
            "market_id",
        ):
            value = notes.get(key)
            if value not in (None, ""):
                market_ids.add(int(value))

        for key in ("target_market_ids", "market_ids", "targets", "protected_markets"):
            values = notes.get(key) or []
            for value in values:
                if value not in (None, ""):
                    market_ids.add(int(value))
        return market_ids

    text = str(notes or "")
    return {int(match) for match in re.findall(r"\b\d+\b", text)}


def _build_move_signature_counts(
    moves: list[dict[str, Any]],
) -> dict[tuple[str, int | None, int | None, str | None], int]:
    counts: dict[tuple[str, int | None, int | None, str | None], int] = defaultdict(int)
    for move in moves:
        signature = (
            str(move.get("action_type", "hold")),
            _optional_int(move.get("target_market_id")),
            _optional_int(move.get("source_market_id")),
            str(move.get("metadata", {}).get("research_option")).strip().lower()
            if move.get("metadata", {}).get("research_option") is not None
            else None,
        )
        counts[signature] += 1
    return dict(counts)


def _attack_breaks_alliance(move: dict[str, Any]) -> bool:
    metadata = move.get("metadata", {}) or {}
    return bool(
        metadata.get("break_alliance")
        or metadata.get("ignore_commitments")
        or metadata.get("override_commitments")
    )
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
    team_ethics = {
        int(team["team_id"]): _clamp(float(team.get("ethical_score", 0.7)), 0.0, 1.0)
        for team in teams
    }

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
        team_ethics,
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

        protected_markets.extend(
            _normalise_market_id_list(alliance.get("protected_markets") or [])
        )

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
    team_ethics: dict[int, float],
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
                "trust": team_ethics.get(int(owner), 0.7),
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
    is_finished = _is_finished_status(status)

    stage_int = game_state.get("current_stage", GameStage.PLAN)
    # ensure frontend has readable string version of game stage
    stage_str = GameStage(stage_int).name if stage_int in GameStage._value2member_map_ else "UNKNOWN"
    leaderboard = _build_leaderboard(game_state)
    reveal_orders = bool(stage_int >= GameStage.ORDERS or is_finished)
    turn_log = game_state.get("turn_log", {}) or {}

    return {
        "session_uuid": game_state.get("session_uuid"),
        "status": _status_value(status),
        "is_finished": is_finished,
        "game_mode": game_state.get("game_mode"),
        "current_round": game_state.get("current_round", 1),
        "current_stage": stage_str,
        "current_team_turn": game_state.get("current_team_turn"),
        "team_order": game_state.get("team_order", []),
        "finished_round": game_state.get("finished_round"),
        "game_over_reason": game_state.get("game_over_reason"),
        "winner_team_id": game_state.get("winner_team_id"),
        "teams": [
            {
                "team_id": t["team_id"],
                "team_name": t["team_name"],
                "colour": t["colour"],
                "ip": t["ip"],
                "ip_spent_this_turn": t.get("ip_spent_this_turn", 0),
                # ethical score hidden until game end
                "ethical_score": (
                    t["ethical_score"] if is_finished else None
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
                "allocated_ip": int(state.get("allocated_ip", 0)),
                "supporting_teams": list(state.get("supporting_teams", [])),
                "research_upgrades": state.get("research_upgrades", []),
            }
            for market_id, state in market_state.items()
        },
        "leaderboard": leaderboard,
        "final_leaderboard": leaderboard if is_finished else None,
        "active_synergies": game_state.get("active_synergies", []),
        "active_quizzes": [
            quiz_helpers.to_public_quiz_payload(quiz)
            for quiz in (turn_log.get("active_quizzes") or [])
        ],
        "quiz_results_submitted_markets": sorted(
            int(market_id)
            for market_id in (turn_log.get("quiz_results") or {}).keys()
        ),
        "resolution_outcomes": turn_log.get("resolution_outcomes", []),
        "alliance_offers": [
            {
                "offer_id": offer["offer_id"],
                "proposer_team_id": offer["proposer_team_id"],
                "recipient_team_id": offer["recipient_team_id"],
                "members": offer.get("members", []),
                "type": offer.get("type", "alliance"),
                "protected_markets": offer.get("protected_markets", []),
                "status": offer.get("status", "pending"),
                "proposed_turn": offer.get("proposed_turn"),
                "resolved_turn": offer.get("resolved_turn"),
                "resolved_by_team_id": offer.get("resolved_by_team_id"),
                "alliance_id": offer.get("alliance_id"),
                "rejection_reason": offer.get("rejection_reason"),
                "notes": offer.get("notes"),
            }
            for offer in (turn_log.get("alliance_offers") or [])
        ],
        "alliances": [
            {
                "alliance_id": a["alliance_id"],
                "members": a["members"],
                "type": a["type"],
                "formed_turn": a["formed_turn"],
                "protected_markets": a.get("protected_markets", []),
                "status": a.get("status", "active"),
                "broken_turn": a.get("broken_turn"),
                "broken_by_team_id": a.get("broken_by_team_id"),
                "broken_reason": a.get("broken_reason"),
            }
            for a in (game_state.get("alliances") or [])
        ],
        "plan_notes": turn_log.get("plan_notes", {}),
        "plan_allocations": turn_log.get("plan_allocations", {}) if reveal_orders else {},
        "plan_allocations_submitted_team_ids": sorted(
            int(team_id)
            for team_id in (turn_log.get("plan_allocations") or {}).keys()
        ),
        "declared_moves": turn_log.get("declared_moves", {}),
        "actual_moves": turn_log.get("actual_moves", {}) if reveal_orders else {},
        "prepared_moves": turn_log.get("prepared_moves", {}) if reveal_orders else {},
        "move_reveal_available": reveal_orders,
    }


def _build_leaderboard(game_state: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Builds a leaderboard from current game state.

    During the game, teams are ordered by IP and markets controlled.
    Once finished, ethical score becomes part of the final ranking order.

    Args:
        game_state (dict): The global game state dictionary.

    Returns:
        list[dict]: A list of team dictionaries sorted by IP, each containing team_id, team_name, ip, and colour.
    """
    teams = game_state.get("teams") or []
    market_state = game_state.get("market_state") or {}
    is_finished = _is_finished_status(game_state.get("status", SessionStatus.IN_PROGRESS))

    markets_per_team: dict[int, int] = {}
    for state in market_state.values():
        owner = state.get("owner")
        if owner:
            numeric_owner = int(owner)
            markets_per_team[numeric_owner] = markets_per_team.get(numeric_owner, 0) + 1

    entries = [
        {
            "team_id": int(t["team_id"]),
            "team_name": t["team_name"],
            "colour": t["colour"],
            "ip": int(t["ip"]),
            "markets_controlled": markets_per_team.get(int(t["team_id"]), 0),
            "ethical_score": float(t["ethical_score"]) if is_finished else None,
        }
        for t in teams
    ]

    sorted_entries = sorted(
        entries,
        key=lambda entry: (
            -entry["ip"],
            -entry["markets_controlled"],
            -(entry["ethical_score"] if entry["ethical_score"] is not None else 0.0),
            entry["team_id"],
        ),
    )
    for index, entry in enumerate(sorted_entries, start=1):
        entry["rank"] = index

    return sorted_entries


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

