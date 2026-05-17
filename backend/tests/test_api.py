import sys
import types

import pytest
from flask import Flask


# Fake commentator module before importing the API module
fake_commentator = types.ModuleType("backend.ai_opponent.agents.commentator")
fake_commentator.get_commentary = lambda state: {
    "headline": "Test",
    "summary": "Test summary",
    "taunt": "Skill issue",
}
sys.modules["backend.ai_opponent.agents.commentator"] = fake_commentator

from backend.routes import api as api_module

# Running test flask app
@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(api_module.api)
    return app

# Running test HTTP client
@pytest.fixture
def client(app):
    return app.test_client()

# Helper functions
def patch_ai_game_state(monkeypatch, team_id=2, difficulty="medium"):
    monkeypatch.setattr(
        api_module.game_service,
        "get_game_state",
        lambda: {
            "teams": [{"team_id": team_id, "is_ai": True}],
            "ai_difficulty": difficulty,
        },
    )
    monkeypatch.setattr(
        api_module.game_service,
        "build_ai_context",
        lambda team__id: {"team_id": team__id, "context": "fake"},
    )


def fake_question_rows():
    return [
        {
            "question_id": 1,
            "skillsbuild_course": "CS",
            "topic": "AI",
            "content": "Q1",
            "option_1": "a",
            "option_2": "b",
            "option_3": "c",
            "option_4": "d",
            "answer": "a",
            "difficulty_level": "easy",
        },
        {
            "question_id": 2,
            "skillsbuild_course": "CS",
            "topic": "AI",
            "content": "Q2",
            "option_1": "a",
            "option_2": "b",
            "option_3": "c",
            "option_4": "d",
            "answer": "b",
            "difficulty_level": "easy",
        },
        {
            "question_id": 3,
            "skillsbuild_course": "CS",
            "topic": "AI",
            "content": "Q3",
            "option_1": "a",
            "option_2": "b",
            "option_3": "c",
            "option_4": "d",
            "answer": "c",
            "difficulty_level": "easy",
        },
    ]

# Tests:

# Tests if market data is returned correctly from the database
def test_get_markets(client, monkeypatch):
    monkeypatch.setattr(
        api_module,
        "fetch_all_markets",
        lambda: [{"id": 1, "name": "Finance"}],
    )

    response = client.get("/api/markets")

    assert response.status_code == 200
    assert response.get_json() == {"markets": [{"id": 1, "name": "Finance"}]}


# Tests if the game status endpoint returns inactive when no game exists
def test_get_game_status_inactive(client, monkeypatch):
    monkeypatch.setattr(
        api_module.game_service,
        "get_public_game_state",
        lambda: None,
    )

    response = client.get("/api/game/status")

    assert response.status_code == 200
    assert response.get_json() == {"is_active": False}


# Tests if the game status endpoint returns the active game details
def test_get_game_status_active(client, monkeypatch):
    monkeypatch.setattr(
        api_module.game_service,
        "get_public_game_state",
        lambda: {
            "status": "running",
            "is_finished": False,
            "current_stage": "quiz",
            "current_round": 3,
            "teams": [{"id": 1}, {"id": 2}],
            "session_uuid": "session-123",
        },
    )

    response = client.get("/api/game/status")

    assert response.status_code == 200
    assert response.get_json() == {
        "is_active": True,
        "status": "running",
        "is_finished": False,
        "current_stage": "quiz",
        "current_round": 3,
        "teams": 2,
        "session_uuid": "session-123",
    }


# Tests if starting a game with no input uses the default settings
def test_start_game_uses_defaults(client, monkeypatch):
    created_state = {
        "session_uuid": "abc123",
        "teams": [{"id": 1, "name": "Player"}],
    }

    def fake_create_game(**kwargs):
        assert kwargs["game_mode"] == "full"
        assert kwargs["include_ai"] is True
        assert kwargs["team_order"] is None
        return created_state

    monkeypatch.setattr(api_module.game_service, "create_game", fake_create_game)
    monkeypatch.setattr(api_module.gameplay_helpers, "save_state", lambda state: None)
    monkeypatch.setattr(
        api_module.gameplay_helpers,
        "get_frontend_state",
        lambda state: {"session_uuid": state["session_uuid"]},
    )

    response = client.post("/api/game/start", json={})

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "game_started"
    assert body["session_uuid"] == "abc123"


# Tests if the AI decision endpoint returns a single action in action mode
def test_get_ai_decision_action(client, monkeypatch):
    patch_ai_game_state(monkeypatch)

    monkeypatch.setattr(
        api_module,
        "choose_action",
        lambda ctx, difficulty: {"action": "move"},
    )
    monkeypatch.setattr(
        api_module,
        "choose_orders",
        lambda ctx, difficulty: {"orders": []},
    )

    response = client.get("/api/ai/decide?mode=action")

    assert response.status_code == 200
    body = response.get_json()
    assert body["mode"] == "action"
    assert body["decision"] == {"action": "move"}


# Tests if the AI decision endpoint returns orders in orders mode
def test_get_ai_decision_orders(client, monkeypatch):
    patch_ai_game_state(monkeypatch)

    monkeypatch.setattr(
        api_module,
        "choose_orders",
        lambda ctx, difficulty: {"orders": [1, 2]},
    )

    response = client.get("/api/ai/decide?mode=orders")

    assert response.status_code == 200
    body = response.get_json()
    assert body["mode"] == "orders"
    assert body["decision"] == {"orders": [1, 2]}


# Tests if the game status endpoint returns a 500 when the service crashes
def test_game_service_failure_returns_500(client, monkeypatch):
    def raise_error():
        raise Exception("error raised")

    monkeypatch.setattr(api_module.game_service, "get_public_game_state", raise_error)

    response = client.get("/api/game/status")

    assert response.status_code == 500
    assert response.get_json() == {"error": "error raised"}


# Tests if an invalid team_id input gets rejected by the order's endpoint
def test_submit_orders_invalid_team_id(client):
    response = client.post("/api/game/orders", json={"team_id": "not-int"})

    assert response.status_code == 400
    assert "error" in response.get_json()


# Tests if team payloads get default values filled in correctly
def test_normalise_team_payload_defaults():
    from backend.routes.api import _normalise_team_payload

    result = _normalise_team_payload([{}])

    assert result == [
        {
            "id": 1,
            "name": "Team 1",
            "colour": "#467096",
            "is_ai": False,
        }
    ]


# Tests if question queries are passed correctly and limits are applied
def test_questions_limit_and_query_params(client, monkeypatch):
    captured = {}

    def fake_fetch_db_questions(**kwargs):
        captured.update(kwargs)
        return fake_question_rows()

    monkeypatch.setattr(api_module, "fetch_db_questions", fake_fetch_db_questions)

    response = client.get("/api/questions?topic=AI&difficulty=easy&limit=2")

    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] == 2
    assert len(body["questions"]) == 2
    assert captured == {"topic": "AI", "difficulty": "easy"}


# Tests if advancing the game stage returns the updated public state
def test_advance_game_stage(client, monkeypatch):
    fake_state = {"current_round": 2, "current_stage": "quiz", "teams": []}

    def fake_advance_stage(force):
        assert force is True
        return fake_state

    monkeypatch.setattr(api_module.game_service, "advance_stage", fake_advance_stage)
    monkeypatch.setattr(api_module.gameplay_helpers, "get_frontend_state", lambda state: state)

    response = client.post("/api/game/advance", json={})

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    assert body["message"] == "Advanced to Round 2 - quiz"
    assert body["game_state"]["current_round"] == 2


# Tests if resolving quizzes returns the updated game state
def test_resolve_pending_quizzes(client, monkeypatch):
    fake_state = {"status": "resolved"}

    def fake_resolve(force):
        assert force is False
        return fake_state

    monkeypatch.setattr(api_module.game_service, "resolve_pending_quizzes", fake_resolve)
    monkeypatch.setattr(api_module.gameplay_helpers, "get_frontend_state", lambda state: state)

    response = client.post("/api/game/resolve", json={"force": False})

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "quizzes_resolved"
    assert body["game_state"]["status"] == "resolved"


# Tests if the demo start endpoint creates a demo game with default demo values
def test_start_demo(client, monkeypatch):
    fake_state = {"session_uuid": "demo123", "teams": []}

    def fake_create_demo_game(**kwargs):
        assert kwargs["game_mode"] == "speedrun"
        assert kwargs["difficulty"] == "medium"
        return fake_state

    monkeypatch.setattr(api_module.game_service, "create_demo_game", fake_create_demo_game)
    monkeypatch.setattr(
        api_module.gameplay_helpers,
        "get_frontend_state",
        lambda state: {"session_uuid": state["session_uuid"]},
    )

    response = client.post("/api/demo/start", json={})

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "demo_started"
    assert body["session_uuid"] == "demo123"


# Tests if the demo step endpoint advances one scripted demo step
def test_run_demo_step(client, monkeypatch):
    fake_state = {"demo_message": "step complete"}

    monkeypatch.setattr(api_module.game_service, "run_demo_step", lambda: fake_state)
    monkeypatch.setattr(api_module.gameplay_helpers, "get_frontend_state", lambda state: state)

    response = client.post("/api/demo/step")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "demo_step_applied"
    assert body["message"] == "step complete"


# Tests if the AI commentary endpoint returns the mocked narration
def test_get_ai_commentary(client, monkeypatch):
    monkeypatch.setattr(
        api_module.game_service,
        "get_game_state",
        lambda: {"teams": [{"id": 1}], "round": 1},
    )
    monkeypatch.setattr(
        api_module,
        "get_commentary",
        lambda state: {
            "headline": "Test",
            "summary": "Test summary",
            "taunt": "Skill issue",
        },
    )

    response = client.get("/api/ai/commentary")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "success"
    assert body["commentary"]["headline"] == "Test"


# tests if team order is correctly passed to game_service and returns state
def test_set_team_order_endpoint(client, monkeypatch):
    def fake_set_team_order(order):
        assert order == [1, 2, 3]
        return {"teams": order}

    monkeypatch.setattr(api_module.game_service, "set_team_order", fake_set_team_order)
    monkeypatch.setattr(api_module.gameplay_helpers, "get_frontend_state", lambda s: s)

    response = client.post("/api/game/team-order", json={"team_order": [1, 2, 3]})

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "team_order_set"


# tests if gameplay moves are submitted correctly
def test_submit_orders_endpoint(client, monkeypatch):
    def fake_submit(team_id, moves):
        assert team_id == 2
        assert moves == ["X", "Y"]
        return {"ok": True}

    monkeypatch.setattr(api_module.game_service, "submit_actual_moves", fake_submit)
    monkeypatch.setattr(api_module.gameplay_helpers, "get_frontend_state", lambda s: s)

    response = client.post("/api/game/orders", json={
        "team_id": 2,
        "moves": ["X", "Y"]
    })

    assert response.status_code == 200
    assert response.get_json()["status"] == "orders_recorded"


# tests that invalid team_id type triggers error handling
def test_plan_notes_invalid_team_id_returns_400(client):
    response = client.post("/api/game/plan-notes", json={
        "team_id": "not-an-int",
        "notes": "Banana"
    })

    assert response.status_code == 400
    assert "error" in response.get_json()