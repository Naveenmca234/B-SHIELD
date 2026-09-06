"""
camera_manager.py
------------------
Owns the lifecycle of all active VideoPipeline instances. Loads camera
configs + threat weights from MongoDB, starts/stops per-camera pipelines,
and exposes the latest frame for MJPEG streaming to the frontend.
"""
import logging
from typing import Dict, Optional

from services.video_pipeline import VideoPipeline
from ai.multi_cue_engine import ThreatWeights
from database.mongodb import get_db

logger = logging.getLogger("ibvap.camera_manager")


class CameraManager:
    def __init__(self):
        self.pipelines: Dict[str, VideoPipeline] = {}

    async def _load_weights(self) -> ThreatWeights:
        db = get_db()
        if db is None:
            return ThreatWeights()
        s = await db.settings.find_one({"_key": "system_settings"})
        if not s:
            return ThreatWeights()
        return ThreatWeights(
            unknown_person=s.get("weightUnknownPerson", 30),
            night_movement=s.get("weightNightMovement", 15),
            fence_crossing=s.get("weightFenceCrossing", 30),
            vehicle_nearby=s.get("weightVehicleNearby", 10),
            high_risk_zone=s.get("weightHighRiskZone", 15),
        )

    async def start_camera(self, camera: dict):
        cam_id = camera["cameraId"]
        if cam_id in self.pipelines:
            await self.stop_camera(cam_id)
        weights = await self._load_weights()
        pipeline = VideoPipeline(camera, weights)
        self.pipelines[cam_id] = pipeline
        await pipeline.start()
        logger.info("Started pipeline for camera %s", cam_id)

    async def stop_camera(self, cam_id: str):
        pipeline = self.pipelines.pop(cam_id, None)
        if pipeline:
            await pipeline.stop()
            logger.info("Stopped pipeline for camera %s", cam_id)

    async def start_all_enabled(self):
        db = get_db()
        if db is None:
            logger.warning("No database connection - cannot auto-start cameras.")
            return
        cursor = db.cameras.find({"enabled": True})
        async for cam in cursor:
            cam.pop("_id", None)
            try:
                await self.start_camera(cam)
            except Exception as e:
                logger.warning("Could not start camera %s: %s", cam.get("cameraId"), e)

    async def stop_all(self):
        for cam_id in list(self.pipelines.keys()):
            await self.stop_camera(cam_id)

    def get_pipeline(self, cam_id: str) -> Optional[VideoPipeline]:
        return self.pipelines.get(cam_id)

    def get_status(self, cam_id: str) -> str:
        p = self.pipelines.get(cam_id)
        return p.status if p else "OFFLINE"

    def get_stats(self, cam_id: str) -> dict:
        p = self.pipelines.get(cam_id)
        return p.stats if p else {"people": 0, "vehicles": 0, "unknown": 0, "threatLevel": "LOW"}

    def get_health(self, cam_id: str) -> dict:
        from services.health_service import evaluate_camera_health
        p = self.pipelines.get(cam_id)
        if p and getattr(p, "health", None):
            return p.health
        status = self.get_status(cam_id)
        return evaluate_camera_health(status, None, None)


camera_manager = CameraManager()
