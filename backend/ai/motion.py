"""
motion.py
---------
Real frame-differencing motion detector using OpenCV background subtraction
(MOG2). Tracks per-camera state so motion intensity/region can be computed
frame to frame, plus a cooldown/debounce mechanism to avoid repeated alerts
from the same continuous movement.
"""
import time
import cv2
import numpy as np


class MotionDetector:
    """One instance should be kept per camera (stateful background model)."""

    def __init__(self, cooldown_seconds: int = 10):
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=300, varThreshold=32, detectShadows=False
        )
        self.cooldown_seconds = cooldown_seconds
        self._last_alert_time = 0.0

    def analyze(self, frame: np.ndarray) -> dict:
        if frame is None or frame.size == 0:
            return {"motionDetected": False, "motionIntensity": 0.0, "region": None}

        fg_mask = self.bg_subtractor.apply(frame)
        fg_mask = cv2.medianBlur(fg_mask, 5)
        _, fg_mask = cv2.threshold(fg_mask, 200, 255, cv2.THRESH_BINARY)

        motion_pixels = int(np.count_nonzero(fg_mask))
        total_pixels = fg_mask.shape[0] * fg_mask.shape[1]
        intensity = round((motion_pixels / total_pixels) * 100.0, 2) if total_pixels else 0.0

        region = None
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            if cv2.contourArea(largest) > 500:
                x, y, w, h = cv2.boundingRect(largest)
                region = {"x": x, "y": y, "w": w, "h": h}

        motion_detected = intensity > 0.5 and region is not None

        return {
            "motionDetected": motion_detected,
            "motionIntensity": intensity,
            "region": region,
        }

    def can_fire_alert(self) -> bool:
        """Cooldown / debounce - prevents repeated alerts from one continuous movement."""
        now = time.time()
        if now - self._last_alert_time >= self.cooldown_seconds:
            self._last_alert_time = now
            return True
        return False
