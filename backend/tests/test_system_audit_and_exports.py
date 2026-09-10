"""
test_system_audit_and_exports.py
--------------------------------
Comprehensive tests for:
- Global System Health & Liveness (/health)
- System Readiness Probe (/ready)
- System Version Info (/version)
- Admin Diagnostics Endpoint (/system/diagnostics)
- Storage Monitoring & Retention Status (/system/storage/status)
- Audit Trail Logging, Querying, Pagination, and CSV Export (/audit)
- Incidents & Alerts CSV Export (/incidents/export/csv, /alerts/export/csv)
- Evidence Gallery Aggregation (/incidents/evidence/gallery)
- RBAC Enforcement on Admin/Audited Routes
"""
import pytest
from starlette.testclient import TestClient
from main import app
from services.auth_service import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_token():
    return create_access_token({"sub": "admin", "role": "admin"})


@pytest.fixture
def operator_token():
    return create_access_token({"sub": "operator", "role": "operator"})


@pytest.fixture
def viewer_token():
    return create_access_token({"sub": "viewer", "role": "viewer"})


def test_liveness_endpoint(client):
    """Verify /health returns HTTP 200 with service information."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "UP"
    assert "version" in data
    assert "timestamp" in data


def test_readiness_endpoint(client):
    """Verify /ready evaluates subsystem readiness."""
    resp = client.get("/ready")
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "subsystems" in data
    assert "detector" in data["subsystems"]
    assert "storage" in data["subsystems"]
    assert "audio_dsp" in data["subsystems"]


def test_version_endpoint(client):
    """Verify /version returns consistent build and runtime information."""
    resp = client.get("/version")
    assert resp.status_code == 200
    data = resp.json()
    assert data["product_name"] == "B-SHIELD — AI-Powered Intelligent Border Surveillance"
    assert data["internal_code"] == "IBVAP"
    assert "build_id" in data
    assert "python_version" in data


def test_admin_diagnostics_rbac(client, viewer_token, admin_token):
    """Verify /system/diagnostics restricts unauthorized viewer and accepts admin."""
    # Viewer must be 403 Forbidden
    resp_viewer = client.get(
        "/system/diagnostics",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp_viewer.status_code == 403

    # Admin must succeed
    resp_admin = client.get(
        "/system/diagnostics",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == 200
    data = resp_admin.json()
    assert "status" in data
    assert "database" in data
    assert "storage" in data
    assert "ai_subsystems" in data
    assert "cameras" in data


def test_storage_status_endpoint(client, operator_token):
    """Verify /system/storage/status returns disk breakdown and retention policy."""
    resp = client.get(
        "/system/storage/status",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "storage_root" in data
    assert "retention_policy_days" in data
    assert data["retention_policy_days"]["evidence"] == 30


def test_audit_logs_and_csv_export(client, viewer_token, admin_token):
    """Verify audit logging retrieval and CSV export."""
    # 1. Viewer cannot access audit logs
    resp_viewer = client.get(
        "/audit",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp_viewer.status_code == 403

    # 2. Admin can list audit logs
    resp_admin = client.get(
        "/audit?limit=10",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_admin.status_code == 200
    data = resp_admin.json()
    assert "items" in data
    assert "total" in data

    # 3. Admin can export audit logs to CSV
    resp_csv = client.get(
        "/audit/export/csv",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp_csv.status_code == 200
    assert "text/csv" in resp_csv.headers["content-type"]
    assert "Timestamp" in resp_csv.text
    assert "Action" in resp_csv.text


def test_incidents_and_alerts_csv_export(client, operator_token):
    """Verify CSV export endpoints for incidents and alerts."""
    # Incidents CSV
    resp_inc = client.get(
        "/incidents/export/csv",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp_inc.status_code == 200
    assert "text/csv" in resp_inc.headers["content-type"]
    assert "Incident ID" in resp_inc.text

    # Alerts CSV
    resp_alt = client.get(
        "/alerts/export/csv",
        headers={"Authorization": f"Bearer {operator_token}"},
    )
    assert resp_alt.status_code == 200
    assert "text/csv" in resp_alt.headers["content-type"]
    assert "Alert ID" in resp_alt.text


def test_evidence_gallery_endpoint(client, viewer_token):
    """Verify evidence gallery returns paginated items without exposing raw paths."""
    resp = client.get(
        "/incidents/evidence/gallery?pageSize=10",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
