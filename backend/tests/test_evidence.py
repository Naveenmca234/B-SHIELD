import os
import tempfile
import pytest
import numpy as np
from fastapi import HTTPException
from services.evidence_service import EvidenceService, calculate_sha256, _safe_resolve_path


def test_calculate_sha256():
    data = b"B-SHIELD_SURVEILLANCE_EVIDENCE"
    h1 = calculate_sha256(data)
    h2 = calculate_sha256(data)
    assert len(h1) == 64
    assert h1 == h2


def test_evidence_save_and_verify():
    with tempfile.TemporaryDirectory() as tmpdir:
        svc = EvidenceService(storage_dir=tmpdir)
        frame = np.zeros((100, 100, 3), dtype=np.uint8)

        # Save snapshot
        doc = svc.save_snapshot(frame, incident_id="INC-TEST-001", camera_id="CAM-01")
        assert doc["incidentId"] == "INC-TEST-001"
        assert doc["cameraId"] == "CAM-01"
        assert doc["sha256"]
        assert doc["relativePath"]

        # Verify on disk
        v_res = svc.verify_evidence(doc["relativePath"], doc["sha256"])
        assert v_res["status"] == "VERIFIED"
        assert v_res["tampered"] is False
        assert v_res["computedHash"] == doc["sha256"]


def test_evidence_tampering_detected():
    with tempfile.TemporaryDirectory() as tmpdir:
        svc = EvidenceService(storage_dir=tmpdir)
        frame = np.ones((100, 100, 3), dtype=np.uint8) * 50

        doc = svc.save_snapshot(frame, incident_id="INC-TEST-002", camera_id="CAM-01")
        full_path = os.path.join(tmpdir, doc["relativePath"])

        # Tamper with the file by appending bytes
        with open(full_path, "ab") as f:
            f.write(b"CORRUPTED_BYTES")

        v_res = svc.verify_evidence(doc["relativePath"], doc["sha256"])
        assert v_res["status"] == "INTEGRITY_FAILED"
        assert v_res["tampered"] is True
        assert v_res["computedHash"] != doc["sha256"]


def test_evidence_missing_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        svc = EvidenceService(storage_dir=tmpdir)
        with pytest.raises(HTTPException) as exc_info:
            svc.verify_evidence("non_existent_file.jpg", "abc12345")
        assert exc_info.value.status_code == 404


def test_evidence_path_traversal_prevention():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Attempt to break out with ../
        with pytest.raises(HTTPException) as exc_info:
            _safe_resolve_path("../../../windows/system32/cmd.exe", base_dir=tmpdir)
        assert exc_info.value.status_code == 400
        assert "path traversal" in exc_info.value.detail.lower()
