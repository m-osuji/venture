from backend.helpers import quiz_helpers as qh


def _base_conflict():
    return {
        "market_id": 2,
        "quiz_topic": "Cybersecurity",
        "conflict_type": "attack_vs_owner",
        "defender_team_id": 2,
        "attacker_team_ids": [1],
        "attack_orders": [{"team_id": 1, "ip_spent": 2}],
        "defender_strength_estimate": 2.0,
    }


def _base_game_state():
    return {
        "market_state": {
            "2": {
                "_security_risk": "medium",
            }
        },
        "active_synergies": [
            {
                "team_id": 2,
                "market1": 1,
                "market2": 2,
                "bonus_type": "ip",
                "bonus_value": "plus_one",
            }
        ],
        "turn_log": {
            "conflicts": [_base_conflict()],
        },
    }


def test_build_quiz_for_conflict_returns_one_question_per_difficulty():
    quiz = qh.build_quiz_for_conflict(_base_conflict())

    assert quiz["market_id"] == 2
    assert quiz["quiz_topic"] == "Cybersecurity"
    assert [question["difficulty_level"] for question in quiz["questions"]] == [
        "easy",
        "medium",
        "hard",
    ]

    public_payload = qh.to_public_quiz_payload(quiz)
    assert public_payload["questions"][0]["answer"].startswith("option_")
    assert public_payload["questions"][0]["options"]["option_1"]


def test_fetch_questions_falls_back_to_same_topic_when_exact_difficulty_missing(monkeypatch):
    def fake_fetch(topic=None, difficulty=None):
        rows = [
            {
                "question_id": 101,
                "topic": "Data Science",
                "difficulty_level": "medium",
                "content": "Medium DS",
                "option_1": "A",
                "option_2": "B",
                "option_3": "C",
                "option_4": "D",
                "answer": "option_1",
            }
        ]
        if topic == "Data Science" and difficulty == "easy":
            return []
        if topic == "Data Science" and difficulty is None:
            return rows
        return []

    monkeypatch.setattr(qh, "db_fetch_questions", fake_fetch)

    questions = qh.fetch_questions_by_topic_and_difficulty("Data Science", "easy")

    assert len(questions) == 1
    assert questions[0]["question_id"] == 101
    assert questions[0]["difficulty_level"] == "medium"


def test_fetch_questions_falls_back_to_any_question_when_topic_missing(monkeypatch):
    def fake_fetch(topic=None, difficulty=None):
        if topic == "Missing Topic" and difficulty == "easy":
            return []
        if topic == "Missing Topic" and difficulty is None:
            return []
        if topic is None and difficulty == "easy":
            return [
                {
                    "question_id": 202,
                    "topic": "Cybersecurity",
                    "difficulty_level": "easy",
                    "content": "Easy fallback",
                    "option_1": "A",
                    "option_2": "B",
                    "option_3": "C",
                    "option_4": "D",
                    "answer": "option_2",
                }
            ]
        return []

    monkeypatch.setattr(qh, "db_fetch_questions", fake_fetch)

    questions = qh.fetch_questions_by_topic_and_difficulty("Missing Topic", "easy")

    assert len(questions) == 1
    assert questions[0]["question_id"] == 202
    assert questions[0]["topic"] == "Cybersecurity"


def test_score_team_answers_applies_correct_and_perfect_round_bonus():
    quiz = qh.build_quiz_for_conflict(_base_conflict())
    questions = quiz["questions"]

    answers = [
        {
            "question_id": questions[0]["question_id"],
            "selected_option": questions[0]["answer"],
            "response_time_ms": 1200,
        },
        {
            "question_id": questions[1]["question_id"],
            "selected_option": questions[1]["answer"],
            "response_time_ms": 1500,
        },
        {
            "question_id": questions[2]["question_id"],
            "selected_option": questions[2]["answer"],
            "response_time_ms": 1800,
        },
    ]

    score = qh.score_team_answers(questions, answers)

    assert score["correct_answers"] == 3
    assert score["perfect_round_bonus"] == 1
    assert score["strength_bonus"] == 4
    assert score["total_response_time_ms"] == 4500


def test_resolve_conflict_from_quiz_uses_quiz_and_market_modifiers():
    conflict = _base_conflict()
    quiz = qh.build_quiz_for_conflict(conflict)
    questions = quiz["questions"]

    team_results = [
        {
            "team_id": 1,
            "questions": questions,
            "answers": [
                {
                    "question_id": questions[0]["question_id"],
                    "selected_option": questions[0]["answer"],
                    "response_time_ms": 1000,
                },
                {
                    "question_id": questions[1]["question_id"],
                    "selected_option": questions[1]["answer"],
                    "response_time_ms": 1200,
                },
                {
                    "question_id": questions[2]["question_id"],
                    "selected_option": questions[2]["answer"],
                    "response_time_ms": 1400,
                },
            ],
        },
        {
            "team_id": 2,
            "questions": questions,
            "answers": [
                {
                    "question_id": questions[0]["question_id"],
                    "selected_option": questions[0]["answer"],
                    "response_time_ms": 900,
                },
                {
                    "question_id": questions[1]["question_id"],
                    "selected_option": "option_1",
                    "response_time_ms": 1100,
                },
                {
                    "question_id": questions[2]["question_id"],
                    "selected_option": questions[2]["answer"],
                    "response_time_ms": 1300,
                },
            ],
        },
    ]

    resolved = qh.resolve_conflict_from_quiz(_base_game_state(), conflict, team_results)

    assert resolved["winner_team_id"] == 1
    assert "Team 1" in resolved["resolution_notes"]
    assert resolved["participants"][0]["team_id"] == 1


def test_build_resolution_outcomes_from_quiz_matches_gameplay_helper_shape():
    conflict = _base_conflict()
    quiz = qh.build_quiz_for_conflict(conflict)
    questions = quiz["questions"]

    quiz_results = [
        {
            "market_id": 2,
            "team_results": [
                {
                    "team_id": 1,
                    "questions": questions,
                    "answers": [
                        {
                            "question_id": questions[0]["question_id"],
                            "selected_option": questions[0]["answer"],
                            "response_time_ms": 1000,
                        },
                        {
                            "question_id": questions[1]["question_id"],
                            "selected_option": questions[1]["answer"],
                            "response_time_ms": 1200,
                        },
                        {
                            "question_id": questions[2]["question_id"],
                            "selected_option": questions[2]["answer"],
                            "response_time_ms": 1400,
                        },
                    ],
                },
                {
                    "team_id": 2,
                    "questions": questions,
                    "answers": [],
                },
            ],
        }
    ]

    outcomes = qh.build_resolution_outcomes_from_quiz(
        _base_game_state(),
        quiz_results,
    )

    assert outcomes == [
        {
            "market_id": 2,
            "winner_team_id": 1,
            "resolution_notes": "Team 1 won on total strength 7.0.",
        }
    ]
