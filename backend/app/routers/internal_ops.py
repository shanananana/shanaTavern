from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth import require_admin
from app.database import get_db
from app.models import Character, ChatMessage, ChatSession, User
from app.schemas import MessageOut, OpsSessionOut, OpsUserOut

router = APIRouter(prefix="/api/internal/ops", tags=["internal-ops"])


@router.get("/users", response_model=list[OpsUserOut])
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    q: str = Query("", max_length=64, description="按用户名筛选"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    query = (
        db.query(
            User.id,
            User.username,
            func.count(func.distinct(ChatSession.id)).label("session_count"),
            func.count(ChatMessage.id).label("message_count"),
            func.max(ChatSession.updated_at).label("last_active"),
        )
        .outerjoin(ChatSession, ChatSession.user_id == User.id)
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .group_by(User.id, User.username)
    )
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(User.username.like(like))
    rows = (
        query.order_by(
            func.coalesce(func.max(ChatSession.updated_at), User.created_at).desc(),
            User.username,
        )
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        OpsUserOut(
            user_id=uid,
            username=username,
            session_count=int(session_count or 0),
            message_count=int(message_count or 0),
            last_active=last_active,
        )
        for uid, username, session_count, message_count, last_active in rows
    ]


@router.get("/sessions", response_model=list[OpsSessionOut])
def list_all_sessions(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
    q: str = Query("", max_length=64, description="按用户名筛选"),
    user_id: int | None = Query(None, description="按用户 ID 筛选"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    query = (
        db.query(
            ChatSession,
            User.username,
            Character.name.label("character_name"),
            func.count(ChatMessage.id).label("message_count"),
        )
        .join(User, ChatSession.user_id == User.id)
        .join(Character, ChatSession.character_id == Character.id)
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .group_by(ChatSession.id, User.username, Character.name)
    )
    if user_id is not None:
        query = query.filter(ChatSession.user_id == user_id)
    elif q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(User.username.like(like))
    rows = query.order_by(ChatSession.updated_at.desc()).offset(offset).limit(limit).all()
    return [
        OpsSessionOut(
            id=session.id,
            user_id=session.user_id,
            username=username,
            character_id=session.character_id,
            character_name=character_name or "",
            title=session.title,
            message_count=int(message_count or 0),
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
        for session, username, character_name, message_count in rows
    ]


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def get_session_messages(
    session_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    session = (
        db.query(ChatSession)
        .options(joinedload(ChatSession.messages))
        .filter(ChatSession.id == session_id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session.messages
