"""
Quiz helpers for Venture conflict resolution.

Database-backed question retrieval via db_helpers.fetch_questions.
All formatting, scoring, and conflict resolution logic is unchanged.
"""

from __future__ import annotations

from typing import Any, Iterable

from backend.helpers.db_helpers import fetch_questions as db_fetch_questions


QUIZ_DIFFICULTY_ORDER = ("easy", "medium", "hard")
DEFAULT_QUESTION_TIME_LIMIT_MS = 30_000

ENUM_SCORE_VALUES: dict[str, float] = {
    "small": 1.0,
    "medium": 2.0,
    "large": 3.0,
    "very large": 4.0,
    "low": 1.0,
    "high": 3.0,
    "very high": 4.0,
}

SYNERGY_OPERATOR_VALUES: dict[str, float] = {
    "plus_two": 2.0,
    "plus_one": 1.0,
    "minus_one": -1.0,
    "ignore_one": 0.0,
}


def fetch_questions_by_topic_and_difficulty(
    topic: str,
    difficulty: str,
    limit: int = 1,
    exclude_question_ids: Iterable[int] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch question dictionaries from the database, filtered by topic and difficulty.
    """
    if limit <= 0:
        return []

    topic_key = _normalise_text(topic)
    difficulty_key = _normalise_text(difficulty)
    excluded = {int(qid) for qid in (exclude_question_ids or [])}

    raw_rows = db_fetch_questions(topic=topic, difficulty=difficulty)
    exact_pool = [
        dict(row)
        for row in raw_rows
        if _normalise_text(row["topic"]) == topic_key
        and _normalise_text(row["difficulty_level"]) == difficulty_key
    ]

    if not exact_pool:
        raise ValueError(
            f"[quiz_helpers] No questions available for topic='{topic}' difficulty='{difficulty}'."
        )

    preferred = [q for q in exact_pool if int(q["question_id"]) not in excluded]

    if len(preferred) >= limit:
        return preferred[:limit]

    selected = preferred[:]
    fallback_index = 0
    while len(selected) < limit:
        selected.append(dict(exact_pool[fallback_index % len(exact_pool)]))
        fallback_index += 1
    return selected


def build_quiz_for_conflict(
    conflict: dict[str, Any], used_question_ids: Iterable[int] | None = None
) -> dict[str, Any]:
    """
    Build a three-question quiz payload for a prepared conflict.
    """
    quiz_topic = conflict.get("quiz_topic")
    if not quiz_topic:
        raise ValueError(f"[quiz_helpers] Conflict is missing quiz_topic: {conflict}")

    used_ids = {int(qid) for qid in (used_question_ids or [])}
    selected_questions: list[dict[str, Any]] = []

    for difficulty in QUIZ_DIFFICULTY_ORDER:
        question = fetch_questions_by_topic_and_difficulty(
            quiz_topic,
            difficulty,
            limit=1,
            exclude_question_ids=used_ids,
        )[0]
        selected_questions.append(question)
        used_ids.add(int(question["question_id"]))

    return {
        "market_id": int(conflict["market_id"]),
        "quiz_topic": quiz_topic,
        "conflict_type": conflict.get("conflict_type"),
        "participant_team_ids": _conflict_participant_team_ids(conflict),
        "time_limit_ms": DEFAULT_QUESTION_TIME_LIMIT_MS,
        "questions": selected_questions,
    }


def build_quizzes_for_pending_conflicts(
    game_state: dict[str, Any], used_question_ids: Iterable[int] | None = None
) -> list[dict[str, Any]]:
    """
    Build quiz payloads for every prepared conflict in the current turn.
    """
    used_ids = {int(qid) for qid in (used_question_ids or [])}
    quizzes: list[dict[str, Any]] = []

    for conflict in game_state.get("turn_log", {}).get("conflicts", []):
        quiz = build_quiz_for_conflict(conflict, used_ids)
        quizzes.append(quiz)
        used_ids.update(question["question_id"] for question in quiz["questions"])

    return quizzes


def to_public_quiz_payload(quiz: dict[str, Any]) -> dict[str, Any]:
    """
    Strip answer keys from a quiz payload so it can be sent to the frontend.
    """
    public_questions = [_question_for_frontend(q) for q in quiz.get("questions", [])]
    return {
        "market_id": quiz.get("market_id"),
        "quiz_topic": quiz.get("quiz_topic"),
        "conflict_type": quiz.get("conflict_type"),
        "participant_team_ids": list(quiz.get("participant_team_ids", [])),
        "time_limit_ms": int(quiz.get("time_limit_ms", DEFAULT_QUESTION_TIME_LIMIT_MS)),
        "questions": public_questions,
    }


def score_team_answers(
    questions: list[dict[str, Any]], submitted_answers: list[dict[str, Any]] | None
) -> dict[str, Any]:
    """
    Convert quiz answers into correctness and tiebreak stats.
    """
    answer_lookup = {
        int(a["question_id"]): a
        for a in (submitted_answers or [])
        if a.get("question_id") is not None
    }

    question_results: list[dict[str, Any]] = []
    correct_answers = 0
    total_response_time_ms = 0

    for question in questions:
        question_id = int(question["question_id"])
        submission = answer_lookup.get(question_id, {})
        selected_option = submission.get("selected_option")
        response_time_ms = int(
            submission.get("response_time_ms", DEFAULT_QUESTION_TIME_LIMIT_MS)
        )
        is_correct = selected_option == question.get("answer")

        if is_correct:
            correct_answers += 1

        total_response_time_ms += max(0, response_time_ms)
        question_results.append(
            {
                "question_id": question_id,
                "selected_option": selected_option,
                "correct_option": question.get("answer"),
                "is_correct": is_correct,
                "response_time_ms": max(0, response_time_ms),
            }
        )

    perfect_round_bonus = 1 if questions and correct_answers == len(questions) else 0
    strength_bonus = correct_answers + perfect_round_bonus

    return {
        "questions_answered": len(answer_lookup),
        "correct_answers": correct_answers,
        "perfect_round_bonus": perfect_round_bonus,
        "strength_bonus": strength_bonus,
        "total_response_time_ms": total_response_time_ms,
        "question_results": question_results,
    }


def resolve_conflict_from_quiz(
    game_state: dict[str, Any],
    conflict: dict[str, Any],
    team_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Resolve one prepared conflict using quiz results and existing market
    modifiers from the game state.
    """
    market_id = int(conflict["market_id"])
    results_by_team = {
        int(r["team_id"]): r
        for r in team_results
        if r.get("team_id") is not None
    }

    participants: list[dict[str, Any]] = []
    for team_id in _conflict_participant_team_ids(conflict):
        raw_result = results_by_team.get(team_id, {"team_id": team_id, "answers": []})
        scored_result = _coerce_team_result(conflict, raw_result)

        position_bonus = _position_strength_bonus(game_state, conflict, team_id)
        synergy_bonus = _conflict_synergy_bonus(game_state, market_id, team_id)
        total_strength = scored_result["strength_bonus"] + position_bonus + synergy_bonus

        participants.append(
            {
                "team_id": team_id,
                "is_defender": team_id == _optional_int(conflict.get("defender_team_id")),
                "correct_answers": int(scored_result["correct_answers"]),
                "perfect_round_bonus": int(scored_result["perfect_round_bonus"]),
                "quiz_strength_bonus": float(scored_result["strength_bonus"]),
                "position_bonus": float(position_bonus),
                "synergy_bonus": float(synergy_bonus),
                "total_strength": float(total_strength),
                "total_response_time_ms": int(scored_result["total_response_time_ms"]),
            }
        )

    ranking = sorted(
        participants,
        key=lambda p: (
            -p["total_strength"],
            p["total_response_time_ms"],
            p["team_id"],
        ),
    )

    winner = ranking[0]
    tied_on_strength = [
        p for p in ranking
        if abs(p["total_strength"] - winner["total_strength"]) < 1e-9
    ]

    if len(tied_on_strength) == 1:
        notes = (
            f"Team {winner['team_id']} won on total strength "
            f"{winner['total_strength']:.1f}."
        )
    else:
        lowest_time = min(p["total_response_time_ms"] for p in tied_on_strength)
        tied_on_time = [
            p for p in tied_on_strength
            if p["total_response_time_ms"] == lowest_time
        ]

        if len(tied_on_time) == 1:
            winner = tied_on_time[0]
            notes = f"Team {winner['team_id']} won on tiebreak time after equal strength."
        else:
            winner = sorted(tied_on_time, key=lambda p: p["team_id"])[0]
            notes = (
                f"Team {winner['team_id']} won on prototype fallback after equal "
                f"strength and equal time."
            )

    return {
        "market_id": market_id,
        "winner_team_id": int(winner["team_id"]),
        "resolution_notes": notes,
        "participants": ranking,
    }


def build_resolution_outcomes_from_quiz(
    game_state: dict[str, Any], quiz_results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """
    Convert quiz result payloads into the outcome format expected by
    gameplay_helpers.apply_resolution_outcomes(...).
    """
    conflicts_by_market = {
        int(conflict["market_id"]): conflict
        for conflict in game_state.get("turn_log", {}).get("conflicts", [])
    }

    outcomes: list[dict[str, Any]] = []
    for quiz_result in quiz_results:
        market_id = int(quiz_result["market_id"])
        conflict = conflicts_by_market.get(market_id)
        if conflict is None:
            raise ValueError(
                f"[quiz_helpers] No prepared conflict exists for market {market_id}."
            )

        resolved = resolve_conflict_from_quiz(
            game_state,
            conflict,
            quiz_result.get("team_results", []),
        )
        outcomes.append(
            {
                "market_id": market_id,
                "winner_team_id": resolved["winner_team_id"],
                "resolution_notes": resolved["resolution_notes"],
            }
        )

    return outcomes


def _question_for_frontend(question: dict[str, Any]) -> dict[str, Any]:
    return {
        "question_id": int(question["question_id"]),
        "topic": question["topic"],
        "difficulty_level": question["difficulty_level"],
        "content": question["content"],
        "options": {
            "option_1": question["option_1"],
            "option_2": question["option_2"],
            "option_3": question["option_3"],
            "option_4": question["option_4"],
        },
    }


def _coerce_team_result(conflict: dict[str, Any], team_result: dict[str, Any]) -> dict[str, Any]:
    questions = team_result.get("questions")
    if questions is None:
        questions = build_quiz_for_conflict(conflict).get("questions", [])

    if "answers" in team_result:
        return score_team_answers(questions, team_result.get("answers", []))

    correct_answers = int(team_result.get("correct_answers", 0))
    perfect_round_bonus = int(
        team_result.get(
            "perfect_round_bonus",
            1 if questions and correct_answers == len(questions) else 0,
        )
    )
    strength_bonus = float(team_result.get("strength_bonus", correct_answers + perfect_round_bonus))

    return {
        "correct_answers": correct_answers,
        "perfect_round_bonus": perfect_round_bonus,
        "strength_bonus": strength_bonus,
        "total_response_time_ms": int(
            team_result.get("total_response_time_ms", len(questions) * DEFAULT_QUESTION_TIME_LIMIT_MS)
        ),
    }


def _conflict_participant_team_ids(conflict: dict[str, Any]) -> list[int]:
    participant_ids: list[int] = []
    defender_team_id = _optional_int(conflict.get("defender_team_id"))
    if defender_team_id is not None:
        participant_ids.append(defender_team_id)

    for team_id in conflict.get("attacker_team_ids", []) or []:
        parsed_team_id = int(team_id)
        if parsed_team_id not in participant_ids:
            participant_ids.append(parsed_team_id)

    return participant_ids


def _position_strength_bonus(
    game_state: dict[str, Any], conflict: dict[str, Any], team_id: int
) -> float:
    defender_team_id = _optional_int(conflict.get("defender_team_id"))
    if defender_team_id == team_id:
        return float(conflict.get("defender_strength_estimate", 0.0))

    attack_commitment = sum(
        int(order.get("ip_spent", 0))
        for order in conflict.get("attack_orders", [])
        if _optional_int(order.get("team_id")) == team_id
    )
    return float(attack_commitment) + _attack_security_bonus(game_state, int(conflict["market_id"]))


def _attack_security_bonus(game_state: dict[str, Any], market_id: int) -> float:
    state = (game_state.get("market_state") or {}).get(str(int(market_id)), {})
    security_score = _enum_score(state.get("_security_risk"))
    return max(0.0, security_score - 1.0)


def _conflict_synergy_bonus(game_state: dict[str, Any], market_id: int, team_id: int) -> float:
    active_synergies = game_state.get("active_synergies", []) or []
    total_bonus = 0.0

    for synergy in active_synergies:
        if _optional_int(synergy.get("team_id")) != team_id:
            continue

        if market_id not in {
            _optional_int(synergy.get("market1")),
            _optional_int(synergy.get("market2")),
        }:
            continue

        bonus_key = _normalise_text(synergy.get("bonus_value"))
        total_bonus += SYNERGY_OPERATOR_VALUES.get(bonus_key, 0.0)

    return total_bonus


def _enum_score(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return ENUM_SCORE_VALUES.get(_normalise_text(value), 0.0)


def _normalise_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)
