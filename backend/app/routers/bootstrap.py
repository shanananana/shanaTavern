from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.auth import can_manage_users, get_current_user
from app.database import get_db
from app.models import ChatSession, Favorite, User
from app.routers.characters import _to_list_item, _visible_characters_query
from app.services.character_sort import sort_characters_by_cuteness
from app.schemas import BootstrapOut, CharacterListItem, SessionOut, UserOut

router = APIRouter(prefix="/api", tags=["bootstrap"])


def _user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.can_manage_users = can_manage_users(user)
    return out


def _favorite_ids(db: Session, user_id: int) -> set[int]:
    rows = db.query(Favorite.character_id).filter(Favorite.user_id == user_id).all()
    return {row[0] for row in rows}


def _list_sessions(db: Session, user: User) -> list[SessionOut]:
    sessions = (
        db.query(ChatSession)
        .options(joinedload(ChatSession.character))
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    result: list[SessionOut] = []
    for session in sessions:
        out = SessionOut.model_validate(session)
        out.character_name = session.character.name if session.character else ""
        result.append(out)
    return result


@router.get("/bootstrap", response_model=BootstrapOut)
def bootstrap(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    favorite_ids = _favorite_ids(db, user.id)
    characters = sort_characters_by_cuteness(
        _visible_characters_query(db, user).all()
    )
    char_items: list[CharacterListItem] = [
        _to_list_item(c, user, favorite_ids) for c in characters
    ]
    return BootstrapOut(
        user=_user_out(user),
        characters=char_items,
        sessions=_list_sessions(db, user),
    )
