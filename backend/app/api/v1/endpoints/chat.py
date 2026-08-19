import asyncio
import base64
import os
import re
import tempfile
from dataclasses import dataclass

import edge_tts
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gemini_client import get_client
from app.agents.orchestrator import handle_message
from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.logger import logger
from app.db.models import User

router = APIRouter(prefix="/chat", tags=["chat"])

SUPPORTED_AUDIO_MIME_EXTENSIONS = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".mp4",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/flac": ".flac",
    "audio/aac": ".aac",
    "audio/aiff": ".aiff",
}


@dataclass
class TranscriptionResult:
    text: str
    mime_type: str
    byte_size: int


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=12_000)


class TTSRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1, max_length=4_000)


def _normalize_audio_mime(content_type: str | None) -> str:
    mime_type = (content_type or "audio/webm").split(";")[0].strip().lower()
    return mime_type if mime_type in SUPPORTED_AUDIO_MIME_EXTENSIONS else "audio/webm"


def _clean_text_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[*_#`>\[\]]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_tts_chunks(text: str, max_chars: int = 900) -> list[str]:
    clean = _clean_text_for_speech(text)
    if not clean:
        return []

    sentences = re.findall(r"[^.!?;]+[.!?;]*", clean)
    chunks: list[str] = []
    current = ""
    for sentence in sentences or [clean]:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            chunks.extend(sentence[i : i + max_chars] for i in range(0, len(sentence), max_chars))
            continue
        if current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()

    if current:
        chunks.append(current)
    return chunks


async def synthesize_speech_base64(text: str) -> str | None:
    """Generate speech via edge-tts and return base64 MP3 data."""
    try:
        chunks: list[bytes] = []
        for speech_chunk in _split_tts_chunks(text):
            communicate = edge_tts.Communicate(
                speech_chunk,
                settings.VOICE_TTS_VOICE,
                rate=settings.VOICE_TTS_RATE,
            )
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio" and "data" in chunk:
                    chunks.append(chunk["data"])  # type: ignore[reportTypedDictNotRequiredAccess]
        tts_audio = b"".join(chunks)
        return base64.b64encode(tts_audio).decode("utf-8") if tts_audio else None
    except Exception:
        logger.exception("TTS generation failed")
        return None


async def _delete_uploaded_file(client, file_name: str) -> None:
    try:
        await client.aio.files.delete(name=file_name)
    except Exception:
        logger.warning("Background voice upload cleanup failed", exc_info=True)


async def transcribe_audio_bytes(audio_bytes: bytes, content_type: str | None) -> TranscriptionResult:
    """Upload audio to Gemini Files API and return precise multilingual transcription."""
    if not audio_bytes:
        return TranscriptionResult(text="", mime_type=_normalize_audio_mime(content_type), byte_size=0)

    if len(audio_bytes) > settings.VOICE_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Audio clip is too large. Try a shorter command.",
        )

    raw_mime = _normalize_audio_mime(content_type)
    suffix = SUPPORTED_AUDIO_MIME_EXTENSIONS[raw_mime]
    prompt = (
        "Transcribe this user command precisely. The user may speak English, Hindi, Gujarati, "
        "or a mix of them. Preserve the spoken language using the English alphabet where possible. "
        "Return only the transcription text. If the audio is silent, garbled, clipped, or unclear, "
        "reply exactly with UNCLEAR_AUDIO."
    )

    tmp_path = None
    uploaded_file = None
    client = get_client()

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        uploaded_file = await client.aio.files.upload(
            file=tmp_path,
            config=types.UploadFileConfig(mime_type=raw_mime),
        )

        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[uploaded_file, prompt],
        )
        return TranscriptionResult(
            text=(response.text or "").strip(),
            mime_type=raw_mime,
            byte_size=len(audio_bytes),
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Voice transcription failed")
        return TranscriptionResult(text="", mime_type=raw_mime, byte_size=len(audio_bytes))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        if uploaded_file is not None and uploaded_file.name:
            asyncio.create_task(_delete_uploaded_file(client, uploaded_file.name))


@router.post("")
async def chat_endpoint(
    request: ChatRequest, session: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)
):
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
            "ts": h.created_at.isoformat(),
        }
        for h in history
    ]


@router.post("/tts")
async def tts_endpoint(request: TTSRequest, current_user: User = Depends(get_current_user)):
    """Convert text to speech using edge-tts and return base64-encoded MP3 audio."""
    return {"audio_base64": await synthesize_speech_base64(request.text)}


@router.post("/voice")
async def chat_voice_endpoint(
    audio: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    audio_bytes = await audio.read()
    transcription = await transcribe_audio_bytes(audio_bytes, audio.content_type)

    if not transcription.text:
        return {"response": "I didn't hear anything.", "transcription": ""}
    if transcription.text == "UNCLEAR_AUDIO":
        return {"response": "I didn't quite catch that. Could you please repeat?", "transcription": ""}

    response_text = await handle_message(session, current_user, transcription.text)

    audio_base64 = await synthesize_speech_base64(response_text)

    return {
        "response": response_text,
        "transcription": transcription.text,
        "audio_base64": audio_base64,
        "audio_mime": transcription.mime_type,
        "audio_bytes": transcription.byte_size,
    }
