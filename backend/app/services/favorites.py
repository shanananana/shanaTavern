from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Favorite


def favorite_ids(db: Session, user_id: int) -> set[int]:
    rows = db.query(Favorite.character_id).filter(Favorite.user_id == user_id).all()
    return {row[0] for row in rows}
