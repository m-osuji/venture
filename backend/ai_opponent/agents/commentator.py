"""
Handles the dynamic narrative generation for the game using the Mellea structured framework
"""

import json
from typing import Any, Optional
from pydantic import BaseModel, Field

from mellea import MelleaSession, generative
from mellea.core import CBlock
from ..knowledge_profile import build_system_prompt
from ..model_loader import init_granite
from ...enums import AgentType, GameStage, AIDifficulty


class CommentaryOutput(BaseModel):
    """The strict, guardrailed schema Mellea will force Granite to output."""

    summary: str = Field(
        description="A brief 2-3 sentence summary of the biggest power shifts or alliances."
    )
    targeted_taunt: str = Field(
        description="A snarky remark directed at the most notable team this round"
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
        "summary": "Tensions are high as the teams prepare for the next round of market manipulation.",
        "targeted_taunt": f"Better luck next round, {highlights['last_place']}.",
    }


# ---------------------------
# mellea generative functions
# ---------------------------
@generative
def _generate_mellea_commentary(
    round_number: int,
    leader: str,
    last_place: str,
    conflicts: list,
    alliances: list,
) -> CommentaryOutput:
    """
    You are the game commentator. In under 100 words, summarise this round entertainingly.
    Stay in character with your persona.

    Current leader: {leader}. Currently trailing: {last_place}.
    Round number: {round_number}.
    Conflicts this round: {conflicts}
    New alliances: {alliances}

    Write a creative summary. targeted_taunt must be a snarky remark.

    Follow the JSON schema strictly.
    """


def _build_event_context(game_state: dict) -> str:
    """ Reactively build the event context based on game stage"""
    stage = game_state.get("current_stage")
    turn_log = game_state.get("turn_log") or {}

    if stage == GameStage.RESOLVE:
        conflicts = turn_log.get("conflicts", [])
        if conflicts:
            return json.dumps(conflicts)
        return "No conflicts this round."

    elif stage == GameStage.ORDERS:
        declared = turn_log.get("declared_moves") or {}
        actual = turn_log.get("actual_moves") or {}
        violations = [
            f"{tid} switched from {declared.get(tid, {}).get('action')} to {actual[tid].get('action')}"
            for tid in actual
            if actual[tid].get("action") != declared.get(tid, {}).get("action")
        ]
        return ", ".join(violations) if violations else "All teams followed through on their plans."

    elif stage == GameStage.NEGOTIATE:
        log = turn_log.get("negotiation_log", [])
        return json.dumps(log) if log else "No negotiations recorded."

    return "No notable events."


def get_commentary(game_state: dict[str, Any]) -> dict[str, str]:
    """
    Main entry point for generating commentary.
    Uses Mellea for guaranteed structured JSON output.
    """
    round_number = game_state.get("current_round", 1)
    highlights = _derive_round_highlights(game_state)
    print(f"[commentator] highlights derived: {highlights}")

    # parse enums safely, defaulting to 1 to prevent int/string crashes
    current_stage_int = game_state.get("current_stage", 1)

    try:
        current_stage = GameStage(current_stage_int)
    except ValueError:
        # default to PLAN if there are any parsing errors
        print(f"[commentator] error parsing stage - '{current_stage_int}'. Defaulting to PLAN.")
        current_stage = GameStage.PLAN

    ai_team = next((t for t in game_state.get("teams", []) if t.get("is_ai")), None)
    difficulty_str = ai_team.get("difficulty", "medium") if ai_team else "medium"

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
        event_context=_build_event_context(game_state),
    )

    try:
        # initialise Mellea
        session = init_granite()
        print("[commentator] session initialised")

        # inject the persona into the Mellea Session
        session.ctx = session.ctx.add(CBlock(base_prompt))
        print("[commentator] context injected")
        # execute generation
        response = _generate_mellea_commentary(
            session, # use session as first positional argument
            round_number=round_number,
            leader=highlights["leader"],
            last_place=highlights["last_place"],
            conflicts=highlights["conflicts"],
            alliances=highlights["new_alliances"],
        )

        print(f"[commentator] response received: {response}")
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
        if "session" in locals():
            session.reset()
