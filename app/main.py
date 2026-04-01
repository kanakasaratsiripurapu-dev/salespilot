"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.data.data_loader import init_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure DB schema (keep it fast for Render free tier)
    logger.info("Starting SalesPilot API...")
    try:
        init_schema()
    except Exception:
        logger.warning("Could not initialise schema — DB may be unavailable")

    # Model warmup deferred to first request (saves RAM on free tier)
    logger.info("Application startup complete.")
    yield
    # Shutdown
    logger.info("Shutting down SalesPilot API.")


app = FastAPI(title="SalesPilot", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# Serve frontend static files
_static_dir = Path(__file__).resolve().parent.parent / "static"
if _static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

    @app.get("/")
    def serve_frontend():
        return FileResponse(str(_static_dir / "index.html"))
