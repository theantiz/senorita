import base64
import os
import tempfile

import edge_tts
from fastapi import APIRouter, Depends, File, UploadFile
from google.genai import types
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gemini_client import get_client
from app.agents.orchestrator import handle_message
from app.core.config import settings
from app.core.logger import logger
from app.api.deps import get_current_user
from app.db.models import User
from app.api.deps import get_db

router = APIRouter(prefix="/chat", tags=["chat"])

class ChatRequest(BaseModel):
    message: str

class TTSRequest(BaseModel):
    text: str

@router.post("")
async def chat_endpoint(request: ChatRequest, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    response_text = await handle_message(session, current_user, request.message)
    return {"response": response_text}


@router.get("")
async def get_chat_history(session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    from sqlalchemy import select
    from app.db.models import Conversation
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(Conversation.created_at.asc())
        .limit(100)
    )
    result = await session.execute(stmt)
    history = result.scalars().all()
    
    return [
        {
            "role": h.role,
            "text": h.content,
            "ts": h.created_at.isoformat()
        }
        for h in history
    ]


@router.post("/tts")
async def tts_endpoint(request: TTSRequest, current_user: User = Depends(get_current_user)):
    """Convert text to speech using edge-tts and return base64-encoded MP3 audio."""
    if not request.text.strip():
        return {"audio_base64": None}
    try:
        communicate = edge_tts.Communicate(request.text, "en-US-AriaNeural")
        tts_audio = b""
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and "data" in chunk:
                tts_audio += chunk["data"]  # type: ignore[reportTypedDictNotRequiredAccess]
        audio_base64 = base64.b64encode(tts_audio).decode("utf-8") if tts_audio else None
    except Exception as e:
        logger.error(f"TTS Error: {e}")
        audio_base64 = None
    return {"audio_base64": audio_base64}


@router.post("/voice")
async def chat_voice_endpoint(
    audio: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Read the audio bytes
    audio_bytes = await audio.read()
    if not audio_bytes:
        return {"response": "I didn't hear anything.", "transcription": ""}

    # Normalise MIME type — strip codec params (e.g. "audio/webm;codecs=opus" → "audio/webm")
    # Gemini's Files API accepts the base type just fine.
    raw_mime = (audio.content_type or "audio/webm").split(";")[0].strip() or "audio/webm"

    # Determine a safe file extension from the mime type
    ext_map = {
        "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mp4": ".mp4",
        "audio/wav": ".wav", "audio/mpeg": ".mp3", "audio/flac": ".flac",
        "audio/aac": ".aac", "audio/aiff": ".aiff",
    }
    suffix = ext_map.get(raw_mime, ".webm")

    prompt = (
        "Transcribe this audio precisely. "
        "If it is garbled, unclear, or you cannot understand what is being said, "
        "reply EXACTLY with 'UNCLEAR_AUDIO'."
    )

    tmp_path = None
    uploaded_file = None
    client = get_client()  # raises ValueError early if API key is missing

    try:
        # Write bytes to a temp file — the Files API requires a file path, not raw bytes
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        # Upload via Files API (handles webm/opus correctly; inline Part.from_bytes does not)
        uploaded_file = await client.aio.files.upload(
            file=tmp_path,
            config=types.UploadFileConfig(mime_type=raw_mime),
        )

        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[uploaded_file, prompt],
        )
        transcribed_text = (response.text or '').strip()

    except Exception as e:
        return {"response": f"Sorry, I had trouble processing the audio: {str(e)}"}

    finally:
        # Clean up temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        # Best-effort cleanup of the Gemini-hosted file
        if uploaded_file is not None and uploaded_file.name:
            try:
                await client.aio.files.delete(name=uploaded_file.name)
            except Exception:
                pass

    if transcribed_text == "UNCLEAR_AUDIO" or not transcribed_text:
        return {"response": "I didn't quite catch that. Could you please repeat?", "transcription": ""}

    # Pass the transcribed text to the orchestrator
    response_text = await handle_message(session, current_user, transcribed_text)

    # Generate TTS audio via edge-tts (free Microsoft Neural TTS)
    audio_base64 = None
    try:
        communicate = edge_tts.Communicate(response_text, "en-US-AriaNeural")
        tts_audio = b""
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and "data" in chunk:
                tts_audio += chunk["data"]  # type: ignore[reportTypedDictNotRequiredAccess]
        if tts_audio:
            audio_base64 = base64.b64encode(tts_audio).decode("utf-8")
    except Exception as e:
        logger.error(f"TTS Error: {e}")

    return {
        "response": response_text,
        "transcription": transcribed_text,
        "audio_base64": audio_base64,
    }
