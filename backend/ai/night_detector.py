"""
night_detector.py
-----------------
Luminance-based Day/Night detection for IBVAP.
Evaluates actual frame illumination to determine whether surveillance
conditions are night/low-light, rather than relying exclusively on host system time.
Supports recorded night CCTV clips analyzed during daytime.
"""
from typing import Optional
from datetime import datetime, time as dtime
import cv2
import numpy as np


def _is_clock_night(night_start: str, night_end: str) -> bool:
    try:
        now = datetime.now().time()
        h1, m1 = map(int, night_start.split(":"))
        h2, m2 = map(int, night_end.split(":"))
        start, end = dtime(hour=h1, minute=m1), dtime(hour=h2, minute=m2)
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end
    except Exception:
        return False


def detect_night_condition(
    frame: np.ndarray,
    night_start: str = "18:30",
    night_end: str = "06:00",
    luminance_threshold: float = 35.0,
) -> dict:
    """
    Evaluates whether the frame depicts night/low-light surveillance conditions.
    Primary signal: Mean gray level luminance (0-100).
    Luminance < 35 -> NIGHT
    Luminance > 55 -> DAY
    Ambiguous (35-55) -> Combines with scheduled camera clock.
    """
    if frame is None or frame.size == 0:
        return {"isNight": False, "luminance": 50.0, "reason": "No frame data"}

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_luminance = float(np.mean(gray)) / 255.0 * 100.0
    clock_night = _is_clock_night(night_start, night_end)

    if mean_luminance < luminance_threshold:
        is_night = True
        reason = f"Low scene luminance ({round(mean_luminance, 1)}/100) indicates night/low-light conditions."
    elif mean_luminance > 55.0:
        is_night = False
        reason = f"High scene luminance ({round(mean_luminance, 1)}/100) indicates daylight conditions."
    else:
        # Ambiguous twilight or heavily overcast
        is_night = clock_night
        reason = (
            f"Twilight illumination ({round(mean_luminance, 1)}/100); "
            f"concurred with scheduled night hours: {clock_night}."
        )

    return {
        "isNight": is_night,
        "luminance": round(mean_luminance, 1),
        "reason": reason,
    }
