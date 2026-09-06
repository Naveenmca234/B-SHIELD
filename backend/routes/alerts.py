from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query

from schemas.misc import AlertStatusUpdate
from services.auth_service import require_operator, require_any
from database.mongodb import get_db
from services.ws_manager import manager

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(
    current_user: dict = Depends(require_any),
    severity: Optional[str] = None,
    alertType: Optional[str] = None,
    cameraId: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    query = {}
    if severity:
        query["severity"] = severity
    if alertType:
        query["alertType"] = alertType
    if cameraId:
        query["cameraId"] = cameraId
    if status:
        query["status"] = status

    total = await db.alerts.count_documents(query)
    cursor = db.alerts.find(query).sort("timestamp", -1).skip((page - 1) * pageSize).limit(pageSize)
    alerts = []
    async for a in cursor:
        a["_id"] = str(a["_id"])
        alerts.append(a)

    return {"items": alerts, "total": total, "page": page, "pageSize": pageSize}


@router.get("/{alert_id}")
async def get_alert(alert_id: str, current_user: dict = Depends(require_any)):
    from bson import ObjectId
    db = get_db()
    try:
        alert = await db.alerts.find_one({"_id": ObjectId(alert_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid alert ID")
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert["_id"] = str(alert["_id"])
    return alert


@router.put("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, current_user: dict = Depends(require_operator)):
    from bson import ObjectId
    db = get_db()
    try:
        oid = ObjectId(alert_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid alert ID")
    result = await db.alerts.update_one(
        {"_id": oid},
        {"$set": {"status": "ACKNOWLEDGED", "acknowledgedBy": current_user["username"],
                  "acknowledgedAt": datetime.utcnow().isoformat()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    await manager.broadcast("alert_updated", {"alertId": alert_id, "status": "ACKNOWLEDGED"})
    return {"message": "Alert acknowledged"}


@router.put("/{alert_id}/resolve")
async def resolve_alert(alert_id: str, current_user: dict = Depends(require_operator)):
    from bson import ObjectId
    db = get_db()
    try:
        oid = ObjectId(alert_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid alert ID")
    result = await db.alerts.update_one(
        {"_id": oid},
        {"$set": {"status": "RESOLVED", "resolvedBy": current_user["username"],
                  "resolvedAt": datetime.utcnow().isoformat()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    await manager.broadcast("alert_updated", {"alertId": alert_id, "status": "RESOLVED"})
    return {"message": "Alert resolved"}
