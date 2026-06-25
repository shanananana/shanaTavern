from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from config import settings

AVATAR_MAX_PX = 256
WEBP_QUALITY = 82
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def encode_avatar_webp(data: bytes, max_px: int = AVATAR_MAX_PX) -> bytes:
    with Image.open(BytesIO(data)) as img:
        if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")
        img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
        out = BytesIO()
        img.save(out, format="WEBP", quality=WEBP_QUALITY, method=4)
        return out.getvalue()


def write_avatar_thumb(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = encode_avatar_webp(src.read_bytes())
    dst.write_bytes(data)


def _thumb_path_for_rel(rel: str) -> Path | None:
    parts = Path(rel).parts
    if not parts:
        return None
    stem = Path(rel).stem
    if parts[0] == "defaults":
        return settings.upload_dir / "defaults" / "thumbs" / f"{stem}.webp"
    if parts[0] == "characters":
        return settings.upload_dir / "characters" / "thumbs" / f"{stem}.webp"
    return None


def display_avatar_url(stored_url: str) -> str:
    """Return WebP thumbnail URL for UI; generate lazily if missing."""
    if not stored_url or not stored_url.startswith("/uploads/"):
        return stored_url or ""

    rel = stored_url.removeprefix("/uploads/")
    src = settings.upload_dir / rel
    if not src.is_file():
        return stored_url

    if rel.startswith("characters/") and rel.endswith(".webp"):
        return stored_url

    thumb_path = _thumb_path_for_rel(rel)
    if thumb_path is None:
        return stored_url

    try:
        src_mtime = src.stat().st_mtime
    except OSError:
        return stored_url

    if not thumb_path.is_file() or thumb_path.stat().st_mtime < src_mtime:
        write_avatar_thumb(src, thumb_path)

    thumb_rel = thumb_path.relative_to(settings.upload_dir).as_posix()
    return f"/uploads/{thumb_rel}"


def delete_avatar_thumbs(stored_url: str) -> None:
    if not stored_url or not stored_url.startswith("/uploads/"):
        return
    rel = stored_url.removeprefix("/uploads/")
    thumb_path = _thumb_path_for_rel(rel)
    if thumb_path and thumb_path.is_file():
        thumb_path.unlink()


def ensure_all_default_thumbs() -> int:
    defaults_dir = settings.upload_dir / "defaults"
    if not defaults_dir.is_dir():
        return 0
    count = 0
    for src in defaults_dir.iterdir():
        if not src.is_file() or src.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        thumb = defaults_dir / "thumbs" / f"{src.stem}.webp"
        try:
            src_mtime = src.stat().st_mtime
        except OSError:
            continue
        if not thumb.is_file() or thumb.stat().st_mtime < src_mtime:
            write_avatar_thumb(src, thumb)
            count += 1
    return count
