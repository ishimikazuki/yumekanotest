from unittest.mock import patch, MagicMock
import pytest
from orchestration import orchestrator, models

@pytest.fixture
def mock_subsystems():
    with patch("orchestration.orchestrator.observe") as mock_observe, \
         patch("orchestration.orchestrator.generate_reply") as mock_actor, \
         patch("orchestration.orchestrator.memory_system") as mock_mem:
        
        # Setup defaults
        mock_observe.return_value = models.ObservationResult(
            updated_state=models.UserState.new("user1"),
            instruction_override=None
        )
        mock_actor.return_value = "Mock Reply"
        mock_mem.retrieve_memory.return_value = []
        
        yield mock_observe, mock_actor, mock_mem

def test_process_chat_turn_legacy_flow(mock_db, mock_subsystems):
    mock_observe, mock_actor, mock_mem = mock_subsystems
    
    user_id = "user1"
    msg = "Hello"
    
    # Add a dummy critic pass
    with patch("orchestration.critic.check_reply", return_value=(True, "")) as mock_critic:
        result = orchestrator.process_chat_turn(user_id, msg)
    
    assert result["reply"] == "Mock Reply"
    assert mock_observe.called
    assert mock_actor.called
    assert mock_mem.save_memory.call_count == 2 # User + Assistant
