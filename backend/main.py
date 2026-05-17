"""OpenClaw Mission Control — FastAPI Backend."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from database import get_db, close_db
from services.native_schema import ensure_native_runtime_schema
from services.runtime_registry import runtime_registry
from routers import tasks, agents, events, orchestrator, projects, debates, memories, office, autopilot, skills, security, costs
from routers import gateway as gateway_router
from routers import runtime as runtime_router
from routers import providers, runs, approvals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Path to built frontend (relative to backend dir → ../frontend/dist)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
SERVE_STATIC = os.path.isdir(STATIC_DIR) and os.environ.get("SERVE_STATIC", "1") != "0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Mission Control backend...")
    db = await get_db()
    await ensure_native_runtime_schema(db)
    logger.info("Database and native runtime schema initialized")
    await runtime_registry.start(db)
    logger.info("Runtime registry started")
    yield
    # Shutdown
    await runtime_registry.stop()
    await close_db()
    logger.info("Shutdown complete")


app = FastAPI(
    title="OpenClaw Mission Control",
    version="0.2.0",
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
app.include_router(orchestrator.router)
app.include_router(projects.router)
app.include_router(debates.router)
app.include_router(memories.router)
app.include_router(office.router)
app.include_router(autopilot.router)
app.include_router(skills.router)
app.include_router(security.router)
app.include_router(costs.router)
app.include_router(runtime_router.router)
app.include_router(providers.router)
app.include_router(runs.router)
app.include_router(approvals.router)
app.include_router(gateway_router.router)


@app.get("/api/health")
async def health():
    db = await get_db()
    runtime = await runtime_registry.status(db)
    return {
        "status": "ok",
        "runtime_ready": runtime["ready"],
        "active_runtime": runtime["active_runtime"],
        # Compatibility fields for older UI/API callers.
        "gateway_connected": False,
        "gateway_authenticated": False,
        "auth_status": runtime["active_runtime"],
        "version": "0.2.0",
    }


# Serve React frontend in production
if SERVE_STATIC:
    # Mount assets subdirectory
    assets_dir = os.path.join(STATIC_DIR, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    # SPA fallback: serve index.html for any non-API, non-static route
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        # Try to serve a real file first (e.g. favicon, robots.txt)
        file_path = os.path.join(STATIC_DIR, path)
        if path and os.path.isfile(file_path):
            return FileResponse(file_path)
        # Otherwise serve index.html for client-side routing
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
