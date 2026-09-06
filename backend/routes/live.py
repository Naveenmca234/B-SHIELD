import os
import uuid
import asyncio
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Header, status
from fastapi.responses import StreamingResponse

from services.auth_service import require_any, require_operator, decode_token
from services.camera_manager import camera_manager
from database.mongodb import get_db
from config import settings

router = APIRouter(prefix="/live", tags=["live"])

ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv"}
MAX_VIDEO_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB limit


async def _mjpeg_generator(camera_id: str):
    boundary = b"--frame\r\n"
    try:
        while True:
            pipeline = camera_manager.get_pipeline(camera_id)
            if pipeline is None or pipeline.status != "ONLINE":
                await asyncio.sleep(0.5)
                continue
            frame_bytes = pipeline.get_latest_jpeg()
            if frame_bytes:
                yield boundary + b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            await asyncio.sleep(0.08)
    except (asyncio.CancelledError, GeneratorExit):
        # Client disconnected cleanly
        return


def extract_and_validate_stream_token(token: Optional[str] = None, authorization: Optional[str] = None) -> dict:
    """Extracts, decodes, and validates JWT token for live stream."""
    auth_token = token
    if not auth_token and authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split(" ", 1)[1]

    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required to view live video stream.",
        )

    try:
        payload = decode_token(auth_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired stream authorization token.",
        )

    role = payload.get("role")
    if role not in ("admin", "operator", "viewer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Insufficient privileges to view camera stream.",
        )
    return payload


@router.get("/stream/{camera_id}")
async def stream_camera(
    camera_id: str,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """
    Authenticated MJPEG stream endpoint.
    Accepts JWT token via query parameter (standard for browser <img> tags)
    or Authorization: Bearer header.
    Requires an authenticated user with admin, operator, or viewer privileges.
    """
    payload = extract_and_validate_stream_token(token, authorization)

    # Verify camera exists in database or active pipeline
    pipeline = camera_manager.get_pipeline(camera_id)
    if pipeline is None:
        db = get_db()
        if db is not None:
            cam = await db.cameras.find_one({"cameraId": camera_id})
            if not cam:
                raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
        else:
            raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found or active.")

    return StreamingResponse(
        _mjpeg_generator(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.post("/upload")
async def upload_video(file: UploadFile = File(...), current_user: dict = Depends(require_operator)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_VIDEO_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported video format: {ext}. Allowed: {ALLOWED_VIDEO_EXT}")

    filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(settings.SAMPLE_VIDEO_DIR, filename)

    # Stream file to disk while enforcing MAX_VIDEO_UPLOAD_BYTES
    bytes_read = 0
    try:
        with open(dest_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > MAX_VIDEO_UPLOAD_BYTES:
                    buffer.close()
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Uploaded video exceeds maximum allowed size of 100MB.",
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        if os.path.exists(dest_path):
            os.remove(dest_path)
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded video: {e}")

    return {"message": "Video uploaded successfully", "filename": filename, "sizeBytes": bytes_read}


@router.get("/sources")
async def list_sources(current_user: dict = Depends(require_any)):
    """Lists available demo video sources for the Live Surveillance page."""
    files = []
    if os.path.isdir(settings.SAMPLE_VIDEO_DIR):
        files = [f for f in os.listdir(settings.SAMPLE_VIDEO_DIR) if os.path.splitext(f)[1].lower() in ALLOWED_VIDEO_EXT]
    return {
        "webcam": {"available": True, "sourceType": "WEBCAM"},
        "sampleVideos": files,
        "note": "RTSP sources require a reachable camera URL configured under Camera Management. "
                "If unreachable during demo, the camera will show OFFLINE / DEMO-SIMULATION.",
    }


@router.post("/start/{camera_id}")
async def start_camera_stream(camera_id: str, current_user: dict = Depends(require_operator)):
    from database.mongodb import get_db
    db = get_db()
    cam = await db.cameras.find_one({"cameraId": camera_id})
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    cam.pop("_id", None)
    await camera_manager.start_camera(cam)
    return {"message": "Camera pipeline started"}


@router.post("/stop/{camera_id}")
async def stop_camera_stream(camera_id: str, current_user: dict = Depends(require_operator)):
    await camera_manager.stop_camera(camera_id)
    return {"message": "Camera pipeline stopped"}
