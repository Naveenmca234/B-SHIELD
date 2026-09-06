from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException

from services.auth_service import require_any
from services.camera_manager import camera_manager
from database.mongodb import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_stats(current_user: dict = Depends(require_any)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    cameras = await db.cameras.find({}).to_list(length=1000)
    total_cameras = len(cameras)
    online_cameras = 0
    degraded_cameras = 0
    coverage_gaps = 0

    people_detected = 0
    vehicles_detected = 0
    unknown_persons = 0

    for c in cameras:
        cam_id = c["cameraId"]
        status = camera_manager.get_status(cam_id)
        pipeline = camera_manager.get_pipeline(cam_id)
        health = getattr(pipeline, "health", {}) if pipeline else {}

        if status == "ONLINE":
            online_cameras += 1
            if health.get("healthState") in ("DEGRADED", "CRITICAL"):
                degraded_cameras += 1
        else:
            coverage_gaps += 1

        if health.get("coverageGap"):
            coverage_gaps = max(coverage_gaps, 1)

        stats = camera_manager.get_stats(cam_id)
        people_detected += stats.get("people", 0)
        vehicles_detected += stats.get("vehicles", 0)
        unknown_persons += stats.get("unknown", 0)

    # Incident counts
    active_incidents = await db.incidents.count_documents({"status": {"$in": ["ALERTED", "ACKNOWLEDGED", "RESPONDING"]}})
    if active_incidents == 0:
        active_incidents = await db.alerts.count_documents({"status": {"$in": ["NEW", "ACKNOWLEDGED"]}})

    critical_alerts = await db.incidents.count_documents({"severity": "CRITICAL", "status": {"$in": ["ALERTED", "ACKNOWLEDGED", "RESPONDING"]}})
    if critical_alerts == 0:
        critical_alerts = await db.alerts.count_documents({"severity": "CRITICAL", "status": {"$in": ["NEW", "ACKNOWLEDGED"]}})

    resolved_count = await db.incidents.count_documents({"status": "RESOLVED"})
    if resolved_count == 0:
        resolved_count = await db.alerts.count_documents({"status": "RESOLVED"})

    # Average response time from incidents collection
    avg_pipeline = [
        {"$match": {"responseTimeSeconds": {"$ne": None}}},
        {"$group": {"_id": None, "avgResponse": {"$avg": "$responseTimeSeconds"}}},
    ]
    avg_cursor = db.incidents.aggregate(avg_pipeline)
    avg_docs = [doc async for doc in avg_cursor]
    avg_response_time = round(avg_docs[0]["avgResponse"], 1) if avg_docs else 0.0

    return {
        "totalCameras": total_cameras,
        "onlineCameras": online_cameras,
        "degradedCameras": degraded_cameras,
        "coverageGaps": coverage_gaps,
        "peopleDetected": people_detected,
        "vehiclesDetected": vehicles_detected,
        "unknownPersons": unknown_persons,
        "activeAlerts": active_incidents,
        "criticalAlerts": critical_alerts,
        "incidentsResolved": resolved_count,
        "avgResponseTimeSeconds": avg_response_time,
    }


@router.get("/charts")
async def get_charts(current_user: dict = Depends(require_any)):
    db = get_db()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    # Efficient $facet aggregation for alert severities and person status
    facet_pipeline = [
        {
            "$facet": {
                "severities": [
                    {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
                ],
                "statuses": [
                    {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                ],
            }
        }
    ]
    facet_cursor = db.incidents.aggregate(facet_pipeline)
    facet_res = [doc async for doc in facet_cursor]

    severity_counts = {}
    if facet_res and "severities" in facet_res[0]:
        for s in facet_res[0]["severities"]:
            if s["_id"]:
                severity_counts[s["_id"]] = s["count"]

    severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    alerts_by_severity = [{"severity": sev, "count": severity_counts.get(sev, 0)} for sev in severities]

    # Events over last 7 days
    events_over_time = []
    for i in range(6, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        count = await db.events.count_documents({"timestamp": {"$regex": f"^{day}"}})
        events_over_time.append({"date": day, "count": count})

    # Unknown vs Authorized
    unknown_count = await db.events.count_documents({"personStatus": "UNKNOWN"})
    authorized_count = await db.events.count_documents({"personStatus": "AUTHORIZED"})

    # Vehicle detections by type
    veh_pipeline = [
        {"$group": {"_id": "$vehicleType", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    veh_cursor = db.plates.aggregate(veh_pipeline)
    vehicle_detections = [
        {"type": doc["_id"] or "other", "count": doc["count"]} async for doc in veh_cursor
    ]
    if not vehicle_detections:
        vehicle_detections = [{"type": vt, "count": 0} for vt in ["car", "truck", "motorcycle", "bus"]]

    # Camera activity
    cam_pipeline = [
        {"$group": {"_id": "$cameraId", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10},
    ]
    cam_cursor = db.events.aggregate(cam_pipeline)
    camera_activity = [
        {"camera": doc["_id"] or "Unknown", "count": doc["count"]} async for doc in cam_cursor
    ]

    return {
        "alertsBySeverity": alerts_by_severity,
        "eventsOverTime": events_over_time,
        "personStatus": [
            {"status": "AUTHORIZED", "count": authorized_count},
            {"status": "UNKNOWN", "count": unknown_count},
        ],
        "vehicleDetections": vehicle_detections,
        "cameraActivity": camera_activity,
    }
