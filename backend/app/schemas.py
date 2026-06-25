from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=4, max_length=64)
    nickname: str = Field(default="", max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    nickname: str
    is_admin: bool
    created_at: datetime
    can_manage_users: bool = False

    model_config = {"from_attributes": True}


class CreateManagedUserRequest(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=4, max_length=64)
    nickname: str = Field(default="", max_length=64)


class ProfileUpdateRequest(BaseModel):
    nickname: str | None = Field(default=None, max_length=64)


class AdminCreateUserRequest(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=4, max_length=64)
    nickname: str = Field(default="", max_length=64)
    is_admin: bool = False


# ── Character ─────────────────────────────────────────────────────────────────

class LorebookEntryIn(BaseModel):
    keys: str
    content: str
    insert_order: int = 100
    position: str = "before_char"
    enabled: bool = True


class LorebookEntryOut(LorebookEntryIn):
    id: int

    model_config = {"from_attributes": True}


class CharacterBase(BaseModel):
    name: str
    avatar_url: str = ""
    description: str = ""
    tags: str = ""
    is_public: bool = False
    system_prompt: str = ""
    personality: str = ""
    scenario: str = ""
    first_mes: str = ""
    mes_example: str = ""
    post_history_instructions: str = ""
    creator_notes: str = ""
    alternate_greetings: str = ""


class CharacterCreate(CharacterBase):
    lorebook_entries: list[LorebookEntryIn] = []


class CharacterUpdate(CharacterBase):
    lorebook_entries: list[LorebookEntryIn] = []


class CharacterOut(CharacterBase):
    id: int
    owner_id: Optional[int]
    is_default: bool
    created_at: datetime
    updated_at: datetime
    lorebook_entries: list[LorebookEntryOut] = []
    can_edit: bool = False

    model_config = {"from_attributes": True}


class CharacterListItem(BaseModel):
    id: int
    name: str
    avatar_url: str
    description: str
    tags: str
    is_default: bool
    is_public: bool
    owner_id: Optional[int]
    can_edit: bool = False
    is_favorited: bool = False

    model_config = {"from_attributes": True}


# ── Ingredient ────────────────────────────────────────────────────────────────

class IngredientBase(BaseModel):
    name: str
    category: str = "personality"
    content: str
    is_public: bool = False


class IngredientCreate(IngredientBase):
    pass


class IngredientOut(IngredientBase):
    id: int
    owner_id: Optional[int]
    is_system: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Recipe ────────────────────────────────────────────────────────────────────

class RecipeItemIn(BaseModel):
    ingredient_id: int
    sort_order: int = 0


class RecipeCreate(BaseModel):
    name: str
    description: str = ""
    items: list[RecipeItemIn] = []


class RecipeItemOut(BaseModel):
    ingredient_id: int
    sort_order: int
    ingredient: IngredientOut

    model_config = {"from_attributes": True}


class RecipeOut(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime
    items: list[RecipeItemOut] = []

    model_config = {"from_attributes": True}


class RecipeApplyRequest(BaseModel):
    name: str = "新角色"
    description: str = ""


class RecipeApplyResult(BaseModel):
    character: CharacterOut


# ── Chat ──────────────────────────────────────────────────────────────────────

class SessionCreate(BaseModel):
    character_id: int
    title: str = "新对话"


class SessionOut(BaseModel):
    id: int
    character_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    character_name: str = ""

    model_config = {"from_attributes": True}


class BootstrapOut(BaseModel):
    user: UserOut
    characters: list[CharacterListItem]
    sessions: list[SessionOut]


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OpsUserOut(BaseModel):
    user_id: int
    username: str
    session_count: int
    message_count: int
    last_active: datetime | None = None


class OpsSessionOut(BaseModel):
    id: int
    user_id: int
    username: str
    character_id: int
    character_name: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ChatSendRequest(BaseModel):
    content: str
    regenerate: bool = False


class LLMStatusOut(BaseModel):
    connected: bool
    model: str
    base_url: str
    available_models: list[str] = []
