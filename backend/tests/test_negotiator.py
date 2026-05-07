import pytest
from unittest.mock import MagicMock, patch

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