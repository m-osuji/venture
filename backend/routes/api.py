import os
import sys
from typing import Any

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from flask import Blueprint, jsonify, request

from backend.ai_opponent.agents.decision_maker import choose_action, choose_orders
from backend.helpers import gameplay_helpers
from backend.helpers.db_helpers import fetch_all_markets
from backend.services import game_service

api = Blueprint("api", __name__)


@api.route("/api/markets", methods=["GET"])
def get_markets():
    """Get static market reference data from the database."""
    try:
        return jsonify({"markets": fetch_all_markets()})
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


@api.route("/api/demo/start", methods=["POST"])
def start_demo():
    """
    Start a seeded one-round demo that the frontend can walk through stage by stage.
    """
    try:
        data = _json_payload()
        teams = _normalise_team_payload(data.get("teams") or [])
        if not teams:
            teams = [
                {"id": 1, "name": "Red Rockets", "colour": "#EE672B", "is_ai": False},
                {"id": 2, "name": "Blue Sparks", "colour": "#467096", "is_ai": False},
            ]

        state = game_service.create_demo_game(
            teams=teams,
            game_mode=str(data.get("mode") or "speedrun").strip().lower(),
            difficulty=str(data.get("difficulty") or "medium").strip().lower(),
            team_order=data.get("team_order"),
        )
        return jsonify(
            {
                "status": "demo_started",
                "session_uuid": state["session_uuid"],
                "game_state": gameplay_helpers.get_frontend_state(state),
            }
        )
    except ValueError as exc:
        return _client_error(exc)
    except Exception as exc:
        return _server_error(exc)


@api.route("/api/demo/step", methods=["POST"])
def run_demo_step():
    """
    Advance the small scripted browser demo by one stage-aware step.
    """
    try:
        state = game_service.run_demo_step()
        public_state = gameplay_helpers.get_frontend_state(state)
        return jsonify(
            {
                "status": "demo_step_applied",
                "message": public_state.get("demo_message"),
                "game_state": public_state,
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
        mode = str(data.get("mode") or request.args.get("mode") or "orders").strip().lower()
        ai_context = game_service.build_ai_context(int(requested_team_id))

        if mode == "action":
            decision = choose_action(ai_context, difficulty=difficulty)
        else:
            decision = choose_orders(ai_context, difficulty=difficulty)

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


def _normalise_team_payload(teams: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalised: list[dict[str, Any]] = []
    for index, team in enumerate(teams, start=1):
        name = str(team.get("name") or f"Team {index}").strip()
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


def _client_error(exc: Exception):
    message = str(exc)
    status_code = 404 if "No active game" in message or "No active game state" in message else 400
    return jsonify({"error": message}), status_code


def _server_error(exc: Exception):
    print(f"[API Error] {exc}")
    return jsonify({"error": str(exc)}), 500
