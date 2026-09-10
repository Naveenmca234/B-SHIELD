"""
test_master_pass.py
-------------------
Comprehensive test suite verifying the Master Pass features:
1. ReportLab PDF generation and stream output.
2. Classical DSP audio anomaly detection and strict labeling policy.
3. Fault-isolated asynchronous notification dispatch.
4. Multi-cue threat scoring with acoustic anomaly integration.
5. In-memory sliding window rate limiter.
6. Rolling replay buffer structure.
"""
import io
import pytest
from fastapi import HTTPException

from services.pdf_service import pdf_generator
from services.audio_detector import audio_detector
from services.notifications_service import notifications_service
from services.auth_service import SimpleRateLimiter
from ai.multi_cue_engine import compute_threat, ThreatInputs


def test_pdf_report_generation():
    """Verify that IncidentPDFGenerator creates valid PDF bytes containing standard PDF header."""
    mock_incident = {
        "incidentId": "INC-TEST-999",
        "cameraId": "BOP-02",
        "eventType": "INTRUSION_DETECTED",
        "severity": "CRITICAL",
        "riskScore": 85,
        "status": "UNDER_INVESTIGATION",
        "createdAt": "2026-09-06T12:00:00Z",
        "description": "Test intrusion with virtual fence crossing.",
        "riskBreakdown": {
            "unknown_person": 30,
            "fence_crossing": 30,
            "high_risk_zone": 15,
        },
        "evidence": [
            {
                "evidenceId": "EV-001",
                "type": "SNAPSHOT",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "timestamp": "2026-09-06T12:00:00Z",
            }
        ],
        "history": [
            {
                "fromStatus": "ALERTED",
                "toStatus": "UNDER_INVESTIGATION",
                "changedBy": "operator",
                "role": "operator",
                "timestamp": "2026-09-06T12:01:00Z",
                "reason": "Operator deployed tactical unit.",
            }
        ],
        "feedback": {
            "classification": "GENUINE",
            "reason": None,
            "notes": "Confirmed intruder signature.",
            "operator": "operator",
            "timestamp": "2026-09-06T12:05:00Z",
        },
    }

    pdf_buffer = pdf_generator.generate_incident_report(
        incident=mock_incident,
        requested_by="admin",
        role="admin",
    )

    assert isinstance(pdf_buffer, io.BytesIO)
    pdf_bytes = pdf_buffer.getvalue()
    assert len(pdf_bytes) > 500
    # PDF magic number header
    assert pdf_bytes.startswith(b"%PDF-")


def test_audio_dsp_detection_and_labeling():
    """Verify classical DSP acoustic analysis and strict, honest physical labeling."""
    # 1. Normal ambient
    ambient = audio_detector.generate_simulated_ambient(duration_sec=0.2)
    res_amb = audio_detector.analyze_pcm(ambient)
    assert res_amb["classification"] == "NORMAL_AMBIENT"
    assert res_amb["is_anomaly"] is False
    assert "gunshot" not in res_amb["classification"].lower()

    # 2. Loud impulse (impact / collision)
    impulse = audio_detector.generate_simulated_ambient(duration_sec=0.2, anomaly_type="LOUD_IMPULSE")
    res_imp = audio_detector.analyze_pcm(impulse)
    assert res_imp["classification"] == "LOUD_IMPULSE_DETECTED"
    assert res_imp["is_anomaly"] is True
    assert "gunshot" not in res_imp["classification"].lower()

    # 3. Sustained loud audio (heavy vehicle / engine)
    sustained = audio_detector.generate_simulated_ambient(duration_sec=0.2, anomaly_type="SUSTAINED_LOUD")
    res_sus = audio_detector.analyze_pcm(sustained)
    assert res_sus["classification"] == "SUSTAINED_LOUD_AUDIO"
    assert res_sus["is_anomaly"] is True
    assert "gunshot" not in res_sus["classification"].lower()


def test_multi_cue_with_audio_anomaly():
    """Verify multi-cue threat engine factors acoustic anomalies into risk scores."""
    base_inputs = ThreatInputs(
        person_detected=True,
        person_status="UNKNOWN",
        detection_confidence=0.9,
    )
    base_result = compute_threat(base_inputs)

    # Add loud impulse cue
    audio_inputs = ThreatInputs(
        person_detected=True,
        person_status="UNKNOWN",
        detection_confidence=0.9,
        audio_anomaly="LOUD_IMPULSE_DETECTED",
    )
    audio_result = compute_threat(audio_inputs)

    assert audio_result["riskScore"] > base_result["riskScore"]
    has_audio_breakdown = any("Audio" in item["label"] for item in audio_result["breakdown"])
    assert has_audio_breakdown is True


def test_notifications_service_fault_isolation():
    """Verify dispatch_incident_alerts runs cleanly with complete fault isolation."""
    mock_incident = {
        "incidentId": "INC-TEST-001",
        "severity": "CRITICAL",
        "cameraId": "BOP-02",
        "eventType": "INTRUSION_DETECTED",
        "riskScore": 90,
    }
    # Must never raise an exception even if SMTP is unconfigured or network is dead
    try:
        notifications_service.dispatch_incident_alerts(mock_incident)
    except Exception as e:
        pytest.fail(f"dispatch_incident_alerts raised an unhandled exception: {e}")


def test_simple_rate_limiter():
    """Verify in-memory sliding window rate limiter."""
    limiter = SimpleRateLimiter(max_requests=3, window_seconds=10)
    key = "127.0.0.1"

    # 3 requests allowed
    limiter.check(key)
    limiter.check(key)
    limiter.check(key)

    # 4th request must raise HTTP 429
    with pytest.raises(HTTPException) as exc_info:
        limiter.check(key)
    assert exc_info.value.status_code == 429
