"""
Terminal demo for one Venture conflict round.

This script is intentionally self-contained. It injects a tiny demo market map
instead of depending on the current SQLite contents, because the live database
does not yet contain enough seeded markets to show a proper contested round.

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
]


def main() -> None:
    args = _parse_args()
    _configure_demo_environment(Path(args.state_path))

    print("=== Venture Backend Demo ===")
    print(f"Using state file: {game_service.gameplay_helpers.GAME_STATE_PATH}")
    print("Reference data: in-script demo markets + hardcoded quiz questions")
    print()

    game_service.create_game(
        teams=DEMO_TEAMS,
        game_mode="speedrun",
        include_ai=False,
        team_order=[1, 2],
    )
    _seed_demo_opening_state()

    print("=== Opening State ===")
    _print_public_state(game_service.get_public_game_state())

    print("=== Plan Stage ===")
    game_service.submit_plan_notes(1, "Attack Cybersecurity to unlock the AI/Cyber synergy.")
    game_service.submit_plan_notes(2, "Hold position and trust the quiz.")
    _print_stage_progress("Plan notes submitted for both teams.")

    game_service.advance_stage()
    print("Moved to NEGOTIATE.")
    game_service.advance_stage()
    print("Moved to ORDERS.")
    print()

    print("=== Orders Stage ===")
    game_service.submit_actual_moves(
        1,
        [
            {
                "action_type": "attack",
                "target_market_id": 2,
                "ip_spent": 2,
                "metadata": {"resource_pool": "current_ip"},
            }
        ],
    )
    game_service.submit_actual_moves(2, [])
    _print_stage_progress("Orders locked in. Red attacks Cybersecurity; Blue holds.")

    resolve_state = game_service.advance_stage()
    print("Moved to RESOLVE.")
    print()

    print("=== Quiz Generated ===")
    public_state = game_service.get_public_game_state()
    _print_public_quiz(public_state["active_quizzes"][0])

    internal_quiz = resolve_state["turn_log"]["active_quizzes"][0]
    team_results = _build_demo_team_results(internal_quiz["questions"])

    print("=== Simulated Answers Submitted ===")
    print("Red Rockets answer all 3 correctly.")
    print("Blue Sparks answer 2 correctly.")
    print()

    game_service.submit_quiz_results(2, team_results)
    update_state = game_service.advance_stage()
    print("Moved to UPDATE.")
    print()

    print("=== Resolution Outcome ===")
    outcome = update_state["turn_log"]["resolution_outcomes"][0]
    print(
        f"Market {outcome['market_id']} winner: Team {outcome['winner_team_id']} "
        f"({outcome['resolution_notes']})"
    )
    print()

    final_state = game_service.advance_stage()
    print("Moved to next round PLAN stage.")
    print()

    print("=== Final State After One Demo Round ===")
    _print_public_state(game_service.get_public_game_state())

    red_team = next(team for team in final_state["teams"] if team["team_id"] == 1)
    print(
        f"Red Rockets now have {red_team['ip']} IP and own market 2, "
        "so the AI/Cyber synergy is active."
    )


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
    state["market_state"]["2"]["allocated_ip"] = 1
    state["teams"][0]["ip"] = 4
    state["teams"][1]["ip"] = 4

    game_service.gameplay_helpers.save_state(state)


def _build_demo_team_results(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    red_answers = []
    blue_answers = []

    for index, question in enumerate(questions):
        red_answers.append(
            {
                "question_id": question["question_id"],
                "selected_option": question["answer"],
                "response_time_ms": 900 + (index * 180),
            }
        )

        if index < 2:
            selected_option = question["answer"]
        else:
            selected_option = "option_1" if question["answer"] != "option_1" else "option_2"

        blue_answers.append(
            {
                "question_id": question["question_id"],
                "selected_option": selected_option,
                "response_time_ms": 1100 + (index * 220),
            }
        )

    return [
        {"team_id": 1, "answers": red_answers},
        {"team_id": 2, "answers": blue_answers},
    ]


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
        print(
            f"  Team {team['team_id']} - {team['team_name']}: "
            f"IP={team['ip']} markets={leaderboard_by_team.get(int(team['team_id']), 0)}"
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


if __name__ == "__main__":
    main()
