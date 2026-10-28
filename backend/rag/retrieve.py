"""Recuperación de fragmentos curriculares por similitud."""

import json
from dataclasses import dataclass

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import DocumentStatus
from app.models import CurricularDocument, DocumentChunk
from rag.embeddings import embed_text


@dataclass
class RetrievedChunk:
    id: int
    document_id: int
    content: str
    unit_name: str
    score: float


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def retrieve_chunks(db: Session, course_id: int, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
    k = top_k or settings.rag_top_k
    query_vec = embed_text(query)
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        return _retrieve_pgvector(db, course_id, query_vec, k)
    return _retrieve_in_memory(db, course_id, query_vec, k)


def _retrieve_pgvector(db: Session, course_id: int, query_vec: list[float], top_k: int) -> list[RetrievedChunk]:
    rows = db.execute(
        text(
            """
            SELECT dc.id, dc.document_id, dc.content, cd.unit_name,
                   1 - (dc.embedding <=> CAST(:qvec AS vector)) AS score
            FROM document_chunks dc
            JOIN curricular_documents cd ON cd.id = dc.document_id
            WHERE cd.course_id = :course_id
              AND cd.status = :status
              AND dc.embedding IS NOT NULL
            ORDER BY dc.embedding <=> CAST(:qvec AS vector)
            LIMIT :limit
            """
        ),
        {
            "qvec": json.dumps(query_vec),
            "course_id": course_id,
            "status": DocumentStatus.INDEXED.value,
            "limit": top_k,
        },
    ).mappings().all()
    return [
        RetrievedChunk(
            id=row["id"],
            document_id=row["document_id"],
            content=row["content"],
            unit_name=row["unit_name"],
            score=float(row["score"]),
        )
        for row in rows
    ]


def _retrieve_in_memory(db: Session, course_id: int, query_vec: list[float], top_k: int) -> list[RetrievedChunk]:
    rows = (
        db.query(DocumentChunk, CurricularDocument)
        .join(CurricularDocument, CurricularDocument.id == DocumentChunk.document_id)
        .filter(
            CurricularDocument.course_id == course_id,
            CurricularDocument.status == DocumentStatus.INDEXED.value,
        )
        .all()
    )
    scored: list[RetrievedChunk] = []
    for chunk, doc in rows:
        vec = json.loads(chunk.embedding_json)
        scored.append(
            RetrievedChunk(
                id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content,
                unit_name=doc.unit_name,
                score=cosine_similarity(query_vec, vec),
            )
        )
    scored.sort(key=lambda c: c.score, reverse=True)
    return scored[:top_k]


def score_chunks_for_query(
    db: Session, course_id: int, query: str, chunk_ids: list[int]
) -> dict[int, float]:
    """Similitud coseno entre la consulta y fragmentos ya seleccionados."""
    if not chunk_ids:
        return {}
    query_vec = embed_text(query)
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        rows = db.execute(
            text(
                """
                SELECT dc.id,
                       1 - (dc.embedding <=> CAST(:qvec AS vector)) AS score
                FROM document_chunks dc
                JOIN curricular_documents cd ON cd.id = dc.document_id
                WHERE cd.course_id = :course_id
                  AND dc.id = ANY(:chunk_ids)
                  AND dc.embedding IS NOT NULL
                """
            ),
            {
                "qvec": json.dumps(query_vec),
                "course_id": course_id,
                "chunk_ids": chunk_ids,
            },
        ).mappings().all()
        return {int(row["id"]): float(row["score"]) for row in rows}

    rows = (
        db.query(DocumentChunk)
        .join(CurricularDocument, CurricularDocument.id == DocumentChunk.document_id)
        .filter(
            CurricularDocument.course_id == course_id,
            DocumentChunk.id.in_(chunk_ids),
        )
        .all()
    )
    scores: dict[int, float] = {}
    for chunk in rows:
        if chunk.embedding_json:
            vec = json.loads(chunk.embedding_json)
            scores[chunk.id] = cosine_similarity(query_vec, vec)
    return scores
