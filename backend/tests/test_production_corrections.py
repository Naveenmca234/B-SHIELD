import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from services.auth_service import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def viewer_token():
    return create_access_token({"sub": "viewer_user", "role": "viewer"})


@pytest.fixture
def operator_token():
    return create_access_token({"sub": "operator_user", "role": "operator"})


def test_viewer_forbidden_on_alert_acknowledge(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}
    res = client.post("/alerts/64b1f2e3d4c5a6b7e8f90123/acknowledge", headers=headers)
    assert res.status_code == 403
    assert "not permitted" in res.json()["detail"].lower() or "insufficient permissions" in res.json()["detail"].lower()


def test_viewer_forbidden_on_alert_resolve(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}
    res = client.post("/alerts/64b1f2e3d4c5a6b7e8f90123/resolve", json={"resolutionNotes": "Resolved by viewer"}, headers=headers)
    assert res.status_code == 403
    assert "not permitted" in res.json()["detail"].lower() or "insufficient permissions" in res.json()["detail"].lower()


def test_viewer_forbidden_on_incident_transition(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}
    res = client.post("/incidents/INC-2026-001/transition", json={"status": "ACKNOWLEDGED"}, headers=headers)
    assert res.status_code == 403
    assert "not permitted" in res.json()["detail"].lower() or "insufficient permissions" in res.json()["detail"].lower()


def test_viewer_forbidden_on_incident_feedback(client, viewer_token):
    headers = {"Authorization": f"Bearer {viewer_token}"}
    res = client.post("/incidents/INC-2026-001/feedback", json={"isFalseAlarm": True, "notes": "test"}, headers=headers)
    assert res.status_code == 403
    assert "not permitted" in res.json()["detail"].lower() or "insufficient permissions" in res.json()["detail"].lower()


def test_dashboard_avg_response_time_semantics(client, viewer_token):
    class MockDB:
        def __init__(self):
            self.incidents = MagicMock()
            self.alerts = MagicMock()
            self.cameras = MagicMock()
            self.events = MagicMock()

            mock_cursor = MagicMock()
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=[])
            self.incidents.find.return_value = mock_cursor
            self.incidents.count_documents = AsyncMock(return_value=0)
            self.alerts.count_documents = AsyncMock(return_value=0)

            cam_cursor = MagicMock()
            cam_cursor.to_list = AsyncMock(return_value=[])
            self.cameras.find.return_value = cam_cursor

            agg_cursor = MagicMock()
            agg_cursor.to_list = AsyncMock(return_value=[])
            self.incidents.aggregate.return_value = agg_cursor

    with patch("routes.dashboard.get_db", return_value=MockDB()):
        headers = {"Authorization": f"Bearer {viewer_token}"}
        res = client.get("/dashboard/stats", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["avgResponseTimeSeconds"] is None


def test_dashboard_avg_response_time_calculated_when_records_exist(client, viewer_token):
    class MockDB:
        def __init__(self):
            self.incidents = MagicMock()
            self.alerts = MagicMock()
            self.cameras = MagicMock()
            self.events = MagicMock()

            mock_cursor = MagicMock()
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=[])
            self.incidents.find.return_value = mock_cursor
            self.incidents.count_documents = AsyncMock(return_value=1)
            self.alerts.count_documents = AsyncMock(return_value=0)

            cam_cursor = MagicMock()
            cam_cursor.to_list = AsyncMock(return_value=[])
            self.cameras.find.return_value = cam_cursor

            agg_cursor = MagicMock()
            # aggregate cursor returns one group doc with the average
            agg_cursor.to_list = AsyncMock(return_value=[{"_id": None, "avgResponse": 24.5}])
            self.incidents.aggregate.return_value = agg_cursor

    with patch("routes.dashboard.get_db", return_value=MockDB()):
        headers = {"Authorization": f"Bearer {viewer_token}"}
        res = client.get("/dashboard/stats", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["avgResponseTimeSeconds"] == 24.5


def test_evidence_verify_missing_file_returns_tampered_gracefully(client, operator_token):
    class MockDB:
        def __init__(self):
            self.incidents = MagicMock()
            self.incidents.find_one = AsyncMock(return_value={
                "incidentId": "INC-TEST-001",
                "evidence": [{
                    "evidenceId": "ev-001",
                    "relativePath": "evidence/non_existent_file.jpg",
                    "sha256": "abcdef1234567890",
                    "timestamp": "2026-03-01T12:00:00Z"
                }]
            })

    with patch("routes.incidents.get_db", return_value=MockDB()):
        headers = {"Authorization": f"Bearer {operator_token}"}
        res = client.get("/incidents/INC-TEST-001/evidence/ev-001/verify", headers=headers)
        assert res.status_code == 200
        result = res.json()
        assert result["tampered"] is True
        assert result["status"] == "FILE_NOT_FOUND"
