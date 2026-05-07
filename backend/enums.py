from enum import Enum, IntEnum


class SessionStatus(str, Enum):
    """
    Enum for game session status, inheriting from str for simple JSON serialisation.
    """

    SETUP = "SETUP"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"


class GameStage(IntEnum):
    """
    Enum allowing for strict ordering of game stages.
    """

    PLAN = 1
    NEGOTIATE = 2
    ORDERS = 3
    RESOLVE = 4
    UPDATE = 5


class AIDifficulty(str, Enum):
    """
    Enum to represent the AI opponent's difficulty levels.
    """

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AgentType(str, Enum):
    """
    Enum to represent the game's different agent types, for maintainability.
    """

    DECISION_MAKER = "decision_maker"
    COMMENTATOR = "commentator"
    NEGOTIATOR = "negotiator"
