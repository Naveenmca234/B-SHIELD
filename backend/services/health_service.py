"""
health_service.py
-----------------
Dynamic Surveillance Health and Coverage Gap Intelligence.
Synthesizes real hardware and computer-vision signals into explainable
health states: HEALTHY, DEGRADED, CRITICAL, OFFLINE.
"""
import time
from typing import Dict, Any, List, Optional


def evaluate_camera_health(
    status: str,
    last_frame_time: Optional[float],
    visibility_data: Optional[Dict[str, Any]],
    pipeline_error: Optional[str] = None,
    fps: float = 0.0,
) -> Dict[str, Any]:
    """
    Computes explainable surveillance health for a camera.
    Returns:
        {
            "healthState": "HEALTHY" | "DEGRADED" | "CRITICAL" | "OFFLINE",
            "healthScore": int (0-100),
            "reasons": List[str],
            "coverageGap": bool,
            "gapNotice": Optional[str],
            "fps": float,
            "lastSeenSeconds": float
        }
    """
    now = time.time()
    reasons: List[str] = []

    if status != "ONLINE" or last_frame_time is None:
        reasons.append("Camera source is currently offline or unreachable.")
        return {
            "healthState": "OFFLINE",
            "healthScore": 0,
            "reasons": reasons,
            "coverageGap": True,
            "gapNotice": "Potential surveillance coverage gap: Camera feed is offline.",
            "fps": 0.0,
            "lastSeenSeconds": round(now - (last_frame_time or now), 1),
        }

    last_seen = now - last_frame_time
    score = 100

    # 1. Frame Freshness check
    if last_seen > 5.0:
        score -= 50
        reasons.append(f"Stale frame stream: no new frame for {int(last_seen)}s.")
    elif last_seen > 2.0:
        score -= 25
        reasons.append("Intermittent frame delivery latency detected.")

    # 2. Pipeline Error check
    if pipeline_error:
        score -= 40
        reasons.append(f"Pipeline warning: {pipeline_error}")

    # 3. Computer Vision / Visibility Quality checks
    if visibility_data:
        v_status = visibility_data.get("visibilityStatus", "CLEAR")
        blur_score = visibility_data.get("blurScore", 100)
        contrast_score = visibility_data.get("contrastScore", 100)
        brightness_score = visibility_data.get("brightnessScore", 50)

        if v_status == "POOR":
            score -= 40
            reasons.append("Overall visibility is POOR; direct optical detection confidence is severely degraded.")
        elif v_status == "MODERATE":
            score -= 15
            reasons.append("Visibility is moderately degraded due to environmental haze or lighting.")

        if blur_score < 25:
            score -= 20
            reasons.append("High image blur / optical defocus detected.")

        if contrast_score < 20:
            score -= 15
            reasons.append("Severe contrast loss (possible fog or lens obstruction).")

        if brightness_score < 15 or brightness_score > 90:
            score -= 15
            reasons.append("Extreme illumination condition (near darkness or camera glare).")

    score = max(0, min(100, score))

    if score >= 75:
        health_state = "HEALTHY"
        coverage_gap = False
        gap_notice = None
    elif score >= 45:
        health_state = "DEGRADED"
        coverage_gap = False
        gap_notice = None
    elif score > 0:
        health_state = "CRITICAL"
        coverage_gap = True
        gap_notice = "Potential coverage gap: Camera capability is CRITICALLY degraded."
    else:
        health_state = "OFFLINE"
        coverage_gap = True
        gap_notice = "Potential coverage gap: Camera feed is unavailable."

    if not reasons:
        reasons.append("Camera operational with clear visibility and stable frame rate.")

    return {
        "healthState": health_state,
        "healthScore": score,
        "reasons": reasons,
        "coverageGap": coverage_gap,
        "gapNotice": gap_notice,
        "fps": round(fps, 1),
        "lastSeenSeconds": round(last_seen, 1),
    }
