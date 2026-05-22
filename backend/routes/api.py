import os
import sys
import random
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from flask import Blueprint, jsonify, request

from backend.ai_opponent.agents.decision_maker import (
    choose_action,
    choose_declared_and_actual_moves,
    choose_orders,
    choose_plan_allocations,
)
from backend.ai_opponent.agents.commentator import get_commentary

from backend.helpers import gameplay_helpers
from backend.helpers.db_helpers import fetch_all_markets, fetch_questions as fetch_db_questions

from backend.services import game_service

api = Blueprint("api", __name__)


@api.route("/api/markets", methods=["GET"])
def get_markets():
    """Get static market reference data from the database."""
    try:
        return jsonify({"markets": fetch_all_markets()})
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/questions", methods=["GET"])
def get_questions():
    """Return question data in the shape the frontend quiz expects."""
    try:
        topic = request.args.get("topic")
        difficulty = request.args.get("difficulty")
        limit = request.args.get("limit", type=int)
        shuffle = str(request.args.get("shuffle") or "false").strip().lower() in {
            "1",
            "true",
            "yes",
        }

        rows = [dict(row) for row in fetch_db_questions(topic=topic, difficulty=difficulty)]
        if shuffle:
            random.shuffle(rows)
        if limit is not None and limit > 0:
            rows = rows[:limit]

        questions = [_frontend_question_payload(row) for row in rows]
        return jsonify(
            {
                "questions": questions,
                "count": len(questions),
                "topic": topic,
                "difficulty": difficulty,
            }
        )
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/game/state", methods=["GET"])
def get_game_state_endpoint():
    """Get the frontend-safe current game state."""
    try:
        game_state = game_service.get_public_game_state()
        if game_state is None:
            return jsonify({"error": "No active game found"}), 404
        return jsonify(game_state)
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/game/status", methods=["GET"])
def get_game_status():
    """Check whether a game is active and expose the current round/stage."""
    try:
        game_state = game_service.get_public_game_state()
        if game_state is None:
            return jsonify({"is_active": False})

        return jsonify(
            {
                "is_active": True,
                "status": game_state.get("status"),
                "is_finished": bool(game_state.get("is_finished")),
                "current_stage": game_state.get("current_stage"),
                "current_round": game_state.get("current_round", 1),
                "teams": len(game_state.get("teams", [])),
                "session_uuid": game_state.get("session_uuid"),
            }
        )
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/game/start", methods=["POST"])
def start_game():
    """Initialise a new game using team data provided by the frontend."""
    try:
        data = _json_payload()
        teams = _normalise_team_payload(data.get("teams") or [])
        if not teams:
            teams = [
                {"id": 1, "name": "Player", "colour": "#FF0000", "is_ai": False},
                {"id": 2, "name": "IBM Granite AI", "colour": "#0000FF", "is_ai": True},
            ]

        team_order = data.get("team_order")
        include_ai = any(team.get("is_ai") for team in teams)
        game_mode = str(data.get("mode") or "full").strip().lower()
        difficulty = str(data.get("difficulty") or "medium").strip().lower()

        # clean up any existing game state before starting a new game to prevent conflicts
        if os.path.exists(gameplay_helpers.GAME_STATE_PATH):
            try:
                os.remove(gameplay_helpers.GAME_STATE_PATH)
            except OSError as e:
                print(f"Error cleaning up old game state: {e}")

        state = game_service.create_game(
            teams=teams,
            game_mode=game_mode,
            include_ai=include_ai,
            team_order=team_order,
        )
        state["ai_difficulty"] = difficulty
        gameplay_helpers.save_state(state)

        return jsonify(
            {
                "status": "game_started",
                "session_uuid": state["session_uuid"],
                "game_state": gameplay_helpers.get_frontend_state(state),
            }
        )
    except ValueError as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/game/team-order", methods=["POST"])
def set_team_order_endpoint():
    try:
        data = _json_payload()
        state = game_service.set_team_order([int(team_id) for team_id in data["team_order"]])
        return jsonify(_state_response("team_order_set", state))
    except (KeyError, TypeError, ValueError) as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/game/opening-setup", methods=["POST"])
def configure_opening_setup_endpoint():
    try:
        data = _json_payload()
        state = game_service.configure_opening_setup(
            [int(team_id) for team_id in data["team_order"]],
            list(data.get("opening_assignments") or []),
        )
        return jsonify(_state_response("opening_setup_configured", state))
    except (KeyError, TypeError, ValueError) as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/game/plan-notes", methods=["POST"])
def submit_plan_notes_endpoint():
    try:
        data = _json_payload()
        state = game_service.submit_plan_notes(int(data["team_id"]), data.get("notes"))
        return jsonify(_state_response("plan_notes_recorded", state))
    except (KeyError, TypeError, ValueError) as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/game/plan-allocation", methods=["POST"])
@api.route("/api/game/plan-allocations", methods=["POST"])
def submit_plan_allocations_endpoint():
    try:
        data = _json_payload()
        state = game_service.submit_plan_allocations(
            int(data["team_id"]),
            list(data.get("allocations") or []),
        )
        return jsonify(_state_response("plan_allocations_recorded", state))
    except (KeyError, TypeError, ValueError) as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/game/declared-moves", methods=["POST"])
def submit_declared_moves_endpoint():
    try:
        data = _json_payload()
        state = game_service.submit_declared_moves(
            int(data["team_id"]),
            list(data.get("moves") or []),
        )
        return jsonify(_state_response("declared_moves_recorded", state))
    except (KeyError, TypeError, ValueError) as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)

@api.route("/api/game/alliance-intent", methods=["POST"])
def submit_alliance_intent_endpoint():
    try:
        data = _json_payload()
        ally_team_id = data.get("ally_team_id")
        state = game_service.submit_alliance_intent(
            int(data["team_id"]),
            int(ally_team_id) if ally_team_id not in (None, "", 0) else None,
        )
        return jsonify(_state_response("alliance_intent_recorded", state))
    except (KeyError, TypeError, ValueError) as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)

@api.route("/api/game/orders", methods=["POST"])
@api.route("/api/game/move", methods=["POST"])
def submit_orders_endpoint():
    try:
        data = _json_payload()
        state = game_service.submit_actual_moves(
            int(data["team_id"]),
            list(data.get("moves") or []),
        )
        return jsonify(_state_response("orders_recorded", state))
    except (KeyError, TypeError, ValueError) as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/game/quiz-results", methods=["POST"])
def submit_quiz_results_endpoint():
    try:
        data = _json_payload()
        state = game_service.submit_quiz_results(
            int(data["market_id"]),
            list(data.get("team_results") or []),
        )
        return jsonify(_state_response("quiz_results_recorded", state))
    except (KeyError, TypeError, ValueError) as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/game/advance", methods=["POST"])
def advance_game_stage():
    """
    Advance the round flow. Defaults to force mode so the UI can drive the loop
    before every frontend form is fully wired.
    """
    try:
        data = _json_payload()
        force = bool(data.get("force", True))
        state = game_service.advance_stage(force=force)
        public_state = gameplay_helpers.get_frontend_state(state)
        return jsonify(
            {
                "status": "success",
                "message": (
                    f"Advanced to Round {public_state.get('current_round')} - "
                    f"{public_state.get('current_stage')}"
                ),
                "game_state": public_state,
            }
        )
    except ValueError as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/game/resolve", methods=["POST"])
def resolve_pending_quizzes_endpoint():
    try:
        data = _json_payload()
        force = bool(data.get("force", False))
        state = game_service.resolve_pending_quizzes(force=force)
        return jsonify(_state_response("quizzes_resolved", state))
    except ValueError as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/ai/commentary", methods=["GET"])
def get_commentary_endpoint():
    """Triggers the Granite AI to generate narrative based on current state."""
    try:
        # get the full state (needed for the context highlights)
        full_state = game_service.get_game_state()
        if not full_state:
            return jsonify({"error": "No active game session"}), 404

        # call Mellea-wrapped agent, returning headline, summary, and taunt
        commentary = get_commentary(full_state)

        return jsonify({
            "status": "success",
            "commentary": commentary
        })
    
    except Exception as exc:
        # catch Granite timeouts or Mellea parsing errors
        return _server_error(exc)

@api.route("/api/ai/context/<int:team_id>", methods=["GET"])
def get_ai_context(team_id: int):
    try:
        return jsonify({"team_id": team_id, "context": game_service.build_ai_context(team_id)})
    except ValueError as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/ai/decide", methods=["GET", "POST"])
def get_ai_decision():
    """Return either one recommended action or a small bundle of orders."""
    try:
        data = _json_payload()
        full_state = game_service.get_game_state()
        if full_state is None:
            return jsonify({"error": "No active game found"}), 404

        requested_team_id = data.get("team_id")
        if requested_team_id is None:
            requested_team_id = request.args.get("team_id", type=int)

        if requested_team_id is None:
            ai_team = next(
                (team for team in full_state.get("teams", []) if team.get("is_ai")),
                None,
            )
            if ai_team is None:
                raise ValueError("No AI team configured in the current game.")
            requested_team_id = int(ai_team["team_id"])

        difficulty = (
            str(
                data.get("difficulty")
                or request.args.get("difficulty")
                or full_state.get("ai_difficulty")
                or "medium"
            )
            .strip()
            .lower()
        )
        mode = str(data.get("mode") or request.args.get("mode") or "stage").strip().lower()
        ai_context = game_service.build_ai_context(int(requested_team_id))
        ai_context["current_stage"] = _stage_name(full_state.get("current_stage"))

        if mode == "action":
            decision = choose_action(ai_context, difficulty=difficulty)
        elif mode in {"orders", "order", "actual"}:
            decision = choose_orders(ai_context, difficulty=difficulty)
        elif mode in {"plan", "planning", "allocation", "allocations"}:
            decision = choose_plan_allocations(ai_context, difficulty=difficulty)
        elif mode in {"negotiation", "negotiate", "declared", "moves"}:
            decision = choose_declared_and_actual_moves(ai_context, difficulty=difficulty)
        else:
            mode, decision = _choose_stage_decision(ai_context, difficulty)

        return jsonify(
            {
                "team_id": int(requested_team_id),
                "difficulty": difficulty,
                "mode": mode,
                "decision": decision,
            }
        )
    except ValueError as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)


def _state_response(status: str, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": status,
        "game_state": gameplay_helpers.get_frontend_state(state),
    }


def _json_payload() -> dict[str, Any]:
    return request.get_json(silent=True) or {}


def _choose_stage_decision(ai_context: dict[str, Any], difficulty: str) -> tuple[str, dict[str, Any]]:
    stage_name = str(ai_context.get("current_stage") or "").upper()
    if stage_name == "PLAN":
        return "plan", choose_plan_allocations(ai_context, difficulty=difficulty)
    if stage_name == "NEGOTIATE":
        return "negotiation", choose_declared_and_actual_moves(ai_context, difficulty=difficulty)
    return "orders", choose_orders(ai_context, difficulty=difficulty)


def _stage_name(raw_stage: Any) -> str:
    if raw_stage is None:
        return "UNKNOWN"
    if hasattr(raw_stage, "name"):
        return str(raw_stage.name)
    try:
        from backend.enums import GameStage

        return GameStage(int(raw_stage)).name
    except (TypeError, ValueError):
        return str(raw_stage).upper()


def _normalise_team_payload(teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalised: list[dict[str, Any]] = []
    for index, team in enumerate(teams, start=1):
        name = (team.get("name") or f"Team {index}").strip()
        colour = str(team.get("colour") or "#467096").strip()
        normalised.append(
            {
                "id": int(team.get("id", index)),
                "name": name,
                "colour": colour,
                "is_ai": bool(team.get("is_ai", False)),
            }
        )
    return normalised


def _frontend_question_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["question_id"]),
        "question_id": int(row["question_id"]),
        "course": row.get("skillsbuild_course"),
        "topic": row["topic"],
        "content": row["content"],
        "options": {
            "a": row["option_1"],
            "b": row["option_2"],
            "c": row["option_3"],
            "d": row["option_4"],
        },
        "option_1": row["option_1"],
        "option_2": row["option_2"],
        "option_3": row["option_3"],
        "option_4": row["option_4"],
        "correct": row["answer"],
        "answer": row["answer"],
        "difficulty": row["difficulty_level"],
        "difficulty_level": row["difficulty_level"],
    }


def _client_error(exc: Exception):
    message = str(exc)
    status_code = 404 if "No active game" in message or "No active game state" in message else 400
    return jsonify({"error": message}), status_code


def _server_error(exc: Exception):
    print(f"[API Error] {exc}")
    return jsonify({"error": str(exc)}), 500
