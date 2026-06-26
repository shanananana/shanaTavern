import logging
import random

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user
from app.character_permissions import assert_can_edit, can_edit, can_view
from app.database import get_db
from app.models import Character, Favorite, LorebookEntry, User
from app.schemas import (
    CharacterCreate,
    CharacterListItem,
    CharacterListPage,
    CharacterOut,
    CharacterUpdate,
    LorebookEntryIn,
)
from app.services.avatar_images import display_avatar_url, invalidate_avatar_cache
from app.services.bootstrap_cache import invalidate as invalidate_bootstrap
from app.services.character_sort import sort_characters_by_cuteness
from app.services.favorites import favorite_ids
from app.services.prompt_builder import character_to_st_json, parse_character_import
from app.services.uploads import delete_avatar_file, save_character_avatar

router = APIRouter(prefix="/api/characters", tags=["characters"])
logger = logging.getLogger(__name__)


def _apply_lorebook(character: Character, entries: list[LorebookEntryIn]) -> None:
    character.lorebook_entries.clear()
    for item in entries:
        character.lorebook_entries.append(
            LorebookEntry(
                keys=item.keys,
                content=item.content,
                insert_order=item.insert_order,
                position=item.position,
                enabled=item.enabled,
            )
        )


def _to_list_item(
    character: Character,
    user: User,
    fav_ids: set[int] | None = None,
) -> CharacterListItem:
    item = CharacterListItem.model_validate(character)
    item.avatar_url = display_avatar_url(character.avatar_url)
    item.can_edit = can_edit(character, user)
    if fav_ids is not None:
        item.is_favorited = character.id in fav_ids
    return item


def _to_character_out(character: Character, user: User) -> CharacterOut:
    out = CharacterOut.model_validate(character)
    out.avatar_url = display_avatar_url(character.avatar_url)
    out.can_edit = can_edit(character, user)
    return out


def _visible_characters_query(db: Session, user: User):
    return db.query(Character).filter(
        (Character.is_default.is_(True))
        | (Character.owner_id == user.id)
        | (Character.is_public.is_(True))
    )


def _filter_characters(
    db: Session,
    user: User,
    scope: str,
    q: str,
    tag: str,
):
    query = db.query(Character)
    if scope == "mine":
        query = query.filter(Character.owner_id == user.id, Character.is_default.is_(False))
    elif scope == "default":
        query = query.filter(Character.is_default.is_(True))
    elif scope == "public":
        query = query.filter(Character.is_public.is_(True))
    elif scope == "favorites":
        query = query.join(Favorite, Favorite.character_id == Character.id).filter(
            Favorite.user_id == user.id
        )
    elif scope == "female":
        query = query.filter(
            (Character.is_default.is_(True))
            | (Character.owner_id == user.id)
            | (Character.is_public.is_(True))
        ).filter(Character.tags.contains("女性"))
    elif scope == "cute":
        query = query.filter(
            (Character.is_default.is_(True))
            | (Character.owner_id == user.id)
            | (Character.is_public.is_(True))
        ).filter(Character.tags.contains("可爱"))
    else:
        query = _visible_characters_query(db, user)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(Character.name.like(like), Character.description.like(like), Character.tags.like(like))
        )
    if tag.strip():
        query = query.filter(Character.tags.like(f"%{tag.strip()}%"))
    return query


@router.get("", response_model=CharacterListPage)
def list_characters(
    scope: str = Query("all", pattern="^(all|mine|default|public|favorites|female|cute)$"),
    q: str = Query("", max_length=64),
    tag: str = Query("", max_length=32),
    page: int = Query(1, ge=1),
    page_size: int = Query(0, ge=0, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = sort_characters_by_cuteness(_filter_characters(db, user, scope, q, tag).all())
    total = len(rows)
    effective_size = page_size if page_size > 0 else total or 1
    if page_size > 0:
        start = (page - 1) * page_size
        rows = rows[start : start + page_size]
    fav_ids = favorite_ids(db, user.id)
    items = [_to_list_item(c, user, fav_ids) for c in rows]
    has_more = page_size > 0 and page * page_size < total
    return CharacterListPage(
        items=items,
        total=total,
        page=page,
        page_size=effective_size,
        has_more=has_more,
    )


@router.get("/random", response_model=CharacterListItem)
def random_character(
    scope: str = Query("cute", pattern="^(all|default|female|cute)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = list_characters(scope=scope, q="", tag="", page=1, page_size=0, user=user, db=db)
    if not result.items:
        raise HTTPException(status_code=404, detail="没有匹配的角色")
    return random.choice(result.items)


@router.get("/tags")
def list_tags(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rows = _visible_characters_query(db, user).with_entities(Character.tags).all()
    tags: set[str] = set()
    for (tag_str,) in rows:
        for t in (tag_str or "").split(","):
            t = t.strip()
            if t:
                tags.add(t)
    return sorted(tags)


@router.get("/{character_id}", response_model=CharacterOut)
def get_character(
    character_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    character = (
        db.query(Character)
        .options(joinedload(Character.lorebook_entries))
        .filter(Character.id == character_id)
        .first()
    )
    if character is None or not can_view(character, user):
        raise HTTPException(status_code=404, detail="角色不存在")
    return _to_character_out(character, user)


@router.post("", response_model=CharacterOut)
def create_character(
    body: CharacterCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    character = Character(
        owner_id=user.id,
        is_default=False,
        **body.model_dump(exclude={"lorebook_entries"}),
    )
    _apply_lorebook(character, body.lorebook_entries)
    db.add(character)
    db.commit()
    db.refresh(character)
    invalidate_bootstrap(user.id)
    logger.info("Character created id=%s user=%s", character.id, user.id)
    return _to_character_out(character, user)


@router.put("/{character_id}", response_model=CharacterOut)
def update_character(
    character_id: int,
    body: CharacterUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    character = (
        db.query(Character)
        .options(joinedload(Character.lorebook_entries))
        .filter(Character.id == character_id)
        .first()
    )
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    if not can_edit(character, user):
        assert_can_edit(character, user)
    for field, value in body.model_dump(exclude={"lorebook_entries"}).items():
        setattr(character, field, value)
    _apply_lorebook(character, body.lorebook_entries)
    db.commit()
    db.refresh(character)
    invalidate_bootstrap(user.id)
    return _to_character_out(character, user)


@router.post("/{character_id}/avatar", response_model=CharacterOut)
async def upload_avatar(
    character_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    character = (
        db.query(Character)
        .options(joinedload(Character.lorebook_entries))
        .filter(Character.id == character_id)
        .first()
    )
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    if not can_edit(character, user):
        assert_can_edit(character, user)
    old_url = character.avatar_url
    character.avatar_url = await save_character_avatar(character_id, file)
    invalidate_avatar_cache(old_url)
    invalidate_avatar_cache(character.avatar_url)
    db.commit()
    db.refresh(character)
    if old_url and old_url != character.avatar_url:
        delete_avatar_file(old_url)
    invalidate_bootstrap(user.id)
    return _to_character_out(character, user)


@router.delete("/{character_id}")
def delete_character(
    character_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    character = db.get(Character, character_id)
    if character is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    if not can_edit(character, user):
        assert_can_edit(character, user)
    db.delete(character)
    db.commit()
    invalidate_bootstrap(user.id)
    return {"ok": True}


@router.post("/{character_id}/fork", response_model=CharacterOut)
def fork_character(
    character_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    source = (
        db.query(Character)
        .options(joinedload(Character.lorebook_entries))
        .filter(Character.id == character_id)
        .first()
    )
    if source is None or not can_view(source, user):
        raise HTTPException(status_code=404, detail="角色不存在")
    clone = Character(
        owner_id=user.id,
        name=f"{source.name} (副本)",
        avatar_url=source.avatar_url,
        description=source.description,
        tags=source.tags,
        system_prompt=source.system_prompt,
        personality=source.personality,
        scenario=source.scenario,
        first_mes=source.first_mes,
        mes_example=source.mes_example,
        post_history_instructions=source.post_history_instructions,
        creator_notes=source.creator_notes,
        alternate_greetings=source.alternate_greetings,
    )
    for entry in source.lorebook_entries:
        clone.lorebook_entries.append(
            LorebookEntry(
                keys=entry.keys,
                content=entry.content,
                insert_order=entry.insert_order,
                position=entry.position,
                enabled=entry.enabled,
            )
        )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    invalidate_bootstrap(user.id)
    return _to_character_out(clone, user)


@router.post("/{character_id}/favorite")
def toggle_favorite(
    character_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    character = db.get(Character, character_id)
    if character is None or not can_view(character, user):
        raise HTTPException(status_code=404, detail="角色不存在")
    existing = (
        db.query(Favorite)
        .filter(Favorite.user_id == user.id, Favorite.character_id == character_id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        invalidate_bootstrap(user.id)
        return {"favorited": False}
    db.add(Favorite(user_id=user.id, character_id=character_id))
    db.commit()
    invalidate_bootstrap(user.id)
    return {"favorited": True}


@router.get("/{character_id}/export")
def export_character(
    character_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    character = (
        db.query(Character)
        .options(joinedload(Character.lorebook_entries))
        .filter(Character.id == character_id)
        .first()
    )
    if character is None or not can_view(character, user):
        raise HTTPException(status_code=404, detail="角色不存在")
    return character_to_st_json(character)


@router.post("/import", response_model=CharacterOut)
def import_character(
    raw: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        parsed = parse_character_import(__import__("json").dumps(raw))
    except (ValueError, __import__("json").JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    body = CharacterCreate(**parsed)
    character = Character(
        owner_id=user.id,
        is_default=False,
        **body.model_dump(exclude={"lorebook_entries"}),
    )
    _apply_lorebook(character, body.lorebook_entries)
    db.add(character)
    db.commit()
    db.refresh(character)
    invalidate_bootstrap(user.id)
    return _to_character_out(character, user)
