"""
video_pipeline.py
------------------
Per-camera async processing loop implementing the hardened IBVAP pipeline:

CCTV/Webcam -> OpenCV capture -> non-blocking YOLO/HOG detection ->
tracking -> face recognition (person) / ANPR (vehicle) ->
night+motion+visibility+trajectory analysis -> multi-cue threat engine ->
surveillance health evaluation -> WebSocket broadcast ->
tamper-evident evidence storage + incident persistence.

CPU-heavy OpenCV/inference tasks are offloaded via asyncio.to_thread so
the main asyncio event loop, HTTP APIs, and WebSockets remain responsive.
"""
import asyncio
import base64
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import cv2
import numpy as np

from ai.detector import ObjectDetector
from ai.tracker import SimplifiedByteTrack
from ai.motion import MotionDetector
from ai.visibility import analyze_visibility
from ai.intrusion import check_fence_crossing, LoiteringDetector
from ai.prediction import TrajectoryPredictor
from ai.night_detector import detect_night_condition
from ai.face_recognition import face_engine
from ai.anpr import process_vehicle_for_plate
from ai.multi_cue_engine import compute_threat, ThreatInputs, ThreatWeights
from services.health_service import evaluate_camera_health
from services.evidence_service import evidence_service
from services.incident_service import incident_service
from services.offline_queue import offline_queue
from services.ws_manager import manager
from database.mongodb import get_db
from config import settings

logger = logging.getLogger("ibvap.pipeline")

# Shared detector across cameras
_shared_detector = ObjectDetector(confidence_threshold=settings.DETECTION_CONFIDENCE_THRESHOLD)


def encode_thumbnail_base64(frame: np.ndarray, max_dim: int = 320) -> str:
    """Generates a tiny thumbnail data URL for real-time frontend notifications."""
    try:
        h, w = frame.shape[:2]
        scale = min(1.0, max_dim / max(h, w))
        small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale < 1.0 else frame
        ok, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 60])
        if ok:
            return "data:image/jpeg;base64," + base64.b64encode(buf).decode("utf-8")
    except Exception:
        pass
    return ""


class VideoPipeline:
    def __init__(self, camera: dict, weights: ThreatWeights):
        self.camera = camera
        self.weights = weights
        self.cap = None
        self.running = False
        self.status = "OFFLINE"
        self.last_frame = None
        self.last_frame_time = None
        self.fps = 0.0
        self._frame_times: List[float] = []

        self.tracker = SimplifiedByteTrack()
        self.predictor = TrajectoryPredictor()
        self.loitering_detector = LoiteringDetector(dwell_threshold_seconds=8.0)
        self.motion_detector = MotionDetector(cooldown_seconds=settings.ALERT_COOLDOWN_SECONDS)
        self._last_event_cooldown: Dict[str, float] = {}

        self.stats = {"people": 0, "vehicles": 0, "unknown": 0, "threatLevel": "LOW"}
        self.health: Dict[str, Any] = {}
        self.error: Optional[str] = None

    def _open_capture(self):
        source_type = self.camera["sourceType"]
        try:
            if source_type == "WEBCAM":
                cap = cv2.VideoCapture(0)
            elif source_type == "VIDEO_FILE":
                path = f"{settings.SAMPLE_VIDEO_DIR}/{self.camera.get('videoFile') or ''}"
                cap = cv2.VideoCapture(path)
            elif source_type == "RTSP":
                cap = cv2.VideoCapture(self.camera.get("rtspUrl") or "", cv2.CAP_FFMPEG)
            else:
                return None
            if not cap or not cap.isOpened():
                return None
            return cap
        except Exception as e:
            logger.warning("Failed to open capture for %s: %s", self.camera["cameraId"], e)
            return None

    async def start(self):
        self.running = True
        asyncio.create_task(self._run_loop())

    async def stop(self):
        self.running = False
        if self.cap:
            self.cap.release()
        self.status = "OFFLINE"

    async def _run_loop(self):
        cam_id = self.camera["cameraId"]
        self.cap = self._open_capture()

        if self.cap is None:
            self.status = "OFFLINE"
            self.error = "Unable to open camera source (DEMO/SIMULATION mode - check device/RTSP/file availability)"
            self.health = evaluate_camera_health(self.status, None, None, self.error)
            await manager.broadcast("camera_status", {
                "cameraId": cam_id, "status": "OFFLINE", "error": self.error, "health": self.health
            })
            return

        self.status = "ONLINE"
        self.last_frame_time = time.time()
        self.health = evaluate_camera_health(self.status, self.last_frame_time, None)
        await manager.broadcast("camera_status", {
            "cameraId": cam_id, "status": "ONLINE", "health": self.health
        })
        frame_count = 0

        try:
            while self.running:
                # Capture frame synchronously
                ok, frame = self.cap.read()
                now = time.time()

                if not ok or frame is None:
                    # Loop video files cleanly; mark RTSP/webcam offline on loss
                    if self.camera["sourceType"] == "VIDEO_FILE":
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        await asyncio.sleep(0.05)
                        continue
                    else:
                        self.status = "OFFLINE"
                        self.error = "Lost connection to camera source"
                        self.health = evaluate_camera_health(self.status, self.last_frame_time, None, self.error)
                        await manager.broadcast("camera_status", {
                            "cameraId": cam_id, "status": "OFFLINE", "error": self.error, "health": self.health
                        })
                        break

                self.last_frame = frame
                self.last_frame_time = now
                frame_count += 1

                # Calculate smoothed FPS
                self._frame_times.append(now)
                if len(self._frame_times) > 15:
                    self._frame_times.pop(0)
                if len(self._frame_times) > 1:
                    duration = self._frame_times[-1] - self._frame_times[0]
                    self.fps = round((len(self._frame_times) - 1) / max(0.01, duration), 1)

                # Frame skipping: fully analyze every 3rd frame
                if frame_count % 3 != 0:
                    await asyncio.sleep(0.01)
                    continue

                await self._process_frame(frame, now)
                await asyncio.sleep(0.03)

        except Exception as e:
            logger.exception("Pipeline error on camera %s: %s", cam_id, e)
            self.status = "OFFLINE"
            self.error = str(e)
            self.health = evaluate_camera_health(self.status, self.last_frame_time, None, self.error)
            await manager.broadcast("camera_status", {
                "cameraId": cam_id, "status": "OFFLINE", "error": self.error, "health": self.health
            })
        finally:
            if self.cap:
                self.cap.release()

    async def _process_frame(self, frame: np.ndarray, timestamp: float):
        cam_id = self.camera["cameraId"]
        h, w = frame.shape[:2]

        # 1. Non-blocking thread offloading for heavy CPU operations
        detections = await asyncio.to_thread(_shared_detector.detect, frame)
        tracks = await asyncio.to_thread(self.tracker.update, detections)
        motion_result = await asyncio.to_thread(self.motion_detector.analyze, frame)
        visibility_result = await asyncio.to_thread(
            analyze_visibility,
            frame,
            settings.VISIBILITY_CLEAR_THRESHOLD,
            settings.VISIBILITY_MODERATE_THRESHOLD,
        )

        # 2. Luminance-based Day/Night analysis
        night_info = await asyncio.to_thread(
            detect_night_condition,
            frame,
            self.camera.get("nightStart", "18:30"),
            self.camera.get("nightEnd", "06:00"),
        )
        is_night = night_info["isNight"]

        # 3. Surveillance Health & Coverage Gap check
        self.health = evaluate_camera_health(
            status=self.status,
            last_frame_time=self.last_frame_time,
            visibility_data=visibility_result,
            pipeline_error=self.error,
            fps=self.fps,
        )

        fence_polygon = self.camera.get("fence") or []
        people = [t for t in tracks if t["class"] == "person"]
        vehicles = [t for t in tracks if t["class"] in ("car", "truck", "bus", "motorcycle")]
        bicycles = [t for t in tracks if t["class"] == "bicycle"]

        self.stats["people"] = len(people)
        self.stats["vehicles"] = len(vehicles)

        overlay_objects = []
        unknown_count = 0
        highest_event = None

        for person in people:
            identity = await asyncio.to_thread(face_engine.identify, frame, person["bbox"])
            status = identity["status"]
            if status == "UNKNOWN":
                unknown_count += 1

            # 4. Loitering Dwell Time & Fence Crossing
            fence_crossing = check_fence_crossing(person["bbox"], w, h, fence_polygon)
            loitering_info = self.loitering_detector.update(
                track_id=person["trackId"],
                bbox=person["bbox"],
                frame_w=w,
                frame_h=h,
                fence_polygon=fence_polygon,
                timestamp=timestamp,
            )
            is_loitering = loitering_info["is_loitering"]

            # 5. Predictive Trajectory Projection
            traj_prediction = self.predictor.update_and_predict(
                track_id=person["trackId"],
                bbox=person["bbox"],
                frame_w=w,
                frame_h=h,
                fence_polygon=fence_polygon,
                timestamp=timestamp,
            )
            predicted_zone = (
                traj_prediction["status"] in ("APPROACHING_RESTRICTED_ZONE", "PREDICTED_ZONE_ENTRY")
            )

            inputs = ThreatInputs(
                person_detected=True,
                person_status=status,
                detection_confidence=person["confidence"],
                is_night=is_night,
                fence_crossing=fence_crossing,
                restricted_zone_activity=fence_crossing or loitering_info["is_inside"],
                predicted_zone_entry=predicted_zone,
                is_loitering=is_loitering,
                motion_detected=motion_result["motionDetected"],
                vehicle_nearby=len(vehicles) > 0,
                bicycle_nearby=len(bicycles) > 0,
                visibility_status=visibility_result["visibilityStatus"],
                camera_risk_level=self.camera.get("riskLevel", "MEDIUM"),
                movement_pattern="loitering" if is_loitering else None,
            )
            threat = compute_threat(inputs, self.weights)

            overlay_objects.append({
                "trackId": person["trackId"],
                "class": "person",
                "confidence": person["confidence"],
                "bbox": person["bbox"],
                "status": status,
                "visibility": visibility_result["visibilityStatus"],
                "threatScore": threat["riskScore"],
                "severity": threat["severity"],
                "trajectory": traj_prediction,
                "loitering": loitering_info,
            })

            if threat["severity"] in ("HIGH", "CRITICAL") or threat["eventType"] in (
                "INTRUSION_DETECTED", "LOITERING_DETECTED", "UNKNOWN_PERSON", "NIGHT_MOVEMENT", "POSSIBLE_INTRUSION"
            ):
                await self._maybe_log_incident_and_alert(
                    frame, cam_id, threat, track_id=person["trackId"],
                    person_status=status, vehicle_type=None, plate_number=None,
                    confidence=person["confidence"], visibility=visibility_result["visibilityStatus"],
                    zone="RESTRICTED ZONE" if fence_crossing else ("LOITERING ZONE" if is_loitering else None),
                    trajectory=traj_prediction,
                )
                highest_event = threat

        # Clean up lost track IDs in loitering detector
        active_ids = {t["trackId"] for t in tracks}
        self.loitering_detector.cleanup_lost_tracks(active_ids, timestamp)

        for vehicle in vehicles:
            plate_info = await asyncio.to_thread(process_vehicle_for_plate, frame, vehicle["bbox"])
            overlay_objects.append({
                "trackId": vehicle["trackId"],
                "class": vehicle["class"],
                "confidence": vehicle["confidence"],
                "bbox": vehicle["bbox"],
                "plateNumber": plate_info.get("plateNumber"),
                "plateStatus": plate_info.get("status", "PLATE_NOT_LOCATED"),
                "plateReason": plate_info.get("reason"),
                "ocrConfidence": plate_info.get("ocrConfidence", 0.0),
            })
            if plate_info.get("plateNumber"):
                await self._log_plate(frame, cam_id, vehicle, plate_info)


        # Poor-visibility possible-intrusion fallback
        if not people and visibility_result["visibilityStatus"] == "POOR":
            inputs = ThreatInputs(
                person_detected=False,
                is_night=is_night,
                fence_crossing=False,
                restricted_zone_activity=False,
                motion_detected=motion_result["motionDetected"],
                vehicle_nearby=len(vehicles) > 0,
                bicycle_nearby=len(bicycles) > 0,
                visibility_status="POOR",
                camera_risk_level=self.camera.get("riskLevel", "MEDIUM"),
            )
            threat = compute_threat(inputs, self.weights)
            if threat["eventType"] == "POSSIBLE_INTRUSION":
                await self._maybe_log_incident_and_alert(
                    frame, cam_id, threat, track_id=None, person_status=None,
                    vehicle_type=None, plate_number=None, confidence=0.0,
                    visibility="POOR", zone=None, trajectory=None,
                )
                highest_event = threat

        self.stats["unknown"] = unknown_count
        self.stats["threatLevel"] = highest_event["severity"] if highest_event else "LOW"

        # Broadcast real-time detections and camera surveillance health
        await manager.broadcast("detection_update", {
            "cameraId": cam_id,
            "objects": overlay_objects,
            "peopleCount": len(people),
            "vehicleCount": len(vehicles),
            "unknownCount": unknown_count,
            "visibility": visibility_result,
            "motion": motion_result,
            "isNight": is_night,
            "nightDetails": night_info,
            "threatLevel": self.stats["threatLevel"],
            "health": self.health,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    async def _maybe_log_incident_and_alert(self, frame: np.ndarray, cam_id: str, threat: dict, **fields):
        try:
            # Per-intruder cooldown key: prevents duplicate alert floods from one person
            # while permitting distinct simultaneous intruders to generate separate alerts.
            track_id = fields.get("track_id")
            key = f"{cam_id}:{threat['eventType']}:{track_id or 'cam'}"
            now = time.time()
            last = self._last_event_cooldown.get(key, 0)
            if now - last < settings.ALERT_COOLDOWN_SECONDS:
                return
            self._last_event_cooldown[key] = now

            db = get_db()
            temp_incident_id = f"TMP-{uuid.uuid4().hex[:6]}"

            # Save tamper-evident evidence to disk with cryptographic SHA-256
            evidence_doc = await asyncio.to_thread(
                evidence_service.save_snapshot, frame, temp_incident_id, cam_id
            )

            thumbnail = encode_thumbnail_base64(frame, max_dim=280)

            # Create unified incident with state machine & evidence reference
            # (incident_service internally handles DB storage with automatic offline queue fallback)
            incident_doc = await incident_service.create_incident(
                db=db,
                camera_id=cam_id,
                threat=threat,
                evidence_doc=evidence_doc,
                track_id=track_id,
                person_status=fields.get("person_status"),
                vehicle_type=fields.get("vehicle_type"),
                plate_number=fields.get("plate_number"),
                confidence=fields.get("confidence"),
                visibility=fields.get("visibility"),
                zone=fields.get("zone"),
                trajectory=fields.get("trajectory"),
            )

            # Prepare broadcast payload with thumbnail for instantaneous notification
            alert_payload = dict(incident_doc)
            alert_payload["thumbnail"] = thumbnail
            alert_payload["alertType"] = threat["eventType"]

            await manager.broadcast("new_incident", incident_doc)
            await manager.broadcast("new_alert", alert_payload)
        except Exception as e:
            logger.warning("Error in _maybe_log_incident_and_alert for %s: %s", cam_id, e)

    async def _log_plate(self, frame: np.ndarray, cam_id: str, vehicle: dict, plate_info: dict):
        try:
            key = f"{cam_id}:plate:{plate_info['plateNumber']}"
            now = time.time()
            last = self._last_event_cooldown.get(key, 0)
            if now - last < settings.ALERT_COOLDOWN_SECONDS:
                return
            self._last_event_cooldown[key] = now

            db = get_db()
            temp_id = f"PLATE-{uuid.uuid4().hex[:6]}"
            evidence_doc = await asyncio.to_thread(
                evidence_service.save_snapshot, frame, temp_id, cam_id
            )

            doc = {
                "cameraId": cam_id,
                "vehicleType": vehicle["class"],
                "trackingId": vehicle["trackId"],
                "plateNumber": plate_info["plateNumber"],
                "plateStatus": plate_info.get("status", "RECOGNIZED"),
                "ocrConfidence": plate_info["ocrConfidence"],
                "reason": plate_info.get("reason"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "evidence": evidence_doc,
                "thumbnail": encode_thumbnail_base64(frame, max_dim=240),
            }

            if db is not None:
                try:
                    result = await db.plates.insert_one(doc)
                    doc["_id"] = str(result.inserted_id)
                except Exception as e:
                    logger.warning("MongoDB plate insert failed mid-run, enqueuing: %s", e)
                    await offline_queue.enqueue_event(doc)
            else:
                await offline_queue.enqueue_event(doc)

            await manager.broadcast("anpr_detected", doc)
        except Exception as e:
            logger.warning("Error logging plate for %s: %s", cam_id, e)

    def get_latest_jpeg(self):
        if self.last_frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", self.last_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        return buf.tobytes() if ok else None
