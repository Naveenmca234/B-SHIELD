from ai.multi_cue_engine import ThreatInputs, compute_threat, severity_from_score


def test_compute_threat_zero_inputs():
    inputs = ThreatInputs()
    res = compute_threat(inputs)
    assert res["riskScore"] == 0
    assert res["severity"] == "LOW"
    assert len(res["breakdown"]) == 0
    assert "No significant risk factors" in res["explanation"]


def test_compute_threat_single_cue():
    # Only night movement without person
    inputs = ThreatInputs(is_night=True, motion_detected=True)
    res = compute_threat(inputs)
    assert res["riskScore"] == 15
    assert res["severity"] == "LOW"
    assert any("Night Movement" in b["label"] for b in res["breakdown"])


def test_compute_threat_bounds_and_critical():
    # Everything active
    inputs = ThreatInputs(
        person_detected=True,
        person_status="UNKNOWN",
        is_night=True,
        fence_crossing=True,
        vehicle_nearby=True,
        camera_risk_level="HIGH",
        predicted_zone_entry=True,
    )
    res = compute_threat(inputs)
    assert res["riskScore"] <= 100
    assert res["riskScore"] >= 80
    assert res["severity"] in ("HIGH", "CRITICAL")
    assert "INTRUSION_DETECTED" in res["eventType"]
    assert len(res["breakdown"]) >= 4
    assert any("Night Movement" in b["label"] for b in res["breakdown"])
    assert any("Fence Crossing" in b["label"] for b in res["breakdown"])


def test_compute_threat_authorized_person():
    inputs = ThreatInputs(
        person_detected=True,
        person_status="AUTHORIZED",
        fence_crossing=False,
    )
    res = compute_threat(inputs)
    assert res["riskScore"] == 0
    assert res["severity"] == "LOW"
    assert "authorized person" in res["explanation"].lower()


def test_severity_from_score():
    assert severity_from_score(0) == "LOW"
    assert severity_from_score(30) == "LOW"
    assert severity_from_score(31) == "MEDIUM"
    assert severity_from_score(60) == "MEDIUM"
    assert severity_from_score(61) == "HIGH"
    assert severity_from_score(80) == "HIGH"
    assert severity_from_score(81) == "CRITICAL"
    assert severity_from_score(100) == "CRITICAL"


def test_compute_threat_confidence_and_loitering():
    # Loitering increases score
    inputs_loiter = ThreatInputs(
        person_detected=True,
        person_status="UNKNOWN",
        is_loitering=True,
        detection_confidence=0.85,
    )

    res_loiter = compute_threat(inputs_loiter)
    assert any("Loitering Detection" in b["label"] for b in res_loiter["breakdown"])
    assert any("High Detection Confidence" in b["label"] for b in res_loiter["breakdown"])
    assert "loitering" in res_loiter["explanation"].lower()
    assert "high" in res_loiter["explanation"].lower()

    # Low confidence reduces score
    inputs_low_conf = ThreatInputs(
        person_detected=True,
        person_status="UNKNOWN",
        detection_confidence=0.30,
    )
    res_low_conf = compute_threat(inputs_low_conf)
    assert any("Low Detection Confidence" in b["label"] for b in res_low_conf["breakdown"])
    assert "marginal" in res_low_conf["explanation"].lower()


