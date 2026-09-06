"""
person_service.py
-----------------
Manages loading, synchronization, and caching of authorized personnel
into the FaceRecognitionEngine from MongoDB.
"""
import base64
import logging
import cv2
import numpy as np
from ai.face_recognition import face_engine

logger = logging.getLogger("ibvap.person_service")


def decode_base64_photo(data_url_or_base64: str) -> np.ndarray:
    """Safely decodes a base64 or data URL image string into an OpenCV BGR frame."""
    try:
        if not data_url_or_base64 or not isinstance(data_url_or_base64, str):
            return None
        data = data_url_or_base64
        if "," in data:
            data = data.split(",", 1)[1]
        raw_bytes = base64.b64decode(data)
        arr = np.frombuffer(raw_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img
    except Exception as exc:
        logger.debug("Failed to decode base64 photo: %s", exc)
        return None


async def sync_authorized_persons_to_face_engine(db) -> int:
    """
    Loads all authorized persons from MongoDB and populates face_engine.known_embeddings.
    Executes cleanly without crashing if db is None, collections are empty,
    or individual person records are malformed.
    Returns the count of successfully registered personnel.
    """
    if db is None:
        logger.info("Database unavailable; skipping authorized personnel sync.")
        return 0

    registered_count = 0
    skipped_count = 0

    try:
        cursor = db.persons.find({"status": "AUTHORIZED"})
        async for person in cursor:
            emp_id = person.get("employeeId")
            photo_data = person.get("photoUrl") or person.get("photoBase64")

            if not emp_id:
                skipped_count += 1
                continue

            # Case 1: Pre-computed embedding array directly stored in record
            if "faceEmbedding" in person and person["faceEmbedding"]:
                try:
                    emb = np.array(person["faceEmbedding"], dtype="float32")
                    face_engine.known_embeddings[emp_id] = emb
                    registered_count += 1
                    continue
                except Exception:
                    pass

            if not photo_data:
                # Registered without biometric photo (e.g. badge-only or pre-enrolled)
                continue

            img = decode_base64_photo(photo_data)
            if img is None:
                skipped_count += 1
                continue

            ok = face_engine.register_face(emp_id, img)
            if ok:
                registered_count += 1
            else:
                skipped_count += 1

        logger.info(
            "Authorized personnel sync complete: %d loaded, %d skipped.",
            registered_count,
            skipped_count,
        )
    except Exception as exc:
        logger.warning("Error during authorized personnel sync: %s", exc)

    return registered_count
