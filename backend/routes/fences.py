from fastapi import APIRouter, Depends, HTTPException

from schemas.misc import FenceCreate
from services.auth_service import require_admin, require_any
from database.mongodb import get_db
from services.camera_manager import camera_manager

router = APIRouter(prefix="/fences", tags=["fences"])


@router.get("")
async def list_fences(current_user: dict = Depends(require_any)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    cameras = await db.cameras.find({}, {"cameraId": 1, "fence": 1, "name": 1}).to_list(length=1000)
    for c in cameras:
        c["_id"] = str(c["_id"])
    return cameras


@router.post("")
async def save_fence(payload: FenceCreate, current_user: dict = Depends(require_admin)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    cam = await db.cameras.find_one({"cameraId": payload.cameraId})
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    points = [p.model_dump() for p in payload.points]
    await db.cameras.update_one(
        {"cameraId": payload.cameraId},
        {"$set": {"fence": points, "fenceZoneName": payload.zoneName}},
    )

    # Live-update the running pipeline's fence config, if active.
    pipeline = camera_manager.get_pipeline(payload.cameraId)
    if pipeline:
        pipeline.camera["fence"] = points

    return {"message": "Virtual fence saved", "cameraId": payload.cameraId, "pointCount": len(points)}
