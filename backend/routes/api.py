import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify
from helpers.db_helpers import fetch_all_markets
from helpers.game_state_helpers import load_state, save_state, init_game_state, _get_frontend_states
from ai_opponent.agents.decision_maker import choose_action
from helpers.gameplay_helpers import _empty_turn_log
from enums import GameStage

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
        sanitised_state = _get_frontend_states(game_state)
        return jsonify(sanitised_state)
    except Exception as e:
        print(f"[API Error - /state]: {e}")
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
        teams = data.get('teams', [])

        if not teams:
            # fallback in case teams aren't present
            teams = [
                {"id": 1, "name": "Player", "colour": "#FF0000", "is_ai": False},
                {"id": 2, "name": "AI Opponent", "colour": "#0000FF", "is_ai": True},
            ]

        # check if any team is marked as ai
        include_ai = any(t.get('is_ai') for t in teams)
        game_mode = data.get('mode', 'full')
    
        game_state = init_game_state(teams=teams, game_mode=game_mode, include_ai=include_ai)
        save_state(game_state)
        
        return jsonify({'status': 'game_started', 'session_uuid': game_state['session_uuid']})
        # return jsonify({'status': 'game_started', 'game_state': game_state})
    except Exception as e:
        print(f"[API Error - /start]: {e}")
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
    
@api.route('/api/game/advance', methods=['POST'])
def advance_game_stage():
    """
    [DEMO ONLY] Forces the game to the next stage.
    Cycles through GameStage enum. If it reaches the end, it advances to the next round.
    """
    try:
        game_state = load_state()
        if game_state is None:
            return jsonify({'error': 'No active game found'}), 404

        current_stage_raw = game_state.get('current_stage', 1)
        
        # get all possible stages in order
        all_stages = list(GameStage)
        
        try:
            # cast the raw JSON value back to an Enum object
            current_stage_enum = GameStage(current_stage_raw)
            current_idx = all_stages.index(current_stage_enum)
            
            # calculate the next index
            next_idx = current_idx + 1
            
            # check if the round is over
            if next_idx >= len(all_stages):
                # if last stage is over, wrap around to the beginning
                next_stage = all_stages[0]
                game_state['current_round'] = game_state.get('current_round', 1) + 1
                
                # reset the turn log at the end of each round
                game_state['turn_log'] = _empty_turn_log()
            else:
                # move to next stage
                next_stage = all_stages[next_idx]

            # update state with new raw value
            game_state['current_stage'] = next_stage.value

            if next_stage.name == 'NEGOTIATE':
                print("[API] Triggering IBM Granite AI...")
                ai_team = next((t for t in game_state.get('teams', []) if t.get('is_ai')), None)

                if ai_team:
                    mock_ai_context = {
                        'current_ip': 5,  
                        'rules': game_state.get('rules', {})
                    }

                    decision = choose_action(mock_ai_context, difficulty=game_state.get('ai_difficulty', 'medium'))
                    print(f"[API] AI Decision: {decision}")
            
        except ValueError:
            # if the current_stage is corrupted, reset to the first stage
            print(f"[API Warning] Invalid stage {current_stage_raw}, resetting to start.")
            game_state['current_stage'] = all_stages[0].value
            next_stage = all_stages[0]

        # save the mutated state back to json file
        save_state(game_state)

        return jsonify({
            'status': 'success',
            'message': f"Advanced to Round {game_state.get('current_round')} - {next_stage.name}",
            'new_stage': next_stage.name,
            'current_round': game_state.get('current_round')
        })

    except Exception as e:
        print(f"[API Error - /api/game/advance]: {e}")
        return jsonify({'error': str(e)}), 500