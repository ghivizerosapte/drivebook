from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.db import close_pool, get_pool
from app.routes import router
from app.seed import seed

ROOT = Path(__file__).resolve().parents[2]
WIDGET_DIR = ROOT / "widget" / "dist"
WIDGET_SRC = ROOT / "widget"
ADMIN_DIR = ROOT / "admin"
LANDING_DIR = ROOT / "landing"


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
    title="PermisPro API",
    version="2.0.0",
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


@app.get("/")
async def root():
    landing_index = LANDING_DIR / "index.html"
    if landing_index.exists():
        return FileResponse(landing_index)
    return RedirectResponse(url="/book", status_code=302)


ROBOTS_TXT = """\
User-agent: GPTBot
Disallow: /

User-agent: ChatGPT-User
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: anthropic-ai
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: Claude-Web
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: PerplexityBot
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: Amazonbot
Disallow: /

User-agent: *
Allow: /
"""


@app.get("/robots.txt")
async def robots_txt():
    # Best-effort: disallows known AI-training/crawler user agents while
    # leaving the site open to regular search engines. A scraper ignoring
    # robots.txt entirely won't be stopped by this — see the `noai` meta
    # tag in landing/*.html for the same signal at the page level.
    return PlainTextResponse(ROBOTS_TXT)


@app.get("/presentation")
async def director_presentation():
    presentation = LANDING_DIR / "presentation.html"
    if presentation.exists():
        return FileResponse(presentation)
    return RedirectResponse(url="/", status_code=302)


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

if LANDING_DIR.exists():
    app.mount("/landing", StaticFiles(directory=str(LANDING_DIR)), name="landing")

# Widget static: serve source during Stage 4 development
if WIDGET_DIR.exists():
    app.mount("/widget", StaticFiles(directory=str(WIDGET_DIR), html=True), name="widget")
elif WIDGET_SRC.exists():
    app.mount("/widget", StaticFiles(directory=str(WIDGET_SRC), html=True), name="widget-src")
