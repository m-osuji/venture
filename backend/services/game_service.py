"""
Thin service layer for Venture game operations.

This wraps the lower-level helper modules so the rest of the project can use
simple stateful operations without repeatedly handling JSON load/save logic.
"""

from __future__ import annotations

import random
from typing import Any

from backend.ai_opponent.agents.decision_maker import (
    choose_declared_and_actual_moves,
    choose_orders,
    choose_plan_allocations,
    get_decision_traits,
)
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


def configure_opening_setup(
    team_order: list[int],
    opening_assignments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    Persist opening turn order and starting market ownership after the tournament.
    """
    state = _load_required_state()
    resolved_team_order = _complete_team_order(state, team_order)
    resolved_assignments = list(opening_assignments or [])
    _fill_missing_opening_assignments(state, resolved_team_order, resolved_assignments)
    gameplay_helpers.configure_opening_setup(state, resolved_team_order, resolved_assignments)
    return _save_and_return(state)


def submit_plan_notes(team_id: int, notes: Any) -> dict[str, Any]:
    """
    Persist one team's plan-stage notes.
    """
    state = _load_required_state()
    gameplay_helpers.submit_plan_notes(state, team_id, notes)
    return _save_and_return(state)


def submit_plan_allocations(team_id: int, allocations: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Persist one team's planning-stage IP allocations.
    """
    state = _load_required_state()
    gameplay_helpers.submit_plan_allocations(state, team_id, allocations)
    return _save_and_return(state)


def submit_declared_moves(team_id: int, moves: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Persist one team's negotiation-stage declared moves.
    """
    state = _load_required_state()
    gameplay_helpers.submit_declared_moves(state, team_id, moves)
    return _save_and_return(state)


def submit_alliance_intent(team_id: int, ally_team_id: int | None) -> dict[str, Any]:
    """
    Persist one team's alliance preference for the current negotiation round.
    """
    state = _load_required_state()
    gameplay_helpers.submit_alliance_intent(state, team_id, ally_team_id)
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
    _auto_play_ai_for_current_stage(state)
    gameplay_helpers.advance_stage(state, force=force)
    _auto_play_ai_for_current_stage(state)
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


def _complete_team_order(state: dict[str, Any], team_order: list[int]) -> list[int]:
    provided = [int(team_id) for team_id in (team_order or [])]
    known_ids = [int(team["team_id"]) for team in (state.get("teams") or [])]
    for team_id in known_ids:
        if team_id not in provided:
            provided.append(team_id)
    return provided


def _fill_missing_opening_assignments(
    state: dict[str, Any],
    team_order: list[int],
    opening_assignments: list[dict[str, Any]],
) -> None:
    assigned_team_ids = {
        int(entry["team_id"])
        for entry in opening_assignments
        if entry.get("team_id") is not None
    }
    used_market_ids: set[int] = set()
    for entry in opening_assignments:
        used_market_ids.add(
            gameplay_helpers._resolve_opening_market_id(  # type: ignore[attr-defined]
                state,
                market_id=entry.get("market_id"),
                market_slug=entry.get("market_slug"),
                used_market_ids=used_market_ids,
            )
        )

    for team_id in team_order:
        numeric_team_id = int(team_id)
        if numeric_team_id in assigned_team_ids:
            continue
        market_id = _choose_opening_market_for_team(state, numeric_team_id, used_market_ids)
        opening_assignments.append({"team_id": numeric_team_id, "market_id": market_id})
        assigned_team_ids.add(numeric_team_id)
        used_market_ids.add(market_id)


def _choose_opening_market_for_team(
    state: dict[str, Any],
    team_id: int,
    used_market_ids: set[int],
) -> int:
    team = next(
        (entry for entry in (state.get("teams") or []) if int(entry["team_id"]) == int(team_id)),
        {},
    )
    is_ai = bool(team.get("is_ai", False))
    candidates: list[tuple[float, int]] = []

    for market_id_str, market in (state.get("market_state") or {}).items():
        market_id = int(market_id_str)
        if market_id in used_market_ids:
            continue

        size_score = _enum_text_score(market.get("_size"))
        growth_score = _enum_text_score(market.get("_growth_potential"))
        regulation_score = _enum_text_score(market.get("_regulation_level"))
        security_score = _enum_text_score(market.get("_security_risk"))

        if is_ai:
            score = (size_score * 1.4) + (growth_score * 1.2) - (regulation_score * 0.6) - (security_score * 0.35)
        else:
            score = (size_score * 1.2) + growth_score - (regulation_score * 0.4) - (security_score * 0.2)

        candidates.append((score, market_id))

    if not candidates:
        raise ValueError("[game_service] No opening markets remain to assign.")

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return int(candidates[0][1])


def _auto_play_ai_for_current_stage(state: dict[str, Any]) -> None:
    stage = GameStage(int(state.get("current_stage", GameStage.PLAN)))
    if stage == GameStage.PLAN:
        _ensure_ai_plan_submissions(state)
        return
    if stage == GameStage.NEGOTIATE:
        _ensure_ai_negotiation_submissions(state)
        return
    if stage == GameStage.ORDERS:
        _ensure_ai_order_submissions(state)
        return
    if stage == GameStage.RESOLVE:
        _ensure_ai_quiz_results(state)


def _ensure_ai_plan_submissions(state: dict[str, Any]) -> None:
    turn_log = state.setdefault("turn_log", gameplay_helpers._empty_turn_log())  # type: ignore[attr-defined]
    plan_notes = turn_log.setdefault("plan_notes", {})
    plan_allocations = turn_log.setdefault("plan_allocations", {})
    difficulty = _ai_difficulty(state)

    for team in _ai_teams(state):
        team_id = int(team["team_id"])
        if str(team_id) in plan_notes or str(team_id) in plan_allocations:
            continue

        context = _build_ai_context_from_state(state, team_id)
        decision = choose_plan_allocations(context, difficulty=difficulty)
        gameplay_helpers.submit_plan_notes(
            state,
            team_id,
            {
                "source": "ai_auto_plan",
                "strategy": decision.get("strategy", "AI auto-generated planning allocations."),
            },
        )
        gameplay_helpers.submit_plan_allocations(
            state,
            team_id,
            list(decision.get("allocations") or []),
        )


def _ensure_ai_negotiation_submissions(state: dict[str, Any]) -> None:
    turn_log = state.setdefault("turn_log", gameplay_helpers._empty_turn_log())  # type: ignore[attr-defined]
    declared_moves = turn_log.setdefault("declared_moves", {})
    stored_actual = turn_log.setdefault("ai_actual_move_drafts", {})
    alliance_intents = turn_log.setdefault("alliance_intents", {})
    difficulty = _ai_difficulty(state)

    for team in _ai_teams(state):
        team_id = int(team["team_id"])
        if str(team_id) not in declared_moves:
            context = _build_ai_context_from_state(state, team_id)
            decision = choose_declared_and_actual_moves(context, difficulty=difficulty)
            actual_moves = _normalise_ai_actual_moves(state, team_id, list(decision.get("actual_moves") or []))
            declared_moves_for_team = _normalise_ai_declared_moves(
                state,
                team_id,
                list(decision.get("declared_moves") or []),
                actual_moves,
                difficulty=difficulty,
            )
            gameplay_helpers.submit_declared_moves(
                state,
                team_id,
                declared_moves_for_team,
            )
            stored_actual[str(team_id)] = actual_moves

        if str(team_id) not in alliance_intents:
            gameplay_helpers.submit_alliance_intent(
                state,
                team_id,
                _choose_ai_alliance_intent(state, team_id, difficulty),
            )


def _ensure_ai_order_submissions(state: dict[str, Any]) -> None:
    turn_log = state.setdefault("turn_log", gameplay_helpers._empty_turn_log())  # type: ignore[attr-defined]
    actual_moves = turn_log.setdefault("actual_moves", {})
    stored_actual = turn_log.setdefault("ai_actual_move_drafts", {})
    difficulty = _ai_difficulty(state)

    for team in _ai_teams(state):
        team_id = int(team["team_id"])
        if str(team_id) in actual_moves:
            continue

        moves = stored_actual.get(str(team_id))
        if moves is None:
            context = _build_ai_context_from_state(state, team_id)
            decision = choose_orders(context, difficulty=difficulty)
            moves = list(decision.get("orders") or [])
        moves = _normalise_ai_actual_moves(state, team_id, list(moves or []))

        gameplay_helpers.submit_actual_moves(state, team_id, moves)


def _ensure_ai_quiz_results(state: dict[str, Any]) -> None:
    turn_log = state.setdefault("turn_log", gameplay_helpers._empty_turn_log())  # type: ignore[attr-defined]
    quizzes = turn_log.get("active_quizzes", []) or []
    recorded_results = turn_log.setdefault("quiz_results", {})
    ai_team_ids = {int(team["team_id"]) for team in _ai_teams(state)}
    difficulty = _ai_difficulty(state)

    for quiz in quizzes:
        market_id = int(quiz["market_id"])
        existing_results = {
            int(result["team_id"]): dict(result)
            for result in (recorded_results.get(str(market_id), {}).get("team_results") or [])
            if result.get("team_id") is not None
        }

        changed = False
        for team_id in (int(entry) for entry in (quiz.get("participant_team_ids") or [])):
            if team_id not in ai_team_ids or team_id in existing_results:
                continue
            existing_results[team_id] = _build_ai_quiz_result(quiz, team_id, difficulty)
            changed = True

        if changed:
            gameplay_helpers.submit_quiz_results(
                state,
                market_id,
                list(existing_results.values()),
            )


def _build_ai_quiz_result(quiz: dict[str, Any], team_id: int, difficulty: str) -> dict[str, Any]:
    traits = get_decision_traits(difficulty)
    questions = list(quiz.get("questions") or [])
    quiz_topic = str(quiz.get("quiz_topic") or "").strip().lower()
    topic_strengths = {
        str(key).strip().lower(): float(value)
        for key, value in (traits.get("topic_strengths") or {}).items()
    }
    default_strength = float(traits.get("quiz_strength", 0.6))
    answers: list[dict[str, Any]] = []

    for question in questions:
        correct_answer = str(question.get("answer") or "option_1")
        difficulty_key = str(question.get("difficulty_level") or "medium").strip().lower()
        question_topic = str(question.get("topic") or quiz_topic).strip().lower()
        topic_strength = topic_strengths.get(question_topic, topic_strengths.get(quiz_topic, default_strength))
        difficulty_modifier = {"easy": 0.14, "medium": 0.0, "hard": -0.12}.get(difficulty_key, 0.0)
        chance_correct = min(0.97, max(0.2, (default_strength * 0.5) + (topic_strength * 0.5) + difficulty_modifier))

        if random.random() <= chance_correct:
            selected_option = correct_answer
        else:
            distractors = [
                option_key
                for option_key in ("option_1", "option_2", "option_3", "option_4")
                if option_key != correct_answer
            ]
            selected_option = random.choice(distractors)

        response_time_ms = _ai_response_time_ms(difficulty, was_correct=selected_option == correct_answer)
        answers.append(
            {
                "question_id": int(question["question_id"]),
                "selected_option": selected_option,
                "response_time_ms": response_time_ms,
            }
        )

    return {
        "team_id": int(team_id),
        "questions": questions,
        "answers": answers,
    }


def _ai_response_time_ms(difficulty: str, *, was_correct: bool) -> int:
    difficulty_key = str(difficulty or "medium").strip().lower()
    if difficulty_key == "easy":
        return random.randint(7000, 15000 if was_correct else 22000)
    if difficulty_key == "hard":
        return random.randint(2200, 6500 if was_correct else 9500)
    return random.randint(4000, 9000 if was_correct else 14000)


def _ai_teams(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [team for team in (state.get("teams") or []) if bool(team.get("is_ai", False))]


def _ai_difficulty(state: dict[str, Any]) -> str:
    return str(state.get("ai_difficulty") or "medium").strip().lower()


def _build_ai_context_from_state(state: dict[str, Any], team_id: int) -> dict[str, Any]:
    context = gameplay_helpers.build_agent_context(state, team_id)
    context["current_stage"] = GameStage(int(state.get("current_stage", GameStage.PLAN))).name
    return context


def _moves_are_only_hold_or_empty(moves: list[dict[str, Any]]) -> bool:
    if not moves:
        return True
    return all(str(move.get("action_type") or "hold").strip().lower() == "hold" for move in moves)


def _build_declared_moves_from_actual(moves: list[dict[str, Any]]) -> list[dict[str, Any]]:
    declared_moves: list[dict[str, Any]] = []
    for move in moves:
        declared_moves.append(
            {
                "action_type": move.get("action_type", "hold"),
                "target_market_id": move.get("target_market_id"),
                "source_market_id": move.get("source_market_id"),
                "ip_spent": move.get("ip_spent", 0),
                "metadata": dict(move.get("metadata") or {}),
            }
        )
    return declared_moves


def _normalise_ai_actual_moves(
    state: dict[str, Any],
    team_id: int,
    moves: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not _moves_are_only_hold_or_empty(moves):
        return moves

    fallback_move = _build_market_backed_ai_attack(state, team_id)
    if fallback_move is not None:
        return [fallback_move]

    return moves or [{"action_type": "hold", "ip_spent": 0, "metadata": {"reason": "no_viable_orders"}}]


def _normalise_ai_declared_moves(
    state: dict[str, Any],
    team_id: int,
    declared_moves: list[dict[str, Any]],
    actual_moves: list[dict[str, Any]],
    *,
    difficulty: str,
) -> list[dict[str, Any]]:
    if _moves_are_only_hold_or_empty(actual_moves):
        return declared_moves or [{"action_type": "hold", "ip_spent": 0, "metadata": {"declared": True}}]

    cleaned_declared = declared_moves or _build_declared_moves_from_actual(actual_moves)
    if _moves_are_only_hold_or_empty(cleaned_declared) and not _moves_are_only_hold_or_empty(actual_moves):
        return cleaned_declared

    if not _declared_moves_match_actual(cleaned_declared, actual_moves):
        return cleaned_declared

    decoy = _build_ai_declared_decoy(state, team_id, actual_moves, difficulty=difficulty)
    return decoy or cleaned_declared


def _declared_moves_match_actual(declared_moves: list[dict[str, Any]], actual_moves: list[dict[str, Any]]) -> bool:
    if len(declared_moves) != len(actual_moves):
        return False

    for declared_move, actual_move in zip(declared_moves, actual_moves):
        if str(declared_move.get("action_type") or "hold") != str(actual_move.get("action_type") or "hold"):
            return False
        if int(declared_move.get("target_market_id") or 0) != int(actual_move.get("target_market_id") or 0):
            return False
        if int(declared_move.get("source_market_id") or 0) != int(actual_move.get("source_market_id") or 0):
            return False
        if str((declared_move.get("metadata") or {}).get("research_option") or "") != str((actual_move.get("metadata") or {}).get("research_option") or ""):
            return False
    return True


def _build_ai_declared_decoy(
    state: dict[str, Any],
    team_id: int,
    actual_moves: list[dict[str, Any]],
    *,
    difficulty: str,
) -> list[dict[str, Any]] | None:
    difficulty_key = str(difficulty or "medium").strip().lower()
    bluff_chance = {
        "easy": 0.45,
        "medium": 0.32,
        "hard": 0.58,
    }.get(difficulty_key, 0.32)
    if random.random() >= bluff_chance:
        return None

    first_move = actual_moves[0] if actual_moves else {}
    action_type = str(first_move.get("action_type") or "hold").strip().lower()

    if action_type == "attack":
        decoy_attack = _build_ai_declared_attack_decoy(state, team_id, first_move, difficulty=difficulty_key)
        if decoy_attack is not None:
            return [decoy_attack]
        return [{"action_type": "hold", "ip_spent": 0, "metadata": {"declared": True, "reason": "concealed_attack"}}]

    if action_type == "research":
        declared_move = dict(first_move)
        declared_move["metadata"] = dict(first_move.get("metadata") or {})
        declared_move["metadata"]["declared"] = True
        declared_move["metadata"]["reason"] = "softened_research_claim"
        if random.random() < 0.5:
            declared_move["action_type"] = "hold"
            declared_move["ip_spent"] = 0
            declared_move["source_market_id"] = first_move.get("source_market_id")
            declared_move["target_market_id"] = first_move.get("target_market_id")
        return [declared_move]

    return None


def _build_ai_declared_attack_decoy(
    state: dict[str, Any],
    team_id: int,
    actual_move: dict[str, Any],
    *,
    difficulty: str,
) -> dict[str, Any] | None:
    ranked_targets = _rank_ai_target_markets(state, team_id)
    actual_target_id = int(actual_move.get("target_market_id") or 0)
    alternatives = [entry for entry in ranked_targets if int(entry["market_id"]) != actual_target_id]
    if not alternatives:
        return None

    top_score = float(alternatives[0]["score"])
    close_alternatives = [entry for entry in alternatives if top_score - float(entry["score"]) <= 1.15]
    pool = close_alternatives[:3] or alternatives[:2]
    chosen = random.choice(pool)

    declared_ip = max(1, min(int(actual_move.get("ip_spent") or 1), 2 if difficulty == "easy" else 3))
    return {
        "action_type": "attack",
        "target_market_id": int(chosen["market_id"]),
        "source_market_id": actual_move.get("source_market_id"),
        "ip_spent": declared_ip,
        "metadata": {
            "declared": True,
            "resource_pool": "market_ip",
            "reason": "decoy_attack",
        },
    }


def _build_market_backed_ai_attack(state: dict[str, Any], team_id: int) -> dict[str, Any] | None:
    context = _build_ai_context_from_state(state, team_id)
    owned_markets = list(context.get("owned_markets") or [])
    market_states = context.get("market_states") or {}
    ranked_targets = _rank_ai_target_markets(state, team_id)

    if not owned_markets or not ranked_targets:
        return None

    sources = sorted(
        owned_markets,
        key=lambda market_id: (
            -int((market_states.get(market_id) or {}).get("allocated_ip", 0)),
            -_score_ai_target_market((state.get("market_state") or {}).get(str(market_id)) or {}),
            market_id,
        ),
    )
    source_market_id = next(
        (
            market_id
            for market_id in sources
            if int((market_states.get(market_id) or {}).get("allocated_ip", 0)) > 0
        ),
        None,
    )
    if source_market_id is None:
        return None

    available_market_ip = int((market_states.get(source_market_id) or {}).get("allocated_ip", 0))
    if available_market_ip <= 0:
        return None

    target_market_id = _choose_ai_target_market(ranked_targets, difficulty=_ai_difficulty(state))

    max_commitment = min(available_market_ip, 3)
    ip_spent = random.randint(1, max_commitment) if max_commitment > 1 else 1

    return {
        "action_type": "attack",
        "target_market_id": int(target_market_id),
        "source_market_id": int(source_market_id),
        "ip_spent": int(ip_spent),
        "metadata": {
            "resource_pool": "market_ip",
            "reason": "ai_market_backed_attack",
        },
    }


def _score_ai_target_market(market: dict[str, Any]) -> float:
    defense = float(market.get("allocated_ip", 0)) + float(market.get("fortification_level", 0))
    size_score = _enum_text_score(market.get("_size"))
    growth_score = _enum_text_score(market.get("_growth_potential"))
    regulation_score = _enum_text_score(market.get("_regulation_level"))
    security_score = _enum_text_score(market.get("_security_risk"))
    owner_bonus = 1.2 if market.get("owner") is not None else 0.7
    return (size_score * 1.4) + (growth_score * 1.1) + owner_bonus - (defense * 0.85) - (regulation_score * 0.35) - (security_score * 0.2)


def _choose_ai_alliance_intent(state: dict[str, Any], team_id: int, difficulty: str) -> int | None:
    traits = get_decision_traits(difficulty)
    candidates = [
        team
        for team in (state.get("teams") or [])
        if int(team["team_id"]) != int(team_id)
        and gameplay_helpers._find_active_alliance_between(state, team_id, int(team["team_id"])) is None  # type: ignore[attr-defined]
    ]
    if not candidates:
        return None

    alliance_chance = max(
        0.0,
        min(
            0.8,
            0.12
            + (float(traits.get("ethical_bias", 0.5)) * 0.35)
            + (float(traits.get("defense_bias", 0.5)) * 0.15)
            - (float(traits.get("aggression", 0.5)) * 0.12),
        ),
    )
    if random.random() > alliance_chance:
        return None

    market_state = state.get("market_state") or {}
    candidates.sort(
        key=lambda team: (
            bool(team.get("is_ai", False)),
            -float(team.get("ethical_score", 1.0)),
            -sum(
                1
                for market in market_state.values()
                if int(market.get("owner") or 0) == int(team["team_id"])
            ),
            int(team["team_id"]),
        )
    )
    return int(candidates[0]["team_id"])


def _rank_ai_target_markets(state: dict[str, Any], team_id: int) -> list[dict[str, float | int]]:
    context = _build_ai_context_from_state(state, team_id)
    raw_market_state = state.get("market_state") or {}
    ranked = []
    for market_id in list(context.get("attackable_markets") or []):
        ranked.append(
            {
                "market_id": int(market_id),
                "score": _score_ai_target_market(raw_market_state.get(str(market_id)) or {}),
            }
        )
    ranked.sort(key=lambda entry: (-float(entry["score"]), int(entry["market_id"])))
    return ranked


def _choose_ai_target_market(ranked_targets: list[dict[str, float | int]], *, difficulty: str) -> int:
    if not ranked_targets:
        raise ValueError("[game_service] No AI target markets available to choose from.")

    difficulty_key = str(difficulty or "medium").strip().lower()
    top_score = float(ranked_targets[0]["score"])
    close_margin = {"easy": 1.6, "medium": 1.1, "hard": 0.7}.get(difficulty_key, 1.1)
    pool_size = {"easy": 3, "medium": 2, "hard": 2}.get(difficulty_key, 2)
    close_targets = [entry for entry in ranked_targets if top_score - float(entry["score"]) <= close_margin]
    pool = close_targets[:pool_size] or ranked_targets[:1]

    if difficulty_key == "hard" and len(pool) > 1 and random.random() < 0.7:
        return int(pool[0]["market_id"])
    if difficulty_key == "medium" and len(pool) > 1 and random.random() < 0.45:
        return int(pool[0]["market_id"])
    return int(random.choice(pool)["market_id"])


def _enum_text_score(value: Any) -> float:
    lookup = {
        "low": 1.0,
        "small": 1.0,
        "medium": 2.0,
        "high": 3.0,
        "large": 3.0,
        "very high": 4.0,
        "very large": 4.0,
    }
    return lookup.get(str(value or "").strip().lower(), 0.0)
