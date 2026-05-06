from copy import deepcopy

from backend.enums import GameStage, SessionStatus
from backend.services import game_service as service


def _stub_reference_data(monkeypatch):
    markets = [
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
    ]

    synergies = [
        {
            "market1": 1,
            "market2": 2,
            "bonus_type": "ip",
            "bonus_value": "plus_one",
        }
    ]

    monkeypatch.setattr(service.gameplay_helpers, "fetch_all_markets", lambda: markets)
    monkeypatch.setattr(service.gameplay_helpers, "fetch_all", lambda query, params=(): synergies)


def _stub_persistence(monkeypatch):
    storage = {"state": None}

    def fake_save_state(state):
        storage["state"] = deepcopy(state)

    def fake_load_state():
        if storage["state"] is None:
            return None
        return deepcopy(storage["state"])

    monkeypatch.setattr(service.gameplay_helpers, "save_state", fake_save_state)
    monkeypatch.setattr(service.gameplay_helpers, "load_state", fake_load_state)
    return storage


def _perfect_answers(questions):
    return [
        {
            "question_id": question["question_id"],
            "selected_option": question["answer"],
            "response_time_ms": 1000 + (index * 250),
        }
        for index, question in enumerate(questions)
    ]


def test_game_service_runs_a_full_conflict_round(monkeypatch):
    _stub_reference_data(monkeypatch)
    storage = _stub_persistence(monkeypatch)

    service.create_game(
        teams=[
            {"id": 1, "name": "Red", "colour": "#f00"},
            {"id": 2, "name": "Blue", "colour": "#00f"},
        ],
        team_order=[1, 2],
    )

    state = service.get_game_state()
    assert state is not None
    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    state["teams"][0]["ip"] = 4
    state["teams"][1]["ip"] = 4
    service.gameplay_helpers.save_state(state)

    service.submit_plan_notes(1, "attack")
    service.submit_plan_notes(2, "hold")
    service.advance_stage()
    service.advance_stage()

    service.submit_actual_moves(
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
    service.submit_actual_moves(2, [])
    resolve_state = service.advance_stage()

    assert resolve_state["current_stage"] == GameStage.RESOLVE
    assert len(resolve_state["turn_log"]["active_quizzes"]) == 1

    public_state = service.get_public_game_state()
    assert public_state is not None
    assert "answer" not in public_state["active_quizzes"][0]["questions"][0]

    quiz = service.get_game_state()["turn_log"]["active_quizzes"][0]
    service.submit_quiz_results(
        2,
        [
            {
                "team_id": 1,
                "answers": _perfect_answers(quiz["questions"]),
            },
            {
                "team_id": 2,
                "answers": [],
            },
        ],
    )

    updated_state = service.advance_stage()
    assert updated_state["current_stage"] == GameStage.UPDATE
    assert updated_state["market_state"]["2"]["owner"] == 1
    assert updated_state["turn_log"]["resolution_outcomes"][0]["winner_team_id"] == 1

    final_state = service.advance_stage()
    assert final_state["current_stage"] == GameStage.PLAN
    assert final_state["current_round"] == 2
    assert storage["state"]["current_round"] == 2


def test_build_ai_context_uses_persisted_state(monkeypatch):
    _stub_reference_data(monkeypatch)
    _stub_persistence(monkeypatch)

    service.create_game(
        teams=[
            {"id": 1, "name": "Red", "colour": "#f00"},
            {"id": 2, "name": "Blue", "colour": "#00f"},
        ],
        team_order=[1, 2],
    )

    state = service.get_game_state()
    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    state["teams"][0]["ip"] = 3
    service.gameplay_helpers.save_state(state)

    context = service.build_ai_context(1)

    assert context["current_ip"] == 3
    assert 1 in context["owned_markets"]
    assert 2 in context["enemy_markets"]


def test_game_service_finishes_when_round_cap_is_reached(monkeypatch):
    _stub_reference_data(monkeypatch)
    storage = _stub_persistence(monkeypatch)

    service.create_game(
        teams=[
            {"id": 1, "name": "Red", "colour": "#f00"},
            {"id": 2, "name": "Blue", "colour": "#00f"},
        ],
        team_order=[1, 2],
    )

    state = service.get_game_state()
    assert state is not None
    state["rules"]["max_rounds"] = 1
    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    state["teams"][0]["ip"] = 4
    state["teams"][1]["ip"] = 4
    service.gameplay_helpers.save_state(state)

    service.submit_plan_notes(1, "attack")
    service.submit_plan_notes(2, "hold")
    service.advance_stage()
    service.advance_stage()
    service.submit_actual_moves(
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
    service.submit_actual_moves(2, [])
    service.advance_stage()

    quiz = service.get_game_state()["turn_log"]["active_quizzes"][0]
    service.submit_quiz_results(
        2,
        [
            {
                "team_id": 1,
                "answers": _perfect_answers(quiz["questions"]),
            },
            {
                "team_id": 2,
                "answers": [],
            },
        ],
    )
    service.advance_stage()
    finished_state = service.advance_stage()

    assert finished_state["status"] == SessionStatus.FINISHED
    assert finished_state["current_stage"] == GameStage.UPDATE
    assert finished_state["winner_team_id"] == 1
    assert finished_state["current_round"] == 1
    assert storage["state"]["status"] == SessionStatus.FINISHED
