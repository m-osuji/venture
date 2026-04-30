from enum import Enum, IntEnum


class GameStage(IntEnum):
    """
    Enum allowing for strict ordering of game stages.
    """

    PLAN = 1
    NEGOTIATE = 2
    ORDERS = 3
    RESOLVE = 4
    UPDATE = 5


class SessionStatus(str, Enum):
    """
    Enum for game session status, inheriting from str for simple JSON serialisation.
    """

    SETUP = "SETUP"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
