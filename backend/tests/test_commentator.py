import sys

import pytest

from backend.ai_opponent.agents import commentator

from backend.ai_opponent.agents.commentator import (
    _derive_round_highlights,
    _fallback_commentary,
    _build_event_context,
)

# Keep module fakes local to commentator tests so later test modules can import
# the real knowledge_profile/model_loader/mellea modules.
for module_name in (
    "backend.ai_opponent.knowledge_profile",
    "backend.ai_opponent.model_loader",
    "mellea",
    "mellea.core",
):
    sys.modules.pop(module_name, None)

@pytest.fixture(autouse=True)
def patch_commentator(monkeypatch):
    monkeypatch.setattr(
        commentator,
        "build_system_prompt",
        lambda *args, **kwargs: "prompt"
    )

    monkeypatch.setattr(
        commentator,
        "init_granite",
        lambda: type("FakeModel", (), {"instruct": lambda self, x: "ok"})())



def test_derive_round_highlights():
    game_state = {
        "current_round": 2,
        "teams": [
            {"team_name": "Alpha", "ip": 100},
            {"team_name": "Beta", "ip": 20},
        ],
        "turn_log": {
            "conflicts": ["war"]
        },
        "alliances": [
            {"formed_turn": 2, "teams": ["A", "B"]},
            {"broken_turn": 2, "teams": ["C", "D"]},
        ]
    }

    result = _derive_round_highlights(game_state)

    assert result["leader"] == "Alpha"
    assert result["last_place"] == "Beta"
    assert result["conflicts"] == ["war"]
    assert len(result["new_alliances"]) == 1
    assert len(result["broken_alliances"]) == 1

def test_fallback_commentary():
    highlights = {
        "last_place": "Beta"
    }

    result = _fallback_commentary(highlights, 2)

    assert "summary" in result
    assert "targeted_taunt" in result
    assert "Beta" in result["targeted_taunt"]


def test_build_event_context_resolve():
    from backend.enums import GameStage

    game_state = {
        "current_stage": GameStage.RESOLVE,
        "turn_log": {
            "conflicts": ["fight"]
        }
    }

    result = _build_event_context(game_state)

    assert "fight" in result

    result = _build_event_context(game_state)

    assert "fight" in result

def test_build_event_context_orders_violation():
    from backend.enums import GameStage

    game_state = {
        "current_stage": GameStage.ORDERS,
        "turn_log": {
            "declared_moves": {
                1: {"action": "attack"}
            },
            "actual_moves": {
                1: {"action": "defend"}
            }
        }
    }

    result = _build_event_context(game_state)

    assert "switched from attack to defend" in result

def test_build_event_context_negotiate():
    from backend.enums import GameStage

    game_state = {
        "current_stage": GameStage.NEGOTIATE,
        "turn_log": {
            "negotiation_log": ["deal made"]
        }
    }

    result = _build_event_context(game_state)

    assert "deal made" in result

def test_build_event_context_unknown_stage():
    result = _build_event_context({})

    assert result == "No notable events."


# Tests commentary fallback activates when generation fails
def test_get_commentary_fallback(monkeypatch):
    from backend.ai_opponent.agents import commentator

    monkeypatch.setattr(
        commentator,
        "init_granite",
        lambda: (_ for _ in ()).throw(Exception("Granite failed"))
    )

    game_state = {
        "current_round": 1,
        "teams": [
            {"team_name": "Alpha", "ip": 100},
            {"team_name": "Beta", "ip": 20},
        ]
    }

    result = commentator.get_commentary(game_state)

    assert "summary" in result
    assert "targeted_taunt" in result

