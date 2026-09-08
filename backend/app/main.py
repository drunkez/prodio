import logging
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .database import SessionLocal, init_db
from .routers import auth, download, media, playlists, radiolist, stream
from .services.playout import sync_schedule

log = logging.getLogger("prodio")
logging.basicConfig(level=logging.INFO)

STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"

scheduler = BackgroundScheduler()


def _schedule_tick():
    db = SessionLocal()
    try:
        result = sync_schedule(db)
        if result:
            log.info("Schedule sync: %s", result)
    except Exception:
        log.exception("Schedule sync failed")
    finally:
        db.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ProDio", version="1.0.0")

    @app.on_event("startup")
    def startup():
        init_db()
        if not scheduler.running:
            scheduler.add_job(_schedule_tick, "interval", seconds=30, id="radiolist")
            scheduler.start()
        log.info("ProDio started — station=%s", settings.station_name)

    @app.on_event("shutdown")
    def shutdown():
        if scheduler.running:
            scheduler.shutdown(wait=False)

    app.include_router(auth.router)
    app.include_router(media.router)
    app.include_router(playlists.router)
    app.include_router(radiolist.router)
    app.include_router(stream.router)
    app.include_router(download.router)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(TEMPLATES_DIR / "index.html")

    @app.get("/health")
    def health():
        return {"ok": True, "station": settings.station_name}

    @app.middleware("http")
    async def no_cache_html(request: Request, call_next):
        response = await call_next(request)
        if request.url.path in ("/", "/index.html"):
            response.headers["Cache-Control"] = "no-store"
        return response

    return app


app = create_app()
