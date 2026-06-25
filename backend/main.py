from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.database import Base, SessionLocal, engine, migrate_schema
from app.routers import admin, auth, bootstrap, characters, chat, ingredients, internal_ops
from app.seed import seed_database
from app.services.avatar_images import ensure_all_default_thumbs
from config import ROOT_DIR, settings

FRONTEND_DIR = ROOT_DIR / "frontend"
INTERNAL_OPS_PAGE = FRONTEND_DIR / "internal" / "ops.html"


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/") or path.startswith("/uploads/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        elif path.endswith(".html") or path == "/":
            response.headers["Cache-Control"] = "no-cache"
        return response


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    ensure_all_default_thumbs()
    yield


app = FastAPI(title="shanaTavern", description="本地 AI 角色扮演酒馆", lifespan=lifespan)

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(CacheControlMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(bootstrap.router)
app.include_router(characters.router)
app.include_router(chat.router)
app.include_router(ingredients.ing_router)
app.include_router(ingredients.recipe_router)
app.include_router(admin.router)
app.include_router(internal_ops.router)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "llm_model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
    }


@app.get("/api/llm-info")
async def llm_info():
    from app.services.llm import check_connection

    connected, models = await check_connection()
    return {
        "model": settings.llm_model,
        "base_url": settings.llm_base_url,
        "connected": connected,
        "available_models": models,
    }


def _page(name: str):
    path = FRONTEND_DIR / name
    if path.exists():
        return FileResponse(path)
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/")
def index():
    return _page("index.html")


@app.get("/__st/ops")
def internal_ops_page():
    """Hidden ops page — not linked from UI; admin login required in-page."""
    if not INTERNAL_OPS_PAGE.exists():
        return FileResponse(FRONTEND_DIR / "index.html")
    return FileResponse(INTERNAL_OPS_PAGE, headers={"Cache-Control": "no-store"})


@app.get("/__tm/ops")
def internal_ops_page_legacy():
    """Legacy path from TavernMixer era."""
    return RedirectResponse(url="/__st/ops", status_code=307)


@app.get("/{page_name}.html")
def html_pages(page_name: str):
    if page_name.startswith("_") or page_name.startswith("internal"):
        raise HTTPException(status_code=404, detail="Not Found")
    return _page(f"{page_name}.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
