"""
Terminal demo for a two-round Venture diplomacy scenario.

This script is intentionally self-contained. It injects a tiny demo market map
instead of depending on the current SQLite contents, because the live database
does not yet contain enough seeded markets to show a reliable end-to-end story.

The scenario showcases:
- alliance creation during NEGOTIATE
- a normal quiz-resolved attack in round 1
- a betrayal attack in round 2
- ethical score penalties and the final leaderboard

Usage:
    uv run python backend/scripts/demo_round.py
    uv run python backend/scripts/demo_round.py --state-path backend/demo_game_state.json
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.services import game_service


DEMO_MARKETS: list[dict[str, Any]] = [
    {
        "market_id": 1,
        "market_name": "AI Tools",
        "size": "medium",
        "regulation_level": "low",
        "growth_potential": "high",
        "security_risk": "low",
        "key_topic": "AI",
    },
    {
        "market_id": 2,
        "market_name": "Cybersecurity",
        "size": "large",
        "regulation_level": "medium",
        "growth_potential": "medium",
        "security_risk": "medium",
        "key_topic": "Cybersecurity",
    },
    {
        "market_id": 3,
        "market_name": "Education",
        "size": "small",
        "regulation_level": "low",
        "growth_potential": "medium",
        "security_risk": "low",
        "key_topic": "Education",
    },
]

DEMO_SYNERGIES: list[dict[str, Any]] = [
    {
        "market1": 1,
        "market2": 2,
        "bonus_type": "ip",
        "bonus_value": "plus_one",
    }
]

DEMO_TEAMS: list[dict[str, Any]] = [
    {"id": 1, "name": "Red Rockets", "colour": "#ff4d4d"},
    {"id": 2, "name": "Blue Sparks", "colour": "#4d79ff"},
    {"id": 3, "name": "Green Circuit", "colour": "#2c9c69"},
]


def main() -> None:
    args = _parse_args()
    _configure_demo_environment(Path(args.state_path))

    print("=== Venture Backend Demo ===")
    print(f"Using state file: {game_service.gameplay_helpers.GAME_STATE_PATH}")
    print("Reference data: in-script demo markets + database-backed quiz questions")
    print()

    game_service.create_game(
        teams=DEMO_TEAMS,
        game_mode="speedrun",
        include_ai=False,
        team_order=[1, 2, 3],
    )
    _seed_demo_opening_state()

    print("=== Opening State ===")
    _print_public_state(game_service.get_public_game_state())
    _play_round_one()
    final_state = _play_round_two()

    print("=== Final Public State ===")
    public_state = game_service.get_public_game_state()
    _print_public_state(public_state)
    _print_final_leaderboard(public_state)
    _print_ethical_aftermath(final_state)
    _print_alliance_summary(public_state)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a one-round Venture backend demo.")
    parser.add_argument(
        "--state-path",
        default="backend/demo_game_state.json",
        help="Path to the JSON state file used only for this demo run.",
    )
    return parser.parse_args()


def _configure_demo_environment(state_path: Path) -> None:
    resolved_path = state_path.resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)

    game_service.gameplay_helpers.GAME_STATE_PATH = str(resolved_path)
    game_service.gameplay_helpers.fetch_all_markets = lambda: deepcopy(DEMO_MARKETS)
    game_service.gameplay_helpers.fetch_all = (
        lambda query, params=(): deepcopy(DEMO_SYNERGIES)
    )


def _seed_demo_opening_state() -> None:
    state = game_service.get_game_state()
    if state is None:
        raise ValueError("[demo_round] Failed to create initial game state.")

    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    state["market_state"]["3"]["owner"] = 3
    state["market_state"]["2"]["allocated_ip"] = 1
    state["market_state"]["3"]["allocated_ip"] = 1
    state["teams"][0]["ip"] = 4
    state["teams"][1]["ip"] = 4
    state["teams"][2]["ip"] = 4
    state.setdefault("rules", {})["max_rounds"] = 2

    game_service.gameplay_helpers.save_state(state)


def _play_round_one() -> None:
    print("=== Round 1: Education Push ===")
    print("=== Plan Stage ===")
    game_service.submit_plan_notes(1, "Attack market 3 and expand early.")
    game_service.submit_plan_notes(2, "Hold market 2 and watch Red's expansion.")
    game_service.submit_plan_notes(3, "Hold market 3 and survive the round.")
    _print_stage_progress("Plan notes submitted for all three teams.")

    game_service.advance_stage()
    print("Moved to NEGOTIATE.")

    attack_move = _demo_attack_move(3, ip_spent=2)
    game_service.submit_declared_moves(1, [attack_move])
    game_service.submit_declared_moves(2, [{"action_type": "hold"}])
    game_service.submit_declared_moves(3, [{"action_type": "hold"}])
    _print_stage_progress(
        "Red openly signals an attack on Education while Blue and Green prepare to hold."
    )

    game_service.advance_stage()
    print("Moved to ORDERS.")
    print()

    print("=== Orders Stage ===")
    game_service.submit_actual_moves(1, [attack_move])
    game_service.submit_actual_moves(2, [{"action_type": "hold"}])
    game_service.submit_actual_moves(3, [{"action_type": "hold"}])
    _print_stage_progress("Orders lock in. Red attacks Education while Blue and Green stay put.")

    resolve_state = game_service.advance_stage()
    print("Moved to RESOLVE.")
    print()

    _resolve_conflict(resolve_state, expected_market_id=3, winner_team_id=1)

    update_state = game_service.advance_stage()
    print("Moved to UPDATE.")
    print()

    print("=== Resolution Outcome ===")
    _print_resolution_outcome(update_state["turn_log"]["resolution_outcomes"], 3)

    game_service.advance_stage()
    print("Moved to next round PLAN stage.")
    print()

    print("=== State After Round 1 ===")
    _print_public_state(game_service.get_public_game_state())


def _play_round_two() -> dict[str, Any]:
    print("=== Round 2: Betrayal at Cybersecurity ===")
    print("=== Plan Stage ===")
    game_service.submit_plan_notes(1, "Hold the alliance and consolidate market 3.")
    game_service.submit_plan_notes(2, "Trust Red and keep market 2 secure.")
    game_service.submit_plan_notes(3, "Recover and watch the leaders.")
    _print_stage_progress("Plans suggest a quiet round, but Red is about to break faith.")

    game_service.advance_stage()
    print("Moved to NEGOTIATE.")

    alliance_state = game_service.propose_alliance(
        2,
        1,
        protected_markets=[2],
        notes="Keep Cybersecurity safe while we work together.",
    )
    offer_id = alliance_state["turn_log"]["alliance_offers"][-1]["offer_id"]
    game_service.accept_alliance_offer(offer_id, 1)
    _print_alliance_summary(game_service.get_public_game_state())

    declared_hold = [{"action_type": "hold"}]
    game_service.submit_declared_moves(1, declared_hold)
    game_service.submit_declared_moves(2, declared_hold)
    game_service.submit_declared_moves(3, declared_hold)
    _print_stage_progress(
        "Red publicly signals a hold order, keeping Blue comfortable inside the alliance."
    )

    game_service.advance_stage()
    print("Moved to ORDERS.")
    print()

    print("=== Orders Stage ===")
    betrayal_attack = _demo_attack_move(2, ip_spent=2, break_alliance=True)
    game_service.submit_actual_moves(1, [betrayal_attack])
    game_service.submit_actual_moves(2, [{"action_type": "hold"}])
    game_service.submit_actual_moves(3, [{"action_type": "hold"}])
    _print_stage_progress(
        "Orders reveal the betrayal: Red secretly attacks allied Cybersecurity instead of holding."
    )

    resolve_state = game_service.advance_stage()
    print("Moved to RESOLVE.")
    print()

    _resolve_conflict(resolve_state, expected_market_id=2, winner_team_id=2)

    update_state = game_service.advance_stage()
    print("Moved to UPDATE.")
    print()

    print("=== Resolution Outcome ===")
    _print_resolution_outcome(update_state["turn_log"]["resolution_outcomes"], 2)

    final_state = game_service.advance_stage()
    print("Game finished after round 2.")
    print()
    return final_state


def _resolve_conflict(
    resolve_state: dict[str, Any], *, expected_market_id: int, winner_team_id: int
) -> None:
    public_state = game_service.get_public_game_state()
    target_quiz = next(
        quiz
        for quiz in public_state["active_quizzes"]
        if int(quiz["market_id"]) == int(expected_market_id)
    )

    print("=== Quiz Generated ===")
    _print_public_quiz(target_quiz)

    internal_quiz = next(
        quiz
        for quiz in resolve_state["turn_log"]["active_quizzes"]
        if int(quiz["market_id"]) == int(expected_market_id)
    )
    team_results = _build_demo_team_results(
        internal_quiz["questions"],
        participant_team_ids=internal_quiz["participant_team_ids"],
        winner_team_id=winner_team_id,
    )

    print("=== Simulated Answers Submitted ===")
    for result in team_results:
        correct_answers = sum(
            1
            for answer, question in zip(result["answers"], internal_quiz["questions"])
            if answer["selected_option"] == question["answer"]
        )
        team_name = _team_name_from_id(result["team_id"])
        print(f"{team_name} answer {correct_answers}/3 correctly.")
    print()

    game_service.submit_quiz_results(expected_market_id, team_results)


def _build_demo_team_results(
    questions: list[dict[str, Any]],
    *,
    participant_team_ids: list[int],
    winner_team_id: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for team_id in participant_team_ids:
        answers: list[dict[str, Any]] = []
        is_winner = int(team_id) == int(winner_team_id)

        for index, question in enumerate(questions):
            if is_winner or index < 2:
                selected_option = question["answer"]
            else:
                selected_option = (
                    "option_1" if question["answer"] != "option_1" else "option_2"
                )

            answers.append(
                {
                    "question_id": question["question_id"],
                    "selected_option": selected_option,
                    "response_time_ms": (
                        900 + (index * 180) if is_winner else 1100 + (index * 220)
                    ),
                }
            )

        results.append({"team_id": int(team_id), "answers": answers})

    return results


def _demo_attack_move(
    target_market_id: int, *, ip_spent: int, break_alliance: bool = False
) -> dict[str, Any]:
    metadata: dict[str, Any] = {"resource_pool": "current_ip"}
    if break_alliance:
        metadata["break_alliance"] = True

    return {
        "action_type": "attack",
        "target_market_id": int(target_market_id),
        "ip_spent": int(ip_spent),
        "metadata": metadata,
    }


def _print_public_state(state: dict[str, Any] | None) -> None:
    if state is None:
        print("No game state found.")
        print()
        return

    leaderboard_by_team = {
        int(entry["team_id"]): int(entry.get("markets_controlled", 0))
        for entry in state.get("leaderboard", [])
    }

    print(
        f"Round {state['current_round']} | Stage {state['current_stage']} | "
        f"Turn order {state['team_order']}"
    )
    print("Teams:")
    for team in state["teams"]:
        ethics_text = (
            f" ethics={team['ethical_score']:.2f}"
            if team.get("ethical_score") is not None
            else ""
        )
        print(
            f"  Team {team['team_id']} - {team['team_name']}: "
            f"IP={team['ip']} markets={leaderboard_by_team.get(int(team['team_id']), 0)}{ethics_text}"
        )

    print("Markets:")
    for market_id, market in sorted(state["market_state"].items()):
        owner = market["owner"]
        owner_label = f"Team {owner}" if owner is not None else "Neutral"
        contested = " (contested)" if market.get("contested") else ""
        print(f"  {market_id}. {market['market_name']}: {owner_label}{contested}")

    if state.get("active_synergies"):
        print("Active synergies:")
        for synergy in state["active_synergies"]:
            print(
                f"  Team {synergy['team_id']} controls markets "
                f"{synergy['market1']} + {synergy['market2']} -> {synergy['bonus_value']}"
            )

    print()


def _print_final_leaderboard(state: dict[str, Any]) -> None:
    entries = state.get("final_leaderboard") or state.get("leaderboard") or []
    if not entries:
        return

    print("=== Final Leaderboard ===")
    for entry in entries:
        ethics = entry.get("ethical_score")
        ethics_text = f" | Ethics {ethics:.2f}" if ethics is not None else ""
        print(
            f"  #{entry.get('rank', '?')} {entry['team_name']} - "
            f"IP {entry['ip']} | Markets {entry['markets_controlled']}{ethics_text}"
        )
    print()


def _print_ethical_aftermath(state: dict[str, Any]) -> None:
    round_history = state.get("round_history") or []
    if not round_history:
        return

    final_round = round_history[-1]
    turn_log = final_round.get("turn_log", {}) or {}
    events = turn_log.get("ethical_events", []) or []
    adjustments = turn_log.get("ethical_adjustments", {}) or {}

    print("=== Ethical Aftermath ===")
    if not events:
        print("  No ethical penalties were recorded.")
    else:
        for event in events:
            print(
                f"  Team {event['team_id']} | {event['category']} | "
                f"-{float(event['penalty']):.2f} | {event['summary']}"
            )

    if adjustments:
        print("Score changes:")
        for team_id, values in sorted(adjustments.items(), key=lambda item: int(item[0])):
            print(
                f"  Team {team_id}: "
                f"{float(values['starting_score']):.2f} -> {float(values['ending_score']):.2f} "
                f"(penalty {float(values['penalty']):.2f})"
            )
    print()


def _print_alliance_summary(state: dict[str, Any]) -> None:
    alliances = state.get("alliances") or []
    if not alliances:
        return

    print("=== Alliances ===")
    for alliance in alliances:
        status = "broken" if alliance.get("broken_turn") is not None else "active"
        members = ", ".join(_team_name_from_id(team_id) for team_id in alliance.get("members", []))
        protected = alliance.get("protected_markets") or []
        protected_text = f" | protected {protected}" if protected else ""
        print(
            f"  {alliance['alliance_id']}: {members} | {status}{protected_text}"
        )
    print()


def _print_public_quiz(quiz: dict[str, Any]) -> None:
    print(
        f"Market {quiz['market_id']} quiz | Topic: {quiz['quiz_topic']} | "
        f"Participants: {quiz['participant_team_ids']}"
    )
    for index, question in enumerate(quiz["questions"], start=1):
        print(f"  Q{index} [{question['difficulty_level']}]: {question['content']}")
        for option_key, option_value in question["options"].items():
            print(f"    {option_key}: {option_value}")
    print()


def _print_stage_progress(message: str) -> None:
    print(message)
    print()


def _print_resolution_outcome(
    outcomes: list[dict[str, Any]], target_market_id: int
) -> None:
    outcome = next(
        outcome for outcome in outcomes if int(outcome["market_id"]) == int(target_market_id)
    )
    print(
        f"Market {outcome['market_id']} winner: Team {outcome['winner_team_id']} "
        f"({outcome['resolution_notes']})"
    )
    print()


def _team_name_from_id(team_id: int) -> str:
    for team in DEMO_TEAMS:
        if int(team["id"]) == int(team_id):
            return str(team["name"])
    return f"Team {team_id}"


if __name__ == "__main__":
    main()
