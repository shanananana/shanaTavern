from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Character, Ingredient, Recipe, RecipeItem, User
from app.schemas import (
    IngredientCreate,
    IngredientOut,
    RecipeApplyRequest,
    RecipeApplyResult,
    RecipeCreate,
    RecipeOut,
    CharacterCreate,
)
from app.services.prompt_builder import merge_ingredients_to_character_fields

router = APIRouter(tags=["ingredients"])


# ── Ingredients ───────────────────────────────────────────────────────────────

ing_router = APIRouter(prefix="/api/ingredients")


@ing_router.get("", response_model=list[IngredientOut])
def list_ingredients(
    scope: str = "all",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Ingredient)
    if scope == "system":
        q = q.filter(Ingredient.is_system.is_(True))
    elif scope == "mine":
        q = q.filter(Ingredient.owner_id == user.id)
    else:
        q = q.filter(
            (Ingredient.is_system.is_(True))
            | (Ingredient.owner_id == user.id)
            | (Ingredient.is_public.is_(True))
        )
    return q.order_by(Ingredient.category, Ingredient.name).all()


@ing_router.post("", response_model=IngredientOut)
def create_ingredient(
    body: IngredientCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = Ingredient(owner_id=user.id, is_system=False, **body.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@ing_router.put("/{ingredient_id}", response_model=IngredientOut)
def update_ingredient(
    ingredient_id: int,
    body: IngredientCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(Ingredient, ingredient_id)
    if item is None:
        raise HTTPException(status_code=404, detail="配料不存在")
    if item.is_system and not user.is_admin:
        raise HTTPException(status_code=403, detail="系统配料仅管理员可改")
    if not item.is_system and item.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权编辑")
    for k, v in body.model_dump().items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item


@ing_router.delete("/{ingredient_id}")
def delete_ingredient(
    ingredient_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = db.get(Ingredient, ingredient_id)
    if item is None:
        raise HTTPException(status_code=404, detail="配料不存在")
    if item.is_system and not user.is_admin:
        raise HTTPException(status_code=403, detail="系统配料仅管理员可删")
    if not item.is_system and item.owner_id != user.id:
        raise HTTPException(status_code=403, detail="无权删除")
    db.delete(item)
    db.commit()
    return {"ok": True}


# ── Recipes ───────────────────────────────────────────────────────────────────

recipe_router = APIRouter(prefix="/api/recipes")


@recipe_router.get("", response_model=list[RecipeOut])
def list_recipes(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recipes = (
        db.query(Recipe)
        .options(joinedload(Recipe.items).joinedload(RecipeItem.ingredient))
        .filter(Recipe.owner_id == user.id)
        .order_by(Recipe.created_at.desc())
        .all()
    )
    return recipes


@recipe_router.post("", response_model=RecipeOut)
def create_recipe(
    body: RecipeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recipe = Recipe(owner_id=user.id, name=body.name, description=body.description)
    for item in body.items:
        ing = db.get(Ingredient, item.ingredient_id)
        if ing is None:
            raise HTTPException(status_code=400, detail=f"配料 {item.ingredient_id} 不存在")
        recipe.items.append(
            RecipeItem(ingredient_id=item.ingredient_id, sort_order=item.sort_order)
        )
    db.add(recipe)
    db.commit()
    db.refresh(recipe)
    return recipe


@recipe_router.post("/{recipe_id}/apply", response_model=RecipeApplyResult)
def apply_recipe(
    recipe_id: int,
    body: RecipeApplyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recipe = (
        db.query(Recipe)
        .options(joinedload(Recipe.items).joinedload(RecipeItem.ingredient))
        .filter(Recipe.id == recipe_id, Recipe.owner_id == user.id)
        .first()
    )
    if recipe is None:
        raise HTTPException(status_code=404, detail="配方不存在")
    sorted_items = sorted(recipe.items, key=lambda i: i.sort_order)
    pairs = [(i.ingredient.category, i.ingredient.content) for i in sorted_items]
    merged = merge_ingredients_to_character_fields(pairs)
    character = Character(
        owner_id=user.id,
        name=body.name,
        description=body.description or recipe.description,
        personality=merged["personality"],
        scenario=merged["scenario"],
        system_prompt=merged["system_prompt"],
        post_history_instructions=merged["post_history_instructions"],
    )
    db.add(character)
    db.commit()
    db.refresh(character)
    return RecipeApplyResult(character=character)


@recipe_router.delete("/{recipe_id}")
def delete_recipe(
    recipe_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    recipe = db.get(Recipe, recipe_id)
    if recipe is None or recipe.owner_id != user.id:
        raise HTTPException(status_code=404, detail="配方不存在")
    db.delete(recipe)
    db.commit()
    return {"ok": True}
