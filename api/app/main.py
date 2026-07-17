from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import close_pool, get_pool
from app.routes import router
from app.seed import seed

ROOT = Path(__file__).resolve().parents[2]
WIDGET_DIR = ROOT / "widget" / "dist"
WIDGET_SRC = ROOT / "widget"
ADMIN_DIR = ROOT / "admin"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    # idempotent seed so fresh deploys have data
    try:
        await seed(force=False)
    except Exception as e:
        print(f"seed warning: {e}")
    yield
    await close_pool()


app = FastAPI(
    title="DriveBook API",
    version="1.0.0",
    description="Independent multi-channel booking module — Chișinău",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/book")
@app.get("/book/")
async def hosted_book():
    # Prefer built dist, else source html
    for p in (WIDGET_DIR / "book.html", WIDGET_SRC / "book.html", WIDGET_SRC / "index.html"):
        if p.exists():
            return FileResponse(p)
    return {"error": "widget not built yet — Stage 4"}


if ADMIN_DIR.exists():
    app.mount("/admin", StaticFiles(directory=str(ADMIN_DIR), html=True), name="admin")

# Widget static: serve source during Stage 4 development
if WIDGET_DIR.exists():
    app.mount("/widget", StaticFiles(directory=str(WIDGET_DIR), html=True), name="widget")
elif WIDGET_SRC.exists():
    app.mount("/widget", StaticFiles(directory=str(WIDGET_SRC), html=True), name="widget-src")
