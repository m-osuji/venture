import pytest

from backend.enums import GameStage, SessionStatus
from backend.helpers import gameplay_helpers as gph


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

    synergies = [
        {
            "market1": 1,
            "market2": 2,
            "bonus_type": "ip",
            "bonus_value": "plus_one",
        }
    ]

    monkeypatch.setattr(gph, "fetch_all_markets", lambda: markets)
    monkeypatch.setattr(gph, "fetch_all", lambda query, params=(): synergies)


def _build_state(monkeypatch):
    _stub_reference_data(monkeypatch)
    state = gph.init_game_state(
        teams=[
            {"id": 1, "name": "Red", "colour": "#f00"},
            {"id": 2, "name": "Blue", "colour": "#00f"},
        ]
    )
    gph.set_team_order(state, [1, 2])
    return state


def _team_entry(state, team_id):
    return next(team for team in state["teams"] if team["team_id"] == team_id)


def _perfect_answers(questions):
    return [
        {
            "question_id": question["question_id"],
            "selected_option": question["answer"],
            "response_time_ms": 1000 + (index * 250),
        }
        for index, question in enumerate(questions)
    ]


def _event_categories(round_entry):
    return {
        event["category"]
        for event in round_entry["turn_log"].get("ethical_events", [])
    }


def test_plan_stage_requires_all_team_notes(monkeypatch):
    state = _build_state(monkeypatch)

    gph.submit_plan_notes(state, 1, {"target": 2})

    with pytest.raises(ValueError):
        gph.advance_stage(state)

    gph.submit_plan_notes(state, 2, {"target": 1})
    gph.advance_stage(state)

    assert state["current_stage"] == GameStage.NEGOTIATE


def test_prepare_resolution_applies_defend_and_builds_conflicts(monkeypatch):
    state = _build_state(monkeypatch)

    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    state["market_state"]["3"]["owner"] = 2
    state["market_state"]["2"]["allocated_ip"] = 1
    state["market_state"]["3"]["allocated_ip"] = 2
    _team_entry(state, 1)["ip"] = 5
    _team_entry(state, 2)["ip"] = 4

    gph.submit_plan_notes(state, 1, "attack")
    gph.submit_plan_notes(state, 2, "defend")
    gph.advance_stage(state)
    gph.advance_stage(state)

    gph.submit_actual_moves(
        state,
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
    gph.submit_actual_moves(
        state,
        2,
        [
            {
                "action_type": "defend",
                "target_market_id": 2,
                "source_market_id": 3,
                "ip_spent": 1,
                "metadata": {"resource_pool": "market_ip"},
            },
            {
                "action_type": "research",
                "target_market_id": 3,
                "source_market_id": 3,
                "ip_spent": 2,
                "metadata": {
                    "resource_pool": "current_ip",
                    "research_option": "improve_security",
                },
            },
        ],
    )

    gph.advance_stage(state)

    assert state["current_stage"] == GameStage.RESOLVE
    assert state["market_state"]["3"]["allocated_ip"] == 1
    assert state["market_state"]["2"]["allocated_ip"] == 2
    assert state["market_state"]["2"]["contested"] is True
    assert _team_entry(state, 1)["ip"] == 3
    assert _team_entry(state, 2)["ip"] == 2
    assert len(state["turn_log"]["pending_research"]) == 1
    assert state["turn_log"]["conflicts"][0]["market_id"] == 2
    assert len(state["turn_log"]["active_quizzes"]) == 1
    assert state["turn_log"]["active_quizzes"][0]["quiz_topic"] == "Cybersecurity"


def test_submit_quiz_results_resolves_conflicts_via_turn_log(monkeypatch):
    state = _build_state(monkeypatch)

    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    _team_entry(state, 1)["ip"] = 4
    _team_entry(state, 2)["ip"] = 4

    gph.submit_plan_notes(state, 1, "attack")
    gph.submit_plan_notes(state, 2, "hold")
    gph.advance_stage(state)
    gph.advance_stage(state)

    gph.submit_actual_moves(
        state,
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
    gph.submit_actual_moves(state, 2, [])
    gph.advance_stage(state)

    quiz = state["turn_log"]["active_quizzes"][0]
    gph.submit_quiz_results(
        state,
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

    gph.advance_stage(state)

    assert state["current_stage"] == GameStage.UPDATE
    assert state["market_state"]["2"]["owner"] == 1
    assert state["turn_log"]["resolution_applied"] is True
    assert state["turn_log"]["quiz_results"]["2"]["market_id"] == 2
    assert state["turn_log"]["resolution_outcomes"][0]["winner_team_id"] == 1


def test_allied_attack_requires_break_alliance_flag(monkeypatch):
    state = _build_state(monkeypatch)

    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    state["alliances"] = [
        {
            "alliance_id": "alliance_1_2",
            "members": [1, 2],
            "type": "alliance",
            "formed_turn": 1,
            "shared_market": 2,
        }
    ]
    _team_entry(state, 1)["ip"] = 4
    _team_entry(state, 2)["ip"] = 4

    gph.submit_plan_notes(state, 1, {"planned_action": "attack", "target_market_id": 2})
    gph.submit_plan_notes(state, 2, "hold")
    gph.advance_stage(state)
    gph.submit_declared_moves(
        state,
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
    gph.submit_declared_moves(state, 2, [])
    gph.advance_stage(state)
    gph.submit_actual_moves(
        state,
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
    gph.submit_actual_moves(state, 2, [])

    with pytest.raises(ValueError):
        gph.advance_stage(state)


def test_alliance_betrayal_breaks_alliance_and_penalises_ethics(monkeypatch):
    state = _build_state(monkeypatch)

    state["current_round"] = 3
    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    state["alliances"] = [
        {
            "alliance_id": "alliance_1_2",
            "members": [1, 2],
            "type": "alliance",
            "formed_turn": 1,
            "shared_market": 2,
        }
    ]
    _team_entry(state, 1)["ip"] = 4
    _team_entry(state, 2)["ip"] = 4

    betrayal_attack = {
        "action_type": "attack",
        "target_market_id": 2,
        "ip_spent": 2,
        "metadata": {
            "resource_pool": "current_ip",
            "break_alliance": True,
        },
    }

    gph.submit_plan_notes(
        state,
        1,
        {"planned_action": "attack", "target_market_id": 2},
    )
    gph.submit_plan_notes(state, 2, "hold")
    gph.advance_stage(state)
    gph.submit_declared_moves(state, 1, [betrayal_attack])
    gph.submit_declared_moves(state, 2, [])
    gph.advance_stage(state)
    gph.submit_actual_moves(state, 1, [betrayal_attack])
    gph.submit_actual_moves(state, 2, [])
    gph.advance_stage(state)

    quiz = state["turn_log"]["active_quizzes"][0]
    gph.submit_quiz_results(
        state,
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
    gph.advance_stage(state)
    gph.advance_stage(state)

    alliance = state["alliances"][0]
    round_entry = state["round_history"][0]

    assert state["current_stage"] == GameStage.PLAN
    assert state["market_state"]["2"]["owner"] == 1
    assert alliance["broken_turn"] == 3
    assert alliance["broken_by_team_id"] == 1
    assert _team_entry(state, 1)["ethical_score"] < 0.8
    assert "alliance_betrayal" in _event_categories(round_entry)
    assert round_entry["turn_log"]["ethical_adjustments"]["1"]["penalty"] > 0.2


def test_plan_and_declared_mismatch_penalise_ethics(monkeypatch):
    state = _build_state(monkeypatch)

    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    _team_entry(state, 1)["ip"] = 4
    _team_entry(state, 2)["ip"] = 4

    gph.submit_plan_notes(
        state,
        1,
        {"planned_action": "hold", "target_market_id": 1},
    )
    gph.submit_plan_notes(state, 2, "hold")
    gph.advance_stage(state)
    gph.submit_declared_moves(
        state,
        1,
        [
            {
                "action_type": "defend",
                "target_market_id": 1,
                "ip_spent": 1,
                "metadata": {"resource_pool": "current_ip"},
            }
        ],
    )
    gph.submit_declared_moves(state, 2, [])
    gph.advance_stage(state)
    gph.submit_actual_moves(
        state,
        1,
        [
            {
                "action_type": "attack",
                "target_market_id": 3,
                "ip_spent": 2,
                "metadata": {"resource_pool": "current_ip"},
            }
        ],
    )
    gph.submit_actual_moves(state, 2, [])
    gph.advance_stage(state)

    quiz = state["turn_log"]["active_quizzes"][0]
    gph.submit_quiz_results(
        state,
        3,
        [
            {
                "team_id": 1,
                "answers": _perfect_answers(quiz["questions"]),
            }
        ],
    )
    gph.advance_stage(state)
    gph.advance_stage(state)

    round_entry = state["round_history"][0]

    assert _team_entry(state, 1)["ethical_score"] < 0.9
    assert "plan_mismatch" in _event_categories(round_entry)
    assert "negotiation_mismatch" in _event_categories(round_entry)


def test_frontend_state_exposes_public_quiz_payload_only(monkeypatch):
    state = _build_state(monkeypatch)

    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    _team_entry(state, 1)["ip"] = 4
    _team_entry(state, 2)["ip"] = 4

    gph.submit_plan_notes(state, 1, "attack")
    gph.submit_plan_notes(state, 2, "hold")
    gph.advance_stage(state)
    gph.advance_stage(state)
    gph.submit_actual_moves(
        state,
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
    gph.submit_actual_moves(state, 2, [])
    gph.advance_stage(state)

    frontend_state = gph.get_frontend_state(state)
    public_question = frontend_state["active_quizzes"][0]["questions"][0]

    assert frontend_state["active_quizzes"][0]["market_id"] == 2
    assert "answer" not in public_question
    assert public_question["options"]["option_1"]


def test_resolution_and_round_update_apply_income_research_and_synergy(monkeypatch):
    state = _build_state(monkeypatch)

    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    _team_entry(state, 1)["ip"] = 5
    _team_entry(state, 2)["ip"] = 4

    gph.submit_plan_notes(state, 1, "expand")
    gph.submit_plan_notes(state, 2, "hold")
    gph.advance_stage(state)
    gph.advance_stage(state)

    gph.submit_actual_moves(
        state,
        1,
        [
            {
                "action_type": "research",
                "target_market_id": 1,
                "source_market_id": 1,
                "ip_spent": 2,
                "metadata": {
                    "resource_pool": "current_ip",
                    "research_option": "increase_production",
                },
            },
            {
                "action_type": "attack",
                "target_market_id": 2,
                "ip_spent": 2,
                "metadata": {"resource_pool": "current_ip"},
            },
        ],
    )
    gph.submit_actual_moves(state, 2, [])

    gph.advance_stage(state)
    gph.apply_resolution_outcomes(
        state,
        [{"market_id": 2, "winner_team_id": 1, "resolution_notes": "Won on quiz"}],
    )
    gph.advance_stage(state)
    gph.advance_stage(state)

    assert state["current_stage"] == GameStage.PLAN
    assert state["current_round"] == 2
    assert state["market_state"]["2"]["owner"] == 1
    assert state["market_state"]["1"]["production_upgrade_level"] == 1
    assert state["market_state"]["1"]["research_level"] == 1
    assert state["active_synergies"] == [
        {
            "team_id": 1,
            "market1": 1,
            "market2": 2,
            "bonus_type": "ip",
            "bonus_value": "plus_one",
        }
    ]
    assert _team_entry(state, 1)["ip"] == 8
    assert len(state["round_history"]) == 1


def test_round_update_finishes_game_when_max_rounds_reached(monkeypatch):
    state = _build_state(monkeypatch)

    state["rules"]["max_rounds"] = 1
    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    _team_entry(state, 1)["ip"] = 4
    _team_entry(state, 2)["ip"] = 4

    gph.submit_plan_notes(state, 1, "attack")
    gph.submit_plan_notes(state, 2, "hold")
    gph.advance_stage(state)
    gph.advance_stage(state)
    gph.submit_actual_moves(
        state,
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
    gph.submit_actual_moves(state, 2, [])
    gph.advance_stage(state)

    quiz = state["turn_log"]["active_quizzes"][0]
    gph.submit_quiz_results(
        state,
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
    gph.advance_stage(state)
    gph.advance_stage(state)

    frontend_state = gph.get_frontend_state(state)

    assert state["status"] == SessionStatus.FINISHED
    assert state["current_stage"] == GameStage.UPDATE
    assert state["current_round"] == 1
    assert state["finished_round"] == 1
    assert state["winner_team_id"] == 1
    assert state["game_over_reason"] == "max_rounds_reached"
    assert state["current_team_turn"] is None
    assert frontend_state["is_finished"] is True
    assert frontend_state["winner_team_id"] == 1
    assert frontend_state["teams"][0]["ethical_score"] is not None

    with pytest.raises(ValueError):
        gph.advance_stage(state)


def test_final_leaderboard_uses_ethics_as_tiebreak(monkeypatch):
    state = _build_state(monkeypatch)

    state["status"] = SessionStatus.FINISHED
    state["finished_round"] = 3
    state["game_over_reason"] = "requested_stop"
    state["market_state"]["1"]["owner"] = 1
    state["market_state"]["2"]["owner"] = 2
    state["teams"][0]["ip"] = 6
    state["teams"][1]["ip"] = 6
    state["teams"][0]["ethical_score"] = 0.65
    state["teams"][1]["ethical_score"] = 0.9

    leaderboard = gph.get_frontend_state(state)["leaderboard"]

    assert leaderboard[0]["team_id"] == 2
    assert leaderboard[0]["ethical_score"] == pytest.approx(0.9)
    assert leaderboard[0]["rank"] == 1
    assert leaderboard[1]["team_id"] == 1

