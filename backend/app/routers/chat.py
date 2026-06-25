import json
import random
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.database import get_db
from app.models import Character, ChatMessage, ChatSession, User
from app.schemas import ChatSendRequest, MessageOut, SessionCreate, SessionOut
from app.services.llm import LLMError, chat_completion_stream
from app.services.prompt_builder import build_chat_messages

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _pick_greeting(character: Character) -> str:
    options = []
    if character.first_mes.strip():
        options.append(character.first_mes.strip())
    if character.alternate_greetings.strip():
        options.extend(
            g.strip()
            for g in character.alternate_greetings.split("|||")
            if g.strip()
        )
    return random.choice(options) if options else ""


def _get_session(db: Session, session_id: int, user: User) -> ChatSession:
    session = (
        db.query(ChatSession)
        .options(
            joinedload(ChatSession.character).joinedload(Character.lorebook_entries),
            joinedload(ChatSession.messages),
        )
        .filter(ChatSession.id == session_id, ChatSession.user_id == user.id)
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(ChatSession)
        .options(joinedload(ChatSession.character))
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    result = []
    for s in sessions:
        out = SessionOut.model_validate(s)
        out.character_name = s.character.name if s.character else ""
        result.append(out)
    return result


@router.post("/sessions", response_model=SessionOut)
def create_session(
    body: SessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    character = db.get(Character, body.character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    session = ChatSession(
        user_id=user.id,
        character_id=body.character_id,
        title=body.title or f"与 {character.name} 的对话",
    )
    db.add(session)
    db.flush()
    greeting = _pick_greeting(character)
    if greeting:
        db.add(
            ChatMessage(
                session_id=session.id,
                role="assistant",
                content=greeting,
            )
        )
    db.commit()
    db.refresh(session)
    out = SessionOut.model_validate(session)
    out.character_name = character.name
    return out


@router.get("/sessions/{session_id}/messages", response_model=list[MessageOut])
def get_messages(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_session(db, session_id, user)
    return session.messages


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_session(db, session_id, user)
    db.delete(session)
    db.commit()
    return {"ok": True}


@router.post("/sessions/{session_id}/send")
async def send_message(
    session_id: int,
    body: ChatSendRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_session(db, session_id, user)
    character = session.character

    def _valid_history() -> list[ChatMessage]:
        return [
            m
            for m in session.messages
            if m.role in ("user", "assistant") and m.content.strip()
        ]

    if body.regenerate:
        if not session.messages or session.messages[-1].role != "assistant":
            raise HTTPException(status_code=400, detail="没有可重新生成的消息")
        last_assistant = session.messages[-1]
        db.delete(last_assistant)
        db.commit()
        db.refresh(session)
        history = _valid_history()
        if not history or history[-1].role != "user":
            raise HTTPException(status_code=400, detail="没有用户消息可重试")
        user_content = history[-1].content
        history = history[:-1]
        llm_messages = build_chat_messages(character, user, history, user_content)
    else:
        if not body.content.strip():
            raise HTTPException(status_code=400, detail="消息不能为空")
        user_content = body.content.strip()
        history = _valid_history()
        llm_messages = build_chat_messages(character, user, history, user_content)
        db.add(ChatMessage(session_id=session.id, role="user", content=user_content))
        db.commit()
        db.refresh(session)

    async def event_stream() -> AsyncIterator[bytes]:
        full_parts: list[str] = []
        try:
            async for token in chat_completion_stream(llm_messages):
                full_parts.append(token)
                payload = json.dumps({"type": "token", "content": token}, ensure_ascii=False)
                yield f"data: {payload}\n\n".encode()
        except LLMError as exc:
            err = json.dumps({"type": "error", "content": str(exc)}, ensure_ascii=False)
            yield f"data: {err}\n\n".encode()
            return

        assistant_text = "".join(full_parts)
        if not assistant_text.strip():
            err = json.dumps(
                {"type": "error", "content": "模型未返回内容，请检查 LM Studio 是否在运行"},
                ensure_ascii=False,
            )
            yield f"data: {err}\n\n".encode()
            return
        msg = ChatMessage(session_id=session.id, role="assistant", content=assistant_text)
        db.add(msg)
        db.commit()
        db.refresh(msg)
        done = json.dumps(
            {"type": "done", "message": MessageOut.model_validate(msg).model_dump(mode="json")},
            ensure_ascii=False,
            default=str,
        )
        yield f"data: {done}\n\n".encode()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/sessions/{session_id}/messages")
def clear_messages(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_session(db, session_id, user)
    for msg in list(session.messages):
        db.delete(msg)
    db.commit()
    return {"ok": True}


@router.delete("/sessions/{session_id}/messages/{message_id}")
def delete_message(
    session_id: int,
    message_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_session(db, session_id, user)
    msg = db.get(ChatMessage, message_id)
    if msg is None or msg.session_id != session.id:
        raise HTTPException(status_code=404, detail="消息不存在")
    db.delete(msg)
    db.commit()
    return {"ok": True}
