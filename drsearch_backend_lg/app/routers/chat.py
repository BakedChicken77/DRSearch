from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from ..database import get_db
from ..models.chat import ChatSession, ChatMessage
from ..services.rag_agent import RAGAgent

router = APIRouter(prefix="/chat", tags=["chat"])
agent = RAGAgent()

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    user_id: str

class ChatResponse(BaseModel):
    response: str
    session_id: str
    context: List[dict]
    timestamp: str

@router.post("/query", response_model=ChatResponse)
async def chat_query(req: ChatRequest, db: Session = Depends(get_db)):
    if req.session_id:
        session = db.query(ChatSession).filter(ChatSession.id == req.session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = ChatSession(user_id=req.user_id, title=f"Chat {datetime.utcnow()}")
        db.add(session)
        db.commit()
        db.refresh(session)

    history_q = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at).all()
    history = [{"role": m.role, "content": m.content} for m in history_q]

    res = await agent.run(req.query, history)

    db.add(ChatMessage(session_id=session.id, role="user", content=req.query))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=res["response"]))
    session.updated_at = datetime.utcnow()
    db.commit()

    return ChatResponse(response=res["response"], session_id=str(session.id), context=res["context"], timestamp=res["timestamp"])

class SessionCreate(BaseModel):
    user_id: str
    title: Optional[str] = None

class SessionOut(BaseModel):
    id: str
    user_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

@router.post("/sessions", response_model=SessionOut)
async def create_session(data: SessionCreate, db: Session = Depends(get_db)):
    sess = ChatSession(user_id=data.user_id, title=data.title)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return SessionOut(id=str(sess.id), user_id=sess.user_id, title=sess.title, created_at=sess.created_at, updated_at=sess.updated_at)

@router.get("/sessions/{user_id}", response_model=List[SessionOut])
async def list_sessions(user_id: str, db: Session = Depends(get_db)):
    sessions = db.query(ChatSession).filter(ChatSession.user_id == user_id).all()
    return [SessionOut(id=str(s.id), user_id=s.user_id, title=s.title, created_at=s.created_at, updated_at=s.updated_at) for s in sessions]

@router.get("/sessions/{session_id}/messages")
async def session_messages(session_id: str, db: Session = Depends(get_db)):
    msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at).all()
    return [{"id": str(m.id), "role": m.role, "content": m.content, "created_at": m.created_at.isoformat()} for m in msgs]
