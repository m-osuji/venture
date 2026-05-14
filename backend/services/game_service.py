"""
Thin service layer for Venture game operations.

This wraps the lower-level helper modules so the rest of the project can use
simple stateful operations without repeatedly handling JSON load/save logic.
"""

from __future__ import annotations

from typing import Any

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


def _load_required_state() -> dict[str, Any]:
    state = gameplay_helpers.load_state()
    if state is None:
        raise ValueError("[game_service] No active game state found. Create a game first.")
    return state


def _save_and_return(state: dict[str, Any]) -> dict[str, Any]:
    gameplay_helpers.save_state(state)
    return state
