from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session, joinedload

from app.auth import can_manage_users, get_current_user
from app.database import get_db
from app.models import ChatSession, User
from app.routers.characters import _to_list_item, _visible_characters_query
from app.schemas import BootstrapOut, CharacterListItem, SessionOut, UserOut
from app.services.bootstrap_cache import get as cache_get
from app.services.bootstrap_cache import invalidate as cache_invalidate
from app.services.bootstrap_cache import set as cache_set
from app.services.character_sort import sort_characters_by_cuteness
from app.services.favorites import favorite_ids
from config import settings

router = APIRouter(prefix="/api", tags=["bootstrap"])
logger = logging.getLogger(__name__)


def _user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.can_manage_users = can_manage_users(user)
    return out


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


def _build_bootstrap(db: Session, user: User) -> BootstrapOut:
    fav_ids = favorite_ids(db, user.id)
    characters = sort_characters_by_cuteness(
        _visible_characters_query(db, user).all()
    )
    char_items: list[CharacterListItem] = [
        _to_list_item(c, user, fav_ids) for c in characters
    ]
    return BootstrapOut(
        user=_user_out(user),
        characters=char_items,
        sessions=_list_sessions(db, user),
    )


@router.get("/bootstrap", response_model=BootstrapOut)
def bootstrap(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    response: Response = Response(),
):
    cached = cache_get(user.id)
    if cached is not None:
        logger.debug("bootstrap cache hit user=%s", user.id)
        response.headers["X-Bootstrap-Cache"] = "HIT"
        return BootstrapOut.model_validate(cached)

    payload = _build_bootstrap(db, user)
    cache_set(user.id, payload.model_dump(mode="json"), settings.bootstrap_cache_ttl)
    response.headers["X-Bootstrap-Cache"] = "MISS"
    return payload


def invalidate_user_bootstrap(user_id: int) -> None:
    cache_invalidate(user_id)
