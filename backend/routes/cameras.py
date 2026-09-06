from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException

from schemas.camera import CameraCreate, CameraUpdate
from services.auth_service import require_admin, require_any
from services.camera_manager import camera_manager
from database.mongodb import get_db

router = APIRouter(prefix="/cameras", tags=["cameras"])



@router.get("")
async def list_cameras(current_user: dict = Depends(require_any)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    cameras = []
    async for c in db.cameras.find({}):
        c["_id"] = str(c["_id"])
        c["status"] = camera_manager.get_status(c["cameraId"])
        c["liveStats"] = camera_manager.get_stats(c["cameraId"])
        c["health"] = camera_manager.get_health(c["cameraId"])
        cameras.append(c)
    return cameras


@router.get("/{camera_id}")
async def get_camera(camera_id: str, current_user: dict = Depends(require_any)):
    db = get_db()
    cam = await db.cameras.find_one({"cameraId": camera_id})
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    cam["_id"] = str(cam["_id"])
    cam["status"] = camera_manager.get_status(camera_id)
    cam["liveStats"] = camera_manager.get_stats(camera_id)
    cam["health"] = camera_manager.get_health(camera_id)
    return cam


@router.post("")
async def create_camera(payload: CameraCreate, current_user: dict = Depends(require_admin)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    existing = await db.cameras.find_one({"cameraId": payload.cameraId})
    if existing:
        raise HTTPException(status_code=400, detail="Camera ID already exists")

    doc = payload.model_dump()
    doc["fence"] = [p if isinstance(p, dict) else p.model_dump() for p in (payload.fence or [])]
    doc["status"] = "OFFLINE"
    doc["createdAt"] = datetime.now(timezone.utc).isoformat()
    await db.cameras.insert_one(doc)


    if payload.enabled:
        try:
            cam_copy = dict(doc)
            cam_copy.pop("_id", None)
            await camera_manager.start_camera(cam_copy)
        except Exception:
            pass

    return {"message": "Camera created", "cameraId": payload.cameraId}


@router.put("/{camera_id}")
async def update_camera(camera_id: str, payload: CameraUpdate, current_user: dict = Depends(require_admin)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    existing = await db.cameras.find_one({"cameraId": camera_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Camera not found")

    update_data = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if "fence" in update_data:
        update_data["fence"] = [p if isinstance(p, dict) else p for p in update_data["fence"]]

    await db.cameras.update_one({"cameraId": camera_id}, {"$set": update_data})
    updated = await db.cameras.find_one({"cameraId": camera_id})
    updated.pop("_id", None)

    await camera_manager.stop_camera(camera_id)
    if updated.get("enabled", True):
        try:
            await camera_manager.start_camera(updated)
        except Exception:
            pass

    return {"message": "Camera updated"}


@router.delete("/{camera_id}")
async def delete_camera(camera_id: str, current_user: dict = Depends(require_admin)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    await camera_manager.stop_camera(camera_id)
    result = await db.cameras.delete_one({"cameraId": camera_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Camera not found")
    return {"message": "Camera deleted"}
