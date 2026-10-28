import json
import time
import uuid
from pathlib import Path

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import DocumentStatus
from app.models import Course, CourseTeacher, CurricularDocument, DocumentChunk, User
from rag.chunking import chunk_text, estimate_tokens
from rag.embeddings import embed_texts, embedding_to_json
from rag.parser import PdfParseError, extract_text_from_pdf


class DocumentServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


PDF_MAGIC = b"%PDF"


def ensure_upload_dir() -> Path:
    path = Path(settings.upload_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def teacher_can_access_course(db: Session, user: User, course_id: int) -> Course | None:
    course = db.query(Course).filter(Course.id == course_id, Course.org_id == user.org_id).first()
    if not course:
        return None
    if user.role in ("admin", "coordinator"):
        return course
    link = (
        db.query(CourseTeacher)
        .filter(CourseTeacher.course_id == course_id, CourseTeacher.teacher_id == user.id)
        .first()
    )
    return course if link else None


def validate_pdf_upload(filename: str, content: bytes) -> None:
    if not filename.lower().endswith(".pdf"):
        raise DocumentServiceError("Solo se permiten archivos PDF", 400)
    if not content.startswith(PDF_MAGIC):
        raise DocumentServiceError("El archivo no es un PDF válido", 400)
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise DocumentServiceError(f"El archivo supera {settings.max_upload_mb} MB", 400)


def ingest_document(
    db: Session,
    *,
    course_id: int,
    unit_name: str,
    filename: str,
    content: bytes,
) -> tuple[CurricularDocument, int]:
    validate_pdf_upload(filename, content)
    unit_name = unit_name.strip()
    if not unit_name:
        raise DocumentServiceError("La unidad curricular es obligatoria", 400)

    upload_root = ensure_upload_dir()
    stored_name = f"{uuid.uuid4().hex}.pdf"
    storage_path = upload_root / stored_name
    storage_path.write_bytes(content)

    doc = CurricularDocument(
        course_id=course_id,
        unit_name=unit_name,
        original_filename=filename,
        storage_path=str(storage_path),
        status=DocumentStatus.PROCESSING.value,
        file_size_bytes=len(content),
    )
    db.add(doc)
    db.flush()

    started = time.perf_counter()
    try:
        full_text, page_count = extract_text_from_pdf(storage_path, settings.max_pdf_pages)
        chunks_content = chunk_text(full_text)
        if not chunks_content:
            raise PdfParseError("No se generaron fragmentos de texto")

        vectors = embed_texts(chunks_content)
        for idx, (chunk_body, vector) in enumerate(zip(chunks_content, vectors, strict=True)):
            chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=idx,
                content=chunk_body,
                embedding_json=embedding_to_json(vector),
                token_count=estimate_tokens(chunk_body),
            )
            db.add(chunk)
            db.flush()
            _sync_pgvector(db, chunk.id, vector)

        doc.status = DocumentStatus.INDEXED.value
        doc.page_count = page_count
        doc.error_message = None
    except PdfParseError as exc:
        doc.status = DocumentStatus.FAILED.value
        doc.error_message = str(exc)
        db.commit()
        raise DocumentServiceError(str(exc), 422) from exc

    db.commit()
    db.refresh(doc)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return doc, elapsed_ms


def _sync_pgvector(db: Session, chunk_id: int, vector: list[float]) -> None:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    db.execute(
        text("UPDATE document_chunks SET embedding = CAST(:vec AS vector) WHERE id = :id"),
        {"vec": json.dumps(vector), "id": chunk_id},
    )


def list_course_documents(db: Session, course_id: int) -> list[dict]:
    rows = (
        db.query(
            CurricularDocument,
            func.count(DocumentChunk.id).label("chunk_count"),
        )
        .outerjoin(DocumentChunk, DocumentChunk.document_id == CurricularDocument.id)
        .filter(CurricularDocument.course_id == course_id)
        .group_by(CurricularDocument.id)
        .order_by(CurricularDocument.created_at.desc())
        .all()
    )
    result: list[dict] = []
    for doc, chunk_count in rows:
        result.append(
            {
                "id": doc.id,
                "course_id": doc.course_id,
                "unit_name": doc.unit_name,
                "original_filename": doc.original_filename,
                "status": doc.status,
                "page_count": doc.page_count,
                "file_size_bytes": doc.file_size_bytes,
                "chunk_count": int(chunk_count or 0),
                "error_message": doc.error_message,
                "created_at": doc.created_at,
            }
        )
    return result


def delete_document(db: Session, user: User, document_id: int) -> None:
    doc = db.query(CurricularDocument).filter(CurricularDocument.id == document_id).first()
    if not doc:
        raise DocumentServiceError("Documento no encontrado", 404)
    course = teacher_can_access_course(db, user, doc.course_id)
    if not course:
        raise DocumentServiceError("Sin permiso para este documento", 403)

    path = Path(doc.storage_path)
    if path.is_file():
        path.unlink(missing_ok=True)
    db.delete(doc)
    db.commit()


def get_teacher_document(db: Session, teacher: User, document_id: int) -> CurricularDocument:
    from app.models import CurricularDocument

    doc = db.query(CurricularDocument).filter(CurricularDocument.id == document_id).first()
    if not doc:
        raise DocumentServiceError("Documento no encontrado", 404)
    if not teacher_can_access_course(db, teacher, doc.course_id):
        raise DocumentServiceError("Sin permiso", 403)
    path = Path(doc.storage_path)
    if not path.is_file():
        raise DocumentServiceError("Archivo no disponible", 404)
    return doc


def list_document_chunk_previews(db: Session, user: User, document_id: int, limit: int = 5) -> list[dict]:
    doc = db.query(CurricularDocument).filter(CurricularDocument.id == document_id).first()
    if not doc:
        raise DocumentServiceError("Documento no encontrado", 404)
    if not teacher_can_access_course(db, user, doc.course_id):
        raise DocumentServiceError("Sin permiso para este documento", 403)
    rows = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .limit(limit)
        .all()
    )
    total = count_indexed_chunks(db, document_id)
    previews = [
        {
            "id": row.id,
            "chunk_index": row.chunk_index,
            "snippet": (row.content[:220] + "…") if len(row.content) > 220 else row.content,
            "token_count": row.token_count,
        }
        for row in rows
    ]
    return {"total_chunks": total, "previews": previews}


def count_indexed_chunks(db: Session, document_id: int) -> int:
    return (
        db.query(DocumentChunk)
        .join(CurricularDocument)
        .filter(
            CurricularDocument.id == document_id,
            CurricularDocument.status == DocumentStatus.INDEXED.value,
        )
        .count()
    )
