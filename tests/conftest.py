import os
import sys
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

# Initialize mock environment variables before importing modules that need them
os.environ["OPENAI_API_KEY"] = "mock_key"
os.environ["XAI_API_KEY"] = "mock_key"

# Ensure project root is importable regardless of current working dir
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestration import storage, models

@pytest.fixture
def mock_db(tmp_path):
    """Create a temporary SQLite DB for testing."""
    db_file = tmp_path / "test_bot.db"
    
    # Patch the DB_PATH in storage module
    with patch("orchestration.storage.DB_PATH", db_file):
        storage.init_db()
        yield db_file

@pytest.fixture
def mock_llm_client():
    """Mock the LLM client methods to avoid real API calls."""
    with patch("orchestration.llm_client.LLMClient.chat") as mock_chat, \
         patch("orchestration.llm_client.LLMClient.json_chat") as mock_json_chat, \
         patch("orchestration.llm_client.LLMClient.has", return_value=True):
        
        mock = MagicMock()
        mock.chat = mock_chat
        mock.json_chat = mock_json_chat
        yield mock

@pytest.fixture
def mock_settings():
    """Mock settings to control provider behavior."""
    with patch("orchestration.settings.settings") as mock:
        mock.llm.observer_provider = "openai"
        mock.llm.actor_provider = "xai"
        mock.llm.observer_model = "gpt-4o-mini"
        mock.llm.actor_model = "grok-4-fast"
        yield mock

@pytest.fixture
def sample_user_state():
    return models.UserState.new("test_user")
