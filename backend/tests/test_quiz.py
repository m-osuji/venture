# backend/tests/test_quiz.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from helpers.quiz_helpers import fetch_questions_by_topic_and_difficulty, build_quiz_for_conflict

questions = fetch_questions_by_topic_and_difficulty("AI", "easy", limit=1)
print("Fetched question:", questions)

fake_conflict = {
    "market_id": 1,
    "quiz_topic": "AI",
    "conflict_type": "attack",
    "defender_team_id": 1,
    "attacker_team_ids": [2],
    "defender_strength_estimate": 0,
    "attack_orders": [],
}
quiz = build_quiz_for_conflict(fake_conflict)
print("Quiz built:", quiz)