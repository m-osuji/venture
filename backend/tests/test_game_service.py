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


def test_get_public_game_state_returns_none_without_state(monkeypatch):
    monkeypatch.setattr(service.gameplay_helpers, "load_state", lambda: None)

    assert service.get_public_game_state() is None


def test_get_public_game_state_projects_frontend_state(monkeypatch):
    state = {"session_uuid": "abc"}

    monkeypatch.setattr(service.gameplay_helpers, "load_state", lambda: state)
    monkeypatch.setattr(
        service.gameplay_helpers,
        "get_frontend_state",
        lambda loaded_state: {"session_uuid": loaded_state["session_uuid"], "public": True},
    )

    assert service.get_public_game_state() == {"session_uuid": "abc", "public": True}


def test_game_service_persists_alliance_lifecycle(monkeypatch):
    _stub_reference_data(monkeypatch)
    _stub_persistence(monkeypatch)

    service.create_game(
        teams=[
            {"id": 1, "name": "Red", "colour": "#f00"},
            {"id": 2, "name": "Blue", "colour": "#00f"},
        ],
        team_order=[1, 2],
    )

    service.submit_plan_notes(1, "ally")
    service.submit_plan_notes(2, "ally")
    service.advance_stage()

    offered_state = service.propose_alliance(
        1,
        2,
        protected_markets=[2],
    )
    offer_id = offered_state["turn_log"]["alliance_offers"][0]["offer_id"]

    accepted_state = service.accept_alliance_offer(offer_id, 2)
    alliance_id = accepted_state["alliances"][0]["alliance_id"]

    assert accepted_state["turn_log"]["alliance_offers"][0]["status"] == "accepted"
    assert accepted_state["alliances"][0]["status"] == "active"

    broken_state = service.break_alliance(
        alliance_id,
        1,
        reason="manual_break",
    )

    assert broken_state["alliances"][0]["status"] == "broken"
    assert broken_state["alliances"][0]["broken_by_team_id"] == 1

def test_game_service_can_reject_alliance_offer(monkeypatch):
    _stub_reference_data(monkeypatch)
    _stub_persistence(monkeypatch)

    service.create_game(
        teams=[
            {"id": 1, "name": "Red", "colour": "#f00"},
            {"id": 2, "name": "Blue", "colour": "#00f"},
        ],
        team_order=[1, 2],
    )

    service.submit_plan_notes(1, "ally")
    service.submit_plan_notes(2, "ally")
    service.advance_stage()

    offered_state = service.propose_alliance(1, 2, protected_markets=[2])
    offer_id = offered_state["turn_log"]["alliance_offers"][0]["offer_id"]

    rejected_state = service.reject_alliance_offer(
        offer_id,
        2,
        reason="not worth it",
    )

    assert rejected_state["turn_log"]["alliance_offers"][0]["status"] == "rejected"
    assert rejected_state["turn_log"]["alliance_offers"][0]["rejection_reason"] == "not worth it"
    assert rejected_state["alliances"] == []


def test_game_service_persists_declared_moves(monkeypatch):
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
    state["current_stage"] = GameStage.NEGOTIATE
    service.gameplay_helpers.save_state(state)

    updated = service.submit_declared_moves(
        1,
        [{"action_type": "hold", "target_market_id": None, "ip_spent": 0}],
    )

    assert updated["turn_log"]["declared_moves"]["1"] == [
        {
            "action_type": "hold",
            "target_market_id": None,
            "source_market_id": None,
            "ip_spent": 0,
            "metadata": {},
        }
    ]

def test_create_demo_game_seeds_scripted_state(monkeypatch):
    markets = [
        {"market_id": 1, "market_name": "Technology", "size": "medium", "regulation_level": "low", "growth_potential": "high", "security_risk": "low", "key_topic": "AI"},
        {"market_id": 2, "market_name": "Finance", "size": "large", "regulation_level": "medium", "growth_potential": "medium", "security_risk": "medium", "key_topic": "Cybersecurity"},
        {"market_id": 3, "market_name": "Cybersecurity", "size": "large", "regulation_level": "low", "growth_potential": "high", "security_risk": "medium", "key_topic": "Cybersecurity"},
    ]
    monkeypatch.setattr(service.gameplay_helpers, "fetch_all_markets", lambda: markets)
    monkeypatch.setattr(service.gameplay_helpers, "fetch_all", lambda query, params=(): [])
    monkeypatch.setattr(service.gameplay_helpers, "_refresh_active_synergies", lambda state: None)
    monkeypatch.setattr(service.gameplay_helpers, "_refresh_market_estimates", lambda state: None)
    storage = _stub_persistence(monkeypatch)

    state = service.create_demo_game(
        teams=[
            {"id": 1, "name": "Red", "colour": "#f00", "is_ai": False},
            {"id": 2, "name": "Blue", "colour": "#00f", "is_ai": False},
        ],
        team_order=[1, 2],
    )

    assert state["demo_script"]["enabled"] is True
    assert state["rules"]["max_rounds"] == 1
    assert storage["state"]["demo_script"]["target_market_id"] == 3


def test_run_demo_step_requires_active_demo(monkeypatch):
    monkeypatch.setattr(service.gameplay_helpers, "load_state", lambda: {"demo_script": {"enabled": False}})

    try:
        service.run_demo_step()
    except ValueError as exc:
        assert "No scripted demo is active" in str(exc)
    else:
        raise AssertionError("Expected inactive demo to raise ValueError")
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


def test_game_service_resolve_pending_quizzes_persists(monkeypatch):
    state = {"current_stage": GameStage.RESOLVE, "turn_log": {"active_quizzes": []}}
    saved = {}

    monkeypatch.setattr(service.gameplay_helpers, "load_state", lambda: deepcopy(state))
    monkeypatch.setattr(
        service.gameplay_helpers,
        "resolve_pending_quizzes",
        lambda loaded_state, force=False: loaded_state.update(
            {"resolved": True, "resolve_force": force}
        ),
    )
    monkeypatch.setattr(
        service.gameplay_helpers,
        "save_state",
        lambda updated_state: saved.update(updated_state),
    )

    updated = service.resolve_pending_quizzes(force=True)

    assert updated["resolved"] is True
    assert updated["resolve_force"] is True
    assert saved["resolved"] is True


def test_game_service_set_team_order_persists(monkeypatch):
    state = {"teams": [{"team_id": 1}, {"team_id": 2}], "team_order": []}
    saved = {}

    monkeypatch.setattr(service.gameplay_helpers, "load_state", lambda: deepcopy(state))
    monkeypatch.setattr(
        service.gameplay_helpers,
        "set_team_order",
        lambda loaded_state, order: loaded_state.update(
            {"team_order": list(order), "current_team_turn": order[0]}
        ),
    )
    monkeypatch.setattr(
        service.gameplay_helpers,
        "save_state",
        lambda updated_state: saved.update(updated_state),
    )

    updated = service.set_team_order([2, 1])

    assert updated["team_order"] == [2, 1]
    assert updated["current_team_turn"] == 2
    assert saved["team_order"] == [2, 1]
