import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_db
from app.db.models import User
from app.db.models.document import Document
from app.db.models.document_chunk import DocumentChunk
from app.memory.embeddings import embed_text
from app.agents.gemini_client import get_client
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into ~500-token chunks with slight overlap."""
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
        i += chunk_size - overlap
    return chunks


def _extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    import io
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


@router.post("")
async def upload_document(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("pdf", "txt"):
        raise HTTPException(status_code=400, detail="Only .pdf and .txt files are supported")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # Extract text
    if ext == "pdf":
        full_text = _extract_text_from_pdf(content)
    else:
        full_text = content.decode("utf-8", errors="replace")

    if not full_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    # Create document record
    doc = Document(
        user_id=current_user.id,
        filename=file.filename,
        source="upload",
        full_text=full_text,
    )
    session.add(doc)
    await session.flush()  # get doc.id

    # Chunk and embed
    chunks = _chunk_text(full_text)
    for idx, chunk_text_str in enumerate(chunks):
        try:
            embedding = await embed_text(chunk_text_str, task_type="RETRIEVAL_DOCUMENT")
        except Exception as e:
            logger.warning(f"Failed to embed chunk {idx}: {e}")
            embedding = None

        chunk = DocumentChunk(
            document_id=doc.id,
            user_id=current_user.id,
            chunk_text=chunk_text_str,
            chunk_index=idx,
            embedding=embedding,
        )
        session.add(chunk)

    # Generate summary via Gemini
    try:
        client = get_client()
        summary_prompt = (
            f"Summarize the following document in 2-3 concise sentences. "
            f"Focus on the main topic, key points, and purpose of the document.\n\n"
            f"{full_text[:8000]}"
        )
        resp = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=summary_prompt,
        )
        doc.summary = (resp.text or "").strip()
    except Exception as e:
        logger.error(f"Failed to generate summary: {e}")
        doc.summary = "Summary generation pending."

    await session.commit()
    await session.refresh(doc)

    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "summary": doc.summary,
        "chunk_count": len(chunks),
        "created_at": doc.created_at.isoformat(),
    }


@router.get("")
async def list_documents(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    result = await session.execute(stmt)
    docs = result.scalars().all()

    out = []
    for d in docs:
        # Get chunk count
        count_stmt = select(func.count()).where(DocumentChunk.document_id == d.id)
        count_res = await session.execute(count_stmt)
        chunk_count = count_res.scalar() or 0

        out.append({
            "id": str(d.id),
            "filename": d.filename,
            "summary": d.summary,
            "chunk_count": chunk_count,
            "created_at": d.created_at.isoformat(),
        })
    return out


@router.get("/{document_id}")
async def get_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await session.get(Document, document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")

    count_stmt = select(func.count()).where(DocumentChunk.document_id == doc.id)
    count_res = await session.execute(count_stmt)
    chunk_count = count_res.scalar() or 0

    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "summary": doc.summary,
        "source": doc.source,
        "chunk_count": chunk_count,
        "created_at": doc.created_at.isoformat(),
    }


@router.delete("/{document_id}")
async def delete_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await session.get(Document, document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")

    await session.delete(doc)  # cascade deletes chunks
    await session.commit()
    return {"ok": True}


@router.get("/{document_id}/questions")
async def get_document_questions(
    document_id: UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await session.get(Document, document_id)
    if not doc or doc.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")

    # Return cached questions if available
    if doc.cached_questions:
        return {"questions": json.loads(doc.cached_questions)}

    # Generate questions via Gemini
    try:
        client = get_client()
        prompt = (
            f"You have just read the following document. Generate 2-4 genuinely useful "
            f"clarifying questions that a thoughtful assistant would ask after reading it. "
            f"Focus on: ambiguous terms, missing information needed to act on the document, "
            f"decisions implied but not confirmed, or context that would help you assist the user better. "
            f"Do NOT generate generic quiz questions. Return ONLY a JSON array of strings.\n\n"
            f"Document title: {doc.filename}\n"
            f"Content:\n{doc.full_text[:12000]}"
        )
        resp = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )
        text = (resp.text or "").strip()
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        questions = json.loads(text.strip())

        # Cache the result
        doc.cached_questions = json.dumps(questions)
        await session.commit()

        return {"questions": questions}
    except Exception as e:
        logger.error(f"Failed to generate questions: {e}")
        return {"questions": [], "error": str(e)}
