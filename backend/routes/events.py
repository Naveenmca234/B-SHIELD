from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from services.auth_service import require_any
from database.mongodb import get_db

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
async def list_events(
    current_user: dict = Depends(require_any),
    search: Optional[str] = None,
    cameraId: Optional[str] = None,
    eventType: Optional[str] = None,
    severity: Optional[str] = None,
    personStatus: Optional[str] = None,
    vehicleType: Optional[str] = None,
    plateNumber: Optional[str] = None,
    dateFrom: Optional[str] = None,
    dateTo: Optional[str] = None,
    sortBy: str = "timestamp",
    sortOrder: int = -1,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    query = {}
    if cameraId:
        query["cameraId"] = cameraId
    if eventType:
        query["eventType"] = eventType
    if severity:
        query["severity"] = severity
    if personStatus:
        query["personStatus"] = personStatus
    if vehicleType:
        query["vehicleType"] = vehicleType
    if plateNumber:
        query["plateNumber"] = {"$regex": plateNumber, "$options": "i"}
    if dateFrom or dateTo:
        query["timestamp"] = {}
        if dateFrom:
            query["timestamp"]["$gte"] = dateFrom
        if dateTo:
            query["timestamp"]["$lte"] = dateTo
    if search:
        query["$or"] = [
            {"eventType": {"$regex": search, "$options": "i"}},
            {"cameraId": {"$regex": search, "$options": "i"}},
            {"explanation": {"$regex": search, "$options": "i"}},
        ]

    total = await db.events.count_documents(query)
    cursor = db.events.find(query).sort(sortBy, sortOrder).skip((page - 1) * pageSize).limit(pageSize)
    events = []
    async for e in cursor:
        e["_id"] = str(e["_id"])
        events.append(e)

    return {"items": events, "total": total, "page": page, "pageSize": pageSize}


@router.get("/{event_id}")
async def get_event(event_id: str, current_user: dict = Depends(require_any)):
    from bson import ObjectId
    db = get_db()
    try:
        event = await db.events.find_one({"_id": ObjectId(event_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid event ID")
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event["_id"] = str(event["_id"])
    return event
