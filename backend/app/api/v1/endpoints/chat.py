import asyncio
import base64
import json
import os
import re
import tempfile
from dataclasses import dataclass

import edge_tts
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, status
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.gemini_client import get_client
from app.agents.orchestrator import handle_message
from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import (
    agent_event_replayed_total,
    voice_failures_total,
    voice_latency,
    voice_requests_total,
    websocket_active_connections,
    websocket_auth_failures_total,
    websocket_connections_total,
    websocket_disconnects_total,
    websocket_reconnects_total,
)
from app.core.rate_limit import limiter
from app.db.models import User

log = get_logger(__name__)

# For backward compat with existing code that imports `logger`
logger = log

router = APIRouter(prefix="/chat", tags=["chat"])

# Maximum WebSocket message size (bytes) — protects against payload flooding
_WS_MAX_MSG_BYTES = 64 * 1024  # 64 KB

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


@router.websocket("/stream")
async def chat_websocket(
    websocket: WebSocket,
    session: AsyncSession = Depends(get_db),
):  # noqa: C901
    from app.api.deps import get_current_user_ws

    try:
        current_user = await get_current_user_ws(websocket, session)
    except Exception:
        websocket_auth_failures_total.inc()
        await websocket.close(code=1008)
        return

    # Rate limit WS connections per user
    user_key = str(current_user.id)
    if not limiter.allow("websocket_connect", user_key):
        log.warning("websocket.rate_limited", user_id=user_key)
        await websocket.close(code=1008)
        return

    await websocket.accept()
    websocket_connections_total.inc()
    websocket_active_connections.inc()

    log.info(
        "websocket.connected",
        user_id=str(current_user.id),
        remote=getattr(websocket, "client", None) and str(websocket.client),
    )

    import uuid

    from sqlalchemy import select

    from app.agents.events import event_broadcaster
    from app.db.models.run import AgentEvent, AgentRun

    active_subscriptions: set[asyncio.Queue] = set()
    active_run_ids: set[uuid.UUID] = set()

    async def _pump_events(q: asyncio.Queue):
        try:
            while True:
                event = await q.get()
                await websocket.send_json(event)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            log.error("websocket.pump_error", error=str(exc))

    tasks = []

    try:
        while True:
            try:
                data_text = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue

            # Enforce message size limit
            if len(data_text.encode()) > _WS_MAX_MSG_BYTES:
                await websocket.send_json({"type": "error", "message": "Message too large."})
                continue

            try:
                data = json.loads(data_text)
            except (ValueError, json.JSONDecodeError):
                await websocket.send_json({"type": "error", "message": "Invalid JSON."})
                continue

            msg_type = data.get("type")

            if msg_type == "pong":
                continue

            if msg_type == "subscribe":
                run_id_str = data.get("agent_run_id")
                if run_id_str:
                    try:
                        run_id = uuid.UUID(run_id_str)
                        if run_id not in active_run_ids:
                            # ── OWNERSHIP VERIFICATION ──────────────────────────────
                            # Verify the run belongs to the authenticated user.
                            # A user must NEVER receive another user's events.
                            ownership_stmt = select(AgentRun).where(
                                AgentRun.id == run_id,
                                AgentRun.user_id == current_user.id,
                            )
                            ownership_result = await session.execute(ownership_stmt)
                            owned_run = ownership_result.scalar_one_or_none()
                            if owned_run is None:
                                log.warning(
                                    "websocket.subscription_denied",
                                    user_id=str(current_user.id),
                                    run_id=str(run_id),
                                    reason="run_not_owned",
                                )
                                await websocket.send_json({"type": "error", "message": "Forbidden."})
                                continue
                            # ────────────────────────────────────────────────────────

                            q = event_broadcaster.subscribe(run_id)
                            active_subscriptions.add(q)
                            active_run_ids.add(run_id)
                            task = asyncio.create_task(_pump_events(q))
                            tasks.append(task)

                            # Replay missed events
                            last_seq = data.get("last_sequence", 0)
                            if last_seq >= 0:
                                replay_stmt = (
                                    select(AgentEvent)
                                    .where(
                                        AgentEvent.run_id == run_id,
                                        AgentEvent.sequence_number > last_seq,
                                    )
                                    .order_by(AgentEvent.sequence_number)
                                )
                                replay_result = await session.execute(replay_stmt)
                                replayed = 0
                                for evt in replay_result.scalars().all():
                                    await websocket.send_json(
                                        {
                                            "event_id": str(evt.id),
                                            "agent_run_id": str(evt.run_id),
                                            "plan_id": str(evt.plan_id) if evt.plan_id else None,
                                            "step_id": evt.step_id,
                                            "type": evt.event_type,
                                            "status": evt.status,
                                            "message": evt.message,
                                            "timestamp": evt.created_at.isoformat(),
                                            "metadata": evt.metadata_payload,
                                            "sequence": evt.sequence_number,
                                        }
                                    )
                                    replayed += 1
                                if replayed:
                                    agent_event_replayed_total.inc(replayed)
                                    websocket_reconnects_total.inc()
                                    log.info(
                                        "websocket.reconnected",
                                        user_id=str(current_user.id),
                                        run_id=str(run_id),
                                        replayed=replayed,
                                    )
                    except ValueError:
                        pass
                continue

            if msg_type == "voice":
                if not limiter.allow("chat_message", user_key):
                    await websocket.send_json({"type": "error", "message": "Rate limit reached. Please slow down."})
                    continue
                audio_base64 = data.get("audio_base64")
                mime_type = data.get("mime_type", "audio/webm")
                if not audio_base64:
                    continue
                import base64
                import time

                audio_bytes = base64.b64decode(audio_base64)
                voice_requests_total.inc()
                start_time = time.time()
                try:
                    transcription = await transcribe_audio_bytes(audio_bytes, mime_type)
                    if not transcription.text or transcription.text == "UNCLEAR_AUDIO":
                        voice_failures_total.inc()
                        await websocket.send_json({"type": "error", "message": "I didn't hear anything clearly."})
                        continue

                    response_text = await handle_message(session, current_user, transcription.text)

                    # We can send the text immediately
                    await websocket.send_json({"type": "final", "message": response_text})

                    # Synthesize and send audio chunk
                    out_audio_b64 = await synthesize_speech_base64(response_text)
                    if out_audio_b64:
                        await websocket.send_json(
                            {
                                "type": "voice_response",
                                "audio_base64": out_audio_b64,
                                "transcription": transcription.text,
                                "message": response_text,
                            }
                        )
                    voice_latency.observe(time.time() - start_time)
                except Exception as exc:
                    voice_failures_total.inc()
                    log.error("websocket.voice_error", user_id=str(current_user.id), error=type(exc).__name__)
                    await websocket.send_json({"type": "error", "message": "Voice processing failed."})
                continue

            # New chat message from WS
            message = data.get("message")
            if message and isinstance(message, str):
                # Rate limit chat messages per user
                if not limiter.allow("chat_message", user_key):
                    await websocket.send_json({"type": "error", "message": "Rate limit reached. Please slow down."})
                    continue
                try:
                    response_text = await handle_message(session, current_user, message)
                    await websocket.send_json({"type": "final", "message": response_text})
                except Exception as exc:
                    log.error("websocket.handler_error", user_id=str(current_user.id), error=type(exc).__name__)
                    await websocket.send_json({"type": "error", "message": "An unexpected error occurred."})

    except WebSocketDisconnect:
        log.info("websocket.disconnected", user_id=str(current_user.id))
    finally:
        websocket_active_connections.dec()
        websocket_disconnects_total.inc()
        for t in tasks:
            t.cancel()
        for run_id, q in zip(active_run_ids, active_subscriptions, strict=False):
            event_broadcaster.unsubscribe(run_id, q)


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
