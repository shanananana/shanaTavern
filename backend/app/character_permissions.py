from __future__ import annotations

from fastapi import HTTPException

from app.models import Character, User


def can_view(character: Character, user: User) -> bool:
    if character.is_default:
        return True
    if character.owner_id == user.id:
        return True
    if character.is_public:
        return True
    return False


def can_edit(character: Character, user: User) -> bool:
    if character.is_default:
        return False
    return character.owner_id == user.id


def assert_can_edit(character: Character, user: User) -> None:
    if character.is_default:
        raise HTTPException(
            status_code=403,
            detail="默认角色不可编辑，请使用「复制」创建自己的版本",
        )
    if character.owner_id != user.id:
        raise HTTPException(status_code=403, detail="只能编辑自己创建的角色")
