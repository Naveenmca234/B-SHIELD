"""
IBVAP Backend - Intelligent Border Video Analytics Platform
Main FastAPI application entrypoint.
"""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings, validate_security_config
from database.mongodb import connect_to_mongo, close_mongo_connection, get_db
from services.camera_manager import camera_manager
from services.person_service import sync_authorized_persons_to_face_engine
from services.offline_queue import offline_queue

from routes import auth, dashboard, cameras, alerts, events, vehicles, persons, fences, settings_routes, live, ws, incidents

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ibvap.main")

app = FastAPI(
    title="B-SHIELD (IBVAP) API",
    description="AI-Powered Intelligent Border Surveillance",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s: %s", request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error. Please try again."})


@app.on_event("startup")
async def on_startup():
    # 1. Verify critical security configuration
    validate_security_config()

    # 2. Establish MongoDB connection (or gracefully degrade if offline)
    await connect_to_mongo()

    # 3. Synchronize authorized personnel from DB into face recognition engine
    db = get_db()
    if db is not None:
        try:
            await sync_authorized_persons_to_face_engine(db)
        except Exception as e:
            logger.warning("Personnel biometric sync skipped or failed: %s", e)

    # 4. Start offline event synchronization background worker
    offline_queue.start_worker(get_db, interval_seconds=5.0)

    # 5. Auto-start enabled camera pipelines
    try:
        await camera_manager.start_all_enabled()
    except Exception as e:
        logger.warning("Camera auto-start skipped: %s", e)


@app.on_event("shutdown")
async def on_shutdown():
    offline_queue.stop_worker()
    await camera_manager.stop_all()
    await close_mongo_connection()


@app.get("/")
async def root():
    return {
        "name": "IBVAP API",
        "description": "Intelligent Border Video Analytics Platform",
        "tagline": "Transforming Existing CCTV into Intelligent Border Surveillance.",
        "status": "running",
    }


@app.get("/health")
async def health():
    from database.mongodb import get_db
    db = get_db()
    return {
        "service": "IBVAP API",
        "api": "ok",
        "database": "connected" if db is not None else "disconnected",
    }


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(cameras.router)
app.include_router(alerts.router)
app.include_router(events.router)
app.include_router(vehicles.router)
app.include_router(persons.router)
app.include_router(fences.router)
app.include_router(settings_routes.router)
app.include_router(live.router)
app.include_router(ws.router)
app.include_router(incidents.router)
