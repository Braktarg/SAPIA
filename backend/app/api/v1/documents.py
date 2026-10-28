from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_teacher
from app.core.database import get_db
from app.models import User
from app.schemas.document import DocumentRead, DocumentUploadResponse
from app.services.document_service import (
    DocumentServiceError,
    delete_document,
    get_teacher_document,
    ingest_document,
    list_course_documents,
    list_document_chunk_previews,
    teacher_can_access_course,
)
from app.services.auth_service import log_audit

router = APIRouter(tags=["documents"])


@router.get("/courses/{course_id}/documents", response_model=list[DocumentRead])
def get_course_documents(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_teacher)],
) -> list[DocumentRead]:
    if not teacher_can_access_course(db, current_user, course_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado")
    return list_course_documents(db, course_id)


@router.post(
    "/courses/{course_id}/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_course_document(
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_teacher)],
    unit_name: Annotated[str, Form()],
    file: UploadFile = File(...),
) -> DocumentUploadResponse:
    if not teacher_can_access_course(db, current_user, course_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Curso no encontrado")

    content = await file.read()
    filename = file.filename or "documento.pdf"
    try:
        doc, processing_ms = ingest_document(
            db,
            course_id=course_id,
            unit_name=unit_name,
            filename=filename,
            content=content,
        )
    except DocumentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    rows = list_course_documents(db, course_id)
    row = next((r for r in rows if r["id"] == doc.id), None)
    if not row:
        raise HTTPException(status_code=500, detail="Documento creado pero no listado")

    log_audit(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        entity_type="curricular_document",
        entity_id=str(doc.id),
        action="document_indexed",
        payload={"course_id": course_id, "unit_name": unit_name, "chunk_count": row["chunk_count"]},
    )

    return DocumentUploadResponse(document=DocumentRead(**row), processing_ms=processing_ms)


@router.get("/documents/{document_id}/chunks")
def get_document_chunks(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_teacher)],
) -> dict:
    try:
        return list_document_chunk_previews(db, current_user, document_id)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/documents/{document_id}/file")
def download_teacher_document(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_teacher)],
) -> FileResponse:
    try:
        doc = get_teacher_document(db, current_user, document_id)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    path = Path(doc.storage_path)
    return FileResponse(path, media_type="application/pdf", filename=doc.original_filename)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    document_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(require_teacher)],
) -> None:
    try:
        delete_document(db, current_user, document_id)
    except DocumentServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
