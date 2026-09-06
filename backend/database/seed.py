"""
Seeds MongoDB with demo data:
- Users (admin / operator / viewer) - DEMO / DEVELOPMENT ONLY
- Demo cameras (webcam + sample video + rtsp placeholder)
- Demo authorized personnel
- Default threat scoring settings
- Demo incident record with genuine on-disk snapshot and real SHA-256 hash

Run with: python -m database.seed
"""
import os
import asyncio
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError

from config import settings
from services.auth_service import hash_password
from services.evidence_service import evidence_service, calculate_sha256
import numpy as np
import cv2


async def seed():
    print("=" * 60)
    print("B-SHIELD / IBVAP - Database Seeding (DEMO / DEVELOPMENT MODE)")
    print("=" * 60)
    client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=4000)
    db = client[settings.MONGODB_DB_NAME]

    try:
        await client.admin.command("ping")
    except ServerSelectionTimeoutError:
        print(f"\n[ERROR] Cannot connect to MongoDB at {settings.MONGODB_URI}.")
        print("Please ensure MongoDB is running (e.g., 'net start MongoDB' or start local mongod).")
        print("If using MongoDB Atlas, configure MONGODB_URI in backend/.env.")
        client.close()
        return False

    now_iso = datetime.now(timezone.utc).isoformat()

    # ---------------- USERS (DEMO / DEVELOPMENT ONLY) ----------------
    users = [
        {
            "username": "admin",
            "password": "IBVAP@123",
            "role": "admin",
            "fullName": "System Administrator [DEMO]",
            "environment": "DEMO / DEVELOPMENT ONLY",
        },
        {
            "username": "operator",
            "password": "Operator@123",
            "role": "operator",
            "fullName": "Security Officer [DEMO]",
            "environment": "DEMO / DEVELOPMENT ONLY",
        },
        {
            "username": "viewer",
            "password": "Viewer@123",
            "role": "viewer",
            "fullName": "Read-Only Viewer [DEMO]",
            "environment": "DEMO / DEVELOPMENT ONLY",
        },
    ]
    for u in users:
        existing = await db.users.find_one({"username": u["username"]})
        if not existing:
            await db.users.insert_one({
                "username": u["username"],
                "passwordHash": hash_password(u["password"]),
                "role": u["role"],
                "fullName": u["fullName"],
                "createdAt": now_iso,
                "isDemoUser": True,
            })
            print(f"[DEMO USER CREATED] {u['username']} (role: {u['role']}) - DEMO CREDENTIALS: {u['password']}")
        else:
            print(f"[USER EXISTS] {u['username']}")

    # ---------------- CAMERAS ----------------
    cameras = [
        {
            "cameraId": "BOP-01",
            "name": "Main Gate Webcam",
            "location": "Border Outpost 1 - Main Gate",
            "sourceType": "WEBCAM",
            "rtspUrl": None,
            "videoFile": None,
            "riskLevel": "MEDIUM",
            "nightStart": "18:30",
            "nightEnd": "06:00",
            "enabled": True,
            "fence": [],
            "status": "OFFLINE",
        },
        {
            "cameraId": "BOP-02",
            "name": "Perimeter Sample Feed",
            "location": "Border Outpost 2 - East Perimeter",
            "sourceType": "VIDEO_FILE",
            "rtspUrl": None,
            "videoFile": "sample_perimeter.mp4",
            "riskLevel": "HIGH",
            "nightStart": "18:30",
            "nightEnd": "06:00",
            "enabled": True,
            "fence": [{"x": 0.2, "y": 0.3}, {"x": 0.8, "y": 0.3}, {"x": 0.8, "y": 0.9}, {"x": 0.2, "y": 0.9}],
            "status": "OFFLINE",
        },
        {
            "cameraId": "BOP-03",
            "name": "Night Watch Camera",
            "location": "Border Outpost 3 - North Fence",
            "sourceType": "RTSP",
            "rtspUrl": "rtsp://demo:demo@192.168.1.50:554/stream1",
            "videoFile": None,
            "riskLevel": "HIGH",
            "nightStart": "18:30",
            "nightEnd": "06:00",
            "enabled": True,
            "fence": [],
            "status": "OFFLINE",
        },
    ]
    for cam in cameras:
        existing = await db.cameras.find_one({"cameraId": cam["cameraId"]})
        if not existing:
            cam["createdAt"] = now_iso
            await db.cameras.insert_one(cam)
            print(f"Created camera: {cam['cameraId']}")
        else:
            print(f"Camera already exists: {cam['cameraId']}")

    # ---------------- PERSONS ----------------
    persons = [
        {"employeeId": "EMP001", "name": "Person A (Demo)", "photoUrl": None, "status": "AUTHORIZED"},
        {"employeeId": "EMP002", "name": "Person B (Demo)", "photoUrl": None, "status": "AUTHORIZED"},
    ]
    for p in persons:
        existing = await db.persons.find_one({"employeeId": p["employeeId"]})
        if not existing:
            p["createdAt"] = now_iso
            await db.persons.insert_one(p)
            print(f"Created person: {p['employeeId']}")
        else:
            print(f"Person already exists: {p['employeeId']}")

    # ---------------- SETTINGS ----------------
    existing_settings = await db.settings.find_one({"_key": "system_settings"})
    if not existing_settings:
        await db.settings.insert_one({
            "_key": "system_settings",
            "weightUnknownPerson": settings.WEIGHT_UNKNOWN_PERSON,
            "weightNightMovement": settings.WEIGHT_NIGHT_MOVEMENT,
            "weightFenceCrossing": settings.WEIGHT_FENCE_CROSSING,
            "weightVehicleNearby": settings.WEIGHT_VEHICLE_NEARBY,
            "weightHighRiskZone": settings.WEIGHT_HIGH_RISK_ZONE,
            "nightStart": settings.NIGHT_START,
            "nightEnd": settings.NIGHT_END,
            "visibilityClearThreshold": settings.VISIBILITY_CLEAR_THRESHOLD,
            "visibilityModerateThreshold": settings.VISIBILITY_MODERATE_THRESHOLD,
            "alertCooldownSeconds": settings.ALERT_COOLDOWN_SECONDS,
            "apiUrl": "http://localhost:8000",
            "websocketUrl": "ws://localhost:8000/ws",
            "uploadDir": settings.UPLOAD_DIR,
            "detectionConfidenceThreshold": settings.DETECTION_CONFIDENCE_THRESHOLD,
        })
        print("Created default system settings")
    else:
        print("Settings already exist")

    # ---------------- DEMO INCIDENTS & EVIDENCE (PHASE 27) ----------------
    demo_inc_id = "INC-DEMO-001"
    existing_inc = await db.incidents.find_one({"incidentId": demo_inc_id})
    if not existing_inc:
        demo_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        cv2.putText(demo_frame, "B-SHIELD DEMO SURVEILLANCE SNAPSHOT", (30, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(demo_frame, f"INCIDENT: {demo_inc_id} | CAMERA: BOP-02", (30, 280),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        evidence_doc = evidence_service.save_snapshot(demo_frame, demo_inc_id, "BOP-02")

        incident_doc = {
            "incidentId": demo_inc_id,
            "cameraId": "BOP-02",
            "eventType": "INTRUSION_DETECTED",
            "severity": "CRITICAL",
            "riskScore": 85,
            "status": "ALERTED",
            "createdAt": now_iso,
            "updatedAt": now_iso,
            "trackingId": 101,
            "personStatus": "UNKNOWN",
            "vehicleType": None,
            "plateNumber": None,
            "confidence": 0.92,
            "visibility": "CLEAR",
            "zone": "RESTRICTED EAST PERIMETER",
            "isDemoIncident": True,
            "explanation": "[DEMO RECORD] Unknown person detected crossing configured virtual fence on East Perimeter.",
            "breakdown": [
                {"label": "Unknown Person", "points": 30},
                {"label": "Fence Crossing", "points": 30},
                {"label": "High-Risk Zone", "points": 15},
                {"label": "Predictive Trajectory", "points": 10},
            ],
            "evidence": [evidence_doc],
            "statusHistory": [
                {
                    "from": "DETECTED",
                    "to": "ALERTED",
                    "by": "SYSTEM_PIPELINE",
                    "at": now_iso,
                    "reason": "Threat engine triggered alert threshold.",
                }
            ],
            "acknowledgedAt": None,
            "acknowledgedBy": None,
            "resolvedAt": None,
            "resolvedBy": None,
            "responseTimeSeconds": None,
            "resolutionTimeSeconds": None,
            "feedback": None,
        }
        await db.incidents.insert_one(incident_doc)

        legacy_alert = dict(incident_doc)
        legacy_alert["alertType"] = "INTRUSION_DETECTED"
        legacy_alert["snapshotPath"] = evidence_doc.get("relativePath")
        await db.alerts.insert_one(legacy_alert)
        print(f"[DEMO INCIDENT CREATED] {demo_inc_id} with verified SHA-256 evidence")

    print("\nSeed complete.")
    client.close()
    return True


if __name__ == "__main__":
    asyncio.run(seed())

