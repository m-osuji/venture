import pytest
from unittest.mock import patch

from backend.helpers.game_state_helpers import (
    init_game_state,
    _cast_market_keys,
    _extract_market_states,
    save_state,
    load_state,
    _get_owner_colour
)

# test init_game_state with mocked fetch_all_markets
@patch("backend.helpers.game_state_helpers.fetch_all_markets")
def test_init_game_state(mock_fetch):
    mock_fetch.return_value = [{"market_id": 1, "market_name": "Test Market", "size": "Small", "regulation_level": 1, "growth_potential": 1, "security_risk": 1, "key_topic": "Tech"}]
    teams = [{"id": 1, "name": "Team A", "colour": "#000"}]
    
    state = init_game_state(teams)
    
    assert len(state["teams"]) == 1
    assert state["teams"][0]["team_name"] == "Team A"
    assert "1" in state["market_state"]
    assert state["market_state"]["1"]["_market_name"] == "Test Market"

# test market key casting
def test_cast_market_keys():
    input_dict = {"1": "data", "2": "more_data"}
    result = _cast_market_keys(input_dict)
    assert result == {1: "data", 2: "more_data"}

# test market extraction logic
def test_extract_market_states():
    market_state = {
        1: {"allocated_ip": 10, "threat": 0.5, "research_level": 2},
        2: {"allocated_ip": 5, "threat": 0.1, "research_level": 0},
        3: {"allocated_ip": 0, "threat": 0.0, "research_level": 0}
    }
    # only extract market 1
    result = _extract_market_states(market_state, [1], [2], [])
    
    assert 1 in result
    assert 2 in result
    assert 3 not in result # should be excluded from result dict keys based on logic

# test save and load (mocking file system)
def test_save_load_state(tmp_path):
    # use a temp directory provided by pytest
    d = tmp_path / "test_state.json"
    with patch("backend.helpers.game_state_helpers.GAME_STATE_PATH", str(d)):
        test_state = {"test": "data"}
        save_state(test_state)
        loaded = load_state()
        assert loaded == test_state

# test helper _get_owner_colour
def test_get_owner_colour():
    teams = [{"team_id": 1, "colour": "#FF0000"}]
    assert _get_owner_colour(1, teams) == "#FF0000"
    assert _get_owner_colour(None, teams) is None
    assert _get_owner_colour(99, teams) is None