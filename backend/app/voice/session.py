import uuid
import logging
import asyncio
from datetime import datetime
from app.voice.vad import VAD
from app.voice.stt import STTProvider
from app.voice.tts import TTSProvider

logger = logging.getLogger(__name__)

class VoiceSession:
    def __init__(self, user_id: str):
        self.session_id = str(uuid.uuid4())
        self.user_id = user_id
        self.state = "IDLE"
        self.vad = VAD()
        self.stt = STTProvider()
        self.tts = TTSProvider()
        self.tts_cancel_event = asyncio.Event()
        self.websocket = None
        
    def transition(self, new_state: str):
        valid_transitions = {
            "IDLE": ["LISTENING"],
            "LISTENING": ["TRANSCRIBING", "IDLE"],
            "TRANSCRIBING": ["THINKING"],
            "THINKING": ["EXECUTING", "SPEAKING", "ERROR"],
            "EXECUTING": ["SPEAKING", "ERROR"],
            "SPEAKING": ["LISTENING", "INTERRUPTED", "IDLE"],
            "INTERRUPTED": ["LISTENING", "IDLE"],
            "ERROR": ["IDLE", "LISTENING"]
        }
        if new_state in valid_transitions.get(self.state, []):
            logger.info(f"VoiceSession {self.session_id}: {self.state} -> {new_state}")
            self.state = new_state
            return True
        logger.error(f"Invalid transition from {self.state} to {new_state}")
        return False
        
    async def receive_audio(self, audio_chunk: bytes):
        if self.state == "SPEAKING":
            # Barge-in detection
            if self.vad.process_chunk(audio_chunk):
                logger.info("Barge-in detected!")
                self.tts_cancel_event.set()
                self.transition("INTERRUPTED")
                self.transition("LISTENING")
                return
                
        if self.state in ["IDLE", "LISTENING"]:
            if self.state == "IDLE":
                self.transition("LISTENING")
            
            transcript = await self.stt.transcribe(audio_chunk)
            if transcript:
                self.transition("TRANSCRIBING")
                return transcript
        return None
