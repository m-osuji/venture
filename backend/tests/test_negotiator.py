import pytest
from unittest.mock import MagicMock, patch

from backend.ai_opponent.agents import negotiator
from backend.ai_opponent.agents.negotiator import get_negotiation_move

@pytest.fixture
def base_agent_context():
    return {
        "current_ip": 10,
        "owned_markets": [1, 2],
        "relationship_states": {
            1: {"trust": 0.8},
            2: {"trust": 0.3},
        },
    }


@pytest.fixture
def base_game_state():
    return {
        "current_round": 1,
        "teams": [
            {"team_id": 1, "team_name": "Team A", "ip": 12, "is_ai": False, "ethical_score": 0.5},
            {"team_id": 2, "team_name": "Team B", "ip": 6, "is_ai": False, "ethical_score": 0.5},
        ],
        "alliances": [],
        "market_state": {
            "1": {"owner": 1},
            "2": {"owner": 1},
            "3": {"owner": 2},
            "4": {"owner": 2},
            "5": {"owner": 2},
            "6": {"owner": 99},
            "7": {"owner": 99},
        },
    }

class DummySession:
    def instruct(self, prompt):
        return "TAUNT: test taunt\nPROPOSAL_DETAIL: test proposal"

@patch("backend.ai_opponent.agents.negotiator.init_granite")
def test_medium_difficulty_returns_valid_move(mock_llm, base_agent_context, base_game_state):
    mock_llm.return_value = DummySession()

    move, _ = get_negotiation_move(
        agent_context=base_agent_context,
        full_game_state=base_game_state,
        ai_team_id=99,
        difficulty="medium",
        previous_rank=None,
    )

    assert move["proposal_type"] in ["alliance", "truce", "none"]
    assert "taunt" in move
    assert "proposal_target" in move


@patch("backend.ai_opponent.agents.negotiator.init_granite")
def test_easy_difficulty_never_betrays(mock_llm, base_agent_context, base_game_state):
    mock_llm.return_value = DummySession()

    for _ in range(10):
        move, _ = get_negotiation_move(
            agent_context=base_agent_context,
            full_game_state=base_game_state,
            ai_team_id=99,
            difficulty="easy",
        )

        assert move["secret_intent"] in ["honour", "neutral"]
        assert move["proposal_type"] in ["alliance", "none"]


@patch("backend.ai_opponent.agents.negotiator.init_granite")
def test_hard_difficulty_produces_output(mock_llm, base_agent_context, base_game_state):
    mock_llm.return_value = DummySession()

    move, _ = get_negotiation_move(
        agent_context=base_agent_context,
        full_game_state=base_game_state,
        ai_team_id=99,
        difficulty="hard",
    )

    assert move["proposal_type"] in ["alliance", "truce", "none"]
    assert isinstance(move["taunt"], str)
    assert len(move["taunt"]) > 0


@patch("backend.ai_opponent.agents.negotiator.init_granite")
def test_llm_failure_fallback(mock_llm, base_agent_context, base_game_state):
    mock_llm.side_effect = Exception("LLM down")

    move, _ = get_negotiation_move(
        agent_context=base_agent_context,
        full_game_state=base_game_state,
        ai_team_id=99,
        difficulty="medium",
    )

    assert move["taunt"] is not None
    assert isinstance(move["proposal_detail"], str)
    assert len(move["proposal_detail"]) > 0

@patch("backend.ai_opponent.agents.negotiator.init_granite")
def test_no_teams_edge_case(mock_llm, base_agent_context):
    mock_llm.return_value = DummySession()

    empty_state = {
        "current_round": 1,
        "teams": [],
        "alliances": [],
        "market_state": {},
    }

    move, _ = get_negotiation_move(
        agent_context=base_agent_context,
        full_game_state=empty_state,
        ai_team_id=99,
        difficulty="medium",
    )

    assert move["current_rank"] == 1
    assert move["proposal_type"] in ["none", "alliance", "truce"]


def test_derive_teams_with_markets_excludes_ai_and_counts_owned_markets(base_game_state):
    base_game_state["teams"].append(
        {"team_id": 99, "team_name": "Granite", "ip": 8, "is_ai": True, "ethical_score": 0.4}
    )
    derived = negotiator.derive_teams_with_markets(base_game_state, ai_team_id=99)

    assert derived == [
        {"team_id": 1, "team_name": "Team A", "ip": 12, "market_count": 2},
        {"team_id": 2, "team_name": "Team B", "ip": 6, "market_count": 3},
    ]


def test_derive_active_alliances_filters_broken_and_other_pairs(base_game_state):
    base_game_state["alliances"] = [
        {"members": [99, 1], "formed_turn": 2},
        {"members": [99, 2], "formed_turn": 3, "broken_turn": 4},
        {"members": [1, 2], "formed_turn": 1},
    ]
    base_game_state["current_round"] = 4

    result = negotiator.derive_active_alliances(base_game_state, ai_team_id=99)

    assert result == [{"with_team_id": 1, "with_team": "Team A", "rounds_active": 3}]


def test_get_trust_levels_uses_relationships_and_ethics_fallback(base_agent_context, base_game_state):
    trust_levels = negotiator.get_trust_levels(base_agent_context, base_game_state)

    assert trust_levels[1] == pytest.approx(0.55)
    assert trust_levels[2] == pytest.approx(0.5)


def test_parse_llm_response_and_no_proposal_override():
    taunt, detail = negotiator.parse_llm_response(
        "TAUNT: Stand aside.\nPROPOSAL_DETAIL: We split the board.",
        fallback_detail="fallback",
        proposal_type=negotiator.PROPOSAL_ALLIANCE,
    )
    assert taunt == "Stand aside."
    assert detail == "We split the board."

    taunt, detail = negotiator.parse_llm_response(
        "No structure here",
        fallback_detail="fallback",
        proposal_type=negotiator.PROPOSAL_NONE,
    )
    assert taunt == "..."
    assert detail == "none"


@patch("backend.ai_opponent.agents.negotiator.random.random", side_effect=[0.1, 0.99])
def test_decide_proposal_easy_can_ally_or_do_nothing(_mock_random):
    strategy = {
        "best_alliance_target": 2,
        "strongest_team": 1,
        "is_losing": False,
        "rank_delta": 0,
    }
    game_state = {"trust_levels": {2: 1.0}, "active_alliances": []}

    proposal = negotiator._decide_proposal(game_state, strategy, "easy")
    assert proposal[0] == negotiator.PROPOSAL_ALLIANCE
    assert proposal[3] == negotiator.INTENT_HONOUR

    proposal = negotiator._decide_proposal(game_state, strategy, "easy")
    assert proposal[0] == negotiator.PROPOSAL_NONE


@patch("backend.ai_opponent.agents.negotiator.random.random", side_effect=[0.1, 0.1, 0.1])
def test_decide_proposal_medium_and_hard_cover_more_branches(_mock_random):
    medium_strategy = {
        "best_alliance_target": 2,
        "strongest_team": 1,
        "is_losing": True,
        "rank_delta": -4,
    }
    medium_state = {"trust_levels": {2: 0.0}, "active_alliances": []}
    medium = negotiator._decide_proposal(medium_state, medium_strategy, "medium")
    assert medium[0] == negotiator.PROPOSAL_ALLIANCE
    assert medium[3] == negotiator.INTENT_BETRAY

    hard_strategy = {
        "best_alliance_target": 2,
        "strongest_team": 1,
        "is_losing": False,
        "rank_delta": 0,
    }
    hard_state = {"trust_levels": {2: 1.0}, "active_alliances": []}
    hard = negotiator._decide_proposal(hard_state, hard_strategy, "hard")
    assert hard[0] == negotiator.PROPOSAL_TRUCE
    assert hard[3] == negotiator.INTENT_HONOUR
