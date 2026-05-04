import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from routes.api import api

def create_app():
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = False # to preserve the order of keys in JSON

    # Register blueprints
    app.register_blueprint(api)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)
