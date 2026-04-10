"""
Simple test to check the Granite model can be initialised and respond to a prompt

Usage:
    Run `python -m pytest backend/tests/test_granite.py -v -s` from project root to execute tests with print statements
"""
# apply Hugging Face compatibility patches before importing any Mellea modules
import backend.helpers.hf_helpers

from backend.ai_opponent.model_loader import init_granite

def test_model_loads():
    m = init_granite()
    assert m is not None

def test_model_responds():
    m = init_granite()
    result = m.instruct("What does IBM stand for? Reply in 5 words or less.")
    print(f"\n> [test_granite] Response: {result}")
    assert result is not None
    assert len(str(result)) > 0