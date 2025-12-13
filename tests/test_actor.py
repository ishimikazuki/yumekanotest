from unittest.mock import MagicMock
import pytest
from orchestration import actor, models

def test_generate_reply_llm_success(mock_llm_client, mock_settings):
    mock_llm_client.chat.return_value = "こんにちは！"
    
    state = models.UserState.new("user1")
    history = []
    memories = []
    
    reply = actor.generate_reply("Hi", history, state, memories)
    assert reply == "こんにちは！"

def test_generate_reply_llm_failure_fallback(mock_llm_client, mock_settings):
    # Simulate LLM failure
    mock_llm_client.chat.side_effect = RuntimeError("API Error")
    
    state = models.UserState.new("user1")
    state.emotion.pleasure = -5.0 # Bad mood
    history = []
    memories = []
    
    # Fallback to simple reflection
    # mood <= -4 takes precedence over "sorry" keyword in _reflect
    reply = actor.generate_reply("ごめんね", history, state, memories)
    assert "イライラしてる" in reply
