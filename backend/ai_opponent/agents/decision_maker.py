"""
decision_maker.py

First-pass AI decision maker for the market strategy game.

What this module does now:
- Generates legal-ish actions from the current game state
- Supports both single-action choice and a small round-order bundle
- Models defend reallocation when source-market IP is available
- Models explicit research options with regulation-aware costs
- Uses DB-backed market/synergy information to score actions
- Uses structured decision traits by difficulty
- Returns debug info to help tune the heuristics

What this module cannot fully do yet:
- It does NOT know your exact runtime game-state schema yet
- It does NOT know the exact engine-side legality rules for all actions
- It does NOT yet handle alliances / negotiation / betrayal in full depth
- It does NOT yet use Mellea/Granite directly
- It assumes enemy_markets are attackable unless attackable_markets is provided
- It uses a few scoring proxies where exact rules are not wired yet

Expected minimal game_state shape (roughly):
{
    "current_ip": 5,
    "owned_markets": [1, 4],
    "enemy_markets": [2, 3],
    "neutral_markets": [5],
    "allied_markets": [6],
    "attackable_markets": [2, 3, 5],  # optional; preferred when available
    "market_states": {
        1: {"threat": 0.6, "research_level": 0, "allocated_ip": 2},
        2: {"enemy_strength_estimate": 3},
        "3": {"enemy_strength_estimate": 2}
    },
    "relationship_states": {
        6: {"alliance_turns": 2, "trust": 0.9}
    },
    "commitments": {
        "avoid_attack_markets": [6]
    },
    "rules": {
        "attack_cost": 1,
        "defend_cost": 1,
        "research_cost": 2,
        "high_regulation_research_surcharge": 1,
        "maintenance_threshold": 5,
        "maintenance_penalty_per_market": 2.0,
        "allow_attack_allies": False,
        "max_orders_per_round": 3
    }
}

Returned action shape:
{
    "action_type": "attack" | "defend" | "research" | "hold",
    "target_market_id": int | None,
    "source_market_id": int | None,
    "ip_spent": int,
    "metadata": {...}
}

choose_orders(...) returns:
{
    "orders": [action_dict, ...],
    "current_ip_spent": int,
    "market_ip_reallocated": int,
    "remaining_current_ip": int,
    "total_score": float
}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
import sqlite3

from backend.helpers.db_helpers import get_db_path
from backend.ai_opponent import knowledge_profile


# -----------------------------------------------------------------------------
# Static configuration / fallback traits
# -----------------------------------------------------------------------------

TOPIC_KEYS = (
    "AI",
    "Data Science",
    "Cybersecurity",
    "AI in Law",
    "Ethics",
    "Education",
)

RESEARCH_OPTIONS: Dict[str, Dict[str, str]] = {
    "increase_production": {
        "label": "Increase Production",
        "description": "Increase market IP generation over time.",
    },
    "reduce_regulation_burden": {
        "label": "Reduce Regulation Burden",
        "description": "Lower future upgrade friction on regulated markets.",
    },
    "improve_security": {
        "label": "Improve Security",
        "description": "Reduce risk-based defensive weakness.",
    },
    "fortify_market": {
        "label": "Fortify Market",
        "description": "Add permanent defensive resilience.",
    },
}

# Fallback traits for a logic-based decision maker.
# Replace / override these later with proper knowledge_profile methods if desired.
DEFAULT_TRAITS_BY_DIFFICULTY: Dict[str, Dict[str, Any]] = {
    "easy": {
        "quiz_strength": 0.35,
        "risk_tolerance": 0.80,
        "aggression": 0.70,
        "defense_bias": 0.25,
        "ethical_bias": 0.55,
        "topic_strengths": {
            "AI": 0.40,
            "Data Science": 0.35,
            "Cybersecurity": 0.35,
            "AI in Law": 0.30,
            "Ethics": 0.40,
            "Education": 0.45,
        },
    },
    "medium": {
        "quiz_strength": 0.60,
        "risk_tolerance": 0.50,
        "aggression": 0.55,
        "defense_bias": 0.60,
        "ethical_bias": 0.70,
        "topic_strengths": {
            "AI": 0.60,
            "Data Science": 0.65,
            "Cybersecurity": 0.55,
            "AI in Law": 0.50,
            "Ethics": 0.60,
            "Education": 0.55,
        },
    },
    "hard": {
        "quiz_strength": 0.85,
        "risk_tolerance": 0.45,
        "aggression": 0.80,
        "defense_bias": 0.80,
        "ethical_bias": 0.25,
        "topic_strengths": {
            "AI": 0.85,
            "Data Science": 0.90,
            "Cybersecurity": 0.85,
            "AI in Law": 0.75,
            "Ethics": 0.70,
            "Education": 0.75,
        },
    },
}

TRAIT_ENUM_SCORE = {
    "small": 1.0,
    "medium": 2.0,
    "large": 3.0,
    "very large": 4.0,
    "low": 1.0,
    "high": 3.0,
    "very high": 4.0,
}

BONUS_OPERATOR_VALUE = {
    "plus_two": 2.0,
    "plus_one": 1.0,
    "minus_one": -1.0,
    "ignore_one": 0.5,  # proxy until exact semantics are wired
}

ACTION_BONUS_WEIGHTS = {
    "attack": {
        "ip": 1.2,
        "research_cost": 0.5,
        "expansion_strength": 1.6,
        "defence": 0.7,
        "regulation_mitigation": 0.9,
        "growth_bonus": 1.1,
        "attack": 1.5,
        "risk_control": 1.0,
        "tiebreak": 0.8,
    },
    "defend": {
        "ip": 1.0,
        "research_cost": 0.4,
        "expansion_strength": 0.6,
        "defence": 1.6,
        "regulation_mitigation": 1.1,
        "growth_bonus": 0.8,
        "attack": 0.5,
        "risk_control": 1.2,
        "tiebreak": 1.0,
    },
    "research": {
        "ip": 1.0,
        "research_cost": 1.7,
        "expansion_strength": 0.7,
        "defence": 0.7,
        "regulation_mitigation": 1.2,
        "growth_bonus": 1.6,
        "attack": 0.4,
        "risk_control": 0.8,
        "tiebreak": 0.6,
    },
    "hold": {
        "ip": 0.2,
        "research_cost": 0.2,
        "expansion_strength": 0.2,
        "defence": 0.2,
        "regulation_mitigation": 0.2,
        "growth_bonus": 0.2,
        "attack": 0.2,
        "risk_control": 0.2,
        "tiebreak": 0.2,
    },
}


# -----------------------------------------------------------------------------
# Data containers
# -----------------------------------------------------------------------------

@dataclass
class Action:
    action_type: str
    target_market_id: Optional[int] = None
    source_market_id: Optional[int] = None
    ip_spent: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "target_market_id": self.target_market_id,
            "source_market_id": self.source_market_id,
            "ip_spent": self.ip_spent,
            "metadata": self.metadata,
        }


@dataclass
class ScoredAction:
    action: Action
    score: float
    reasons: Dict[str, float]

    def to_debug_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "score": round(self.score, 3),
            "reasons": {k: round(v, 3) for k, v in self.reasons.items()},
        }


@dataclass
class BundleSelectionState:
    remaining_current_ip: int
    remaining_reallocatable_ip: Dict[int, int]


# -----------------------------------------------------------------------------
# Public entry point
# -----------------------------------------------------------------------------

def choose_action(
    game_state: Dict[str, Any],
    difficulty: str = "medium",
    return_debug: bool = False,
) -> Dict[str, Any]:
    """
    Main decision-maker entry point.

    Steps:
    1. Get decision traits
    2. Generate legal-ish actions
    3. Score each action
    4. Choose the best action
    """
    traits = get_decision_traits(difficulty)
    legal_actions = generate_legal_actions(game_state)

    if not legal_actions:
        fallback = Action(action_type="hold", ip_spent=0, metadata={"reason": "no_legal_actions"})
        return fallback.to_dict()

    scored_actions: List[ScoredAction] = []
    for action in legal_actions:
        score, reasons = score_action(action, game_state, traits)
        scored_actions.append(ScoredAction(action=action, score=score, reasons=reasons))

    chosen = select_best_action(scored_actions)

    if return_debug:
        ranked = sorted(scored_actions, key=lambda sa: sa.score, reverse=True)
        return {
            "chosen_action": chosen.action.to_dict(),
            "chosen_score": round(chosen.score, 3),
            "chosen_reasons": {k: round(v, 3) for k, v in chosen.reasons.items()},
            "traits": traits,
            "ranked_actions": [sa.to_debug_dict() for sa in ranked],
        }

    return chosen.action.to_dict()


def choose_orders(
    game_state: Dict[str, Any],
    difficulty: str = "medium",
    return_debug: bool = False,
    max_actions: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Best-effort round planner that returns a small compatible order bundle.
    """
    traits = get_decision_traits(difficulty)
    scored_actions = _score_legal_actions(game_state, traits)
    current_ip = _get_current_ip(game_state)

    if not scored_actions:
        fallback = Action(action_type="hold", ip_spent=0, metadata={"reason": "no_legal_actions"})
        return {
            "orders": [fallback.to_dict()],
            "current_ip_spent": 0,
            "market_ip_reallocated": 0,
            "remaining_current_ip": current_ip,
            "total_score": 0.0,
        }

    hold_action = next((sa for sa in scored_actions if sa.action.action_type == "hold"), None)
    hold_score = hold_action.score if hold_action else 0.0

    selected, selection_state = select_best_order_bundle(
        scored_actions,
        game_state,
        traits,
        hold_score=hold_score,
        max_actions=max_actions,
    )

    if not selected:
        fallback = hold_action or ScoredAction(
            action=Action(action_type="hold", ip_spent=0, metadata={"reason": "no_viable_orders"}),
            score=hold_score,
            reasons={"fallback": hold_score},
        )
        selected = [fallback]

    current_ip_spent = sum(
        sa.action.ip_spent for sa in selected if _action_uses_shared_ip(sa.action)
    )
    market_ip_reallocated = sum(
        sa.action.ip_spent for sa in selected if _action_uses_reallocated_ip(sa.action)
    )

    response = {
        "orders": [sa.action.to_dict() for sa in selected],
        "current_ip_spent": current_ip_spent,
        "market_ip_reallocated": market_ip_reallocated,
        "remaining_current_ip": selection_state.remaining_current_ip,
        "total_score": round(sum(sa.score for sa in selected), 3),
    }

    if return_debug:
        ranked = sorted(scored_actions, key=lambda sa: sa.score, reverse=True)
        response.update(
            {
                "traits": traits,
                "selected_actions_debug": [sa.to_debug_dict() for sa in selected],
                "ranked_actions": [sa.to_debug_dict() for sa in ranked],
            }
        )

    return response


# -----------------------------------------------------------------------------
# Trait handling
# -----------------------------------------------------------------------------

def get_decision_traits(difficulty: str) -> Dict[str, Any]:
    """
    Fetch structured traits for the decision-maker.

    This is future-proofed:
    - If knowledge_profile later exposes get_decision_traits(difficulty), use it.
    - Otherwise fall back to local defaults.
    """
    difficulty = difficulty.lower().strip()

    profile_method = getattr(knowledge_profile, "get_decision_traits", None)
    if callable(profile_method):
        raw = profile_method(difficulty)
        if isinstance(raw, dict):
            return _normalise_traits(raw, difficulty)

    if difficulty not in DEFAULT_TRAITS_BY_DIFFICULTY:
        raise ValueError(
            f"[decision_maker] Invalid difficulty: {difficulty}. "
            f"Choose from {list(DEFAULT_TRAITS_BY_DIFFICULTY.keys())}."
        )

    return _normalise_traits(DEFAULT_TRAITS_BY_DIFFICULTY[difficulty], difficulty)


def _normalise_traits(raw: Dict[str, Any], difficulty: str) -> Dict[str, Any]:
    topic_strengths = raw.get("topic_strengths", {}) or {}
    normalised_topics = {}

    fallback_quiz_strength = float(raw.get("quiz_strength", 0.5))

    for topic in TOPIC_KEYS:
        normalised_topics[topic] = float(topic_strengths.get(topic, fallback_quiz_strength))

    return {
        "difficulty": difficulty,
        "quiz_strength": float(raw.get("quiz_strength", 0.5)),
        "risk_tolerance": float(raw.get("risk_tolerance", 0.5)),
        "aggression": float(raw.get("aggression", 0.5)),
        "defense_bias": float(raw.get("defense_bias", 0.5)),
        "ethical_bias": float(raw.get("ethical_bias", 0.5)),
        "topic_strengths": normalised_topics,
    }


# -----------------------------------------------------------------------------
# Legal action generation
# -----------------------------------------------------------------------------

def generate_legal_actions(game_state: Dict[str, Any]) -> List[Action]:
    """
    Generates legal-ish actions from the current state.

    Known limitation:
    Until the exact engine legality rules / adjacency / stage restrictions are wired,
    this function uses a sensible approximation:
    - attackable_markets if provided
    - otherwise enemy_markets
    """
    rules = game_state.get("rules", {}) or {}
    current_ip = _get_current_ip(game_state)

    owned_markets = _as_int_list(game_state.get("owned_markets", []))
    enemy_markets = _as_int_list(game_state.get("enemy_markets", []))
    neutral_markets = _as_int_list(game_state.get("neutral_markets", []))
    allied_markets = set(_as_int_list(game_state.get("allied_markets", [])))

    attackable_markets = _resolve_attackable_markets(game_state)

    attack_cost = int(rules.get("attack_cost", 1))
    defend_cost = int(rules.get("defend_cost", 1))
    forbid_attack_allies = _attacking_allies_is_hard_blocked(rules)

    actions: List[Action] = [Action(action_type="hold", ip_spent=0)]

    if current_ip <= 0 and not any(_get_market_reallocatable_ip(game_state, market) > 0 for market in owned_markets):
        return actions

    # Attack actions
    if current_ip >= attack_cost:
        for target in attackable_markets:
            relationship = _get_market_relationship(target, enemy_markets, allied_markets, neutral_markets)
            if relationship == "ally" and forbid_attack_allies:
                continue

            for spend in _candidate_spends(current_ip, attack_cost):
                actions.append(
                    Action(
                        action_type="attack",
                        target_market_id=target,
                        ip_spent=spend,
                        metadata={
                            "resource_pool": "current_ip",
                            "target_relationship": relationship,
                            "breaks_alliance": relationship == "ally",
                        },
                    )
                )

    # Defend / research actions on owned markets
    for market_id in owned_markets:
        if current_ip >= defend_cost:
            for spend in _candidate_spends(current_ip, defend_cost):
                actions.append(
                    Action(
                        action_type="defend",
                        target_market_id=market_id,
                        ip_spent=spend,
                        metadata={
                            "defend_mode": "allocate",
                            "resource_pool": "current_ip",
                        },
                    )
                )

        for source_market_id in owned_markets:
            if source_market_id == market_id:
                continue

            source_available_ip = _get_market_reallocatable_ip(game_state, source_market_id)
            if source_available_ip < defend_cost:
                continue

            for spend in _candidate_spends(source_available_ip, defend_cost):
                actions.append(
                    Action(
                        action_type="defend",
                        target_market_id=market_id,
                        source_market_id=source_market_id,
                        ip_spent=spend,
                        metadata={
                            "defend_mode": "reallocate",
                            "resource_pool": "market_ip",
                            "source_available_ip": source_available_ip,
                        },
                    )
                )

        research_cost = _get_research_cost_for_market(market_id, game_state)
        if current_ip >= research_cost:
            surcharge_applied = research_cost > int(rules.get("research_cost", 2))
            for option_key, option_meta in RESEARCH_OPTIONS.items():
                actions.append(
                    Action(
                        action_type="research",
                        target_market_id=market_id,
                        source_market_id=market_id,
                        ip_spent=research_cost,
                        metadata={
                            "resource_pool": "current_ip",
                            "research_option": option_key,
                            "research_label": option_meta["label"],
                            "research_cost": research_cost,
                            "high_regulation_surcharge_applied": surcharge_applied,
                        },
                    )
                )

    return _dedupe_actions(actions)


def _resolve_attackable_markets(game_state: Dict[str, Any]) -> List[int]:
    explicit = game_state.get("attackable_markets")
    if explicit is not None:
        return _as_int_list(explicit)

    enemy_markets = _as_int_list(game_state.get("enemy_markets", []))
    neutral_markets = _as_int_list(game_state.get("neutral_markets", []))
    return _unique_ints(enemy_markets + neutral_markets)


def _attacking_allies_is_hard_blocked(rules: Dict[str, Any]) -> bool:
    if "forbid_attack_allies" in rules:
        return bool(rules.get("forbid_attack_allies"))
    if "allow_attack_allies" in rules:
        return not bool(rules.get("allow_attack_allies"))
    return False


def _candidate_spends(current_ip: int, min_cost: int) -> List[int]:
    """
    Generate a small set of candidate spend sizes.
    Keeps search space manageable until the exact action-allocation engine is known.
    """
    if current_ip < min_cost:
        return []

    options = {min_cost, current_ip}

    mid = max(min_cost, current_ip // 2)
    options.add(mid)

    return sorted(options)


def _dedupe_actions(actions: List[Action]) -> List[Action]:
    seen = set()
    unique_actions = []

    for action in actions:
        key = (
            action.action_type,
            action.target_market_id,
            action.source_market_id,
            action.ip_spent,
            _freeze_value(action.metadata),
        )
        if key not in seen:
            seen.add(key)
            unique_actions.append(action)

    return unique_actions


def _freeze_value(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((str(k), _freeze_value(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple, set)):
        return tuple(_freeze_value(v) for v in value)
    return value


# -----------------------------------------------------------------------------
# Scoring
# -----------------------------------------------------------------------------

def _score_legal_actions(game_state: Dict[str, Any], traits: Dict[str, Any]) -> List[ScoredAction]:
    legal_actions = generate_legal_actions(game_state)
    scored_actions: List[ScoredAction] = []

    for action in legal_actions:
        score, reasons = score_action(action, game_state, traits)
        scored_actions.append(ScoredAction(action=action, score=score, reasons=reasons))

    return scored_actions


def score_action(
    action: Action,
    game_state: Dict[str, Any],
    traits: Dict[str, Any],
) -> Tuple[float, Dict[str, float]]:
    if action.action_type == "attack":
        return _score_attack(action, game_state, traits)
    if action.action_type == "defend":
        return _score_defend(action, game_state, traits)
    if action.action_type == "research":
        return _score_research(action, game_state, traits)
    return _score_hold(action, game_state, traits)


def select_best_order_bundle(
    scored_actions: List[ScoredAction],
    game_state: Dict[str, Any],
    traits: Dict[str, Any],
    *,
    hold_score: float = 0.0,
    max_actions: Optional[int] = None,
) -> Tuple[List[ScoredAction], BundleSelectionState]:
    selection_state = BundleSelectionState(
        remaining_current_ip=_get_current_ip(game_state),
        remaining_reallocatable_ip={
            market_id: _get_market_reallocatable_ip(game_state, market_id)
            for market_id in _as_int_list(game_state.get("owned_markets", []))
        },
    )

    resolved_max_actions = _resolve_max_actions(game_state, max_actions)
    if resolved_max_actions <= 0:
        return [], selection_state

    non_hold_actions = [sa for sa in scored_actions if sa.action.action_type != "hold"]
    ranked = sorted(non_hold_actions, key=lambda sa: sa.score, reverse=True)
    selected: List[ScoredAction] = []

    rules = game_state.get("rules", {}) or {}
    primary_margin = float(rules.get("primary_action_margin", 0.0))
    follow_up_margin = float(rules.get("follow_up_action_margin", 1.0))

    for action_type in _action_type_priority_order(ranked, game_state, traits):
        if len(selected) >= resolved_max_actions:
            break

        candidate = _pick_best_candidate_of_type(ranked, action_type, selected, selection_state)
        if candidate is None or candidate.score <= hold_score + primary_margin:
            continue

        selected.append(candidate)
        _apply_selected_action(selection_state, candidate.action)

    for candidate in ranked:
        if len(selected) >= resolved_max_actions:
            break
        if candidate in selected or candidate.score <= hold_score + follow_up_margin:
            continue
        if not _is_action_affordable(candidate.action, selection_state):
            continue
        if not _is_action_compatible(candidate.action, [sa.action for sa in selected]):
            continue

        selected.append(candidate)
        _apply_selected_action(selection_state, candidate.action)

    return selected, selection_state


def _resolve_max_actions(game_state: Dict[str, Any], max_actions: Optional[int]) -> int:
    if max_actions is not None:
        return max(0, int(max_actions))

    rules = game_state.get("rules", {}) or {}
    return max(1, int(rules.get("max_orders_per_round", 3)))


def _action_type_priority_order(
    ranked_actions: List[ScoredAction],
    game_state: Dict[str, Any],
    traits: Dict[str, Any],
) -> List[str]:
    type_best_score = {
        "attack": -9999.0,
        "defend": -9999.0,
        "research": -9999.0,
    }

    for scored in ranked_actions:
        if scored.action.action_type in type_best_score:
            type_best_score[scored.action.action_type] = max(
                type_best_score[scored.action.action_type],
                scored.score,
            )

    max_threat = max(
        (_get_market_threat(game_state, market_id) for market_id in _as_int_list(game_state.get("owned_markets", []))),
        default=0.0,
    )

    if max_threat >= 0.65:
        type_best_score["defend"] += 2.0
    if traits["aggression"] >= 0.65:
        type_best_score["attack"] += 1.0
    if max_threat <= 0.3 and _get_current_ip(game_state) >= 2:
        type_best_score["research"] += 0.6

    return sorted(type_best_score.keys(), key=lambda action_type: type_best_score[action_type], reverse=True)


def _pick_best_candidate_of_type(
    ranked_actions: List[ScoredAction],
    action_type: str,
    selected: List[ScoredAction],
    selection_state: BundleSelectionState,
) -> Optional[ScoredAction]:
    selected_actions = [sa.action for sa in selected]

    for candidate in ranked_actions:
        if candidate.action.action_type != action_type:
            continue
        if not _is_action_affordable(candidate.action, selection_state):
            continue
        if not _is_action_compatible(candidate.action, selected_actions):
            continue
        return candidate

    return None


def _is_action_affordable(action: Action, selection_state: BundleSelectionState) -> bool:
    if _action_uses_reallocated_ip(action):
        if action.source_market_id is None:
            return False
        return selection_state.remaining_reallocatable_ip.get(action.source_market_id, 0) >= action.ip_spent

    return selection_state.remaining_current_ip >= action.ip_spent


def _apply_selected_action(selection_state: BundleSelectionState, action: Action) -> None:
    if _action_uses_reallocated_ip(action):
        if action.source_market_id is None:
            return
        selection_state.remaining_reallocatable_ip[action.source_market_id] = (
            selection_state.remaining_reallocatable_ip.get(action.source_market_id, 0) - action.ip_spent
        )
        return

    selection_state.remaining_current_ip -= action.ip_spent


def _is_action_compatible(action: Action, selected_actions: List[Action]) -> bool:
    if action.action_type == "hold":
        return not selected_actions

    action_owned_touch = _owned_markets_touched(action)

    for existing in selected_actions:
        if existing.action_type == "hold":
            return False
        if action.action_type == "attack" and existing.action_type == "attack":
            if action.target_market_id == existing.target_market_id:
                return False
        if action_owned_touch and _owned_markets_touched(existing):
            if action_owned_touch.intersection(_owned_markets_touched(existing)):
                return False

    return True


def _owned_markets_touched(action: Action) -> Set[int]:
    touched: Set[int] = set()

    if action.action_type == "defend":
        if action.target_market_id is not None:
            touched.add(action.target_market_id)
        if action.source_market_id is not None:
            touched.add(action.source_market_id)
    elif action.action_type == "research":
        if action.target_market_id is not None:
            touched.add(action.target_market_id)

    return touched


def _action_uses_reallocated_ip(action: Action) -> bool:
    return str(action.metadata.get("resource_pool", "")) == "market_ip"


def _action_uses_shared_ip(action: Action) -> bool:
    return not _action_uses_reallocated_ip(action)


def _score_attack(
    action: Action,
    game_state: Dict[str, Any],
    traits: Dict[str, Any],
) -> Tuple[float, Dict[str, float]]:
    if action.target_market_id is None:
        return -9999.0, {"invalid": -9999.0}

    owned_markets = _as_int_list(game_state.get("owned_markets", []))
    allied_markets = set(_as_int_list(game_state.get("allied_markets", [])))
    enemy_markets = _as_int_list(game_state.get("enemy_markets", []))
    neutral_markets = _as_int_list(game_state.get("neutral_markets", []))

    attrs = get_market_attributes(action.target_market_id)
    market_value = _estimate_market_value(attrs)
    topic_confidence = _estimate_topic_confidence(attrs.get("key_topic"), traits)
    synergy_value = _estimate_capture_synergy_value(action.target_market_id, owned_markets, "attack")
    threat_after_expansion = _estimate_expansion_penalty(action.target_market_id, game_state, traits)
    maintenance_penalty = _estimate_maintenance_penalty_after_gain(game_state, gained_markets=1)

    regulation_score = _enum_to_score(attrs.get("regulation_level"))
    security_score = _enum_to_score(attrs.get("security_risk"))
    size_score = _enum_to_score(attrs.get("size"))

    # Approximate cost / strength model until exact conflict resolution rules are wired in.
    attack_commitment = action.ip_spent * (0.6 + 0.8 * traits["aggression"])
    quiz_edge = (traits["quiz_strength"] * 2.5) + (topic_confidence * 2.0)
    reward_for_big_market = size_score * 1.2

    regulation_penalty = regulation_score * (1.4 - 0.5 * traits["risk_tolerance"])

    # Security risk is ambiguous in your design:
    # high risk may mean danger, but also potentially more reward.
    # So we model both.
    risk_penalty = security_score * (1.5 - traits["risk_tolerance"])
    risk_reward = security_score * traits["risk_tolerance"] * 0.8

    enemy_strength = _get_enemy_strength_estimate(game_state, action.target_market_id)
    contest_readiness = attack_commitment + quiz_edge
    enemy_pressure = enemy_strength * (1.2 - 0.4 * traits["risk_tolerance"])
    breakthrough_bonus = max(0.0, contest_readiness - enemy_strength) * 0.45

    relationship = str(
        action.metadata.get(
            "target_relationship",
            _get_market_relationship(action.target_market_id, enemy_markets, allied_markets, neutral_markets),
        )
    )
    neutral_expansion_bonus = 1.0 if relationship == "neutral" else 0.0
    betrayal_penalty = _estimate_betrayal_penalty(action, game_state, traits)

    score = (
        market_value * (1.0 + 0.4 * traits["aggression"])
        + reward_for_big_market
        + synergy_value * 2.2
        + quiz_edge
        + attack_commitment
        + risk_reward
        + breakthrough_bonus
        + neutral_expansion_bonus
        - regulation_penalty
        - risk_penalty
        - enemy_pressure
        - threat_after_expansion
        - maintenance_penalty
        - betrayal_penalty
    )

    reasons = {
        "market_value": market_value,
        "size_bonus": reward_for_big_market,
        "topic_confidence": topic_confidence * 2.0,
        "synergy_value": synergy_value * 2.2,
        "quiz_edge": quiz_edge,
        "attack_commitment": attack_commitment,
        "risk_reward": risk_reward,
        "breakthrough_bonus": breakthrough_bonus,
        "neutral_expansion_bonus": neutral_expansion_bonus,
        "regulation_penalty": -regulation_penalty,
        "risk_penalty": -risk_penalty,
        "enemy_pressure": -enemy_pressure,
        "expansion_penalty": -threat_after_expansion,
        "maintenance_penalty": -maintenance_penalty,
        "betrayal_penalty": -betrayal_penalty,
    }

    return score, reasons


def _score_defend(
    action: Action,
    game_state: Dict[str, Any],
    traits: Dict[str, Any],
) -> Tuple[float, Dict[str, float]]:
    if action.target_market_id is None:
        return -9999.0, {"invalid": -9999.0}

    owned_markets = _as_int_list(game_state.get("owned_markets", []))
    attrs = get_market_attributes(action.target_market_id)

    market_value = _estimate_market_value(attrs)
    threat = _get_market_threat(game_state, action.target_market_id)
    synergy_protection = _estimate_capture_synergy_value(action.target_market_id, owned_markets, "defend")
    current_research_level = _coerce_float(
        _get_market_state(game_state, action.target_market_id).get("research_level", 0)
    )

    defense_commitment = action.ip_spent * (0.5 + traits["defense_bias"])
    irreplaceability = market_value + synergy_protection * 1.5 + current_research_level * 0.6
    defend_mode = action.metadata.get("defend_mode", "allocate")
    source_exposure = 0.0
    reallocation_efficiency = 0.0
    cost_friction = 0.15 * action.ip_spent

    if defend_mode == "reallocate" and action.source_market_id is not None:
        source_market_id = action.source_market_id
        source_attrs = get_market_attributes(source_market_id)
        source_threat = _get_market_threat(game_state, source_market_id)
        source_value = _estimate_market_value(source_attrs)
        source_available = max(_get_market_reallocatable_ip(game_state, source_market_id), action.ip_spent)

        source_exposure = (
            source_threat
            * max(1.0, source_value)
            * (action.ip_spent / max(1.0, float(source_available)))
            * 1.8
        )
        reallocation_efficiency = max(0.0, threat - source_threat) * 2.4
        cost_friction = 0.05 * action.ip_spent

    score = (
        threat * (4.0 + 3.0 * traits["defense_bias"])
        + irreplaceability
        + defense_commitment
        + reallocation_efficiency
        - source_exposure
        - cost_friction
    )

    reasons = {
        "threat": threat * (4.0 + 3.0 * traits["defense_bias"]),
        "market_value": market_value,
        "synergy_protection": synergy_protection * 1.5,
        "research_level_protection": current_research_level * 0.6,
        "defense_commitment": defense_commitment,
        "reallocation_efficiency": reallocation_efficiency,
        "source_exposure": -source_exposure,
        "cost_friction": -cost_friction,
    }

    return score, reasons


def _score_research(
    action: Action,
    game_state: Dict[str, Any],
    traits: Dict[str, Any],
) -> Tuple[float, Dict[str, float]]:
    if action.target_market_id is None:
        return -9999.0, {"invalid": -9999.0}

    attrs = get_market_attributes(action.target_market_id)
    state = _get_market_state(game_state, action.target_market_id)
    threat = _get_market_threat(game_state, action.target_market_id)
    growth_score = _enum_to_score(attrs.get("growth_potential"))
    market_value = _estimate_market_value(attrs)
    regulation_score = _enum_to_score(attrs.get("regulation_level"))
    security_score = _enum_to_score(attrs.get("security_risk"))
    research_synergy = _estimate_capture_synergy_value(
        action.target_market_id,
        _as_int_list(game_state.get("owned_markets", [])),
        "research",
    )

    # Safer markets are better research targets.
    safety_bonus = max(0.0, 1.0 - threat) * 2.0
    future_value = growth_score * 2.1 + market_value * 0.35 + research_synergy * 1.2

    # Research is more attractive to calmer / more disciplined profiles.
    personality_fit = (1.0 - traits["aggression"]) + traits["defense_bias"] * 0.5
    option_value, option_reasons = _score_research_option(
        action,
        state,
        threat=threat,
        growth_score=growth_score,
        market_value=market_value,
        regulation_score=regulation_score,
        security_score=security_score,
        research_synergy=research_synergy,
    )
    upgrade_level = _get_upgrade_level(state, str(action.metadata.get("research_option", "")))
    diminishing_returns = upgrade_level * 1.2

    score = (
        future_value
        + safety_bonus
        + personality_fit
        + option_value
        - threat * 2.0
        - 0.22 * action.ip_spent
        - diminishing_returns
    )

    reasons = {
        "future_value": future_value,
        "safety_bonus": safety_bonus,
        "personality_fit": personality_fit,
        "option_value": option_value,
        "threat_penalty": -threat * 2.0,
        "spend_penalty": -0.22 * action.ip_spent,
        "diminishing_returns": -diminishing_returns,
    }
    reasons.update(option_reasons)

    return score, reasons


def _score_research_option(
    action: Action,
    state: Dict[str, Any],
    *,
    threat: float,
    growth_score: float,
    market_value: float,
    regulation_score: float,
    security_score: float,
    research_synergy: float,
) -> Tuple[float, Dict[str, float]]:
    option_key = str(action.metadata.get("research_option", "increase_production"))

    if option_key == "increase_production":
        value = growth_score * 2.8 + market_value * 0.6 + research_synergy * 0.6
        return value, {"production_value": value}

    if option_key == "reduce_regulation_burden":
        surcharge_bonus = 1.4 if action.metadata.get("high_regulation_surcharge_applied") else 0.0
        value = regulation_score * 3.0 + research_synergy * 0.8 + surcharge_bonus
        return value, {"regulation_relief_value": value}

    if option_key == "improve_security":
        value = security_score * 2.7 + threat * 2.0 + market_value * 0.25
        return value, {"security_upgrade_value": value}

    if option_key == "fortify_market":
        value = threat * 4.5 + market_value * 0.55 + research_synergy * 0.8
        return value, {"fortify_value": value}

    fallback = growth_score + market_value * 0.2 - _get_upgrade_level(state, option_key) * 0.4
    return fallback, {"generic_research_value": fallback}


def _score_hold(
    action: Action,
    game_state: Dict[str, Any],
    traits: Dict[str, Any],
) -> Tuple[float, Dict[str, float]]:
    current_ip = int(game_state.get("current_ip", 0))
    owned_markets = _as_int_list(game_state.get("owned_markets", []))

    max_threat = 0.0
    for market_id in owned_markets:
        max_threat = max(max_threat, _get_market_threat(game_state, market_id))

    # Holding should be possible, but not usually dominant unless options are bad or state is uncertain.
    cautious_value = (1.0 - traits["aggression"]) * 0.7 + traits["defense_bias"] * 0.6
    uncertainty_value = max_threat * 0.6
    save_value = min(current_ip, 4) * 0.15

    score = cautious_value + uncertainty_value + save_value

    reasons = {
        "cautious_value": cautious_value,
        "uncertainty_value": uncertainty_value,
        "save_value": save_value,
    }

    return score, reasons


def select_best_action(scored_actions: List[ScoredAction]) -> ScoredAction:
    """
    Deterministic selection for now.
    Easy to test and debug.
    """
    if not scored_actions:
        return ScoredAction(Action("hold", ip_spent=0), score=0.0, reasons={"fallback": 0.0})

    action_priority = {
        "attack": 4,
        "defend": 3,
        "research": 2,
        "hold": 1,
    }

    return max(
        scored_actions,
        key=lambda sa: (
            sa.score,
            action_priority.get(sa.action.action_type, 0),
            -(sa.action.ip_spent or 0),  # prefer lower spend on exact score ties
        ),
    )


# -----------------------------------------------------------------------------
# DB-backed static knowledge helpers
# -----------------------------------------------------------------------------

def get_market_attributes(market_id: int) -> Dict[str, Any]:
    """
    Uses the knowledge_profile helper if available.
    """
    return knowledge_profile.get_attributes(market_id)


def get_submarkets(parent_market_id: int) -> List[int]:
    rows = _fetch_all(
        "SELECT sub_market FROM MarketLink WHERE parent_market = ?",
        (parent_market_id,),
    )
    return [int(row["sub_market"]) for row in rows]


def get_synergies_for_market(market_id: int) -> List[Dict[str, Any]]:
    rows = _fetch_all(
        """
        SELECT market1, market2, bonus_type, bonus_value
        FROM Synergy
        WHERE market1 = ? OR market2 = ?
        """,
        (market_id, market_id),
    )
    return [dict(row) for row in rows]


def _fetch_all(query: str, params: Tuple[Any, ...]) -> List[sqlite3.Row]:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.execute(query, params)
        return cursor.fetchall()
    finally:
        conn.close()


# -----------------------------------------------------------------------------
# Game-state helpers
# -----------------------------------------------------------------------------

def _get_current_ip(game_state: Dict[str, Any]) -> int:
    return max(0, int(game_state.get("current_ip", 0)))


def _as_int_list(values: Any) -> List[int]:
    if not values:
        return []
    return [int(v) for v in values]


def _unique_ints(values: Iterable[int]) -> List[int]:
    seen = set()
    ordered: List[int] = []

    for value in values:
        numeric = int(value)
        if numeric in seen:
            continue
        seen.add(numeric)
        ordered.append(numeric)

    return ordered


def _get_market_state(game_state: Dict[str, Any], market_id: int) -> Dict[str, Any]:
    market_states = game_state.get("market_states", {}) or {}
    return market_states.get(market_id, market_states.get(str(market_id), {})) or {}


def _get_relationship_state(game_state: Dict[str, Any], market_id: int) -> Dict[str, Any]:
    relationship_states = game_state.get("relationship_states", {}) or {}
    return relationship_states.get(market_id, relationship_states.get(str(market_id), {})) or {}


def _get_market_relationship(
    market_id: int,
    enemy_markets: List[int],
    allied_markets: Set[int],
    neutral_markets: List[int],
) -> str:
    if market_id in allied_markets:
        return "ally"
    if market_id in enemy_markets:
        return "enemy"
    if market_id in neutral_markets:
        return "neutral"
    return "unknown"


def _get_market_threat(game_state: Dict[str, Any], market_id: int) -> float:
    """
    Looks for a normalized threat value in market_states.

    Expected examples:
    market_states[4] = {"threat": 0.8}
    """
    state = _get_market_state(game_state, market_id)
    threat = state.get("threat", 0.0)

    return _clamp(_coerce_float(threat), 0.0, 1.0)


def _get_market_reallocatable_ip(game_state: Dict[str, Any], market_id: int) -> int:
    state = _get_market_state(game_state, market_id)

    for key in (
        "reallocatable_ip",
        "allocated_ip",
        "available_ip",
        "defense_ip",
        "stored_ip",
        "ip",
    ):
        if key in state:
            return max(0, int(state.get(key, 0)))

    return 0


def _get_enemy_strength_estimate(game_state: Dict[str, Any], market_id: int) -> float:
    state = _get_market_state(game_state, market_id)
    return max(0.0, _coerce_float(state.get("enemy_strength_estimate", 0.0)))


def _get_research_cost_for_market(market_id: int, game_state: Dict[str, Any]) -> int:
    rules = game_state.get("rules", {}) or {}
    attrs = get_market_attributes(market_id)

    base_cost = int(rules.get("research_cost", 2))
    high_regulation_threshold = float(rules.get("high_regulation_threshold", 3.0))
    surcharge = int(rules.get("high_regulation_research_surcharge", 1))

    if _enum_to_score(attrs.get("regulation_level")) >= high_regulation_threshold:
        return base_cost + surcharge

    return base_cost


def _get_upgrade_level(state: Dict[str, Any], option_key: str) -> float:
    option_specific_keys = {
        "increase_production": ("production_upgrade_level", "production_level"),
        "reduce_regulation_burden": ("regulation_reduction_level", "regulation_upgrade_level"),
        "improve_security": ("security_upgrade_level", "security_level"),
        "fortify_market": ("fortification_level", "defense_upgrade_level"),
    }

    for key in option_specific_keys.get(option_key, ()):
        if key in state:
            return max(0.0, _coerce_float(state.get(key, 0.0)))

    research_upgrades = state.get("research_upgrades", {}) or {}
    if isinstance(research_upgrades, dict):
        return max(0.0, _coerce_float(research_upgrades.get(option_key, 0.0)))

    return 0.0


def _estimate_betrayal_penalty(
    action: Action,
    game_state: Dict[str, Any],
    traits: Dict[str, Any],
) -> float:
    target_market_id = action.target_market_id
    if target_market_id is None or action.action_type != "attack":
        return 0.0

    allied_markets = set(_as_int_list(game_state.get("allied_markets", [])))
    commitments = game_state.get("commitments", {}) or {}
    relationship_state = _get_relationship_state(game_state, target_market_id)

    avoid_attack_markets = set(_as_int_list(commitments.get("avoid_attack_markets", [])))
    protected_markets = set(_as_int_list(commitments.get("protected_markets", [])))
    promised_support_markets = set(_as_int_list(commitments.get("promised_support_markets", [])))

    ethical_score = _clamp(_coerce_float(game_state.get("ethical_score", 0.5)), 0.0, 1.0)
    alliance_turns = max(0.0, _coerce_float(relationship_state.get("alliance_turns", 0.0)))
    trust = _clamp(_coerce_float(relationship_state.get("trust", 0.5)), 0.0, 1.0)

    penalty = 0.0
    if target_market_id in allied_markets:
        penalty += 4.0
    if target_market_id in avoid_attack_markets:
        penalty += 3.0
    if target_market_id in protected_markets:
        penalty += 2.5
    if target_market_id in promised_support_markets:
        penalty += 2.0

    penalty += alliance_turns * 0.8
    penalty *= 0.6 + (0.8 * trust)
    penalty *= 0.7 + traits["ethical_bias"] + (0.3 * ethical_score)

    return penalty


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


# -----------------------------------------------------------------------------
# Scoring helpers
# -----------------------------------------------------------------------------

def _enum_to_score(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    value_str = str(value).strip().lower()
    return TRAIT_ENUM_SCORE.get(value_str, 0.0)


def _estimate_market_value(attrs: Dict[str, Any]) -> float:
    """
    Proxy for how generally desirable a market is.

    Uses:
    - size
    - growth potential
    - a small boost if it appears to be a parent market
    """
    size_score = _enum_to_score(attrs.get("size"))
    growth_score = _enum_to_score(attrs.get("growth_potential"))
    market_id = int(attrs.get("market_id", 0))

    parent_bonus = 0.6 if get_submarkets(market_id) else 0.0

    return size_score * 2.2 + growth_score * 1.8 + parent_bonus


def _estimate_topic_confidence(topic: Optional[str], traits: Dict[str, Any]) -> float:
    if not topic:
        return traits["quiz_strength"]

    topic_strengths = traits.get("topic_strengths", {}) or {}

    # exact match first
    if topic in topic_strengths:
        return float(topic_strengths[topic])

    # case-insensitive fallback
    for key, value in topic_strengths.items():
        if str(key).strip().lower() == str(topic).strip().lower():
            return float(value)

    return traits["quiz_strength"]


def _estimate_capture_synergy_value(
    candidate_market_id: int,
    owned_markets: List[int],
    action_type: str,
) -> float:
    """
    Estimate synergy value that would become relevant if the AI owns / preserves candidate_market_id.

    If the paired market is already owned, synergy matters immediately.
    """
    total = 0.0
    for row in get_synergies_for_market(candidate_market_id):
        market1 = int(row["market1"])
        market2 = int(row["market2"])

        counterpart = market2 if market1 == candidate_market_id else market1
        if counterpart not in owned_markets:
            continue

        bonus_type = str(row["bonus_type"])
        bonus_value = str(row["bonus_value"])

        operator_value = BONUS_OPERATOR_VALUE.get(bonus_value, 0.0)
        type_weight = ACTION_BONUS_WEIGHTS.get(action_type, {}).get(bonus_type, 1.0)

        total += operator_value * type_weight

    return total


def _estimate_expansion_penalty(
    target_market_id: int,
    game_state: Dict[str, Any],
    traits: Dict[str, Any],
) -> float:
    """
    Proxy for 'if I take this market, how exposed / awkward does my empire become?'

    Known limitation:
    Without a real live board-graph or enemy-position system, this is heuristic.
    """
    attrs = get_market_attributes(target_market_id)
    security_score = _enum_to_score(attrs.get("security_risk"))
    regulation_score = _enum_to_score(attrs.get("regulation_level"))

    # Risk-averse AIs feel this penalty more strongly.
    penalty = (security_score * 0.9 + regulation_score * 0.5) * (1.1 - 0.7 * traits["risk_tolerance"])
    return max(0.0, penalty)


def _estimate_maintenance_penalty_after_gain(
    game_state: Dict[str, Any],
    gained_markets: int,
) -> float:
    """
    Maintenance is only estimated because the exact live rule engine is not wired here yet.
    """
    rules = game_state.get("rules", {}) or {}
    owned_count = len(_as_int_list(game_state.get("owned_markets", [])))

    threshold = int(rules.get("maintenance_threshold", 5))
    penalty_per_market = float(rules.get("maintenance_penalty_per_market", 2.0))

    projected = owned_count + gained_markets
    if projected <= threshold:
        return 0.0

    excess = projected - threshold
    return excess * penalty_per_market


# -----------------------------------------------------------------------------
# Example manual run
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    mock_game_state = {
        "current_ip": 5,
        "owned_markets": [1, 4],
        "enemy_markets": [2, 3, 5],
        "allied_markets": [],
        "attackable_markets": [2, 3, 5],
        "market_states": {
            1: {"threat": 0.7, "research_level": 1},
            4: {"threat": 0.2, "research_level": 0},
            2: {"enemy_strength_estimate": 3},
            3: {"enemy_strength_estimate": 2},
            5: {"enemy_strength_estimate": 4},
        },
        "rules": {
            "attack_cost": 1,
            "defend_cost": 1,
            "research_cost": 2,
            "maintenance_threshold": 5,
            "maintenance_penalty_per_market": 2.0,
            "allow_attack_allies": False,
        },
    }

    result = choose_action(mock_game_state, difficulty="medium", return_debug=True)
    print(result)
