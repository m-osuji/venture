# tests if database path is returned as a string ending in db.db
from backend.helpers import db_helpers


def test_get_db_path():
    path = db_helpers.get_db_path()

    assert isinstance(path, str)
    assert path.endswith("db.db")

# tests if fetch_all_markets converts rows into dictionaries
def test_fetch_all_markets(monkeypatch):
    monkeypatch.setattr(
        db_helpers,
        "fetch_all",
        lambda query: [
            {"market_id": 1, "name": "Finance"},
            {"market_id": 2, "name": "AI"},
        ],
    )

    result = db_helpers.fetch_all_markets()

    assert result == [
        {"market_id": 1, "name": "Finance"},
        {"market_id": 2, "name": "AI"},
    ]

# tests if fetch_market_by_id returns dictionary for valid market
def test_fetch_market_by_id(monkeypatch):
    monkeypatch.setattr(
        db_helpers,
        "fetch_one",
        lambda query, params: {
            "market_id": 1,
            "name": "Finance",
        },
    )

    result = db_helpers.fetch_market_by_id(1)

    assert result == {
        "market_id": 1,
        "name": "Finance",
    }

# tests if fetch_market_by_id returns None when market does not exist
def test_fetch_market_by_id_not_found(monkeypatch):
    monkeypatch.setattr(
        db_helpers,
        "fetch_one",
        lambda query, params: None,
    )

    result = db_helpers.fetch_market_by_id(999)

    assert result is None

# tests if fetch_questions passes correct query filters
def test_fetch_questions_with_filters(monkeypatch):
    captured = {}

    def fake_fetch_all(query, params):
        captured["query"] = query
        captured["params"] = params
        return []

    monkeypatch.setattr(db_helpers, "fetch_all", fake_fetch_all)

    db_helpers.fetch_questions(topic="AI", difficulty="easy")

    assert "topic = ?" in captured["query"]
    assert "difficulty_level = ?" in captured["query"]
    assert captured["params"] == ["AI", "easy"]

# tests if fetch_questions works with no filters
def test_fetch_questions_no_filters(monkeypatch):
    captured = {}

    def fake_fetch_all(query, params):
        captured["query"] = query
        captured["params"] = params
        return []

    monkeypatch.setattr(db_helpers, "fetch_all", fake_fetch_all)

    db_helpers.fetch_questions()

    assert captured["params"] == []
    assert "WHERE 1=1" in captured["query"]