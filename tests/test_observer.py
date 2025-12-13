from unittest.mock import MagicMock
import pytest
from orchestration import observer, models

def test_update_state_llm_success(mock_llm_client, mock_settings):
    # Mock LLM response
    mock_llm_client.json_chat.return_value = {
        "emotion": {"pleasure": 5.0, "arousal": 2.0, "dominance": 1.0},
        "scenario": {"variables": {"visited": True}},
        "instruction_override": "Be happy"
    }

    state = models.UserState.new("user1")
    history = []
    
    result = observer.update_state("Hello", state, history)
    
    # Observer applies decay(0.1) -> x * 0.99
    assert result.updated_state.emotion.pleasure == 4.95
    assert result.updated_state.scenario.variables.get("visited") is True
    assert result.instruction_override == "Be happy"

def test_update_state_llm_failure_fallback(mock_llm_client, mock_settings):
    # Simulate LLM failure
    mock_llm_client.has.return_value = False # Simulate provider not available or error
    
    # Or force raise error
    mock_llm_client.json_chat.side_effect = RuntimeError("API Error")
    
    state = models.UserState.new("user1")
    history = []
    
    # This should currently fail until we implement fallback
    # We expect it to fallback to keyword matching
    # "好き" -> pleasure +1.0
    result = observer.update_state("あ、これ好き！", state, history)
    
    assert result.updated_state.emotion.pleasure > 0.0
    assert result.instruction_override is None # No instruction from simple rule
