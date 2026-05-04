import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify
from helpers.db_helpers import fetch_all_markets
from helpers.game_state_helpers import load_state, save_state, init_game_state
from ai_opponent.agents.decision_maker import choose_action

api = Blueprint('api', __name__)

@api.route('/api/markets', methods=['GET'])
def get_markets():
    """Get all market data from database"""
    try:
        markets = fetch_all_markets()
        return jsonify({'markets': markets})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/api/game/state', methods=['GET'])
def get_game_state_endpoint():
    """Get current game state"""
    try:
        game_state = load_state()
        if game_state is None:
            return jsonify({'error': 'No active game found'}), 404
        return jsonify(game_state)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/api/game/move', methods=['POST'])
def submit_move():
    """Submit a player move"""
    try:
        data = request.get_json()
        # TODO: Validate and process the move
        # For now, just return success
        return jsonify({'status': 'move_processed', 'data': data})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/api/ai/decide', methods=['GET'])
def get_ai_decision():
    """Get AI opponent's next decision"""
    try:
        game_state = load_state()
        if game_state is None:
            return jsonify({'error': 'No active game found'}), 404

        # Extract AI-relevant game state (this might need adjustment)
        ai_context = {
            'current_ip': 5,  # TODO: Get from actual game state
            'owned_markets': [1],  # TODO: Get from actual game state
            'enemy_markets': [2, 3],  # TODO: Get from actual game state
            'market_states': {},  # TODO: Build from actual game state
            'rules': game_state.get('rules', {})
        }

        decision = choose_action(ai_context, difficulty='medium')
        return jsonify({'decision': decision})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/api/game/start', methods=['POST'])
def start_game():
    """Initialize a new game"""
    try:
        data = request.get_json() or {}
        difficulty = data.get('difficulty', 'medium')
        game_mode = data.get('mode', 'full')

        # Create teams (simplified for now)
        teams = [
            {"id": 1, "name": "Player", "colour": "#FF0000", "is_ai": False},
            {"id": 2, "name": "AI Opponent", "colour": "#0000FF", "is_ai": True},
        ]

        game_state = init_game_state(teams=teams, game_mode=game_mode, include_ai=True)
        save_state(game_state)

        return jsonify({'status': 'game_started', 'game_state': game_state})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api.route('/api/game/status', methods=['GET'])
def get_game_status():
    """Check current game status"""
    try:
        game_state = load_state()
        if game_state is None:
            return jsonify({'is_active': False})

        status = {
            'is_active': True,
            'current_stage': game_state.get('current_stage', 'unknown'),
            'current_round': game_state.get('current_round', 1),
            'teams': len(game_state.get('teams', []))
        }
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500