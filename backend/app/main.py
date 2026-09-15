from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from backend.app.api import router
from backend.app.config import get_settings
from backend.app.db import SessionLocal
from backend.app.services.bootstrap import init_db

ROOT = Path(__file__).resolve().parents[2]
PROTOTYPE = ROOT / "prototype"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db: Session = SessionLocal()
    try:
        init_db(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Trust Ladder API",
        description="Safe AI automation for MSP operations — model proposes, platform disposes.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list + ["null"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    if PROTOTYPE.is_dir():
        app.mount("/prototype", StaticFiles(directory=str(PROTOTYPE), html=True), name="prototype")
    return app


app = create_app()
