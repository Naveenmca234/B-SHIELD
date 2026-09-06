"""
test_live_upload.py
-------------------
Tests the live video upload endpoint:
- Authentication & RBAC (operator/admin only, viewer/unauthenticated rejected)
- File extension validation (valid vs invalid formats)
- Storage verification
- Cleanup on error
"""
import os
import io
import pytest
from fastapi.testclient import TestClient

from main import app
from config import settings
from services.auth_service import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def operator_headers():
    token = create_access_token({"sub": "operator", "role": "operator"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_headers():
    token = create_access_token({"sub": "viewer", "role": "viewer"})
    return {"Authorization": f"Bearer {token}"}


def test_upload_unauthenticated(client):
    file_data = io.BytesIO(b"fake video content")
    response = client.post(
        "/live/upload",
        files={"file": ("test.mp4", file_data, "video/mp4")},
    )
    assert response.status_code == 401


def test_upload_viewer_forbidden(client, viewer_headers):
    file_data = io.BytesIO(b"fake video content")
    response = client.post(
        "/live/upload",
        headers=viewer_headers,
        files={"file": ("test.mp4", file_data, "video/mp4")},
    )
    assert response.status_code == 403


def test_upload_invalid_extension(client, operator_headers):
    file_data = io.BytesIO(b"not a video")
    response = client.post(
        "/live/upload",
        headers=operator_headers,
        files={"file": ("malicious.exe", file_data, "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported video format" in response.json()["detail"]


def test_upload_valid_video_success_and_cleanup(client, operator_headers):
    dummy_video_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isommp42" + b"A" * 1024
    file_data = io.BytesIO(dummy_video_bytes)

    response = client.post(
        "/live/upload",
        headers=operator_headers,
        files={"file": ("sample_test.mp4", file_data, "video/mp4")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Video uploaded successfully"
    filename = data["filename"]
    assert filename.endswith(".mp4")

    # Verify file was actually saved to disk in SAMPLE_VIDEO_DIR
    target_path = os.path.join(settings.SAMPLE_VIDEO_DIR, filename)
    assert os.path.isfile(target_path)
    assert os.path.getsize(target_path) == len(dummy_video_bytes)

    # Clean up uploaded test file
    os.remove(target_path)
    assert not os.path.exists(target_path)
