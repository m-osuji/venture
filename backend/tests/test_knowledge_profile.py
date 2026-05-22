import pytest

from backend.enums import AIDifficulty, AgentType, GameStage
from backend.ai_opponent.knowledge_profile import (
    get_attributes,
    get_persona,
    get_quiz_stats,
    build_system_prompt,
    build_knowledge_profile,
)

def test_get_attributes_success(monkeypatch):
    # patch the REAL dependency path
    monkeypatch.setattr(
        "backend.helpers.db_helpers.fetch_market_by_id",
        lambda market_id: {
            "market_id": market_id,
            "market_name": "Finance",
        },
    )

    result = get_attributes(1)

    assert result["market_id"] == 1
    assert result["market_name"] == "Finance"


def test_get_attributes_missing_market(monkeypatch):
    monkeypatch.setattr(
        "backend.helpers.db_helpers.fetch_market_by_id",
        lambda market_id: None,
    )

    with pytest.raises(ValueError, match="does not exist"):
        get_attributes(999)


def test_get_attributes_db_error(monkeypatch):
    def boom(_):
        raise Exception("db exploded")

    monkeypatch.setattr(
        "backend.helpers.db_helpers.fetch_market_by_id",
        boom,
    )

    with pytest.raises(ValueError, match="Error fetching market data"):
        get_attributes(1)

def test_get_persona_easy():
    result = get_persona(AIDifficulty.EASY)
    assert "flashy, careless beginner investor" in result


def test_get_persona_invalid():
    with pytest.raises(ValueError, match="Invalid difficulty"):
        get_persona("impossible")  # type: ignore


def test_get_quiz_stats_known_topic():
    result = get_quiz_stats(AIDifficulty.HARD, "Cybersecurity")

    assert result["win_probability"] == 0.95
    assert result["speed_ms"] == 2500


def test_get_quiz_stats_unknown_topic():
    result = get_quiz_stats(AIDifficulty.MEDIUM, "Unknown Topic")

    assert result["win_probability"] == 0.50
    assert result["speed_ms"] == 5000


def test_get_quiz_stats_invalid_difficulty():
    with pytest.raises(ValueError, match="Invalid difficulty"):
        get_quiz_stats("broken", "AI")  # type: ignore

def test_build_system_prompt_decision_maker_plan():
    result = build_system_prompt(
        agent_type=AgentType.DECISION_MAKER,
        difficulty=AIDifficulty.MEDIUM,
        agent_context={"ip": 25, "owned_markets": [{"name": "Healthcare"}]},
        current_stage=GameStage.PLAN,
        event_context="",
    )

    assert "smart, careful business manager" in result
    assert "PLAN stage" in result
    assert "25 Influence Points" in result
    assert "Healthcare" in result


def test_build_system_prompt_decision_maker_orders():
    result = build_system_prompt(
        agent_type=AgentType.DECISION_MAKER,
        difficulty=AIDifficulty.HARD,
        agent_context={"ip": 10, "owned_markets": []},
        current_stage=GameStage.ORDERS,
        event_context="You promised not to attack.",
    )

    assert "cold, ruthless, and expert market boss" in result
    assert "ORDERS stage" in result
    assert "You promised not to attack." in result


def test_build_system_prompt_negotiator():
    result = build_system_prompt(
        agent_type=AgentType.NEGOTIATOR,
        difficulty=AIDifficulty.EASY,
        agent_context={"ip": 5, "owned_markets": [{"name": "AI"}]},
        current_stage=GameStage.NEGOTIATE,
        event_context="Recent trade talks",
    )

    assert "NEGOTIATE stage" in result
    assert "Recent trade talks" in result
    assert "propose an alliance" in result


def test_build_system_prompt_commentator():
    result = build_system_prompt(
        agent_type=AgentType.COMMENTATOR,
        difficulty=AIDifficulty.EASY,
        agent_context={"ip": 0, "owned_markets": []},
        current_stage=GameStage.RESOLVE,
        event_context="Market chaos",
    )

    assert "RESOLVE stage" in result
    assert "Market chaos" in result
    assert "under 100 words" in result


def test_build_system_prompt_invalid_agent_type():
    with pytest.raises(ValueError, match="Unknown agent_type"):
        build_system_prompt(
            agent_type="bad",  # type: ignore
            difficulty=AIDifficulty.EASY,
            agent_context={},
            current_stage=GameStage.PLAN,
        )

def test_build_knowledge_profile():
    result = build_knowledge_profile(AIDifficulty.EASY)

    assert "flashy, careless beginner investor" in result
    assert "AI opponent in a market strategy game" in result