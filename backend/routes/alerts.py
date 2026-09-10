from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query

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


@router.get("/export/csv")
async def export_alerts_csv(
    current_user: dict = Depends(require_any),
    severity: Optional[str] = None,
    alertType: Optional[str] = None,
    cameraId: Optional[str] = None,
    status: Optional[str] = None,
):
    """Exports alerts matching current filters as RFC-4180 CSV."""
    import io
    import csv
    from fastapi import Response
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

    cursor = db.alerts.find(query).sort("timestamp", -1).limit(5000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Alert ID",
        "Incident ID",
        "Timestamp (UTC)",
        "Severity",
        "Status",
        "Camera ID",
        "Alert Type",
        "Location",
        "Acknowledged By",
        "Acknowledged At",
    ])

    async for a in cursor:
        writer.writerow([
            str(a.get("_id", "")),
            a.get("incidentId", ""),
            a.get("timestamp", ""),
            a.get("severity", ""),
            a.get("status", ""),
            a.get("cameraId", ""),
            a.get("alertType", ""),
            a.get("location", ""),
            a.get("acknowledgedBy", "") or "—",
            a.get("acknowledgedAt", "") or "—",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="b-shield-alerts.csv"'},
    )


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


from services.incident_service import incident_service

@router.put("/{alert_id}/acknowledge")
@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, current_user: dict = Depends(require_operator)):
    from bson import ObjectId
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    alert = None
    try:
        alert = await db.alerts.find_one({"_id": ObjectId(alert_id)})
    except Exception:
        pass
    if not alert:
        alert = await db.alerts.find_one({"incidentId": alert_id})
    if not alert:
        alert = await db.incidents.find_one({"incidentId": alert_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert/Incident not found")

    target_id = alert.get("incidentId") or alert_id
    try:
        updated = await incident_service.transition_incident(
            db=db,
            incident_id=target_id,
            new_status="ACKNOWLEDGED",
            username=current_user["username"],
            user_role=current_user["role"],
            reason="Operator acknowledged alert",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    now_iso = datetime.utcnow().isoformat()
    # Ensure legacy alerts record is also updated if alertId was an ObjectId
    if "_id" in alert:
        try:
            await db.alerts.update_one(
                {"_id": alert["_id"]},
                {"$set": {"status": "ACKNOWLEDGED", "acknowledgedBy": current_user["username"], "acknowledgedAt": now_iso}}
            )
        except Exception:
            pass

    await manager.broadcast("alert_updated", {"alertId": alert_id, "incidentId": target_id, "status": "ACKNOWLEDGED"})
    await manager.broadcast("incident_updated", {"incidentId": target_id, "status": "ACKNOWLEDGED", "updatedBy": current_user["username"]})
    return {"message": "Alert acknowledged", "incident": updated}


@router.put("/{alert_id}/resolve")
@router.post("/{alert_id}/resolve")
async def resolve_alert(alert_id: str, current_user: dict = Depends(require_operator)):
    from bson import ObjectId
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    alert = None
    try:
        alert = await db.alerts.find_one({"_id": ObjectId(alert_id)})
    except Exception:
        pass
    if not alert:
        alert = await db.alerts.find_one({"incidentId": alert_id})
    if not alert:
        alert = await db.incidents.find_one({"incidentId": alert_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert/Incident not found")

    target_id = alert.get("incidentId") or alert_id
    try:
        updated = await incident_service.transition_incident(
            db=db,
            incident_id=target_id,
            new_status="RESOLVED",
            username=current_user["username"],
            user_role=current_user["role"],
            reason="Operator resolved alert",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    now_iso = datetime.utcnow().isoformat()
    if "_id" in alert:
        try:
            await db.alerts.update_one(
                {"_id": alert["_id"]},
                {"$set": {"status": "RESOLVED", "resolvedBy": current_user["username"], "resolvedAt": now_iso}}
            )
        except Exception:
            pass

    await manager.broadcast("alert_updated", {"alertId": alert_id, "incidentId": target_id, "status": "RESOLVED"})
    await manager.broadcast("incident_updated", {"incidentId": target_id, "status": "RESOLVED", "updatedBy": current_user["username"]})
    return {"message": "Alert resolved", "incident": updated}

