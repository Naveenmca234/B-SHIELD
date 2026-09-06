import time
import pytest
from services.health_service import evaluate_camera_health


def test_evaluate_camera_health_offline():
    res = evaluate_camera_health(
        status="OFFLINE",
        last_frame_time=None,
        visibility_data=None,
    )
    assert res["healthState"] == "OFFLINE"
    assert res["healthScore"] == 0
    assert res["coverageGap"] is True
    assert "offline" in res["gapNotice"].lower()


def test_evaluate_camera_health_healthy():
    now = time.time()
    res = evaluate_camera_health(
        status="ONLINE",
        last_frame_time=now,
        visibility_data={"visibilityStatus": "CLEAR", "visibilityScore": 85, "blurScore": 80, "contrastScore": 70, "brightnessScore": 55},
        fps=25.0,
    )
    assert res["healthState"] == "HEALTHY"
    assert res["healthScore"] >= 75
    assert res["coverageGap"] is False


def test_evaluate_camera_health_degraded():
    now = time.time()
    res = evaluate_camera_health(
        status="ONLINE",
        last_frame_time=now,
        visibility_data={"visibilityStatus": "MODERATE", "visibilityScore": 50, "blurScore": 20, "contrastScore": 15, "brightnessScore": 50},
        fps=15.0,
    )
    assert res["healthState"] == "DEGRADED"
    assert any("visibility" in r.lower() for r in res["reasons"])


def test_evaluate_camera_health_critical_coverage_gap():
    now = time.time()
    res = evaluate_camera_health(
        status="ONLINE",
        last_frame_time=now,
        visibility_data={"visibilityStatus": "POOR", "visibilityScore": 10, "blurScore": 10, "contrastScore": 10, "brightnessScore": 10},
        pipeline_error="Persistent frame decoding failure",
        fps=2.0,
    )
    assert res["healthState"] in ("CRITICAL", "OFFLINE")
    assert res["coverageGap"] is True
    assert res["gapNotice"] is not None
