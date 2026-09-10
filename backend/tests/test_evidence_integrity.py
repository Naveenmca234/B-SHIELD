import os
import pytest
import numpy as np
from fastapi import HTTPException
from services.evidence_service import (
    calculate_sha256,
    _safe_resolve_path,
    EvidenceService,
)


def test_calculate_sha256():
    data = b"IBVAP Tamper-Evident Evidence Test"
    expected = "10f3f63b5737d7b8fde97fabc11b385bdd81c02c65fef5f1670fa3b7dc644ea6"
    assert calculate_sha256(data) == expected


def test_save_and_verify_evidence(tmp_path):
    storage = str(tmp_path / "snapshots")
    service = EvidenceService(storage_dir=storage)

    # Synthetic image
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[20:80, 20:80] = (0, 255, 0)

    # Save
    meta = service.save_snapshot(frame, incident_id="INC-TEST-01", camera_id="BOP-01")
    assert "sha256" in meta
    assert meta["verificationStatus"] == "VERIFIED"
    assert os.path.isfile(os.path.join(storage, meta["relativePath"]))

    # Verify pristine
    verify_res = service.verify_evidence(meta["relativePath"], meta["sha256"])
    assert verify_res["status"] == "VERIFIED"
    assert verify_res["tampered"] is False

    # Simulate tampering: overwrite file with modified byte content
    full_path = os.path.join(storage, meta["relativePath"])
    with open(full_path, "ab") as f:
        f.write(b"TAMPERED_BYTES")

    tampered_res = service.verify_evidence(meta["relativePath"], meta["sha256"])
    assert tampered_res["status"] == "INTEGRITY_FAILED"
    assert tampered_res["tampered"] is True


def test_safe_resolve_path_traversal():
    with pytest.raises(HTTPException) as excinfo:
        _safe_resolve_path("../../../windows/system32/cmd.exe")
    assert excinfo.value.status_code == 400
    assert "path traversal" in excinfo.value.detail.lower()
