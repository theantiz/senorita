import asyncio
from uuid import uuid4

from sqlalchemy import select, text

from app.api.v1.endpoints.documents import _chunk_text
from app.db.models import Document, DocumentChunk, User
from app.db.session import async_session_factory
from app.memory.embeddings import embed_text


async def main():
    async with async_session_factory() as session:
        # 1. Get user
        res = await session.execute(select(User).limit(1))
        user = res.scalars().first()
        if not user:
            print("No user found.")
            return

        print("--- STEP 1: Uploading Document ---")
        full_text = """
        Project Orion: Phase 3 Architecture Review

        Overview
        Project Orion is our next-generation distributed database system designed for high-frequency trading platforms. Phase 3 focuses on latency reduction and cross-region replication strategies.

        Latency Goals
        The primary objective for Phase 3 is to reduce P99 read latency from 45ms to under 12ms globally. This will be achieved through our new proprietary routing algorithm, codenamed "Slipstream".

        Slipstream Algorithm
        Slipstream works by preemptively caching read-heavy partitions in edge nodes based on historical access patterns. It was developed by the Core Data team (led by Dr. Elena Rostova) over the last 18 months.

        Storage Layer Changes
        We are transitioning from traditional block storage to NVMe-over-Fabrics (NVMe-oF) for all tier-1 clusters. The migration is scheduled to begin on November 14th, 2026. This requires a complete rewrite of the storage controller module in Rust.
        """

        doc_id = uuid4()
        doc = Document(
            id=doc_id,
            user_id=user.id,
            filename="Project_Orion_Spec.txt",
            source="upload",
            full_text=full_text,
            summary="A test document summary.",
        )
        session.add(doc)
        await session.flush()

        chunks = _chunk_text(full_text, chunk_size=50, overlap=10)
        for idx, chunk_text_str in enumerate(chunks):
            embedding = await embed_text(chunk_text_str, task_type="RETRIEVAL_DOCUMENT")
            chunk = DocumentChunk(
                document_id=doc.id, user_id=user.id, chunk_text=chunk_text_str, chunk_index=idx, embedding=embedding
            )
            session.add(chunk)

        await session.commit()
        print(f"Document {doc.id} created with {len(chunks)} chunks.")

        print("\n--- STEP 2: Verify in DB ---")
        doc_res = await session.execute(text(f"SELECT id, filename FROM documents WHERE id = '{doc.id}'"))
        print("documents table:", doc_res.fetchall())
        chunk_res = await session.execute(text(f"SELECT count(*) FROM document_chunks WHERE document_id = '{doc.id}'"))
        print("document_chunks count:", chunk_res.scalar())

        print("\n--- STEP 3: Search Document (Slipstream query) ---")
        from app.agents.tool_registry import _handle_search_document

        query = "Who developed the Slipstream algorithm?"
        print(f"Query: {query}")
        result = await _handle_search_document(session, user.id, query, str(doc.id))

        if "results" in result and result["results"]:
            top_match = result["results"][0]
            print(f"Retrieved chunk_index: {top_match['chunk_index']}")
            print(f"Retrieved chunk_text:\n{top_match['chunk_text']}")
        else:
            print("No matching chunks found.")

        print("\n--- STEP 4: Delete Document (PURGE) ---")
        # Simulate cascade delete
        await session.delete(doc)
        await session.commit()

        doc_check = await session.execute(text(f"SELECT * FROM documents WHERE id = '{doc.id}'"))
        print("documents table rows:", len(doc_check.fetchall()))

        chunk_check = await session.execute(text(f"SELECT * FROM document_chunks WHERE document_id = '{doc.id}'"))
        print("document_chunks table rows:", len(chunk_check.fetchall()))


if __name__ == "__main__":
    asyncio.run(main())
