from orchestration import storage, models

def test_init_db(mock_db):
    assert mock_db.exists()

def test_crud_user_state(mock_db):
    user_id = "user1"
    state = models.UserState.new(user_id)
    state.emotion.pleasure = 8.0
    
    storage.update_state(user_id, state)
    
    fetched = storage.fetch_state(user_id)
    assert fetched is not None
    assert fetched.user_id == user_id
    assert fetched.emotion.pleasure == 8.0
    
    assert storage.fetch_state("non_existent") is None

def test_chat_history(mock_db):
    user_id = "user1"
    storage.append_log(user_id, "user", "Hello")
    storage.append_log(user_id, "assistant", "Hi there")
    
    history = storage.fetch_history(user_id, limit=5)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "Hello"
    assert history[1]["role"] == "assistant"
    assert history[1]["content"] == "Hi there"

def test_reset_user(mock_db):
    user_id = "user_reset"
    storage.update_state(user_id, models.UserState.new(user_id))
    storage.append_log(user_id, "user", "foo")
    
    storage.reset_user(user_id)
    assert storage.fetch_state(user_id) is None
    assert len(storage.fetch_history(user_id)) == 0
