"""
incidents.py
------------
API router for IBVAP Incidents, Evidence Verification, and Operator Feedback.
"""
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Response, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from services.auth_service import require_any, require_operator, pdf_export_limiter
from services.incident_service import incident_service
from services.evidence_service import evidence_service
from services.pdf_service import pdf_generator
from database.mongodb import get_db
from services.ws_manager import manager

router = APIRouter(prefix="/incidents", tags=["incidents"])


class TransitionRequest(BaseModel):
    status: str
    reason: Optional[str] = None


class FeedbackRequest(BaseModel):
    classification: str  # GENUINE | FALSE_ALARM | UNCERTAIN
    reason: Optional[str] = None
    notes: Optional[str] = None


class BatchTransitionRequest(BaseModel):
    incidentIds: List[str]
    status: str
    reason: Optional[str] = None


@router.get("")
async def list_incidents(
    current_user: dict = Depends(require_any),
    severity: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    cameraId: Optional[str] = None,
    eventType: Optional[str] = None,
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=200),
):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    query = {}
    if severity:
        query["severity"] = severity
    if status_filter:
        query["status"] = status_filter
    if cameraId:
        query["cameraId"] = cameraId
    if eventType:
        query["eventType"] = eventType

    total = await db.incidents.count_documents(query)
    cursor = db.incidents.find(query).sort("createdAt", -1).skip((page - 1) * pageSize).limit(pageSize)

    items = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        items.append(doc)

    return {"items": items, "total": total, "page": page, "pageSize": pageSize}


@router.get("/export/csv")
async def export_incidents_csv(
    current_user: dict = Depends(require_any),
    severity: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    cameraId: Optional[str] = None,
):
    """Exports incidents matching filter criteria as RFC-4180 CSV."""
    import io
    import csv
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    query: dict = {}
    if severity:
        query["severity"] = severity
    if status_filter:
        query["status"] = status_filter
    if cameraId:
        query["cameraId"] = cameraId

    cursor = db.incidents.find(query).sort("createdAt", -1).limit(5000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Incident ID",
        "Created At (UTC)",
        "Severity",
        "Risk Score",
        "Status",
        "Camera ID",
        "Event Type",
        "Acknowledged At",
        "Acknowledged By",
        "Resolved At",
        "Resolved By",
        "Evidence Count",
    ])

    async for inc in cursor:
        dt = inc.get("details")
        ev_type = dt.get("event_type", "Perimeter Alert") if isinstance(dt, dict) else "Perimeter Alert"
        writer.writerow([
            inc.get("incidentId", ""),
            inc.get("createdAt", ""),
            inc.get("severity", ""),
            inc.get("riskScore", 0),
            inc.get("status", ""),
            inc.get("cameraId", ""),
            ev_type,
            inc.get("acknowledgedAt", "") or "—",
            inc.get("acknowledgedBy", "") or "—",
            inc.get("resolvedAt", "") or "—",
            inc.get("resolvedBy", "") or "—",
            len(inc.get("evidence", [])),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="b-shield-incidents.csv"'},
    )


@router.get("/evidence/gallery")
async def get_evidence_gallery(
    current_user: dict = Depends(require_any),
    page: int = Query(1, ge=1),
    pageSize: int = Query(24, ge=1, le=100),
    cameraId: Optional[str] = None,
):
    """Returns paginated evidence gallery across recorded incidents."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    match_stage: dict = {"evidence": {"$exists": True, "$ne": []}}
    if cameraId:
        match_stage["cameraId"] = cameraId

    pipeline = [
        {"$match": match_stage},
        {"$unwind": "$evidence"},
        {"$project": {
            "_id": 0,
            "incidentId": "$incidentId",
            "cameraId": "$cameraId",
            "severity": "$severity",
            "timestamp": "$createdAt",
            "evidence": "$evidence",
        }},
        {"$sort": {"timestamp": -1}},
        {"$skip": (page - 1) * pageSize},
        {"$limit": pageSize},
    ]

    cursor = db.incidents.aggregate(pipeline)
    items = []
    async for doc in cursor:
        ev = doc.get("evidence", {})
        fn = ev.get("fileName") or ""
        items.append({
            "incidentId": doc.get("incidentId"),
            "cameraId": doc.get("cameraId"),
            "severity": doc.get("severity"),
            "timestamp": ev.get("timestamp") or doc.get("timestamp"),
            "evidenceId": ev.get("evidenceId"),
            "sha256": ev.get("sha256"),
            "fileSize": ev.get("fileSize"),
            "fileName": fn,
            "url": f"/api/incidents/evidence/file/{doc.get('incidentId')}/{fn}" if fn else None,
        })

    count_cursor = db.incidents.aggregate([
        {"$match": match_stage},
        {"$unwind": "$evidence"},
        {"$count": "total"},
    ])
    total_doc = await count_cursor.to_list(length=1)
    total = total_doc[0]["total"] if total_doc else 0

    return {"items": items, "total": total, "page": page, "pageSize": pageSize}


@router.get("/{incident_id}")
async def get_incident(incident_id: str, current_user: dict = Depends(require_any)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    incident = await db.incidents.find_one({"incidentId": incident_id})
    if not incident:
        from bson import ObjectId
        try:
            incident = await db.incidents.find_one({"_id": ObjectId(incident_id)})
        except Exception:
            pass

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    incident["_id"] = str(incident["_id"])
    return incident


@router.get("/{incident_id}/report.pdf")
async def get_incident_pdf_report(
    incident_id: str,
    request: Request,
    current_user: dict = Depends(require_any),
):
    """
    Generate an official, tamper-evident PDF dossier for the specified incident.
    Protected with rate limiting.
    """
    client_ip = request.client.host if request.client else "unknown"
    pdf_export_limiter.check(client_ip)

    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    incident = await db.incidents.find_one({"incidentId": incident_id})
    if not incident:
        from bson import ObjectId
        try:
            incident = await db.incidents.find_one({"_id": ObjectId(incident_id)})
        except Exception:
            pass

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    incident["_id"] = str(incident["_id"])
    pdf_buffer = pdf_generator.generate_incident_report(
        incident=incident,
        requested_by=current_user.get("username", "operator"),
        role=current_user.get("role", "operator"),
    )

    filename = f"Incident_{incident.get('incidentId', incident_id)}_Dossier.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )



@router.put("/{incident_id}/transition")
@router.post("/{incident_id}/transition")
async def transition_incident(
    incident_id: str,
    payload: TransitionRequest,
    current_user: dict = Depends(require_operator),
):
    db = get_db()
    updated = await incident_service.transition_incident(
        db=db,
        incident_id=incident_id,
        new_status=payload.status,
        username=current_user["username"],
        user_role=current_user["role"],
        reason=payload.reason,
    )
    await manager.broadcast("incident_updated", {
        "incidentId": updated.get("incidentId"),
        "status": payload.status,
        "updatedBy": current_user["username"],
    })
    return updated


@router.post("/batch-transition")
@router.post("/batch-action")
async def batch_transition(
    payload: BatchTransitionRequest,
    current_user: dict = Depends(require_operator),
):
    """Batch acknowledge or resolve multiple alerts/incidents safely."""
    db = get_db()
    results = []
    # Normalize action to status if action is provided
    target_status = payload.status
    if hasattr(payload, "action") and not target_status:
        target_status = getattr(payload, "action")
    if target_status == "ACKNOWLEDGE":
        target_status = "ACKNOWLEDGED"
    elif target_status == "RESOLVE":
        target_status = "RESOLVED"

    for inc_id in payload.incidentIds:
        try:
            await incident_service.transition_incident(
                db=db,
                incident_id=inc_id,
                new_status=target_status,
                username=current_user["username"],
                user_role=current_user["role"],
                reason=payload.reason or "Batch operator action.",
            )
            results.append({"incidentId": inc_id, "status": "SUCCESS"})
        except Exception as e:
            results.append({"incidentId": inc_id, "status": "FAILED", "error": str(e)})

    await manager.broadcast("incidents_batch_updated", {
        "status": target_status,
        "updatedBy": current_user["username"],
        "count": len(payload.incidentIds),
    })
    return {"results": results, "status": target_status}


@router.post("/{incident_id}/feedback")
async def record_feedback(
    incident_id: str,
    payload: FeedbackRequest,
    current_user: dict = Depends(require_operator),
):
    db = get_db()
    res = await incident_service.record_feedback(
        db=db,
        incident_id=incident_id,
        classification=payload.classification,
        reason=payload.reason,
        notes=payload.notes,
        operator=current_user["username"],
    )
    return res


@router.get("/{incident_id}/evidence/{evidence_id}/verify")
async def verify_evidence_hash(
    incident_id: str,
    evidence_id: str,
    current_user: dict = Depends(require_any),
):
    """
    Computes cryptographic SHA-256 of the actual evidence file on disk
    and verifies it against the immutable stored hash.
    Records an evidence audit log.
    """
    db = get_db()
    incident = await db.incidents.find_one({"incidentId": incident_id})
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    evidence_match = None
    for ev in incident.get("evidence", []):
        if ev.get("evidenceId") == evidence_id or ev.get("sha256") == evidence_id:
            evidence_match = ev
            break

    if not evidence_match:
        raise HTTPException(status_code=404, detail="Evidence item not found in this incident.")

    try:
        result = evidence_service.verify_evidence(
            rel_path=evidence_match["relativePath"],
            stored_hash=evidence_match["sha256"],
        )
    except HTTPException as e:
        if e.status_code == 404:
            result = {
                "status": "FILE_NOT_FOUND",
                "computedHash": None,
                "storedHash": evidence_match["sha256"],
                "verifiedAt": datetime.now(timezone.utc).isoformat(),
                "tampered": True,
                "error": "Evidence file not found on disk.",
            }
        else:
            raise

    # Record access audit log
    await evidence_service.log_access(
        db=db,
        evidence_id=evidence_id,
        incident_id=incident_id,
        user=current_user["username"],
        action="VERIFY_SHA256",
    )

    return {
        "evidenceId": evidence_id,
        "incidentId": incident_id,
        **result,
    }


@router.get("/evidence/file/{incident_id}/{filename}")
async def get_evidence_file(
    incident_id: str,
    filename: str,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    """Authenticated file retrieval for evidence snapshots."""
    from services.auth_service import decode_token
    auth_token = token
    if not auth_token and authorization and authorization.startswith("Bearer "):
        auth_token = authorization.split(" ")[1]

    if not auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication token required.")
    try:
        decode_token(auth_token)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    rel_path = f"{incident_id}/{filename}"
    file_bytes = evidence_service.read_evidence_bytes(rel_path)
    return Response(content=file_bytes, media_type="image/jpeg")



@router.get("/analytics/feedback")
async def get_feedback_analytics(current_user: dict = Depends(require_any)):
    """Computes operator false-alarm vs genuine incident analytics."""
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    total_feedback = await db.feedback_logs.count_documents({})
    if total_feedback == 0:
        return {
            "totalFeedback": 0,
            "genuinePercentage": 0.0,
            "falseAlarmPercentage": 0.0,
            "uncertainPercentage": 0.0,
            "byReason": [],
        }

    genuine = await db.feedback_logs.count_documents({"classification": "GENUINE"})
    false_alarm = await db.feedback_logs.count_documents({"classification": "FALSE_ALARM"})
    uncertain = await db.feedback_logs.count_documents({"classification": "UNCERTAIN"})

    reasons_pipeline = [
        {"$match": {"classification": "FALSE_ALARM"}},
        {"$group": {"_id": "$reason", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    reasons_cursor = db.feedback_logs.aggregate(reasons_pipeline)
    by_reason = [{"reason": doc["_id"] or "unspecified", "count": doc["count"]} async for doc in reasons_cursor]

    return {
        "totalFeedback": total_feedback,
        "genuineCount": genuine,
        "falseAlarmCount": false_alarm,
        "uncertainCount": uncertain,
        "genuinePercentage": round((genuine / total_feedback) * 100, 1),
        "falseAlarmPercentage": round((false_alarm / total_feedback) * 100, 1),
        "uncertainPercentage": round((uncertain / total_feedback) * 100, 1),
        "byReason": by_reason,
    }
