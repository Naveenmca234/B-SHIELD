import base64
import io
from datetime import datetime

import numpy as np
import cv2
from fastapi import APIRouter, Depends, HTTPException

from schemas.misc import PersonCreate
from services.auth_service import require_admin, require_any
from database.mongodb import get_db
from ai.face_recognition import face_engine

router = APIRouter(prefix="/persons", tags=["persons"])


def _decode_base64_image(data_url: str):
    try:
        if "," in data_url:
            data_url = data_url.split(",", 1)[1]
        img_bytes = base64.b64decode(data_url)
        arr = np.frombuffer(img_bytes, dtype=np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None


@router.get("")
async def list_persons(current_user: dict = Depends(require_any)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    persons = []
    async for p in db.persons.find({}):
        p["_id"] = str(p["_id"])
        persons.append(p)
    return persons


@router.post("")
async def create_person(payload: PersonCreate, current_user: dict = Depends(require_admin)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    existing = await db.persons.find_one({"employeeId": payload.employeeId})
    if existing:
        raise HTTPException(status_code=400, detail="Employee ID already registered")

    photo_url = None
    if payload.photoBase64:
        image = _decode_base64_image(payload.photoBase64)
        if image is None:
            raise HTTPException(status_code=400, detail="Invalid image data")
        registered = face_engine.register_face(payload.employeeId, image)
        if not registered:
            raise HTTPException(
                status_code=400,
                detail="No face could be detected in the provided photo. Please upload a clear, front-facing consented photo.",
            )
        photo_url = payload.photoBase64  # stored inline for demo purposes

    doc = {
        "employeeId": payload.employeeId,
        "name": payload.name,
        "photoUrl": photo_url,
        "status": "AUTHORIZED",
        "createdAt": datetime.utcnow().isoformat(),
    }
    await db.persons.insert_one(doc)
    return {"message": "Authorized person registered", "employeeId": payload.employeeId}


@router.delete("/{employee_id}")
async def delete_person(employee_id: str, current_user: dict = Depends(require_admin)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    result = await db.persons.delete_one({"employeeId": employee_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Person not found")
    face_engine.remove_face(employee_id)
    return {"message": "Person removed"}


@router.get("/detections/recent")
async def recent_detections(current_user: dict = Depends(require_any)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    authorized = []
    unknown = []
    async for e in db.events.find({"personStatus": "AUTHORIZED"}).sort("timestamp", -1).limit(20):
        e["_id"] = str(e["_id"])
        authorized.append(e)
    async for e in db.events.find({"personStatus": "UNKNOWN"}).sort("timestamp", -1).limit(20):
        e["_id"] = str(e["_id"])
        unknown.append(e)
    return {"authorized": authorized, "unknown": unknown}
