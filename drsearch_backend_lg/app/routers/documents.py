from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import datetime
import os
import uuid
from ..database import get_db
from ..models.documents import Document
from ..services.vector_store import VectorStoreService
from ..config import get_settings

router = APIRouter(prefix="/documents", tags=["documents"])
store = VectorStoreService()
settings = get_settings()

class DocumentOut(BaseModel):
    id: str
    filename: str
    content_type: str
    file_size: int
    uploaded_by: str
    uploaded_at: datetime
    processed: str
    chunk_count: int

@router.post("/upload", response_model=DocumentOut)
async def upload(file: UploadFile = File(...), user_id: str = "anon", db: Session = Depends(get_db)):
    if file.size > settings.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="file too large")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1]
    unique = f"{uuid.uuid4()}{ext}"
    path = os.path.join(settings.UPLOAD_DIR, unique)
    with open(path, "wb") as f:
        f.write(await file.read())

    doc = Document(filename=file.filename, file_path=path, content_type=file.content_type, file_size=file.size, uploaded_by=user_id, processed="processing")
    db.add(doc)
    db.commit()
    db.refresh(doc)
    chunks = await store.add_document(path, {"document_id": str(doc.id), "filename": file.filename})
    doc.chunk_count = chunks
    doc.processed = "completed"
    db.commit()
    return DocumentOut(id=str(doc.id), filename=doc.filename, content_type=doc.content_type, file_size=doc.file_size, uploaded_by=doc.uploaded_by, uploaded_at=doc.uploaded_at, processed=doc.processed, chunk_count=doc.chunk_count)

@router.get("/", response_model=List[DocumentOut])
async def list_docs(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [DocumentOut(id=str(d.id), filename=d.filename, content_type=d.content_type, file_size=d.file_size, uploaded_by=d.uploaded_by, uploaded_at=d.uploaded_at, processed=d.processed, chunk_count=d.chunk_count) for d in docs]

@router.delete("/{document_id}")
async def delete_doc(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="not found")
    await store.delete_document(doc.filename)
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    db.delete(doc)
    db.commit()
    return {"message": "deleted"}

@router.get("/vector-store")
async def list_vector():
    return await store.list_documents()
