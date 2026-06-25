from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import hash_password, require_admin
from app.database import get_db
from app.models import (
    Character,
    ChatMessage,
    ChatSession,
    Favorite,
    Ingredient,
    LorebookEntry,
    Recipe,
    RecipeItem,
    User,
)
from app.schemas import AdminCreateUserRequest, CharacterCreate, CharacterOut, IngredientCreate, IngredientOut, LLMStatusOut
from app.services.llm import check_connection
from config import settings

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _purge_user(db: Session, user_id: int) -> None:
    session_ids = [
        s.id for s in db.query(ChatSession.id).filter(ChatSession.user_id == user_id).all()
    ]
    if session_ids:
        db.query(ChatMessage).filter(ChatMessage.session_id.in_(session_ids)).delete(
            synchronize_session=False
        )
        db.query(ChatSession).filter(ChatSession.user_id == user_id).delete(synchronize_session=False)

    db.query(Favorite).filter(Favorite.user_id == user_id).delete(synchronize_session=False)

    char_ids = [
        c.id for c in db.query(Character.id).filter(Character.owner_id == user_id).all()
    ]
    if char_ids:
        char_session_ids = [
            s.id for s in db.query(ChatSession.id).filter(ChatSession.character_id.in_(char_ids)).all()
        ]
        if char_session_ids:
            db.query(ChatMessage).filter(ChatMessage.session_id.in_(char_session_ids)).delete(
                synchronize_session=False
            )
            db.query(ChatSession).filter(ChatSession.character_id.in_(char_ids)).delete(
                synchronize_session=False
            )
        db.query(Favorite).filter(Favorite.character_id.in_(char_ids)).delete(synchronize_session=False)
        db.query(LorebookEntry).filter(LorebookEntry.character_id.in_(char_ids)).delete(
            synchronize_session=False
        )
        db.query(Character).filter(Character.owner_id == user_id).delete(synchronize_session=False)

    recipe_ids = [r.id for r in db.query(Recipe.id).filter(Recipe.owner_id == user_id).all()]
    if recipe_ids:
        db.query(RecipeItem).filter(RecipeItem.recipe_id.in_(recipe_ids)).delete(synchronize_session=False)
        db.query(Recipe).filter(Recipe.owner_id == user_id).delete(synchronize_session=False)

    db.query(Ingredient).filter(Ingredient.owner_id == user_id).delete(synchronize_session=False)


@router.get("/llm-status", response_model=LLMStatusOut)
async def llm_status(_: User = Depends(require_admin)):
    connected, models = await check_connection()
    return LLMStatusOut(
        connected=connected,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
        available_models=models,
    )


@router.get("/users")
def list_users(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "nickname": u.nickname,
            "is_admin": u.is_admin,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.post("/users")
def create_user(
    body: AdminCreateUserRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=body.username.strip(),
        password_hash=hash_password(body.password),
        nickname=(body.nickname or body.username).strip()[:64],
        is_admin=body.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname,
        "is_admin": user.is_admin,
    }


@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    target = db.get(User, user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.is_admin:
        admin_count = db.query(User).filter(User.is_admin.is_(True)).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="不能删除最后一个管理员")
    _purge_user(db, user_id)
    db.delete(target)
    db.commit()
    return {"ok": True}


@router.post("/characters", response_model=CharacterOut)
def admin_create_default_character(
    body: CharacterCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from app.routers.characters import _apply_lorebook

    character = Character(is_default=True, owner_id=None, **body.model_dump(exclude={"lorebook_entries"}))
    _apply_lorebook(character, body.lorebook_entries)
    db.add(character)
    db.commit()
    db.refresh(character)
    return character


@router.post("/ingredients", response_model=IngredientOut)
def admin_create_system_ingredient(
    body: IngredientCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = Ingredient(is_system=True, owner_id=None, is_public=True, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
