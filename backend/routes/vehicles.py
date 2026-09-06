from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from services.auth_service import require_any
from database.mongodb import get_db

router = APIRouter(tags=["vehicles"])


@router.get("/vehicles")
async def list_vehicles(
    current_user: dict = Depends(require_any),
    plateNumber: Optional[str] = None,
    cameraId: Optional[str] = None,
    vehicleType: Optional[str] = None,
    dateFrom: Optional[str] = None,
    dateTo: Optional[str] = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    query = {}
    if plateNumber:
        query["plateNumber"] = {"$regex": plateNumber, "$options": "i"}
    if cameraId:
        query["cameraId"] = cameraId
    if vehicleType:
        query["vehicleType"] = vehicleType
    if dateFrom or dateTo:
        query["timestamp"] = {}
        if dateFrom:
            query["timestamp"]["$gte"] = dateFrom
        if dateTo:
            query["timestamp"]["$lte"] = dateTo

    total = await db.plates.count_documents(query)
    cursor = db.plates.find(query).sort("timestamp", -1).skip((page - 1) * pageSize).limit(pageSize)
    plates = []
    async for p in cursor:
        p["_id"] = str(p["_id"])
        plates.append(p)

    return {"items": plates, "total": total, "page": page, "pageSize": pageSize}


@router.get("/plates")
async def list_plates(current_user: dict = Depends(require_any)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    plates = []
    async for p in db.plates.find({}).sort("timestamp", -1).limit(100):
        p["_id"] = str(p["_id"])
        plates.append(p)
    return plates
