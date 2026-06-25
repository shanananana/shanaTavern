from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image

from app.services.avatar_images import delete_avatar_thumbs, encode_avatar_webp
from config import settings

ALLOWED_TYPES = {"JPEG", "PNG", "GIF", "WEBP"}
MAX_BYTES = settings.max_upload_mb * 1024 * 1024


def _detect_image_kind(data: bytes) -> str | None:
    try:
        with Image.open(BytesIO(data)) as img:
            fmt = (img.format or "").upper()
            return fmt if fmt in ALLOWED_TYPES else None
    except OSError:
        return None


def _upload_root() -> Path:
    root = settings.upload_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


async def save_character_avatar(character_id: int, file: UploadFile) -> str:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="图片不能超过 5MB")

    kind = _detect_image_kind(data)
    if kind is None:
        raise HTTPException(status_code=400, detail="仅支持 JPG / PNG / GIF / WebP")

    folder = _upload_root() / "characters"
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{character_id}_{uuid.uuid4().hex[:12]}.webp"
    path = folder / filename
    path.write_bytes(encode_avatar_webp(data))
    return f"/uploads/characters/{filename}"


def delete_avatar_file(avatar_url: str) -> None:
    if not avatar_url or not avatar_url.startswith("/uploads/"):
        return
    rel = avatar_url.removeprefix("/uploads/")
    path = settings.upload_dir / rel
    if path.exists() and path.is_file():
        path.unlink()
    delete_avatar_thumbs(avatar_url)
