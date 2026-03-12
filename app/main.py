"""FastAPI application entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.data.data_loader import init_schema
from app.ml.predictor import warm_up

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure DB schema and warm up predictor
    logger.info("Starting SalesPilot API...")
    try:
        init_schema()
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
