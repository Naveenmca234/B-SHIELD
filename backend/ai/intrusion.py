"""
intrusion.py
------------
Virtual fence / restricted-zone intrusion logic.
Fence is stored as a polygon of normalized points (0.0-1.0 range so it is
resolution independent). Uses a real point-in-polygon test (ray casting)
against the bottom-center point of a tracked object's bounding box (the
object's "feet" position, standard practice in surveillance systems).
"""
from typing import List, Dict, Any, Optional


def point_in_polygon(x: float, y: float, polygon: List[Dict[str, float]]) -> bool:
    """Ray-casting algorithm. polygon: [{x, y}, ...] normalized 0-1 coords."""
    if not polygon or len(polygon) < 3:
        return False

    n = len(polygon)
    inside = False
    px, py = x, y
    x1, y1 = polygon[0]["x"], polygon[0]["y"]
    for i in range(1, n + 1):
        x2, y2 = polygon[i % n]["x"], polygon[i % n]["y"]
        if py > min(y1, y2):
            if py <= max(y1, y2):
                if px <= max(x1, x2):
                    if y1 != y2:
                        xinters = (py - y1) * (x2 - x1) / (y2 - y1) + x1
                    else:
                        xinters = px
                    if x1 == x2 or px <= xinters:
                        inside = not inside
        x1, y1 = x2, y2
    return inside


def check_fence_crossing(bbox: Dict[str, int], frame_w: int, frame_h: int, fence_polygon: List[Dict[str, float]]) -> bool:
    """
    bbox: pixel bbox {x,y,w,h}
    fence_polygon: normalized points [{x,y}] in range 0-1
    Returns True if the object's foot-point falls inside the restricted zone.
    """
    if not fence_polygon or frame_w == 0 or frame_h == 0:
        return False
    foot_x = (bbox["x"] + bbox["w"] / 2.0) / frame_w
    foot_y = (bbox["y"] + bbox["h"]) / frame_h
    return point_in_polygon(foot_x, foot_y, fence_polygon)


class LoiteringDetector:
    """
    Per-track dwell-time loitering detector within virtual fence zones.
    Tracks entry time and continuous presence for each track_id.
    If a tracked person's foot-point remains inside the configured polygon
    longer than `dwell_threshold_seconds`, triggers LOITERING.
    Resets state when track leaves the zone or is cleaned up.
    """
    def __init__(self, dwell_threshold_seconds: float = 8.0):
        self.dwell_threshold = dwell_threshold_seconds
        # track_id -> {"entry_time": float, "last_seen": float, "alerted": bool}
        self._dwell_state: Dict[int, Dict[str, Any]] = {}

    def update(
        self,
        track_id: int,
        bbox: Dict[str, int],
        frame_w: int,
        frame_h: int,
        fence_polygon: List[Dict[str, float]],
        timestamp: float,
    ) -> Dict[str, Any]:
        """
        Updates dwell tracking for a track.
        Returns:
            {
                "is_inside": bool,
                "dwell_seconds": float,
                "is_loitering": bool,
                "just_triggered": bool,  # True only on the first threshold breach
            }
        """
        if not fence_polygon or len(fence_polygon) < 3 or frame_w == 0 or frame_h == 0:
            return {"is_inside": False, "dwell_seconds": 0.0, "is_loitering": False, "just_triggered": False}

        inside = check_fence_crossing(bbox, frame_w, frame_h, fence_polygon)

        if not inside:
            # Person has left the zone -> reset dwell state
            if track_id in self._dwell_state:
                del self._dwell_state[track_id]
            return {"is_inside": False, "dwell_seconds": 0.0, "is_loitering": False, "just_triggered": False}

        if track_id not in self._dwell_state:
            self._dwell_state[track_id] = {
                "entry_time": timestamp,
                "last_seen": timestamp,
                "alerted": False,
            }

        state = self._dwell_state[track_id]
        state["last_seen"] = timestamp
        dwell_time = max(0.0, timestamp - state["entry_time"])

        is_loitering = dwell_time >= self.dwell_threshold
        just_triggered = False
        if is_loitering and not state["alerted"]:
            just_triggered = True
            state["alerted"] = True

        return {
            "is_inside": True,
            "dwell_seconds": round(dwell_time, 1),
            "is_loitering": is_loitering,
            "just_triggered": just_triggered,
        }

    def cleanup_track(self, track_id: int):
        self._dwell_state.pop(track_id, None)

    def cleanup_lost_tracks(self, active_track_ids: set, current_time: float, max_idle: float = 3.0):
        for tid in list(self._dwell_state.keys()):
            if tid not in active_track_ids:
                if current_time - self._dwell_state[tid]["last_seen"] > max_idle:
                    del self._dwell_state[tid]

