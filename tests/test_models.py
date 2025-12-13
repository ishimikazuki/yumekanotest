from orchestration.models import EmotionState, UserState, ScenarioState

def test_emotion_state_clamping():
    emo = EmotionState(pleasure=15.0, arousal=-20.0, dominance=0.0)
    emo.clamp()
    assert emo.pleasure == 10.0
    assert emo.arousal == -10.0
    assert emo.dominance == 0.0

def test_emotion_state_decay():
    emo = EmotionState(pleasure=10.0, arousal=10.0, dominance=10.0)
    emo.decay(rate=1.0) # decay factor 0.1
    assert emo.pleasure == 9.0
    assert emo.arousal == 9.0
    assert emo.dominance == 10.0 # dominance is not decayed

def test_user_state_serialization():
    user_id = "test_user"
    state = UserState.new(user_id)
    state.emotion.pleasure = 5.0
    state.scenario.current_phase = "phase_2"
    
    data = state.to_dict()
    assert data["user_id"] == user_id
    assert data["emotion"]["pleasure"] == 5.0
    assert data["scenario"]["current_phase"] == "phase_2"
    
    restored = UserState.from_dict(data)
    assert restored.user_id == user_id
    assert restored.emotion.pleasure == 5.0
    assert restored.scenario.current_phase == "phase_2"
