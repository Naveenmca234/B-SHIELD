"""
Seeds MongoDB with demo data:
- Users (admin / operator / viewer) - DEMO / DEVELOPMENT ONLY
- Demo cameras (webcam + sample video + rtsp placeholder)
- Demo authorized personnel
- Default threat scoring settings
- Demo incident record with genuine on-disk snapshot and real SHA-256 hash

Run with: python -m database.seed
"""
import asyncio
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ServerSelectionTimeoutError

from config import settings
from services.auth_service import hash_password
from services.evidence_service import evidence_service
import numpy as np
import cv2


async def seed_db(db):
    """Populates users, cameras, demo incident, and settings into any async Mongo database."""
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
            "mapX": 25.0,
            "mapY": 65.0,
            "mapZone": "Sector Alpha",
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
            "mapX": 68.0,
            "mapY": 35.0,
            "mapZone": "Sector Bravo",
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
            "mapX": 45.0,
            "mapY": 20.0,
            "mapZone": "Sector Charlie",
            "status": "OFFLINE",
        },
        {
            "cameraId": "BOP-04",
            "name": "South Outpost Thermal",
            "location": "Border Outpost 4 - South Sector",
            "sourceType": "VIDEO_FILE",
            "rtspUrl": None,
            "videoFile": None,
            "riskLevel": "LOW",
            "nightStart": "18:30",
            "nightEnd": "06:00",
            "enabled": True,
            "fence": [],
            "mapX": 80.0,
            "mapY": 75.0,
            "mapZone": "Sector Delta",
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
            await db.cameras.update_one(
                {"cameraId": cam["cameraId"]},
                {"$set": {"mapX": cam["mapX"], "mapY": cam["mapY"], "mapZone": cam["mapZone"]}}
            )
            print(f"Camera exists, updated map coordinates: {cam['cameraId']}")

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
            "weightUnknownPerson": 30,
            "weightNightMovement": 15,
            "weightFenceCrossing": 30,
            "weightVehicleNearby": 10,
            "weightHighRiskZone": 15,
            "alertCooldownSeconds": settings.ALERT_COOLDOWN_SECONDS,
            "apiUrl": "http://localhost:8000",
            "websocketUrl": "ws://localhost:8000/ws",
            "uploadDir": settings.UPLOAD_DIR,
            "detectionConfidenceThreshold": settings.DETECTION_CONFIDENCE_THRESHOLD,
        })
        print("Created default system settings")
    else:
        print("Settings already exist")

    # ---------------- DEMO INCIDENTS & EVIDENCE (MULTI-HOUR & MULTI-CAMERA) ----------------
    demo_incidents_data = [
        {
            "id": "INC-DEMO-001",
            "cam": "BOP-02",
            "name": "Perimeter Sample Feed",
            "loc": "Border Outpost 2 - East Perimeter",
            "type": "INTRUSION_DETECTED",
            "sev": "CRITICAL",
            "score": 85,
            "status": "RESOLVED",
            "time_iso": "2026-09-06T02:15:30Z",
            "person": "UNKNOWN",
            "resp": 28.5,
            "res": 84.0,
            "feedback": {"classification": "GENUINE", "reason": None, "notes": "Confirmed unknown footprint near fence.", "operator": "operator"},
        },
        {
            "id": "INC-DEMO-002",
            "cam": "BOP-01",
            "name": "Main Gate Webcam",
            "loc": "Border Outpost 1 - Main Gate",
            "type": "LOITERING",
            "sev": "HIGH",
            "score": 72,
            "status": "RESOLVED",
            "time_iso": "2026-09-06T08:40:15Z",
            "person": "UNKNOWN",
            "resp": 42.0,
            "res": 110.0,
            "feedback": {"classification": "FALSE_ALARM", "reason": "animal", "notes": "Stray dog triggered motion dwell detector.", "operator": "operator"},
        },
        {
            "id": "INC-DEMO-003",
            "cam": "BOP-03",
            "name": "Night Watch Camera",
            "loc": "Border Outpost 3 - North Fence",
            "type": "NIGHT_MOVEMENT",
            "sev": "MEDIUM",
            "score": 55,
            "status": "ACKNOWLEDGED",
            "time_iso": "2026-09-06T14:20:00Z",
            "person": "UNKNOWN",
            "resp": 35.0,
            "res": None,
            "feedback": None,
        },
        {
            "id": "INC-DEMO-004",
            "cam": "BOP-04",
            "name": "South Outpost Thermal",
            "loc": "Border Outpost 4 - South Sector",
            "type": "VIRTUAL_FENCE_APPROACH",
            "sev": "LOW",
            "score": 25,
            "status": "RESOLVED",
            "time_iso": "2026-09-06T19:10:45Z",
            "person": "AUTHORIZED",
            "resp": 55.0,
            "res": 140.0,
            "feedback": {"classification": "FALSE_ALARM", "reason": "vegetation", "notes": "High wind blew tree branch near line.", "operator": "operator"},
        },
        {
            "id": "INC-DEMO-005",
            "cam": "BOP-02",
            "name": "Perimeter Sample Feed",
            "loc": "Border Outpost 2 - East Perimeter",
            "type": "INTRUSION_DETECTED",
            "sev": "CRITICAL",
            "score": 90,
            "status": "ALERTED",
            "time_iso": "2026-09-06T22:50:10Z",
            "person": "UNKNOWN",
            "resp": None,
            "res": None,
            "feedback": None,
        },
    ]

    for item in demo_incidents_data:
        inc_id = item["id"]
        existing = await db.incidents.find_one({"incidentId": inc_id})
        if not existing:
            demo_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(demo_frame, f"B-SHIELD EVIDENCE RECORD: {inc_id}", (30, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(demo_frame, f"CAM: {item['cam']} | TIME: {item['time_iso']}", (30, 280),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            evidence_doc = evidence_service.save_snapshot(demo_frame, inc_id, item["cam"])

            inc_doc = {
                "incidentId": inc_id,
                "cameraId": item["cam"],
                "cameraName": item["name"],
                "location": item["loc"],
                "eventType": item["type"],
                "severity": item["sev"],
                "riskScore": item["score"],
                "status": item["status"],
                "createdAt": item["time_iso"],
                "updatedAt": item["time_iso"],
                "timestamp": item["time_iso"],
                "trackingId": 100 + int(inc_id[-3:]),
                "personStatus": item["person"],
                "vehicleType": None,
                "plateNumber": None,
                "confidence": 0.91,
                "visibility": "CLEAR",
                "zone": item["loc"],
                "isDemoIncident": True,
                "explanation": f"[DEMO RECORD] Threat engine event at {item['loc']}.",
                "breakdown": [
                    {"label": "Perimeter Threat", "points": item["score"] // 2},
                    {"label": "Zone Activity", "points": item["score"] - (item["score"] // 2)},
                ],
                "evidence": [evidence_doc],
                "history": [
                    {
                        "fromStatus": "DETECTED",
                        "toStatus": item["status"],
                        "changedBy": "system",
                        "role": "system",
                        "timestamp": item["time_iso"],
                        "reason": "Threat engine policy trigger",
                    }
                ],
                "responseTimeSeconds": item["resp"],
                "resolutionTimeSeconds": item["res"],
                "feedback": item["feedback"],
            }
            await db.incidents.insert_one(inc_doc)

            # Insert legacy alert
            legacy_alert = dict(inc_doc)
            legacy_alert["alertType"] = item["type"]
            legacy_alert["snapshotPath"] = evidence_doc.get("relativePath")
            await db.alerts.insert_one(legacy_alert)

            # Seed feedback_log if present
            if item["feedback"] and hasattr(db, "feedback_logs"):
                fb_entry = {
                    "incidentId": inc_id,
                    "classification": item["feedback"]["classification"],
                    "reason": item["feedback"]["reason"],
                    "notes": item["feedback"]["notes"],
                    "operator": item["feedback"]["operator"],
                    "timestamp": item["time_iso"],
                }
                await db.feedback_logs.insert_one(fb_entry)

            print(f"[DEMO INCIDENT CREATED] {inc_id} ({item['sev']}, score: {item['score']})")


async def seed():
    print("=" * 60)
    print("B-SHIELD / IBVAP - Database Seeding (DEMO / DEVELOPMENT MODE)")
    print("=" * 60)
    client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=3000)
    db = client[settings.MONGODB_DB_NAME]

    try:
        await client.admin.command("ping")
    except ServerSelectionTimeoutError:
        print(f"\n[ERROR] Cannot connect to MongoDB at {settings.MONGODB_URI}.")
        print("Please ensure MongoDB is running (e.g., 'net start MongoDB' or start local mongod).")
        print("If using MongoDB Atlas, configure MONGODB_URI in backend/.env.")
        client.close()
        return False

    await seed_db(db)
    print("\nSeed complete.")
    client.close()
    return True


if __name__ == "__main__":
    asyncio.run(seed())


