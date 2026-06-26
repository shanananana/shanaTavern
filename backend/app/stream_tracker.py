from __future__ import annotations

import asyncio

_active_streams = 0
_lock = asyncio.Lock()


async def begin_stream() -> None:
    global _active_streams
    async with _lock:
        _active_streams += 1


async def end_stream() -> None:
    global _active_streams
    async with _lock:
        if _active_streams > 0:
            _active_streams -= 1


async def active_stream_count() -> int:
    async with _lock:
        return _active_streams
