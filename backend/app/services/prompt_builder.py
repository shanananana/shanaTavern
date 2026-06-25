from __future__ import annotations

import json
import re
from typing import Any

from app.models import Character, ChatMessage, LorebookEntry, User
from app.schemas import LorebookEntryIn


def _substitute(text: str, char_name: str, user_name: str) -> str:
    if not text:
        return ""
    return (
        text.replace("{{char}}", char_name)
        .replace("{{user}}", user_name)
        .replace("{{Char}}", char_name)
        .replace("{{User}}", user_name)
    )


def match_lorebook_entries(
    entries: list[LorebookEntry], user_text: str
) -> list[LorebookEntry]:
    text_lower = user_text.lower()
    matched: list[LorebookEntry] = []
    for entry in entries:
        if not entry.enabled:
            continue
        keys = [k.strip().lower() for k in entry.keys.split(",") if k.strip()]
        if any(k in text_lower for k in keys):
            matched.append(entry)
    return sorted(matched, key=lambda e: e.insert_order)


def build_system_prompt(
    character: Character,
    user: User,
    latest_user_message: str = "",
) -> str:
    char_name = character.name
    user_name = user.nickname or user.username
    parts: list[str] = []

    if character.system_prompt:
        parts.append(_substitute(character.system_prompt, char_name, user_name))
    if character.personality:
        parts.append(
            f"[Personality]\n{_substitute(character.personality, char_name, user_name)}"
        )
    if character.scenario:
        parts.append(
            f"[Scenario]\n{_substitute(character.scenario, char_name, user_name)}"
        )

    lore_before: list[str] = []
    lore_after: list[str] = []
    for entry in match_lorebook_entries(character.lorebook_entries, latest_user_message):
        content = _substitute(entry.content, char_name, user_name)
        if entry.position == "after_char":
            lore_after.append(content)
        else:
            lore_before.append(content)

    if lore_before:
        parts.append("[World Info]\n" + "\n".join(lore_before))

    base = "\n\n".join(p for p in parts if p.strip())

    if character.post_history_instructions:
        post = _substitute(character.post_history_instructions, char_name, user_name)
        base = f"{base}\n\n[Post-History Instructions]\n{post}" if base else post

    if lore_after:
        suffix = "\n".join(lore_after)
        base = f"{base}\n\n[Additional World Info]\n{suffix}" if base else suffix

    return base.strip()


def _greeting_texts(character: Character) -> set[str]:
    texts: set[str] = set()
    if character.first_mes.strip():
        texts.add(character.first_mes.strip())
    for part in character.alternate_greetings.split("|||"):
        if part.strip():
            texts.add(part.strip())
    return texts


def _trim_history_for_llm(
    history: list[ChatMessage],
    character: Character,
) -> list[ChatMessage]:
    """Prepare alternation-safe history for the LLM.

    - Opening greetings are UI-only; leading assistant turns break Qwen/Huihui.
    - Drop unanswered trailing user messages (failed prior requests).
    """
    items = [m for m in history if m.content.strip()]
    greetings = _greeting_texts(character)
    if greetings:
        items = [
            m
            for m in items
            if not (m.role == "assistant" and m.content.strip() in greetings)
        ]
    while items and items[0].role == "assistant":
        items.pop(0)
    while items and items[-1].role == "user":
        items.pop()
    return items


def build_chat_messages(
    character: Character,
    user: User,
    history: list[ChatMessage],
    user_message: str,
    *,
    include_examples: bool = True,
) -> list[dict[str, str]]:
    system = build_system_prompt(character, user, user_message)
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})

    if include_examples and character.mes_example.strip():
        example = _substitute(
            character.mes_example, character.name, user.nickname or user.username
        )
        messages.append(
            {
                "role": "system",
                "content": f"[Example Dialogue]\n{example}",
            }
        )

    for msg in _trim_history_for_llm(history, character):
        messages.append({"role": msg.role, "content": msg.content})

    if user_message.strip():
        messages.append({"role": "user", "content": user_message})
    return messages


def merge_ingredients_to_character_fields(
    ingredients: list[tuple[str, str]],
) -> dict[str, str]:
    """按 category 合并配料内容到角色字段。"""
    buckets: dict[str, list[str]] = {
        "system": [],
        "personality": [],
        "scenario": [],
        "style": [],
        "post_history": [],
    }
    for category, content in ingredients:
        key = category if category in buckets else "personality"
        buckets[key].append(content.strip())

    return {
        "personality": "\n".join(buckets["personality"]),
        "scenario": "\n".join(buckets["scenario"]),
        "system_prompt": "\n".join(buckets["system"]),
        "post_history_instructions": "\n".join(
            buckets["post_history"] + buckets["style"]
        ),
    }


def character_to_st_json(character: Character) -> dict[str, Any]:
    alt = [g.strip() for g in character.alternate_greetings.split("|||") if g.strip()]
    return {
        "name": character.name,
        "description": character.description,
        "personality": character.personality,
        "scenario": character.scenario,
        "first_mes": character.first_mes,
        "mes_example": character.mes_example,
        "creator_notes": character.creator_notes,
        "system_prompt": character.system_prompt,
        "post_history_instructions": character.post_history_instructions,
        "tags": [t.strip() for t in character.tags.split(",") if t.strip()],
        "alternate_greetings": alt,
        "character_book": {
            "entries": [
                {
                    "keys": e.keys.split(","),
                    "content": e.content,
                    "insertion_order": e.insert_order,
                    "position": 0 if e.position == "before_char" else 1,
                    "enabled": e.enabled,
                }
                for e in character.lorebook_entries
            ]
        },
    }


def character_from_st_json(data: dict[str, Any]) -> dict[str, Any]:
    book = data.get("character_book") or data.get("data", {}).get("character_book") or {}
    entries_raw = book.get("entries", [])
    lorebook: list[LorebookEntryIn] = []
    for item in entries_raw:
        if isinstance(item, dict):
            keys = item.get("keys", [])
            if isinstance(keys, list):
                keys_str = ",".join(str(k) for k in keys)
            else:
                keys_str = str(keys)
            lorebook.append(
                LorebookEntryIn(
                    keys=keys_str,
                    content=item.get("content", ""),
                    insert_order=item.get("insertion_order", 100),
                    position="before_char"
                    if item.get("position", 0) == 0
                    else "after_char",
                    enabled=item.get("enabled", True),
                )
            )

    alt = data.get("alternate_greetings", [])
    if isinstance(alt, list):
        alt_str = "|||".join(str(a) for a in alt)
    else:
        alt_str = ""

    tags = data.get("tags", [])
    if isinstance(tags, list):
        tags_str = ",".join(str(t) for t in tags)
    else:
        tags_str = str(tags or "")

    return {
        "name": data.get("name", "未命名角色"),
        "description": data.get("description", ""),
        "personality": data.get("personality", ""),
        "scenario": data.get("scenario", ""),
        "first_mes": data.get("first_mes", ""),
        "mes_example": data.get("mes_example", ""),
        "creator_notes": data.get("creator_notes", ""),
        "system_prompt": data.get("system_prompt", ""),
        "post_history_instructions": data.get("post_history_instructions", ""),
        "alternate_greetings": alt_str,
        "tags": tags_str,
        "lorebook_entries": lorebook,
    }


def parse_character_import(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("{"):
        data = json.loads(raw)
        if "data" in data and isinstance(data["data"], dict):
            merged = {**data, **data["data"]}
            return character_from_st_json(merged)
        return character_from_st_json(data)
    raise ValueError("仅支持 JSON 格式角色卡")
