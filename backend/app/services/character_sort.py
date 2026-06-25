from __future__ import annotations

from app.models import Character

_CUTE_BOOST = ("软萌", "兽耳", "女仆", "元气", "治愈", "校园", "偶像", "甜点", "傲娇", "俏皮", "慵懒")
_COOL_PENALTY = ("御姐", "冷淡", "严肃", "霸道总裁", "痞气", "佣兵", "剑客")


def cuteness_score(tags: str) -> int:
    parts = {t.strip() for t in (tags or "").split(",") if t.strip()}
    score = 0
    if "可爱" in parts:
        score += 1000
    for i, tag in enumerate(_CUTE_BOOST):
        if tag in parts:
            score += 50 - i
    for tag in _COOL_PENALTY:
        if tag in parts:
            score -= 80
    if "男性" in parts:
        score -= 200
    return score


def sort_characters_by_cuteness(characters: list[Character]) -> list[Character]:
    return sorted(characters, key=lambda c: (-cuteness_score(c.tags), c.id))
