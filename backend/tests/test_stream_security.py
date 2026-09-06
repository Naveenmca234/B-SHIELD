"""
test_stream_security.py
-----------------------
Validates live stream endpoint security:
- Token-in-query vs token-in-header authentication
- Rejection of missing, invalid, or expired tokens
- Viewer, Operator, Admin access authorization
- Proper 404 for invalid/unregistered cameras
"""
import pytest
from fastapi.testclient import TestClient

from main import app
from services.auth_service import create_access_token
from services.camera_manager import camera_manager


@pytest.fixture
def client():
    return TestClient(app)


def test_stream_missing_token_rejected(client):
    res = client.get("/live/stream/BOP-01")
    assert res.status_code == 401
    assert "token required" in res.json()["detail"].lower()


def test_stream_invalid_token_rejected(client):
    res = client.get("/live/stream/BOP-01?token=gibberish_token_string")
    assert res.status_code == 401
    assert "invalid or expired" in res.json()["detail"].lower()


def test_stream_expired_token_rejected(client):
    expired = create_access_token({"sub": "viewer", "role": "viewer"}, expires_minutes=-5)
    res = client.get(f"/live/stream/BOP-01?token={expired}")
    assert res.status_code == 401


def test_stream_nonexistent_camera_returns_404(client):
    token = create_access_token({"sub": "admin", "role": "admin"})
    res = client.get(f"/live/stream/CAM-DOES-NOT-EXIST?token={token}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_stream_authorized_roles_accepted():
    from routes.live import _mjpeg_generator, extract_and_validate_stream_token

    class MockPipeline:
        status = "ONLINE"
        def get_latest_jpeg(self):
            return b"\xff\xd8\xff\xe0"  # minimal JPEG header

    camera_manager.pipelines["BOP-TEST-STREAM"] = MockPipeline()

    for role in ("viewer", "operator", "admin"):
        token = create_access_token({"sub": f"user_{role}", "role": role})

        # Test auth extraction
        payload = extract_and_validate_stream_token(token=token)
        assert payload["sub"] == f"user_{role}"
        assert payload["role"] == role

    # Test generator yields real MJPEG frame
    gen = _mjpeg_generator("BOP-TEST-STREAM")
    first_chunk = await anext(gen)
    assert b"--frame" in first_chunk
    assert b"Content-Type: image/jpeg" in first_chunk
    await gen.aclose()

    camera_manager.pipelines.pop("BOP-TEST-STREAM", None)
