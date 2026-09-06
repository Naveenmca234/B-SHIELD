"""
incident_service.py
-------------------
Unified Incident Lifecycle and Operator Feedback Management for IBVAP.
Enforces valid state machine transitions:
DETECTED -> ALERTED -> ACKNOWLEDGED -> RESPONDING -> RESOLVED
Calculates real response and resolution metrics and logs feedback.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status

logger = logging.getLogger("ibvap.incidents")

VALID_STATUSES = {
    "DETECTED", "ALERTED", "ACKNOWLEDGED", "RESPONDING", "RESOLVED", "FALSE_ALARM", "UNCERTAIN"
}

ALLOWED_TRANSITIONS = {
    "DETECTED": {"ALERTED", "ACKNOWLEDGED", "FALSE_ALARM"},
    "ALERTED": {"ACKNOWLEDGED", "RESPONDING", "RESOLVED", "FALSE_ALARM"},
    "ACKNOWLEDGED": {"RESPONDING", "RESOLVED", "FALSE_ALARM"},
    "RESPONDING": {"RESOLVED", "FALSE_ALARM", "ACKNOWLEDGED"},
    "RESOLVED": {"REOPENED"},  # Requires admin privilege
    "FALSE_ALARM": {"REOPENED"},
    "UNCERTAIN": {"RESOLVED", "FALSE_ALARM"},
    "REOPENED": {"ACKNOWLEDGED", "RESPONDING"},
}

FALSE_ALARM_REASONS = {
    "animal", "vegetation", "weather", "shadow", "vehicle", "lighting", "tracking_error", "other"
}


def generate_incident_id() -> str:
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:6].upper()
    return f"INC-{today_str}-{short_uuid}"


def calculate_duration_seconds(start_iso: Optional[str], end_iso: Optional[str]) -> Optional[int]:
    """Calculates elapsed seconds between two ISO 8601 timestamps."""
    if not start_iso or not end_iso:
        return None
    try:
        t1 = datetime.fromisoformat(start_iso)
        t2 = datetime.fromisoformat(end_iso)
        diff = (t2 - t1).total_seconds()
        return max(0, int(diff))
    except Exception:
        return None


class IncidentService:
    async def create_incident(
        self,
        db,
        camera_id: str,
        threat: Dict[str, Any],
        evidence_doc: Optional[Dict[str, Any]] = None,
        track_id: Optional[int] = None,
        person_status: Optional[str] = None,
        vehicle_type: Optional[str] = None,
        plate_number: Optional[str] = None,
        confidence: Optional[float] = None,
        visibility: Optional[str] = None,
        zone: Optional[str] = None,
        trajectory: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Creates a new unified incident document."""
        incident_id = generate_incident_id()
        now_iso = datetime.now(timezone.utc).isoformat()

        evidence_list = []
        if evidence_doc:
            evidence_list.append(evidence_doc)

        incident_doc = {
            "incidentId": incident_id,
            "cameraId": camera_id,
            "eventType": threat["eventType"],
            "severity": threat["severity"],
            "riskScore": threat["riskScore"],
            "status": "ALERTED",
            "createdAt": now_iso,
            "updatedAt": now_iso,
            "trackingId": track_id,
            "personStatus": person_status,
            "vehicleType": vehicle_type,
            "plateNumber": plate_number,
            "confidence": confidence,
            "visibility": visibility,
            "zone": zone,
            "trajectory": trajectory,
            "explanation": threat["explanation"],
            "breakdown": threat["breakdown"],
            "evidence": evidence_list,
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

        if db is not None:
            try:
                await db.incidents.insert_one(incident_doc)
                # Also keep legacy collections synchronized for backward compatibility
                legacy_alert = dict(incident_doc)
                legacy_alert["_id"] = incident_doc.get("_id")
                legacy_alert["alertType"] = threat["eventType"]
                if evidence_doc and "relativePath" in evidence_doc:
                    legacy_alert["snapshotPath"] = evidence_doc["relativePath"]
                await db.alerts.insert_one(legacy_alert)
            except Exception as e:
                logger.warning("MongoDB write failed mid-run, enqueuing to offline queue: %s", e)
                try:
                    from services.offline_queue import offline_queue
                    await offline_queue.enqueue_event(incident_doc)
                except Exception as qe:
                    logger.error("Failed to enqueue event to offline queue: %s", qe)
        else:
            try:
                from services.offline_queue import offline_queue
                await offline_queue.enqueue_event(incident_doc)
            except Exception as qe:
                logger.error("Failed to enqueue event to offline queue: %s", qe)

        return incident_doc

    async def transition_incident(
        self,
        db,
        incident_id: str,
        new_status: str,
        username: str,
        user_role: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Performs a validated state transition."""
        if db is None:
            raise HTTPException(status_code=503, detail="Database unavailable.")

        if new_status not in VALID_STATUSES and new_status != "REOPENED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{new_status}'. Allowed: {VALID_STATUSES}",
            )

        incident = await db.incidents.find_one({"incidentId": incident_id})
        if not incident:
            # Fallback search by legacy Mongo ObjectId string if needed
            from bson import ObjectId
            try:
                incident = await db.incidents.find_one({"_id": ObjectId(incident_id)})
            except Exception:
                pass

        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found.")

        current_status = incident.get("status", "ALERTED")

        # Check permitted state transitions
        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            # Allow admin override for re-opening
            if new_status == "REOPENED" and user_role != "admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only an administrator can reopen a resolved or closed incident.",
                )
            elif new_status != "REOPENED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid transition from '{current_status}' to '{new_status}'.",
                )

        now_iso = datetime.now(timezone.utc).isoformat()
        update_fields: Dict[str, Any] = {
            "status": new_status,
            "updatedAt": now_iso,
        }

        history_entry = {
            "from": current_status,
            "to": new_status,
            "by": username,
            "at": now_iso,
            "reason": reason or f"Operator transitioned incident to {new_status}.",
        }

        # Track response metrics
        if new_status == "ACKNOWLEDGED" and not incident.get("acknowledgedAt"):
            update_fields["acknowledgedAt"] = now_iso
            update_fields["acknowledgedBy"] = username
            resp_time = calculate_duration_seconds(incident.get("createdAt"), now_iso)
            update_fields["responseTimeSeconds"] = resp_time

        if new_status in ("RESOLVED", "FALSE_ALARM") and not incident.get("resolvedAt"):
            update_fields["resolvedAt"] = now_iso
            update_fields["resolvedBy"] = username
            ack_time = incident.get("acknowledgedAt") or incident.get("createdAt")
            res_time = calculate_duration_seconds(ack_time, now_iso)
            update_fields["resolutionTimeSeconds"] = res_time

        await db.incidents.update_one(
            {"incidentId": incident.get("incidentId")},
            {
                "$set": update_fields,
                "$push": {"statusHistory": history_entry},
            },
        )

        # Sync legacy alerts collection
        await db.alerts.update_one(
            {"incidentId": incident.get("incidentId")},
            {"$set": {"status": new_status, "updatedAt": now_iso}},
        )

        updated = await db.incidents.find_one({"incidentId": incident.get("incidentId")})
        if updated and "_id" in updated:
            updated["_id"] = str(updated["_id"])
        return updated

    async def record_feedback(
        self,
        db,
        incident_id: str,
        classification: str,
        reason: Optional[str],
        operator: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Records operator false-alarm or genuine incident feedback."""
        if db is None:
            raise HTTPException(status_code=503, detail="Database unavailable.")

        if classification not in ("GENUINE", "FALSE_ALARM", "UNCERTAIN"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Feedback classification must be GENUINE, FALSE_ALARM, or UNCERTAIN.",
            )

        if classification == "FALSE_ALARM" and reason and reason not in FALSE_ALARM_REASONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid false-alarm reason. Allowed: {FALSE_ALARM_REASONS}",
            )

        feedback_entry = {
            "classification": classification,
            "reason": reason,
            "notes": notes,
            "operator": operator,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        result = await db.incidents.update_one(
            {"incidentId": incident_id},
            {"$set": {"feedback": feedback_entry}},
        )
        if result and getattr(result, "matched_count", 1) == 0:
            raise HTTPException(status_code=404, detail="Incident not found.")

        # Store in feedback analytics log
        if hasattr(db, "feedback_logs"):
            await db.feedback_logs.insert_one({
                "incidentId": incident_id,
                **feedback_entry,
            })

        return {"status": "RECORDED", "message": "Feedback recorded successfully", "feedback": feedback_entry}


incident_service = IncidentService()
