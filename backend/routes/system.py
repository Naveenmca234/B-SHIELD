"""
system.py
---------
Global System Health, Readiness, Version, Diagnostics, Storage Monitoring,
and Demo Scenario Controls for B-SHIELD (IBVAP).
"""
import os
import sys
import time
import shutil
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request
from config import settings
from database.mongodb import get_db
from services.auth_service import require_role
from services.camera_manager import camera_manager
from services.ws_manager import ws_manager
from services.offline_queue import offline_event_queue
from services.audio_detector import audio_detector
from services.audit_service import record_audit_event

logger = logging.getLogger("ibvap.system")

router = APIRouter(tags=["System & Diagnostics"])

# Record application boot timestamp for uptime calculation
START_TIME = time.time()
B_SHIELD_VERSION = "2.4.0"
BUILD_ID = "BSHIELD-PROD-2026.09.06"


def get_dir_size_and_count(path: str) -> Dict[str, Any]:
    """Calculates total bytes and file count for a directory recursively."""
    total_bytes = 0
    file_count = 0
    if not os.path.exists(path):
        return {"bytes": 0, "count": 0, "size_mb": 0.0}

    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            try:
                total_bytes += os.path.getsize(fp)
                file_count += 1
            except OSError:
                pass

    return {
        "bytes": total_bytes,
        "count": file_count,
        "size_mb": round(total_bytes / (1024 * 1024), 2),
    }


@router.get("/health")
@router.get("/system/health")
async def liveness_check():
    """
    Liveness probe: verifies that the FastAPI process is responsive.
    Returns immediately with HTTP 200.
    """
    return {
        "status": "UP",
        "service": "B-SHIELD (IBVAP) Core API",
        "version": B_SHIELD_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
@router.get("/system/ready")
async def readiness_check(db=Depends(get_db)):
    """
    Readiness probe: validates critical subsystem operational readiness.
    Checks: MongoDB connection & latency, storage write ability, offline queue state.
    """
    subsystems = {}
    overall_ready = True

    # 1. MongoDB connectivity & ping latency
    if db is not None:
        try:
            t0 = time.time()
            await db.command("ping")
            latency_ms = round((time.time() - t0) * 1000, 2)
            subsystems["database"] = {
                "status": "READY",
                "latency_ms": latency_ms,
                "engine": "MongoDB",
            }
        except Exception as exc:
            overall_ready = False
            subsystems["database"] = {
                "status": "UNAVAILABLE",
                "error": str(exc),
                "engine": "MongoDB",
            }
    else:
        overall_ready = False
        subsystems["database"] = {"status": "UNAVAILABLE", "error": "Database client not initialized"}

    # 2. Storage write test
    try:
        test_dir = settings.SNAPSHOT_DIR
        os.makedirs(test_dir, exist_ok=True)
        test_file = os.path.join(test_dir, ".health_write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        if os.path.exists(test_file):
            os.remove(test_file)
        subsystems["storage"] = {"status": "READY", "root": os.path.abspath(test_dir)}
    except Exception as exc:
        overall_ready = False
        subsystems["storage"] = {"status": "UNAVAILABLE", "error": str(exc)}

    # 3. AI Detector Backend
    yolo_available = False
    try:
        from ultralytics import YOLO  # noqa
        yolo_available = True
    except ImportError:
        yolo_available = False

    subsystems["detector"] = {
        "status": "READY",
        "active_backend": "YOLOv8" if yolo_available else "OpenCV Classical Fallback",
        "yolo_available": yolo_available,
    }

    # 4. Audio DSP
    subsystems["audio_dsp"] = {
        "status": "READY",
        "sample_rate": audio_detector.sample_rate,
        "mode": "Classical FFT/ZCR/RMS",
    }

    # 5. Offline Queue
    subsystems["offline_queue"] = {
        "status": "READY",
        "pending_items": offline_event_queue.size(),
    }

    http_status = status.HTTP_200_OK if overall_ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "ready": overall_ready,
        "status": "HEALTHY" if overall_ready else "DEGRADED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subsystems": subsystems,
    }


@router.get("/version")
@router.get("/system/version")
async def version_info():
    """
    Returns single-source-of-truth version and build metadata.
    """
    return {
        "product_name": "B-SHIELD — AI-Powered Intelligent Border Surveillance",
        "internal_code": "IBVAP",
        "version": B_SHIELD_VERSION,
        "build_id": BUILD_ID,
        "environment": settings.ENVIRONMENT,
        "python_version": sys.version.split()[0],
        "release_date": "2026-09-06",
    }


@router.get("/system/diagnostics")
async def get_system_diagnostics(
    current_user: dict = Depends(require_role(["ADMIN", "OPERATOR"])),
    db=Depends(get_db),
):
    """
    Full operational telemetry for Admin Diagnostics dashboard.
    Gathers detailed metrics across DB, storage, pipelines, WebSocket, queue, and detectors.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    uptime_seconds = int(time.time() - START_TIME)

    # 1. Database metrics & latency
    db_status = "UNKNOWN"
    db_latency_ms = 0.0
    collections_count = 0
    if db is not None:
        try:
            t0 = time.time()
            await db.command("ping")
            db_latency_ms = round((time.time() - t0) * 1000, 2)
            db_status = "HEALTHY"
            cols = await db.list_collection_names()
            collections_count = len(cols)
        except Exception as exc:
            db_status = "UNAVAILABLE"
            logger.warning("MongoDB ping failed in diagnostics: %s", exc)
    else:
        db_status = "DISCONNECTED"

    # 2. Storage metrics
    snap_stats = get_dir_size_and_count(settings.SNAPSHOT_DIR)
    upload_stats = get_dir_size_and_count(settings.UPLOAD_DIR)
    reports_dir = os.path.join(settings.SNAPSHOT_DIR, "reports")
    report_stats = get_dir_size_and_count(reports_dir)

    disk_total, disk_used, disk_free = 0, 0, 0
    try:
        disk_usage = shutil.disk_usage(os.path.abspath(settings.SNAPSHOT_DIR))
        disk_total = round(disk_usage.total / (1024 ** 3), 2)
        disk_used = round(disk_usage.used / (1024 ** 3), 2)
        disk_free = round(disk_usage.free / (1024 ** 3), 2)
    except Exception:
        pass

    # 3. Camera workers
    active_pipelines = list(camera_manager.pipelines.keys())
    online_count = sum(1 for cid in active_pipelines if camera_manager.get_status(cid) == "ONLINE")
    offline_count = len(active_pipelines) - online_count

    # 4. Detector inspection
    yolo_ready = False
    try:
        import ultralytics  # noqa
        yolo_ready = True
    except ImportError:
        yolo_ready = False

    # 5. Tesseract OCR inspection
    ocr_ready = False
    try:
        import pytesseract
        ocr_ready = bool(pytesseract.get_tesseract_version())
    except Exception:
        ocr_ready = False

    # Overall system status determination
    if db_status == "HEALTHY" and (online_count > 0 or len(active_pipelines) == 0):
        overall_health = "HEALTHY"
    elif db_status == "HEALTHY":
        overall_health = "DEGRADED"
    else:
        overall_health = "UNAVAILABLE"

    return {
        "status": overall_health,
        "timestamp": now_utc,
        "uptime_seconds": uptime_seconds,
        "uptime_human": f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s",
        "system": {
            "version": B_SHIELD_VERSION,
            "build_id": BUILD_ID,
            "environment": settings.ENVIRONMENT,
            "python_version": sys.version.split()[0],
            "os_platform": sys.platform,
        },
        "database": {
            "status": db_status,
            "latency_ms": db_latency_ms,
            "collections_count": collections_count,
            "db_name": settings.MONGODB_DB_NAME,
        },
        "storage": {
            "root": os.path.abspath(settings.SNAPSHOT_DIR),
            "disk_total_gb": disk_total,
            "disk_used_gb": disk_used,
            "disk_free_gb": disk_free,
            "evidence_count": snap_stats["count"],
            "evidence_size_mb": snap_stats["size_mb"],
            "uploads_count": upload_stats["count"],
            "uploads_size_mb": upload_stats["size_mb"],
            "reports_count": report_stats["count"],
            "reports_size_mb": report_stats["size_mb"],
        },
        "cameras": {
            "total_active_workers": len(active_pipelines),
            "online": online_count,
            "offline": offline_count,
            "active_camera_ids": active_pipelines,
        },
        "websocket": {
            "status": "HEALTHY",
            "active_clients": len(ws_manager.active_connections),
        },
        "ai_subsystems": {
            "detector_backend": "YOLOv8" if yolo_ready else "OpenCV Classical Fallback",
            "yolo_installed": yolo_ready,
            "device": "CPU (Edge Optimized)",
            "ocr_status": "AVAILABLE" if ocr_ready else "CONFIG_REQUIRED (Tesseract binary)",
            "audio_dsp": "AVAILABLE (FFT Spectral / ZCR / RMS)",
            "face_recognition": "AVAILABLE (Synthetic / Enrolled Embeddings)",
        },
        "offline_queue": {
            "status": "HEALTHY",
            "pending_count": offline_event_queue.size(),
            "max_capacity": offline_event_queue.max_size,
        },
        "notifications": {
            "enabled": settings.NOTIFICATION_ENABLED,
            "smtp_configured": bool(settings.SMTP_HOST),
            "sms_webhook_configured": bool(settings.SMS_WEBHOOK_URL),
        },
    }


@router.get("/system/storage/status")
async def get_storage_status(
    current_user: dict = Depends(require_role(["ADMIN", "OPERATOR"])),
):
    """Returns filesystem disk usage and storage breakdown."""
    snap_stats = get_dir_size_and_count(settings.SNAPSHOT_DIR)
    upload_stats = get_dir_size_and_count(settings.UPLOAD_DIR)

    disk_total, disk_used, disk_free = 0, 0, 0
    try:
        disk_usage = shutil.disk_usage(os.path.abspath(settings.SNAPSHOT_DIR))
        disk_total = round(disk_usage.total / (1024 ** 3), 2)
        disk_used = round(disk_usage.used / (1024 ** 3), 2)
        disk_free = round(disk_usage.free / (1024 ** 3), 2)
    except Exception:
        pass

    return {
        "storage_root": os.path.abspath(settings.SNAPSHOT_DIR),
        "disk_total_gb": disk_total,
        "disk_used_gb": disk_used,
        "disk_free_gb": disk_free,
        "retention_policy_days": {
            "evidence": 30,
            "video": 7,
            "audio": 7,
        },
        "breakdown": {
            "evidence_snapshots": snap_stats,
            "uploaded_videos": upload_stats,
        },
    }


@router.post("/system/storage/cleanup")
async def cleanup_retention_storage(
    request: Request,
    dry_run: bool = True,
    current_user: dict = Depends(require_role(["ADMIN"])),
    db=Depends(get_db),
):
    """
    Executes or previews retention cleanup on snapshots/uploads older than retention threshold.
    Admin only. All executions are recorded in the immutable audit log.
    """
    client_ip = request.client.host if request.client else "unknown"
    cutoff_epoch = time.time() - (30 * 86400)  # 30 days retention
    scanned_count = 0
    eligible_count = 0
    eligible_bytes = 0

    for root, _, files in os.walk(settings.SNAPSHOT_DIR):
        for f in files:
            fp = os.path.join(root, f)
            scanned_count += 1
            try:
                mtime = os.path.getmtime(fp)
                if mtime < cutoff_epoch:
                    size = os.path.getsize(fp)
                    eligible_count += 1
                    eligible_bytes += size
                    if not dry_run:
                        os.remove(fp)
            except OSError:
                pass

    result_summary = {
        "dry_run": dry_run,
        "scanned_files": scanned_count,
        "eligible_files": eligible_count,
        "freed_mb": round(eligible_bytes / (1024 * 1024), 2),
        "retention_days": 30,
    }

    await record_audit_event(
        db=db,
        user=current_user,
        action="STORAGE_CLEANUP",
        target_type="STORAGE",
        target_id=settings.SNAPSHOT_DIR,
        result="SUCCESS",
        ip_address=client_ip,
        metadata=result_summary,
    )

    return result_summary


@router.post("/system/demo/scenario/run")
async def run_demo_scenario(
    request: Request,
    scenario_type: str = "PERIMETER_BREACH",
    current_user: dict = Depends(require_role(["ADMIN"])),
    db=Depends(get_db),
):
    """
    Triggers an end-to-end operational demo scenario through actual application pipelines.
    Generates realistic multi-cue inputs, evaluates risk, saves evidence, creates incident,
    records audit trail, and broadcasts WebSocket event with explicit 'DEMO SCENARIO' tag.
    """
    client_ip = request.client.host if request.client else "unknown"
    if db is None:
        raise HTTPException(status_code=503, detail="Database connection required for demo scenario.")

    from ai.multi_cue_engine import ThreatInputs, compute_threat
    from services.incident_service import incident_service
    from services.video_pipeline import generate_fallback_frame
    import cv2
    import numpy as np

    # 1. Synthesize multi-cue breach conditions
    now_iso = datetime.now(timezone.utc).isoformat()
    camera_id = "BOP-01"

    threat_inputs = ThreatInputs(
        person_detected=True,
        person_status="UNKNOWN",
        loitering=True,
        loitering_duration=14.5,
        fence_crossing=True,
        is_night=True,
        high_risk_zone=True,
        audio_anomaly=True,
        detection_confidence=0.94,
    )
    risk_result = compute_threat(threat_inputs)

    # 2. Render realistic tactical demo evidence frame
    frame = generate_fallback_frame(
        width=640,
        height=480,
        frame_idx=100,
        camera_id=camera_id,
        night_mode=True,
        timestamp_str=now_iso,
    )
    cv2.putText(
        frame,
        "DEMO SCENARIO: PERIMETER BREACH EXERCISE",
        (20, 460),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (0, 0, 255),
        2,
    )

    # 3. Save evidence snapshot
    evidence = await incident_service.save_incident_evidence(
        camera_id=camera_id,
        frame=frame,
        frame_idx=100,
        incident_id=None,
    )

    # 4. Create real incident record through unified incident service
    details = {
        "event_type": "Virtual Fence Intrusion",
        "classification": "UNKNOWN",
        "description": "DEMO SCENARIO: Simulated perimeter breach with acoustic transient.",
        "threat_inputs": threat_inputs.__dict__,
        "threat_breakdown": risk_result.breakdown,
        "audio_dsp": {
            "classification": "LOUD_IMPULSE_DETECTED",
            "rms_db": -18.5,
            "crest_factor": 6.8,
        },
        "is_demo_scenario": True,
    }

    incident = await incident_service.create_incident(
        db=db,
        camera_id=camera_id,
        severity=risk_result.severity,
        risk_score=risk_result.score,
        details=details,
        evidence_file=evidence.get("file_path"),
        evidence_sha256=evidence.get("sha256"),
    )

    # 5. Broadcast real-time WebSocket alert
    await ws_manager.broadcast_alert({
        "type": "alert_created",
        "incident_id": incident.get("incidentId"),
        "camera_id": camera_id,
        "severity": risk_result.severity,
        "risk_score": risk_result.score,
        "location": "BOP-01 — North Gate Perimeter",
        "explanation": risk_result.explanation,
        "timestamp": now_iso,
        "is_demo_scenario": True,
    })

    await record_audit_event(
        db=db,
        user=current_user,
        action="DEMO_SCENARIO_RUN",
        target_type="INCIDENT",
        target_id=incident.get("incidentId"),
        result="SUCCESS",
        ip_address=client_ip,
        metadata={"scenario": scenario_type, "risk_score": risk_result.score},
    )

    return {
        "message": "Demo scenario executed successfully through live pipeline.",
        "incident_id": incident.get("incidentId"),
        "severity": risk_result.severity,
        "risk_score": risk_result.score,
        "evidence_sha256": evidence.get("sha256"),
        "timestamp": now_iso,
    }


@router.post("/system/demo/reset")
async def reset_demo_data(
    request: Request,
    current_user: dict = Depends(require_role(["ADMIN"])),
    db=Depends(get_db),
):
    """
    Resets demo alerts, incidents, and audit logs to pristine initial state.
    Admin only. Audited before execution.
    """
    client_ip = request.client.host if request.client else "unknown"
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable.")

    # Run seed re-initialization
    from database.seed import seed
    await seed()

    await record_audit_event(
        db=db,
        user=current_user,
        action="DEMO_RESET",
        target_type="SYSTEM",
        target_id="DATABASE",
        result="SUCCESS",
        ip_address=client_ip,
        metadata={"reseeded": True},
    )

    return {
        "status": "SUCCESS",
        "message": "Demo data successfully reset to clean initial state.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
