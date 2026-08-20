import pytest
from app.voice.session import VoiceSession

def test_voice_session_transitions():
    vs = VoiceSession("test_user")
    assert vs.state == "IDLE"
    
    # Valid transition
    assert vs.transition("LISTENING") == True
    assert vs.state == "LISTENING"
    
    assert vs.transition("TRANSCRIBING") == True
    assert vs.state == "TRANSCRIBING"
    
    # Invalid transition (TRANSCRIBING to EXECUTING directly)
    assert vs.transition("EXECUTING") == False
    assert vs.state == "TRANSCRIBING"

