"""OpenClaw Mission Control — FastAPI Backend."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import get_db, close_db
from services.gateway_bridge import gateway
from routers import tasks, agents, events

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Mission Control backend...")
    await get_db()
    logger.info("Database initialized")
    await gateway.start()
    logger.info(f"Gateway bridge started → {settings.gateway_url}")
    yield
    # Shutdown
    await gateway.stop()
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="OpenClaw Mission Control",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(tasks.router)
app.include_router(agents.router)
app.include_router(events.router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "gateway_connected": gateway.connected,
        "version": "0.1.0",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
