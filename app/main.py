"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.data.data_loader import init_schema, load_csv
from app.db.session import SessionLocal
from app.ml.predictor import warm_up
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure DB schema and warm up predictor
    logger.info("Starting SalesPilot API...")
    try:
        init_schema()
        # Auto-load CSV data if accounts table is empty (first deploy)
        db = SessionLocal()
        try:
            count = db.execute(text("SELECT COUNT(*) FROM accounts")).scalar()
            if count == 0:
                logger.info("Empty database detected — loading CSV seed data...")
                load_csv("data/raw")
                logger.info("Seed data loaded successfully.")
        except Exception as e:
            logger.warning(f"Could not auto-load data: {e}")
        finally:
            db.close()
    except Exception:
        logger.warning("Could not initialise schema — DB may be unavailable")
    warm_up()
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
