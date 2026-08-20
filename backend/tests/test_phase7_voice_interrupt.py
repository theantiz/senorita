import pytest
import asyncio
from app.voice.session import VoiceSession

@pytest.mark.asyncio
async def test_voice_barge_in():
    vs = VoiceSession("test_user")
    vs.transition("LISTENING")
    vs.transition("TRANSCRIBING")
    vs.transition("THINKING")
    vs.transition("SPEAKING")
    
    assert vs.state == "SPEAKING"
    
    # Simulate user sending massive audio chunk while agent is speaking
    chunk = b"fake_audio_data" * 100 # Large enough to trigger VAD
    
    await vs.receive_audio(chunk)
    
    assert vs.tts_cancel_event.is_set() == True
    assert vs.state == "LISTENING"
