from backend.ai_opponent.agents import decision_maker as dm


def _stub_market_knowledge(monkeypatch, attrs_by_market):
    monkeypatch.setattr(dm, "get_market_attributes", lambda market_id: dict(attrs_by_market[int(market_id)]))
    monkeypatch.setattr(dm, "get_submarkets", lambda market_id: [])
    monkeypatch.setattr(dm, "get_synergies_for_market", lambda market_id: [])


def test_generate_legal_actions_has_no_defend_and_supports_research_options(monkeypatch):
    _stub_market_knowledge(
        monkeypatch,
        {
            1: {
                "market_id": 1,
                "size": "Medium",
                "growth_potential": "High",
                "regulation_level": "High",
                "security_risk": "Low",
                "key_topic": "AI",
            },
            2: {
                "market_id": 2,
                "size": "Small",
                "growth_potential": "Medium",
                "regulation_level": "Low",
                "security_risk": "Low",
                "key_topic": "Education",
            },
            3: {
                "market_id": 3,
                "size": "Medium",
                "growth_potential": "Medium",
                "regulation_level": "Low",
                "security_risk": "Low",
                "key_topic": "Data Science",
            },
        },
    )

    game_state = {
        "current_ip": 4,
        "owned_markets": [1, 2],
        "enemy_markets": [3],
        "market_states": {
            1: {"allocated_ip": 3},
            2: {"allocated_ip": 1},
        },
        "rules": {
            "attack_cost": 1,
            "defend_cost": 1,
            "research_cost": 2,
            "high_regulation_research_surcharge": 1,
        },
    }

    actions = dm.generate_legal_actions(game_state)

    assert all(action.action_type != "defend" for action in actions)

    market_one_research = [
        action
        for action in actions
        if action.action_type == "research" and action.target_market_id == 1
    ]

    assert {action.metadata["research_option"] for action in market_one_research} == set(dm.RESEARCH_OPTIONS)
    assert all(action.ip_spent == 3 for action in market_one_research)


def test_choose_plan_allocations_only_uses_owned_markets_and_budget(monkeypatch):
    _stub_market_knowledge(
        monkeypatch,
        {
            1: {
                "market_id": 1,
                "size": "Large",
                "growth_potential": "High",
                "regulation_level": "Medium",
                "security_risk": "High",
                "key_topic": "AI",
            },
            2: {
                "market_id": 2,
                "size": "Small",
                "growth_potential": "Low",
                "regulation_level": "Low",
                "security_risk": "Low",
                "key_topic": "Education",
            },
            3: {
                "market_id": 3,
                "size": "Large",
                "growth_potential": "Medium",
                "regulation_level": "Low",
                "security_risk": "Low",
                "key_topic": "Cybersecurity",
            },
        },
    )

    game_state = {
        "current_ip": 4,
        "owned_markets": [1, 2],
        "enemy_markets": [3],
        "market_states": {1: {"threat": 0.9}, 2: {"threat": 0.1}},
    }

    result = dm.choose_plan_allocations(game_state, difficulty="medium")

    assert result["ip_allocated"] == 4
    assert result["remaining_ip"] == 0
    assert {entry["market_id"] for entry in result["allocations"]}.issubset({1, 2})
    assert result["allocations"][0]["market_id"] == 1


def test_choose_orders_returns_compatible_bundle_within_budgets(monkeypatch):
    _stub_market_knowledge(
        monkeypatch,
        {
            1: {
                "market_id": 1,
                "size": "Large",
                "growth_potential": "Low",
                "regulation_level": "Medium",
                "security_risk": "Low",
                "key_topic": "Ethics",
            },
            2: {
                "market_id": 2,
                "size": "Medium",
                "growth_potential": "High",
                "regulation_level": "High",
                "security_risk": "Medium",
                "key_topic": "AI",
            },
            3: {
                "market_id": 3,
                "size": "Large",
                "growth_potential": "Medium",
                "regulation_level": "Low",
                "security_risk": "Low",
                "key_topic": "Cybersecurity",
            },
        },
    )

    game_state = {
        "current_ip": 5,
        "owned_markets": [1, 2],
        "enemy_markets": [3],
        "market_states": {
            1: {"threat": 0.9},
            2: {"threat": 0.1, "allocated_ip": 2},
            3: {"enemy_strength_estimate": 1},
        },
        "rules": {
            "attack_cost": 1,
            "defend_cost": 1,
            "research_cost": 2,
            "high_regulation_research_surcharge": 1,
            "max_orders_per_round": 3,
        },
    }

    result = dm.choose_orders(game_state, difficulty="medium")

    assert result["orders"]
    assert result["orders"][0]["action_type"] != "hold"
    assert len(result["orders"]) >= 2
    assert result["current_ip_spent"] <= game_state["current_ip"]
    assert result["market_ip_reallocated"] <= 2


def test_choose_declared_and_actual_moves_can_bluff_on_betrayal(monkeypatch):
    _stub_market_knowledge(
        monkeypatch,
        {
            1: {
                "market_id": 1,
                "size": "Medium",
                "growth_potential": "Medium",
                "regulation_level": "Low",
                "security_risk": "Low",
                "key_topic": "AI",
            },
            9: {
                "market_id": 9,
                "size": "Large",
                "growth_potential": "High",
                "regulation_level": "Low",
                "security_risk": "Low",
                "key_topic": "AI",
            },
        },
    )

    game_state = {
        "current_ip": 4,
        "owned_markets": [1],
        "allied_markets": [9],
        "attackable_markets": [9],
        "market_states": {9: {"enemy_strength_estimate": 0}},
        "commitments": {"avoid_attack_markets": [9], "protected_markets": [9]},
        "rules": {"allow_attack_allies": True, "attack_cost": 1, "research_cost": 2, "max_orders_per_round": 1},
        "ethical_score": 0.1,
    }

    result = dm.choose_declared_and_actual_moves(game_state, difficulty="hard", max_actions=1)

    assert result["honesty"] == "betrayal"
    assert result["actual_moves"][0]["action_type"] == "attack"
    assert result["declared_moves"][0]["action_type"] == "hold"


def test_attack_scoring_penalises_betrayal_commitments(monkeypatch):
    _stub_market_knowledge(
        monkeypatch,
        {
            1: {
                "market_id": 1,
                "size": "Medium",
                "growth_potential": "Medium",
                "regulation_level": "Low",
                "security_risk": "Low",
                "key_topic": "AI",
            },
            9: {
                "market_id": 9,
                "size": "Large",
                "growth_potential": "High",
                "regulation_level": "Low",
                "security_risk": "Low",
                "key_topic": "AI",
            },
        },
    )

    action = dm.Action(
        action_type="attack",
        target_market_id=9,
        ip_spent=3,
        metadata={
            "resource_pool": "current_ip",
            "target_relationship": "ally",
            "breaks_alliance": True,
        },
    )
    traits = dm.get_decision_traits("medium")

    baseline_state = {
        "current_ip": 3,
        "owned_markets": [1],
        "allied_markets": [9],
        "market_states": {9: {"enemy_strength_estimate": 1}},
        "rules": {"allow_attack_allies": True},
    }
    committed_state = {
        **baseline_state,
        "relationship_states": {
            9: {"alliance_turns": 3, "trust": 1.0},
        },
        "commitments": {
            "avoid_attack_markets": [9],
            "protected_markets": [9],
        },
        "ethical_score": 1.0,
    }

    baseline_score, _ = dm.score_action(action, baseline_state, traits)
    committed_score, _ = dm.score_action(action, committed_state, traits)

    assert committed_score < baseline_score


def test_choose_action_keeps_single_action_interface(monkeypatch):
    _stub_market_knowledge(
        monkeypatch,
        {
            1: {
                "market_id": 1,
                "size": "Medium",
                "growth_potential": "Medium",
                "regulation_level": "Low",
                "security_risk": "Low",
                "key_topic": "AI",
            },
            2: {
                "market_id": 2,
                "size": "Large",
                "growth_potential": "High",
                "regulation_level": "Low",
                "security_risk": "Low",
                "key_topic": "AI",
            },
        },
    )

    game_state = {
        "current_ip": 3,
        "owned_markets": [1],
        "enemy_markets": [2],
        "market_states": {2: {"enemy_strength_estimate": 1}},
        "rules": {"attack_cost": 1, "defend_cost": 1, "research_cost": 2},
    }

    result = dm.choose_action(game_state, difficulty="medium")

    assert "action_type" in result
    assert "orders" not in result
