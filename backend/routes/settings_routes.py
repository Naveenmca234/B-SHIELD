from fastapi import APIRouter, Depends, HTTPException

from schemas.misc import SettingsUpdate
from services.auth_service import require_admin, require_any
from database.mongodb import get_db

router = APIRouter(prefix="/settings", tags=["settings"])

FIELD_MAP = {
    "weightUnknownPerson": "weightUnknownPerson",
    "weightNightMovement": "weightNightMovement",
    "weightFenceCrossing": "weightFenceCrossing",
    "weightVehicleNearby": "weightVehicleNearby",
    "weightHighRiskZone": "weightHighRiskZone",
    "nightStart": "nightStart",
    "nightEnd": "nightEnd",
    "visibilityClearThreshold": "visibilityClearThreshold",
    "visibilityModerateThreshold": "visibilityModerateThreshold",
    "alertCooldownSeconds": "alertCooldownSeconds",
    "apiUrl": "apiUrl",
    "websocketUrl": "websocketUrl",
    "uploadDir": "uploadDir",
    "detectionConfidenceThreshold": "detectionConfidenceThreshold",
}


@router.get("")
async def get_settings(current_user: dict = Depends(require_any)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    s = await db.settings.find_one({"_key": "system_settings"})
    if not s:
        raise HTTPException(status_code=404, detail="Settings not initialized - run the seed script.")
    s["_id"] = str(s["_id"])
    return s


@router.put("")
async def update_settings(payload: SettingsUpdate, current_user: dict = Depends(require_admin)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    update_data = {v: getattr(payload, k) for k, v in FIELD_MAP.items() if getattr(payload, k) is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No settings fields provided")

    await db.settings.update_one({"_key": "system_settings"}, {"$set": update_data}, upsert=True)
    updated = await db.settings.find_one({"_key": "system_settings"})
    updated["_id"] = str(updated["_id"])
    return updated
