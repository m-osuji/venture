"""
Handles the dynamic narrative generation for the game using the Mellea structured framework
"""

import json
from typing import TypedDict, Any, Optional
from pydantic import BaseModel, Field

from mellea import MelleaSession, generative
from mellea.core import CBlock
from ..knowledge_profile import build_system_prompt
from ..model_loader import init_granite
from ...enums import AgentType, GameStage, AIDifficulty


class CommentaryOutput(BaseModel):
    """The strict, guardrailed schema Mellea will force Granite to output."""

    headline: str = Field(
        description="A catchy, one-sentence news headline about the current round."
    )
    summary: str = Field(
        description="A brief 2-3 sentence summary of the biggest power shifts or alliances."
    )
    targeted_taunt: Optional[str] = Field(
        description="A quick, witty jab at the player in last place, or a warning to the leader."
    )


def _derive_round_highlights(game_state: dict[str, Any]) -> dict[str, Any]:
    """
    Extracts the public, interesting events from the game state
    for the Commentator to talk about.
    """
    turn_log = game_state.get("turn_log", {})
    teams = game_state.get("teams", [])

    # sort teams by IP to find leader and last place
    sorted_teams = sorted(teams, key=lambda t: t.get("ip", 0), reverse=True)
    leader = sorted_teams[0]["team_name"] if sorted_teams else "Unknown"
    last_place = sorted_teams[-1]["team_name"] if sorted_teams else "Unknown"

    return {
        "leader": leader,
        "last_place": last_place,
        "conflicts": turn_log.get("conflicts", []),
        "new_alliances": [
            a
            for a in game_state.get("alliances", [])
            if a.get("formed_turn") == game_state.get("current_round")
        ],
        "broken_alliances": [
            a
            for a in game_state.get("alliances", [])
            if a.get("broken_turn") == game_state.get("current_round")
        ],
    }


def _fallback_commentary(
    highlights: dict[str, Any], round_number: int
) -> dict[str, str]:
    """Failsafe if the IBM toolkit goes down."""
    return {
        "headline": f"Round {round_number} concludes with {highlights['leader']} in the lead!",
        "summary": "Tensions are high as the teams prepare for the next round of market manipulation.",
        "targeted_taunt": f"Better luck next round, {highlights['last_place']}.",
    }


# ---------------------------
# mellea generative functions
# ---------------------------
@generative
def _generate_mellea_commentary(
    m: MelleaSession,
    round_number: int,
    leader: str,
    last_place: str,
    conflicts: list,
    alliances: list,
) -> CommentaryOutput:
    """
    You are the game commentator. Synthesize the following game state into an entertaining update.
    Match the tone and personality of your persona at all times.

    GAME STATE (Round {round_number})
    Leader: {leader}
    Trailing: {last_place}

    RECENT EVENTS:
    Conflicts: {conflicts}
    New Alliances: {alliances}

    Follow the required JSON schema strictly.
    """
    pass


def get_commentary(game_state: dict[str, Any]) -> dict[str, str]:
    """
    Main entry point for generating commentary.
    Uses Mellea for guaranteed structured JSON output.
    """
    round_number = game_state.get("current_round", 1)
    highlights = _derive_round_highlights(game_state)

    # parse enums safely, defaulting to 1 to prevent int/string crashes
    current_stage_int = game_state.get("current_stage", 1)

    try:
        current_stage = GameStage(current_stage_int)
    except ValueError:
        # default to PLAN if there are any parsing errors
        print(f"[commentator] error parsing stage - '{current_stage_int}'. Defaulting to PLAN.")
        current_stage = GameStage.PLAN

    difficulty_str = game_state.get("ai_difficulty", "medium")
    try:
        difficulty = AIDifficulty(difficulty_str.lower())
    except ValueError:
        # default to MEDIUM if there are any parsing errors
        print(f"[commentator] error parsing AI difficulty - '{difficulty_str}'. Defaulting to MEDIUM.")
        difficulty = AIDifficulty.MEDIUM

    # get the persona context
    base_prompt = build_system_prompt(
        AgentType.COMMENTATOR,
        difficulty=difficulty,
        agent_context={},
        current_stage=current_stage,
        event_context="",
    )

    try:
        # initialise Mellea
        m = init_granite()

        # inject the persona into the Mellea Session
        m.ctx = m.ctx.add(CBlock(base_prompt))

        # execute generation
        response = _generate_mellea_commentary(
            m,
            round_number=round_number,
            leader=highlights["leader"],
            last_place=highlights["last_place"],
            conflicts=highlights["conflicts"],
            alliances=highlights["new_alliances"],
        )

        # safely parse Pydantic to Dict
        if hasattr(response, "model_dump"):
            return response.model_dump()
        elif hasattr(response, "dict"):
            return response.dict()
        else:
            return dict(response)

    except Exception as e:
        print(
            f"[commentator] Mellea structured generation failed ({e}). Using fallback."
        )
        return _fallback_commentary(highlights, round_number)

    finally:
        # reset the context so the persona is cleared for the next AI task
        if "m" in locals():
            m.reset()
