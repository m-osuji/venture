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
    assert public_state["active_quizzes"][0]["questions"][0]["answer"].startswith("option_")

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


def test_game_service_forms_mutual_alliance_from_intents(monkeypatch):
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

    service.submit_declared_moves(1, [])
    service.submit_declared_moves(2, [])
    service.submit_alliance_intent(1, 2)
    service.submit_alliance_intent(2, 1)

    orders_state = service.advance_stage()

    assert orders_state["current_stage"] == GameStage.ORDERS
    assert len(orders_state["alliances"]) == 1
    assert orders_state["alliances"][0]["members"] == [1, 2]


def test_game_service_persists_plan_allocations_and_replaces_them(monkeypatch):
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
    state["market_state"]["2"]["owner"] = 1
    state["teams"][0]["ip"] = 5
    service.gameplay_helpers.save_state(state)

    updated = service.submit_plan_allocations(
        1,
        [
            {"market_id": 1, "ip_allocated": 2},
            {"market_id": 2, "ip_allocated": 1},
        ],
    )

    assert updated["teams"][0]["ip"] == 2
    assert updated["market_state"]["1"]["allocated_ip"] == 2
    assert updated["market_state"]["2"]["allocated_ip"] == 1
    assert updated["turn_log"]["plan_allocations"]["1"] == [
        {"market_id": 1, "ip_allocated": 2},
        {"market_id": 2, "ip_allocated": 1},
    ]

    updated = service.submit_plan_allocations(
        1,
        [
            {"market_id": 2, "ip_allocated": 4},
        ],
    )

    assert updated["teams"][0]["ip"] == 1
    assert updated["market_state"]["1"]["allocated_ip"] == 0
    assert updated["market_state"]["2"]["allocated_ip"] == 4
    assert updated["turn_log"]["plan_allocations"]["1"] == [
        {"market_id": 2, "ip_allocated": 4},
    ]


def test_game_service_can_advance_plan_with_allocations_only(monkeypatch):
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
    state["teams"][0]["ip"] = 2
    state["teams"][1]["ip"] = 2
    service.gameplay_helpers.save_state(state)

    service.submit_plan_allocations(1, [{"market_id": 1, "ip_allocated": 2}])
    service.submit_plan_allocations(2, [])

    next_state = service.advance_stage()

    assert next_state["current_stage"] == GameStage.NEGOTIATE
    public_state = service.get_public_game_state()
    assert public_state["plan_allocations"] == {}
    assert public_state["plan_allocations_submitted_team_ids"] == [1, 2]


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


def test_configure_opening_setup_auto_assigns_missing_ai_market(monkeypatch):
    _stub_reference_data(monkeypatch)
    _stub_persistence(monkeypatch)

    service.create_game(
        teams=[
            {"id": 1, "name": "Red", "colour": "#f00", "is_ai": False},
            {"id": 2, "name": "Granite", "colour": "#00f", "is_ai": True},
        ],
        team_order=[1, 2],
        include_ai=True,
    )

    state = service.get_game_state()
    assert state is not None
    state["ai_difficulty"] = "medium"
    service.gameplay_helpers.save_state(state)

    configured = service.configure_opening_setup(
        [1, 2],
        [{"team_id": 1, "market_id": 1}],
    )

    owners = {
        int(market_id): market["owner"]
        for market_id, market in configured["market_state"].items()
        if market.get("owner") is not None
    }

    assert owners[1] == 1
    assert 2 in owners.values()
    assert next(team for team in configured["teams"] if team["team_id"] == 2)["ip"] > 0


def test_advance_stage_auto_submits_ai_actions_and_merges_quiz_results(monkeypatch):
    _stub_reference_data(monkeypatch)
    _stub_persistence(monkeypatch)

    service.create_game(
        teams=[
            {"id": 1, "name": "Red", "colour": "#f00", "is_ai": False},
            {"id": 2, "name": "Granite", "colour": "#00f", "is_ai": True},
        ],
        team_order=[1, 2],
        include_ai=True,
    )

    state = service.get_game_state()
    assert state is not None
    state["ai_difficulty"] = "medium"
    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    state["teams"][0]["ip"] = 4
    state["teams"][1]["ip"] = 4
    service.gameplay_helpers.save_state(state)

    monkeypatch.setattr(
        service,
        "choose_plan_allocations",
        lambda context, difficulty: {"allocations": [], "strategy": "hold reserves"},
    )
    monkeypatch.setattr(
        service,
        "choose_declared_and_actual_moves",
        lambda context, difficulty: {"declared_moves": [], "actual_moves": []},
    )
    monkeypatch.setattr(
        service,
        "choose_orders",
        lambda context, difficulty: {"orders": []},
    )
    monkeypatch.setattr(
        service,
        "_build_ai_quiz_result",
        lambda quiz, team_id, difficulty: {
            "team_id": team_id,
            "questions": quiz["questions"],
            "answers": [],
        },
    )

    service.submit_plan_notes(1, "attack")
    negotiate_state = service.advance_stage()

    assert negotiate_state["current_stage"] == GameStage.NEGOTIATE
    assert negotiate_state["turn_log"]["plan_allocations"]["2"] == []
    assert negotiate_state["turn_log"]["declared_moves"]["2"][0]["action_type"] == "hold"

    orders_state = service.advance_stage()
    assert orders_state["current_stage"] == GameStage.ORDERS

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

    resolve_state = service.advance_stage()
    assert resolve_state["current_stage"] == GameStage.RESOLVE
    assert resolve_state["turn_log"]["actual_moves"]["2"][0]["action_type"] == "hold"
    assert resolve_state["turn_log"]["quiz_results"]["2"]["team_results"][0]["team_id"] == 2

    quiz = service.get_game_state()["turn_log"]["active_quizzes"][0]
    service.submit_quiz_results(
        2,
        [
            {
                "team_id": 1,
                "answers": _perfect_answers(quiz["questions"]),
            }
        ],
    )

    updated_state = service.get_game_state()
    stored_team_ids = {
        int(result["team_id"])
        for result in updated_state["turn_log"]["quiz_results"]["2"]["team_results"]
    }
    assert stored_team_ids == {1, 2}

    post_resolve = service.advance_stage()
    assert post_resolve["current_stage"] == GameStage.UPDATE
    assert post_resolve["market_state"]["2"]["owner"] == 1


def test_ai_falls_back_to_market_backed_attack_when_orders_would_hold(monkeypatch):
    _stub_reference_data(monkeypatch)
    _stub_persistence(monkeypatch)

    service.create_game(
        teams=[
            {"id": 1, "name": "Red", "colour": "#f00", "is_ai": False},
            {"id": 2, "name": "Granite", "colour": "#00f", "is_ai": True},
        ],
        team_order=[1, 2],
        include_ai=True,
    )

    state = service.get_game_state()
    assert state is not None
    state["ai_difficulty"] = "medium"
    state["current_stage"] = GameStage.NEGOTIATE
    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["1"]["allocated_ip"] = 0
    state["market_state"]["2"]["owner"] = 2
    state["market_state"]["2"]["allocated_ip"] = 3
    state["teams"][0]["ip"] = 0
    state["teams"][1]["ip"] = 0
    state["turn_log"]["declared_moves"] = {}
    state["turn_log"]["actual_moves"] = {}
    service.gameplay_helpers.save_state(state)

    monkeypatch.setattr(
        service,
        "choose_declared_and_actual_moves",
        lambda context, difficulty: {
            "declared_moves": [{"action_type": "hold", "ip_spent": 0, "metadata": {}}],
            "actual_moves": [{"action_type": "hold", "ip_spent": 0, "metadata": {}}],
        },
    )

    negotiated = service.advance_stage()

    ai_declared = negotiated["turn_log"]["declared_moves"]["2"]
    ai_actual_draft = negotiated["turn_log"]["ai_actual_move_drafts"]["2"]

    assert ai_actual_draft[0]["action_type"] == "attack"
    assert ai_declared[0]["action_type"] == "hold"
    assert ai_actual_draft[0]["metadata"]["resource_pool"] == "market_ip"
    assert ai_actual_draft[0]["source_market_id"] == 2
    assert ai_actual_draft[0]["target_market_id"] == 1


def test_ai_can_publish_decoy_declared_move_during_negotiation(monkeypatch):
    _stub_reference_data(monkeypatch)
    _stub_persistence(monkeypatch)

    service.create_game(
        teams=[
            {"id": 1, "name": "Red", "colour": "#f00", "is_ai": False},
            {"id": 2, "name": "Granite", "colour": "#00f", "is_ai": True},
        ],
        team_order=[1, 2],
        include_ai=True,
    )

    state = service.get_game_state()
    assert state is not None
    state["ai_difficulty"] = "hard"
    state["current_stage"] = GameStage.NEGOTIATE
    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    state["market_state"]["2"]["allocated_ip"] = 3
    state["market_state"]["3"] = {
        "owner": None,
        "allocated_ip": 0,
        "_size": "Large",
        "_growth_potential": "High",
        "_regulation_level": "Low",
        "_security_risk": "Low",
    }
    state["turn_log"]["declared_moves"] = {}
    state["turn_log"]["actual_moves"] = {}
    service.gameplay_helpers.save_state(state)

    monkeypatch.setattr(
        service,
        "choose_declared_and_actual_moves",
        lambda context, difficulty: {
            "declared_moves": [
                {
                    "action_type": "attack",
                    "target_market_id": 1,
                    "source_market_id": 2,
                    "ip_spent": 2,
                    "metadata": {"resource_pool": "market_ip"},
                }
            ],
            "actual_moves": [
                {
                    "action_type": "attack",
                    "target_market_id": 1,
                    "source_market_id": 2,
                    "ip_spent": 2,
                    "metadata": {"resource_pool": "market_ip"},
                }
            ],
        },
    )
    monkeypatch.setattr(service.random, "random", lambda: 0.0)
    monkeypatch.setattr(service.random, "choice", lambda seq: seq[-1])

    negotiated = service.advance_stage()

    ai_declared = negotiated["turn_log"]["declared_moves"]["2"][0]
    ai_actual = negotiated["turn_log"]["ai_actual_move_drafts"]["2"][0]

    assert ai_actual["target_market_id"] == 1
    assert ai_declared["action_type"] == "attack"
    assert ai_declared["target_market_id"] == 3
    assert ai_declared["metadata"]["reason"] == "decoy_attack"
