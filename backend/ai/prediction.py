"""
prediction.py
-------------
Predictive Intrusion Path analysis for IBVAP.
Maintains short-term observed movement history for tracked individuals,
smooths noise, estimates trajectory vectors, and projects whether movement
is heading toward or will intersect configured restricted zones.

Core policy: NEVER predicts human intent. Only projects observed physical motion.
"""
import math
from typing import List, Dict, Tuple, Optional, Any
from ai.intrusion import point_in_polygon


def _line_intersects_segment(p1: Tuple[float, float], p2: Tuple[float, float],
                             q1: Tuple[float, float], q2: Tuple[float, float]) -> bool:
    """Checks if line segment (p1-p2) intersects segment (q1-q2)."""
    def ccw(a, b, c):
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    return (ccw(p1, q1, q2) != ccw(p2, q1, q2)) and (ccw(p1, p2, q1) != ccw(p1, p2, q2))


class TrajectoryPredictor:
    def __init__(self, history_len: int = 10, projection_horizon: float = 2.0):
        # trackId -> list of (norm_x, norm_y, timestamp)
        self.history: Dict[int, List[Tuple[float, float, float]]] = {}
        self.history_len = history_len
        self.projection_horizon = projection_horizon  # projection distance multiplier

    def update_and_predict(
        self,
        track_id: int,
        bbox: Dict[str, int],
        frame_w: int,
        frame_h: int,
        fence_polygon: List[Dict[str, float]],
        timestamp: float,
    ) -> Dict[str, Any]:
        """
        Updates coordinate history for track_id and calculates trajectory projection.
        Returns:
            {
                "status": "NO_CONFLICT" | "APPROACHING_RESTRICTED_ZONE" | "PREDICTED_ZONE_ENTRY",
                "velocity": float,           # normalized units / sec
                "directionDegrees": float,  # 0-360 compass direction
                "currentFootprint": {"x": float, "y": float},
                "projectedFootprint": {"x": float, "y": float},
                "explanation": str
            }
        """
        if frame_w == 0 or frame_h == 0:
            return {"status": "NO_CONFLICT", "velocity": 0.0, "directionDegrees": 0.0}

        # Calculate normalized bottom-center (footprint) coordinate
        curr_x = (bbox["x"] + bbox["w"] / 2.0) / frame_w
        curr_y = (bbox["y"] + bbox["h"]) / frame_h

        if track_id not in self.history:
            self.history[track_id] = []

        pts = self.history[track_id]
        pts.append((curr_x, curr_y, timestamp))
        if len(pts) > self.history_len:
            pts.pop(0)

        # If we have fewer than 3 historical points, movement is not yet established
        if len(pts) < 3:
            return {
                "status": "NO_CONFLICT",
                "velocity": 0.0,
                "directionDegrees": 0.0,
                "currentFootprint": {"x": round(curr_x, 3), "y": round(curr_y, 3)},
                "projectedFootprint": {"x": round(curr_x, 3), "y": round(curr_y, 3)},
                "explanation": "Insufficient movement history to project trajectory.",
            }

        # Calculate smoothed displacement over recent window
        dx = pts[-1][0] - pts[0][0]
        dy = pts[-1][1] - pts[0][1]
        dt = max(0.1, pts[-1][2] - pts[0][2])

        vx = dx / dt
        vy = dy / dt
        speed = math.sqrt(vx * vx + vy * vy)

        # Direction in degrees (0 = right, 90 = down, 180 = left, 270 = up in screen coords)
        angle_rad = math.atan2(vy, vx)
        angle_deg = (math.degrees(angle_rad) + 360) % 360

        # Project position forward
        proj_x = max(0.0, min(1.0, curr_x + vx * self.projection_horizon))
        proj_y = max(0.0, min(1.0, curr_y + vy * self.projection_horizon))

        # Check intersection with virtual fence polygon
        status = "NO_CONFLICT"
        explanation = "Trajectory indicates stationary or clear perimeter movement."

        if fence_polygon and len(fence_polygon) >= 3 and speed > 0.02:
            # 1. Is projected point inside polygon?
            inside_proj = point_in_polygon(proj_x, proj_y, fence_polygon)
            # 2. Does trajectory segment intersect any polygon boundary?
            intersects_boundary = False
            n = len(fence_polygon)
            for i in range(n):
                q1 = (fence_polygon[i]["x"], fence_polygon[i]["y"])
                q2 = (fence_polygon[(i + 1) % n]["x"], fence_polygon[(i + 1) % n]["y"])
                if _line_intersects_segment((curr_x, curr_y), (proj_x, proj_y), q1, q2):
                    intersects_boundary = True
                    break

            if inside_proj or intersects_boundary:
                status = "PREDICTED_ZONE_ENTRY"
                explanation = "Short-term movement trajectory projects direct entry into the restricted zone."
            else:
                # Check if moving closer to the polygon centroid
                poly_cx = sum(p["x"] for p in fence_polygon) / n
                poly_cy = sum(p["y"] for p in fence_polygon) / n
                dist_curr = math.dist((curr_x, curr_y), (poly_cx, poly_cy))
                dist_proj = math.dist((proj_x, proj_y), (poly_cx, poly_cy))
                if dist_proj < dist_curr and (dist_curr - dist_proj) > 0.05:
                    status = "APPROACHING_RESTRICTED_ZONE"
                    explanation = "Observed trajectory projects movement toward the configured restricted zone."

        return {
            "status": status,
            "velocity": round(speed, 3),
            "directionDegrees": round(angle_deg, 1),
            "currentFootprint": {"x": round(curr_x, 3), "y": round(curr_y, 3)},
            "projectedFootprint": {"x": round(proj_x, 3), "y": round(proj_y, 3)},
            "explanation": explanation,
        }

    def cleanup_track(self, track_id: int):
        self.history.pop(track_id, None)
