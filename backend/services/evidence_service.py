"""
evidence_service.py
-------------------
Tamper-evident evidence storage and verification service for IBVAP.
Preserves surveillance snapshots with cryptographic SHA-256 integrity hashes,
provides verification against disk, prevents directory traversal,
and records audit trails.
"""
import os
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import cv2
import numpy as np
from fastapi import HTTPException, status
from config import settings

logger = logging.getLogger("ibvap.evidence")


def calculate_sha256(data_bytes: bytes) -> str:
    """Computes SHA-256 cryptographic hash of byte content."""
    return hashlib.sha256(data_bytes).hexdigest()


def calculate_file_sha256(file_path: str) -> str:
    """Computes SHA-256 hash of a file on disk."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def _safe_resolve_path(rel_or_abs_path: str, base_dir: Optional[str] = None) -> str:
    """
    Resolves file path and verifies that it is strictly confined within SNAPSHOT_DIR
    to prevent path traversal attacks. Uses os.path.commonpath for strict containment.
    """
    base = os.path.abspath(base_dir or settings.SNAPSHOT_DIR)
    if os.path.isabs(rel_or_abs_path):
        target_path = os.path.abspath(rel_or_abs_path)
    else:
        target_path = os.path.abspath(os.path.join(base, rel_or_abs_path))

    try:
        common = os.path.commonpath([base, target_path])
        if os.path.abspath(common) != base:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: Invalid evidence path (path traversal detected).",
            )
    except (ValueError, Exception):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security violation: Invalid evidence path (path traversal detected).",
        )
    return target_path



class EvidenceService:
    def __init__(self, storage_dir: str = settings.SNAPSHOT_DIR):
        self.storage_dir = os.path.abspath(storage_dir)
        os.makedirs(self.storage_dir, exist_ok=True)

    def save_snapshot(self, frame: np.ndarray, incident_id: str, camera_id: str) -> Dict[str, Any]:
        """
        Encodes frame to JPEG, saves to snapshots/<incident_id>/<timestamp>_<hash8>.jpg,
        and calculates cryptographic SHA-256.
        Returns evidence metadata dict.
        """
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            return {"error": "Failed to encode frame to JPEG"}

        img_bytes = buf.tobytes()
        full_hash = calculate_sha256(img_bytes)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        short_hash = full_hash[:8]

        incident_dir = os.path.join(self.storage_dir, incident_id)
        os.makedirs(incident_dir, exist_ok=True)

        filename = f"{ts}_{short_hash}.jpg"
        full_path = os.path.join(incident_dir, filename)

        with open(full_path, "wb") as f:
            f.write(img_bytes)

        rel_path = os.path.relpath(full_path, self.storage_dir).replace("\\", "/")

        return {
            "evidenceId": f"EV-{incident_id}-{short_hash}",
            "incidentId": incident_id,
            "cameraId": camera_id,
            "filename": filename,
            "relativePath": rel_path,
            "sha256": full_hash,
            "sizeBytes": len(img_bytes),
            "mimeType": "image/jpeg",
            "capturedAt": datetime.now(timezone.utc).isoformat(),
            "verificationStatus": "VERIFIED",
        }

    def verify_evidence(self, rel_path: str, stored_hash: str) -> Dict[str, Any]:
        """
        Reads actual evidence file from disk, recalculates SHA-256,
        and compares with stored hash.
        Returns {"status": "VERIFIED"|"INTEGRITY_FAILED", "computedHash", "storedHash"}
        """
        target_path = _safe_resolve_path(rel_path, base_dir=self.storage_dir)
        if not os.path.isfile(target_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Evidence file not found on disk.",
            )

        computed = calculate_file_sha256(target_path)
        is_valid = (computed.lower() == stored_hash.lower())

        return {
            "status": "VERIFIED" if is_valid else "INTEGRITY_FAILED",
            "computedHash": computed,
            "storedHash": stored_hash,
            "verifiedAt": datetime.now(timezone.utc).isoformat(),
            "tampered": not is_valid,
        }

    def read_evidence_bytes(self, rel_path: str) -> bytes:
        """Safely reads evidence bytes with path traversal validation."""
        target_path = _safe_resolve_path(rel_path)
        if not os.path.isfile(target_path):
            raise HTTPException(status_code=404, detail="Evidence file not found.")
        with open(target_path, "rb") as f:
            return f.read()

    async def log_access(self, db, evidence_id: str, incident_id: str, user: str, action: str):
        """Records an immutable evidence access audit record."""
        if db is not None:
            try:
                await db.evidence_audits.insert_one({
                    "evidenceId": evidence_id,
                    "incidentId": incident_id,
                    "accessedBy": user,
                    "action": action,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.warning("Failed to record evidence audit log: %s", e)


evidence_service = EvidenceService()
