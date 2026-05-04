# handles the negotiation logic for the AI opponent strategy

import re
import random
import html
from typing import Any
from ..knowledge_profile import build_knowledge_profile
from ..model_loader import init_granite

# What the ai is able to offer
PROPOSAL_ALLIANCE = 'alliance'
PROPOSAL_TRUCE    = 'truce'
PROPOSAL_NONE     = 'none'

# what the ai secretly intends
INTENT_HONOUR  = 'honour'
INTENT_BETRAY  = 'betray'
INTENT_NEUTRAL = 'neutral'

# starting betrayal probability before anything is applied
BASE_BETRAY_CHANCE = {'easy': 0.00, 'medium': 0.20, 'hard': 0.50}

from typing import TypedDict, Any


class NegotiationMove(TypedDict):
    proposal_type: str
    proposal_target: str
    proposal_detail: str
    secret_intent: str
    taunt: str
    current_rank: int
    _reasoning: str


def derive_teams_with_markets(game_state, ai_team_id):
    teams = game_state.get('teams', [])
    market_state = game_state.get('market_state', {})

    markets_per_team = {}

    for state in market_state.values():
        owner = state.get('owner')
        if owner is not None:
            markets_per_team[owner] = markets_per_team.get(owner, 0) + 1

    result = []
    for t in teams:
        if t['team_id'] == ai_team_id or t.get('is_ai', False):
            continue

        result.append({
            'team_id': t['team_id'],
            'team_name': t['team_name'],
            'ip': t.get('ip', 0),
            'market_count': markets_per_team.get(t['team_id'], 0),
        })

    return result


def derive_active_alliances(game_state: dict[str, Any], ai_team_id: int) -> list[dict[str, Any]]:
    #gets the current alliances with the ai and how long they've been active

    alliances  = game_state.get('alliances', [])
    teams      = game_state.get('teams', [])
    current_round = game_state.get('current_round', 1)

    team_name_lookup = {t['team_id']: t['team_name'] for t in teams}

    result = []
    for alliance in alliances:
        if alliance.get('broken_turn') is not None:
            continue

        members = alliance.get('members', [])
        if ai_team_id not in members:
            continue

        formed_turn   = int(alliance.get('formed_turn') or 1)
        rounds_active = max(1, current_round - formed_turn + 1)

        for member in members:
            if member != ai_team_id:
                result.append({
                    'with_team_id': member,
                    'with_team': team_name_lookup.get(member, str(member)),
                    'rounds_active': rounds_active,
                })

    return result


def get_trust_levels(agent_context, game_state):
    # relationship_states are for per market, so they get mapped back to teams
    teams = game_state.get('teams', [])
    market_state = game_state.get('market_state', {})
    rel_states = agent_context.get('relationship_states', {})

    trust_totals = {}
    trust_counts = {}

    for market_id, rel in rel_states.items():
        market = market_state.get(str(market_id)) or market_state.get(market_id)
        if not market:
            continue

        owner = market.get('owner')
        if owner is None:
            continue

        trust = rel.get('trust', 0.7)

        if owner not in trust_totals:
            trust_totals[owner] = 0
            trust_counts[owner] = 0

        trust_totals[owner] += trust
        trust_counts[owner] += 1

    result = {}
    for t in teams:
        tid = t['team_id']

        if tid in trust_totals:
            result[tid] = trust_totals[tid] / trust_counts[tid]
        else:
            result[tid] = t.get('ethical_score', 0.5)

    return result


def score_game_state(game_state: dict[str, Any]) -> dict[str, Any]:
    teams         = game_state.get('teams', [])
    owned_markets = game_state.get('owned_markets', [])
    previous_rank = game_state.get('previous_rank')

    if not teams:
        return {
            'strongest_team': None,
            'weakest_team': None,
            'is_losing': False,
            'rank_delta': 0,
            'current_rank': 1,
            'ai_market_count': len(owned_markets),
            'avg_team_markets': 0.0,
            'best_alliance_target': None,
            'threat_ranking': [],
        }

    def team_score(t):
        return t.get('ip', 0) + len(t.get('markets', [])) * 2

    sorted_teams   = sorted(teams, key=team_score, reverse=True)
    threat_ranking = [t.get('team_name', 'Unknown') for t in sorted_teams]

    avg_team_markets = sum(len(t.get('markets', [])) for t in teams) / len(teams)
    is_losing        = len(owned_markets) < avg_team_markets

    ai_score   = game_state.get('current_ip', 0) + len(owned_markets) * 2
    all_scores = [team_score(t) for t in teams]

    current_rank = sum(1 for s in all_scores if s > ai_score) + 1
    rank_delta   = (int(previous_rank) - current_rank) if previous_rank is not None else 0

    active_ally_ids = {
        a.get('with_team_id')
        for a in game_state.get('active_alliances', [])
    }

    non_allied = [t for t in sorted_teams if t['team_id'] not in active_ally_ids]
    best_target = non_allied[-1]['team_id'] if non_allied else None

    return {
        'strongest_team':       sorted_teams[0]['team_id'],
        'weakest_team':         sorted_teams[-1]['team_id'],
        'is_losing':            is_losing,
        'rank_delta':           rank_delta,
        'current_rank':         current_rank,
        'ai_market_count':      len(owned_markets),
        'avg_team_markets':     avg_team_markets,
        'best_alliance_target': best_target,
        'threat_ranking':       threat_ranking,
    }


def _decide_proposal(
    game_state: dict[str, Any],
    strategy:   dict[str, Any],
    difficulty: str,
) -> tuple[str, str, str, str, str]:
    # Chooses what negotiation action the AI will take between: alliance, truce or nothing

    trust_levels      = game_state.get('trust_levels', {})
    active_ally_ids   = {
        a.get('with_team_id')
        for a in game_state.get('active_alliances', [])
    }

    best_target = strategy.get('best_alliance_target')
    strongest   = strategy.get('strongest_team')
    is_losing   = strategy.get('is_losing', False)
    rank_delta  = strategy.get('rank_delta', 0)

    def betrayal_chance(target):
        base = BASE_BETRAY_CHANCE.get(difficulty, 0.0)

        trust = trust_levels.get(target, 0.5)
        trust_modifier = (0.5 - trust) * 0.6

        momentum_modifier = max(-0.15, min(0.2, -rank_delta * 0.05))

        chance = base + trust_modifier + momentum_modifier
        return max(0.0, min(0.9, chance))

    def willingness_to_ally(target):
        trust = trust_levels.get(target, 0.5)
        return random.random() < (0.75 * trust + 0.125)

    def resolve_intent(chance):
        return INTENT_BETRAY if chance > 0.5 else INTENT_HONOUR

    if difficulty == 'easy':
        if best_target is not None and willingness_to_ally(best_target):
            return (
                PROPOSAL_ALLIANCE,
                best_target,
                "I propose a truce, I will not attack any of your markets this round.",
                INTENT_HONOUR,
                f"Easy: alliance with {best_target}",
            )
        return (PROPOSAL_NONE, 'none', 'none', INTENT_NEUTRAL, "Easy: no suitable target.")

    if difficulty == 'medium':
        if is_losing and best_target is not None and willingness_to_ally(best_target):
            chance = betrayal_chance(best_target)
            intent = resolve_intent(chance)

            return (
                PROPOSAL_ALLIANCE,
                best_target,
                "I propose an alliance, I will not attack any of your markets this round.",
                intent,
                f"Medium: alliance with {best_target}",
            )

        if strongest is not None and strongest not in active_ally_ids:
            return (
                PROPOSAL_TRUCE,
                strongest,
                "I will not attack any of your markets this round. Let us not waste IP on each other.",
                INTENT_HONOUR,
                f"Medium: truce with leader {strongest}",
            )

        return (PROPOSAL_NONE, 'none', 'none', INTENT_NEUTRAL, "Medium: no move.")

    if difficulty == 'hard':
        if strongest is not None and strongest not in active_ally_ids and random.random() < 0.2:
            return (
                PROPOSAL_TRUCE,
                strongest,
                "Stay out of my way and I'll stay out of yours for one round.",
                INTENT_HONOUR,
                f"Hard: pressure on {strongest}",
            )

        if best_target is not None and willingness_to_ally(best_target):
            chance = betrayal_chance(best_target)
            intent = resolve_intent(chance)

            return (
                PROPOSAL_ALLIANCE,
                best_target,
                "An alliance between us makes sense, I will not attack any of your markets this round.",
                intent,
                f"Hard: alliance with {best_target}",
            )

        return (PROPOSAL_NONE, 'none', 'none', INTENT_NEUTRAL, "Hard: no target.")

    return (PROPOSAL_NONE, 'none', 'none', INTENT_NEUTRAL, "Fallback")


def make_prompt(
    game_state: dict[str, Any],
    strategy: dict[str, Any],
    proposal_type: str,
    proposal_target: str,
    proposal_detail: str,
    secret_intent: str,
    difficulty: str,
) -> str:

    base_prompt = build_knowledge_profile(difficulty)

    teams_summary = "".join(
        f"  - {html.escape(t.get('team_name') or 'Unknown')}: {t.get('ip', 0)} IP, {len(t.get('markets', []))} market(s)\n"
        for t in game_state.get('teams', [])
    )

    alliances_summary = "".join(
        f"  - Allied with {a.get('with_team', 'Unknown')} for {a.get('rounds_active', 0)} round(s)\n"
        for a in game_state.get('active_alliances', [])
    ) or "  - No active alliances\n"

    rank_delta = strategy.get('rank_delta', 0)
    momentum = "improving" if rank_delta > 0 else "declining" if rank_delta < 0 else "steady"

    intent_context = {
        INTENT_HONOUR:  "You intend to honour this proposal.",
        INTENT_BETRAY:  "You intend to betray this proposal later, don't hint at it.",
        INTENT_NEUTRAL: "You are making no proposal this round.",
    }.get(secret_intent, "")

    if proposal_type == PROPOSAL_NONE:
        proposal_detail = 'none'

    return f"""
{base_prompt}

GAME STATE (Round {game_state.get('round_number', '?')})
Your IP: {game_state.get('current_ip', 0)} | Markets: {strategy.get('ai_market_count', 0)} | Status: {'LOSING' if strategy.get('is_losing') else 'WINNING'} | Momentum: {momentum}
Threat ranking: {', '.join(strategy.get('threat_ranking', []))}
Teams: {teams_summary}Alliances: {alliances_summary}

DECISION
Proposal: {proposal_type} → {proposal_target} | {proposal_detail}
{intent_context}

Write a one-sentence in-character taunt for all players, and rephrase the proposal in your voice.

TAUNT: <one sentence>
PROPOSAL_DETAIL: <rephrased or 'none'>
"""


def parse_llm_response(raw: str, fallback_detail: str, proposal_type: str) -> tuple[str, str]:
    taunt_match  = re.search(r'TAUNT:\s*(.*?)(?:\n|$)', raw, re.DOTALL | re.IGNORECASE)
    detail_match = re.search(r'PROPOSAL_DETAIL:\s*(.*)', raw, re.DOTALL | re.IGNORECASE)

    taunt  = taunt_match.group(1).strip() if taunt_match else '...'
    detail = detail_match.group(1).strip() if detail_match else fallback_detail

    if proposal_type == PROPOSAL_NONE:
        detail = 'none'

    return taunt, detail


def _fallback_taunt(difficulty: str, strategy: dict[str, Any]) -> str:
    strongest = strategy.get('strongest_team', 'everyone')

    return {
        'easy':   "I hope we can all have fun today!",
        'medium': "Choose your allies wisely this round.",
        'hard':   f"{strongest}, youre next...",
    }.get(difficulty, '...')


def get_negotiation_move(
    agent_context: dict[str, Any],
    full_game_state: dict[str, Any],
    ai_team_id: int,
    difficulty: str,
    previous_rank: int | None = None,
) -> tuple[NegotiationMove, Any]:

    teams = derive_teams_with_markets(full_game_state, ai_team_id)
    active_alliances = derive_active_alliances(full_game_state, ai_team_id)
    trust_levels = get_trust_levels(agent_context, full_game_state)

    internal_state = {
        'current_ip': full_game_state.get('current_ip', 0),
        'owned_markets': agent_context.get('owned_markets', []),
        'teams': teams,
        'active_alliances': active_alliances,
        'trust_levels': trust_levels,
        'round_number': full_game_state.get('current_round', '?'),
        'previous_rank': previous_rank,
    }

    strategy = score_game_state(internal_state)

    proposal_type, proposal_target, proposal_detail, secret_intent, reasoning = _decide_proposal(
        internal_state, strategy, difficulty
    )

    try:
        session = init_granite()
        prompt = make_prompt(
            internal_state,
            strategy,
            proposal_type,
            proposal_target,
            proposal_detail,
            secret_intent,
            difficulty,
        )

        response = session.instruct(prompt)
        raw_text = str(response)

        taunt, parsed_detail = parse_llm_response(raw_text, proposal_detail, proposal_type)

        if taunt == '...':
            taunt = _fallback_taunt(difficulty, strategy)

        proposal_detail = parsed_detail

    except Exception as e:
        print(f'[negotiator] Granite failed ({e}). Using fallback.')
        taunt = _fallback_taunt(difficulty, strategy)
        if proposal_type == PROPOSAL_NONE:
            proposal_detail = 'none'

    return {
        'proposal_type': proposal_type,
        'proposal_target': proposal_target,
        'proposal_detail': proposal_detail,
        'secret_intent': secret_intent,
        'taunt': taunt,
        'current_rank': strategy.get('current_rank', 1),
        '_reasoning': reasoning,
    }, reasoning