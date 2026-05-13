import os
# ensure environment variable is toggled
os.environ["TORCHDYNAMO_DISABLE"] = "1"

import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from flask import Flask

try:
    from flask_cors import CORS
except ImportError:
    CORS = None

from backend.routes.api import api


def create_app():
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False

    if CORS is not None:
        CORS(app)
    else:

        @app.after_request
        def add_cors_headers(response):
            # Keep the frontend unblocked even if flask-cors is not installed locally.
            response.headers.setdefault("Access-Control-Allow-Origin", "*")
            response.headers.setdefault(
                "Access-Control-Allow-Headers", "Content-Type, Authorization"
            )
            response.headers.setdefault(
                "Access-Control-Allow-Methods", "GET, POST, OPTIONS"
            )
            return response

    app.register_blueprint(api)
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
