import pytest
import base64
from app.voice.session import VoiceSession

@pytest.mark.asyncio
async def test_receive_audio_triggers_stt():
    vs = VoiceSession("test_user")
    
    # First small chunk (no transcript yet)
    t1 = await vs.receive_audio(b"fake" * 10)
    assert t1 is None
    
    # Massive chunk triggers STT finish
    t2 = await vs.receive_audio(b"fake" * 500)
    assert t2 == "What is my next task?"
    
    assert vs.state == "TRANSCRIBING"

