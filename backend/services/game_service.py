"""
Thin service layer for Venture game operations.

This wraps the lower-level helper modules so the rest of the project can use
simple stateful operations without repeatedly handling JSON load/save logic.
"""

from __future__ import annotations

from typing import Any

from backend.enums import GameStage
from backend.helpers import gameplay_helpers


def create_game(
    teams: list[dict[str, Any]],
    game_mode: str = "speedrun",
    include_ai: bool = False,
    team_order: list[int] | None = None,
) -> dict[str, Any]:
    """
    Create a fresh game state, optionally set the turn order, and persist it.
    """
    state = gameplay_helpers.init_game_state(
        teams=teams,
        game_mode=game_mode,
        include_ai=include_ai,
    )

    if team_order is not None:
        gameplay_helpers.set_team_order(state, team_order)

    gameplay_helpers.save_state(state)
    return state


def get_game_state() -> dict[str, Any] | None:
    """
    Return the full persisted internal game state, if present.
    """
    return gameplay_helpers.load_state()


def get_public_game_state() -> dict[str, Any] | None:
    """
    Return the frontend-safe view of the persisted game state, if present.
    """
    state = get_game_state()
    if state is None:
        return None
    return gameplay_helpers.get_frontend_state(state)


def set_team_order(team_order: list[int]) -> dict[str, Any]:
    """
    Persist the team turn order for the current game.
    """
    state = _load_required_state()
    gameplay_helpers.set_team_order(state, team_order)
    return _save_and_return(state)


def submit_plan_notes(team_id: int, notes: Any) -> dict[str, Any]:
    """
    Persist one team's plan-stage notes.
    """
    state = _load_required_state()
    gameplay_helpers.submit_plan_notes(state, team_id, notes)
    return _save_and_return(state)


def submit_declared_moves(team_id: int, moves: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Persist one team's negotiation-stage declared moves.
    """
    state = _load_required_state()
    gameplay_helpers.submit_declared_moves(state, team_id, moves)
    return _save_and_return(state)


def propose_alliance(
    proposer_team_id: int,
    recipient_team_id: int,
    *,
    alliance_type: str = "alliance",
    shared_market: int | None = None,
    protected_markets: list[int] | None = None,
    notes: Any = None,
) -> dict[str, Any]:
    """
    Persist a pending alliance offer for the current NEGOTIATE stage.
    """
    state = _load_required_state()
    gameplay_helpers.propose_alliance(
        state,
        proposer_team_id,
        recipient_team_id,
        alliance_type=alliance_type,
        shared_market=shared_market,
        protected_markets=protected_markets,
        notes=notes,
    )
    return _save_and_return(state)


def accept_alliance_offer(offer_id: str, responder_team_id: int) -> dict[str, Any]:
    """
    Accept a pending alliance offer and persist the resulting alliance.
    """
    state = _load_required_state()
    gameplay_helpers.accept_alliance_offer(state, offer_id, responder_team_id)
    return _save_and_return(state)


def reject_alliance_offer(
    offer_id: str,
    responder_team_id: int,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    """
    Reject a pending alliance offer and persist the updated negotiation state.
    """
    state = _load_required_state()
    gameplay_helpers.reject_alliance_offer(
        state,
        offer_id,
        responder_team_id,
        reason=reason,
    )
    return _save_and_return(state)


def break_alliance(
    alliance_id: str,
    acting_team_id: int,
    *,
    reason: str = "manual_break",
) -> dict[str, Any]:
    """
    Explicitly break an active alliance during the NEGOTIATE stage.
    """
    state = _load_required_state()
    gameplay_helpers.break_alliance(
        state,
        alliance_id,
        acting_team_id,
        reason=reason,
    )
    return _save_and_return(state)


def submit_actual_moves(team_id: int, moves: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Persist one team's binding orders for the current round.
    """
    state = _load_required_state()
    gameplay_helpers.submit_actual_moves(state, team_id, moves)
    return _save_and_return(state)


def submit_quiz_results(
    market_id: int, team_results: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Persist quiz results for one market conflict during the RESOLVE stage.
    """
    state = _load_required_state()
    gameplay_helpers.submit_quiz_results(state, market_id, team_results)
    return _save_and_return(state)


def advance_stage(force: bool = False) -> dict[str, Any]:
    """
    Advance the current game to the next stage and persist it.
    """
    state = _load_required_state()
    gameplay_helpers.advance_stage(state, force=force)
    return _save_and_return(state)


def resolve_pending_quizzes(force: bool = False) -> dict[str, Any]:
    """
    Resolve any stored quiz results for the current RESOLVE stage and persist them.
    """
    state = _load_required_state()
    gameplay_helpers.resolve_pending_quizzes(state, force=force)
    return _save_and_return(state)


def build_ai_context(team_id: int) -> dict[str, Any]:
    """
    Return the AI-facing state slice for one team.
    """
    state = _load_required_state()
    return gameplay_helpers.build_agent_context(state, team_id)


def create_demo_game(
    teams: list[dict[str, Any]],
    game_mode: str = "speedrun",
    difficulty: str = "medium",
    team_order: list[int] | None = None,
) -> dict[str, Any]:
    """
    Create a small scripted session for tomorrow's demo.
    """
    include_ai = any(team.get("is_ai") for team in teams)
    state = create_game(
        teams=teams,
        game_mode=game_mode,
        include_ai=include_ai,
        team_order=team_order,
    )

    state["ai_difficulty"] = str(difficulty or "medium").strip().lower()
    state["rules"]["max_rounds"] = 1

    ordered_team_ids = state.get("team_order") or [int(team["team_id"]) for team in state["teams"]]
    if len(ordered_team_ids) < 2:
        raise ValueError("[game_service] Demo mode needs at least two teams.")

    attacker_team_id = int(ordered_team_ids[0])
    defender_team_id = int(ordered_team_ids[1])
    support_team_ids = [int(team_id) for team_id in ordered_team_ids[2:]]

    attacker_home = _find_market_id_by_name(state, "Technology")
    defender_home = _find_market_id_by_name(state, "Finance")
    target_market = _find_market_id_by_name(state, "Cybersecurity")
    reserve_markets = [
        _find_market_id_by_name(state, "Food & Water", required=False),
        _find_market_id_by_name(state, "Energy", required=False),
        _find_market_id_by_name(state, "Education", required=False),
    ]

    _seed_demo_market_control(
        state,
        attacker_team_id,
        defender_team_id,
        support_team_ids,
        attacker_home,
        defender_home,
        target_market,
        reserve_markets,
    )

    state["demo_script"] = {
        "enabled": True,
        "scenario": "scripted_round",
        "step_index": 0,
        "attacker_team_id": attacker_team_id,
        "defender_team_id": defender_team_id,
        "support_team_ids": support_team_ids,
        "attacker_home_market_id": attacker_home,
        "defender_home_market_id": defender_home,
        "target_market_id": target_market,
        "last_message": (
            f"{_team_name(state, attacker_team_id)} is preparing a push into "
            f"{_market_name(state, target_market)}."
        ),
    }

    gameplay_helpers.save_state(state)
    return state


def run_demo_step() -> dict[str, Any]:
    """
    Advance one scripted step of the small browser demo.
    """
    state = _load_required_state()
    demo_script = state.get("demo_script") or {}
    if not demo_script.get("enabled"):
        raise ValueError("[game_service] No scripted demo is active.")

    if gameplay_helpers._is_finished_status(state.get("status")):
        return state

    current_stage = GameStage(int(state.get("current_stage", GameStage.PLAN)))
    attacker_team_id = int(demo_script["attacker_team_id"])
    defender_team_id = int(demo_script["defender_team_id"])
    target_market_id = int(demo_script["target_market_id"])
    attacker_home_market_id = int(demo_script["attacker_home_market_id"])
    defender_home_market_id = int(demo_script["defender_home_market_id"])
    support_team_ids = [int(team_id) for team_id in demo_script.get("support_team_ids", [])]

    if current_stage == GameStage.PLAN:
        gameplay_helpers.submit_plan_notes(
            state,
            attacker_team_id,
            {
                "planned_action": "attack",
                "target_market_id": target_market_id,
                "source_market_id": attacker_home_market_id,
            },
        )
        gameplay_helpers.submit_plan_notes(
            state,
            defender_team_id,
            {
                "planned_action": "hold",
                "target_market_id": defender_home_market_id,
            },
        )
        for team_id in support_team_ids:
            gameplay_helpers.submit_plan_notes(
                state,
                team_id,
                {"planned_action": "hold"},
            )
        gameplay_helpers.advance_stage(state)
        demo_script["last_message"] = (
            f"{_team_name(state, attacker_team_id)} spots an opening in "
            f"{_market_name(state, target_market_id)} during the planning phase."
        )

    elif current_stage == GameStage.NEGOTIATE:
        gameplay_helpers.submit_declared_moves(
            state,
            attacker_team_id,
            [
                _demo_attack_move(target_market_id, ip_spent=2),
            ],
        )
        gameplay_helpers.submit_declared_moves(state, defender_team_id, [])
        for team_id in support_team_ids:
            gameplay_helpers.submit_declared_moves(state, team_id, [])
        gameplay_helpers.advance_stage(state)
        demo_script["last_message"] = (
            f"Negotiations end quietly. {_team_name(state, attacker_team_id)} keeps the "
            f"attack on {_market_name(state, target_market_id)} hidden until orders lock."
        )

    elif current_stage == GameStage.ORDERS:
        gameplay_helpers.submit_actual_moves(
            state,
            attacker_team_id,
            [_demo_attack_move(target_market_id, ip_spent=2)],
        )
        gameplay_helpers.submit_actual_moves(state, defender_team_id, [])
        for team_id in support_team_ids:
            gameplay_helpers.submit_actual_moves(state, team_id, [])
        gameplay_helpers.advance_stage(state)
        demo_script["last_message"] = (
            f"Orders are revealed: {_team_name(state, attacker_team_id)} launches the "
            f"attack on {_market_name(state, target_market_id)}."
        )

    elif current_stage == GameStage.RESOLVE:
        active_quizzes = state.get("turn_log", {}).get("active_quizzes") or []
        if active_quizzes:
            target_quiz = next(
                (
                    quiz
                    for quiz in active_quizzes
                    if int(quiz.get("market_id", -1)) == target_market_id
                ),
                active_quizzes[0],
            )
            gameplay_helpers.submit_quiz_results(
                state,
                int(target_quiz["market_id"]),
                _build_demo_quiz_results(
                    target_quiz,
                    attacker_team_id,
                    defender_team_id,
                ),
            )
        gameplay_helpers.advance_stage(state)
        demo_script["last_message"] = (
            f"The quiz swings the battle. {_team_name(state, attacker_team_id)} wins "
            f"{_market_name(state, target_market_id)} on stronger answers."
        )

    elif current_stage == GameStage.UPDATE:
        gameplay_helpers.advance_stage(state)
        winner_team_id = state.get("winner_team_id") or attacker_team_id
        demo_script["last_message"] = (
            f"Round complete. {_team_name(state, winner_team_id)} finishes on top of the "
            "leaderboard after the market takeover."
        )

    else:
        raise ValueError(f"[game_service] Unsupported demo stage {current_stage.name}.")

    demo_script["step_index"] = int(demo_script.get("step_index", 0)) + 1
    gameplay_helpers.save_state(state)
    return state


def _load_required_state() -> dict[str, Any]:
    state = gameplay_helpers.load_state()
    if state is None:
        raise ValueError("[game_service] No active game state found. Create a game first.")
    return state


def _save_and_return(state: dict[str, Any]) -> dict[str, Any]:
    gameplay_helpers.save_state(state)
    return state


def _find_market_id_by_name(
    state: dict[str, Any], market_name: str, *, required: bool = True
) -> int | None:
    desired = str(market_name).strip().lower()
    for market_id, market in (state.get("market_state") or {}).items():
        if str(market.get("_market_name", "")).strip().lower() == desired:
            return int(market_id)
    if required:
        raise ValueError(f"[game_service] Demo market '{market_name}' was not found.")
    return None


def _seed_demo_market_control(
    state: dict[str, Any],
    attacker_team_id: int,
    defender_team_id: int,
    support_team_ids: list[int],
    attacker_home_market_id: int,
    defender_home_market_id: int,
    target_market_id: int,
    reserve_markets: list[int | None],
) -> None:
    market_state = state.get("market_state") or {}

    for team in state.get("teams", []):
        team_id = int(team["team_id"])
        team["ip"] = 4
        if team_id == attacker_team_id:
            team["ip"] = 6
        elif team_id == defender_team_id:
            team["ip"] = 3
        team["ip_spent_this_turn"] = 0
        team["ethical_score"] = 1.0

    for market in market_state.values():
        market["owner"] = None
        market["contested"] = False
        market["supporting_teams"] = []
        market["allocated_ip"] = 0
        market["research_upgrades"] = []

    market_state[str(attacker_home_market_id)]["owner"] = attacker_team_id
    market_state[str(attacker_home_market_id)]["allocated_ip"] = 1
    market_state[str(defender_home_market_id)]["owner"] = defender_team_id
    market_state[str(defender_home_market_id)]["allocated_ip"] = 1
    market_state[str(target_market_id)]["owner"] = defender_team_id
    market_state[str(target_market_id)]["allocated_ip"] = 1

    for team_id, reserve_market_id in zip(support_team_ids, reserve_markets):
        if reserve_market_id is None:
            continue
        market_state[str(int(reserve_market_id))]["owner"] = int(team_id)
        market_state[str(int(reserve_market_id))]["allocated_ip"] = 1

    gameplay_helpers._refresh_active_synergies(state)
    gameplay_helpers._refresh_market_estimates(state)


def _demo_attack_move(target_market_id: int, *, ip_spent: int) -> dict[str, Any]:
    return {
        "action_type": "attack",
        "target_market_id": int(target_market_id),
        "ip_spent": int(ip_spent),
        "metadata": {"resource_pool": "current_ip"},
    }


def _build_demo_quiz_results(
    quiz: dict[str, Any],
    attacker_team_id: int,
    defender_team_id: int,
) -> list[dict[str, Any]]:
    attacker_answers: list[dict[str, Any]] = []
    defender_answers: list[dict[str, Any]] = []

    for index, question in enumerate(quiz.get("questions", [])):
        correct_option = question["answer"]
        attacker_answers.append(
            {
                "question_id": int(question["question_id"]),
                "selected_option": correct_option,
                "response_time_ms": 850 + (index * 180),
            }
        )

        defender_option = correct_option
        if index == len(quiz.get("questions", [])) - 1:
            defender_option = "option_1" if correct_option != "option_1" else "option_2"

        defender_answers.append(
            {
                "question_id": int(question["question_id"]),
                "selected_option": defender_option,
                "response_time_ms": 1150 + (index * 220),
            }
        )

    return [
        {"team_id": int(attacker_team_id), "answers": attacker_answers},
        {"team_id": int(defender_team_id), "answers": defender_answers},
    ]


def _team_name(state: dict[str, Any], team_id: int) -> str:
    team = next(
        (team for team in (state.get("teams") or []) if int(team["team_id"]) == int(team_id)),
        None,
    )
    return team["team_name"] if team else f"Team {team_id}"


def _market_name(state: dict[str, Any], market_id: int) -> str:
    market = (state.get("market_state") or {}).get(str(int(market_id)), {})
    return str(market.get("_market_name") or f"Market {market_id}")
