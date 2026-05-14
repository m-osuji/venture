from backend.enums import (
    SessionStatus,
    GameStage,
    AIDifficulty,
    AgentType
)

def test_session_status_values():
    assert SessionStatus.SETUP == "SETUP"
    assert SessionStatus.IN_PROGRESS == "IN_PROGRESS"
    assert SessionStatus.PAUSED == "PAUSED"
    assert SessionStatus.FINISHED == "FINISHED"

def test_ai_difficulty_values():
    assert AIDifficulty.EASY == "easy"
    assert AIDifficulty.MEDIUM == "medium"
    assert AIDifficulty.HARD == "hard"

def test_agent_type_values():
    assert AgentType.DECISION_MAKER == "decision_maker"
    assert AgentType.COMMENTATOR == "commentator"
    assert AgentType.NEGOTIATOR == "negotiator"

def test_game_stage_ordering():
    stages = list(GameStage)
    assert stages == [
        GameStage.PLAN,
        GameStage.NEGOTIATE,
        GameStage.ORDERS,
        GameStage.RESOLVE,
        GameStage.UPDATE,
    ]
