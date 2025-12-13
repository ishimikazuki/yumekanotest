from unittest.mock import MagicMock
import pytest
from orchestration import critic

def test_critic_success(mock_llm_client, mock_settings):
    mock_llm_client.chat.return_value = '{"is_ok": true, "feedback": ""}'
    
    is_ok, feedback = critic.check_reply("User input", "Draft reply")
    assert is_ok is True
    assert feedback == ""

def test_critic_failure_fallback(mock_llm_client, mock_settings):
    mock_llm_client.chat.side_effect = RuntimeError("API Error")
    
    # Should catch error and return True (pass)
    is_ok, feedback = critic.check_reply("User input", "Draft reply")
    assert is_ok is True
    assert feedback == ""
