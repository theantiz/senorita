import logging

logger = logging.getLogger(__name__)

class VAD:
    def __init__(self):
        self.is_speaking = False
        
    def process_chunk(self, audio_chunk: bytes) -> bool:
        """Returns True if speech is detected (mock implementation for MVP)."""
        # In a real implementation, we'd use WebRTC VAD or Silero VAD here.
        # For this prototype, we'll assume any chunk > 100 bytes is speech
        return len(audio_chunk) > 100
