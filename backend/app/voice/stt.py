import logging

logger = logging.getLogger(__name__)

class STTProvider:
    def __init__(self):
        self.buffer = bytearray()
        
    async def transcribe(self, audio_chunk: bytes) -> str:
        """Returns transcript if finalized, otherwise empty string."""
        # MVP: Hardcode mock transcript or rely on a real API if needed.
        # Since we can't safely call Google Cloud STT without credentials in this environment, 
        # we will mock the transcription output for structural testing.
        self.buffer.extend(audio_chunk)
        if len(self.buffer) > 1000:
            res = "What is my next task?"
            self.buffer.clear()
            return res
        return ""
