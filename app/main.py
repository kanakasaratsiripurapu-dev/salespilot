"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import settings
from app.data.data_loader import init_schema, load_csv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SalesPilot API...")
    try:
        init_schema()
        data_dir = Path(settings.DATA_DIR)
        if data_dir.exists() and (data_dir / "accounts.csv").exists():
            logger.info("Loading CSV data into database...")
            counts = load_csv(str(data_dir))
            logger.info("Data loaded: %s", counts)
        else:
            logger.warning("CSV data directory not found at %s — skipping data load", data_dir)
    except Exception as e:
        logger.warning("Startup data load failed: %s", e)

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
