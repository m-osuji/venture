import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from flask import Flask

from backend.routes.api import api

def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False  # to preserve the order of keys in JSON

    @app.after_request
    def add_cors_headers(response):
        """
        Keep the demo frontend unblocked when it runs on a separate dev server.
        """
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
        response.headers.setdefault(
            "Access-Control-Allow-Headers", "Content-Type, Authorization"
        )
        response.headers.setdefault(
            "Access-Control-Allow-Methods", "GET, POST, OPTIONS"
        )
        return response

    # Register blueprints
    app.register_blueprint(api)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
