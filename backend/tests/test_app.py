import backend.app

# testing app creation
def test_create_app():
    app = backend.app.create_app()

    assert app.config["JSON_SORT_KEYS"] is False
    assert "api" in app.blueprints

# tests if app without CORS installed still has the correct fallback CORS headers
def test_fallback_cors_headers(monkeypatch):
    monkeypatch.setattr(backend.app, "CORS", None)

    app = backend.app.create_app()
    client = app.test_client()

    response = client.get("/")

    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert "Content-Type" in response.headers["Access-Control-Allow-Headers"]

# tests if app with CORS installed still has the correct CORS headers
def test_flask_cors_branch(monkeypatch):
    called = {}

    def fake_cors(app):
        called["used"] = True

    monkeypatch.setattr(backend.app, "CORS", fake_cors)

    app = backend.app.create_app()

    assert called["used"] is True