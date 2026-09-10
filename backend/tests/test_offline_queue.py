"""
test_offline_queue.py
---------------------
Tests the offline event queue and synchronization system:
- Enqueuing when DB is offline
- Status tracking: PENDING -> RETRYING -> SYNCED / FAILED
- Safe idempotent sync to MongoDB (no duplicate records created)
- Mid-run DB failure fallback during incident creation
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from services.offline_queue import OfflineEventQueue
from services.incident_service import incident_service


@pytest.fixture
def temp_queue(tmp_path):
    queue_dir = tmp_path / "offline_queue"
    queue = OfflineEventQueue(queue_dir=str(queue_dir))
    return queue


class MockCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                return d
        return None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return MagicMock(inserted_id="mock_id")


class MockDatabase:
    def __init__(self):
        self.incidents = MockCollection()
        self.alerts = MockCollection()
        self.plates = MockCollection()
        self.events = MockCollection()


@pytest.mark.asyncio
async def test_offline_queue_enqueue_and_sync(temp_queue):
    event_payload = {
        "incidentId": "INC-TEST-001",
        "cameraId": "BOP-01",
        "eventType": "INTRUSION_DETECTED",
        "severity": "CRITICAL",
        "riskScore": 85,
    }

    # 1. Enqueue while offline
    event_id = await temp_queue.enqueue_event(event_payload)
    assert event_id == "INC-TEST-001"

    backlog = temp_queue._read_queue()
    assert len(backlog) == 1
    assert backlog[0]["status"] == "PENDING"
    assert backlog[0]["attempts"] == 0

    # 2. Sync to mock DB
    mock_db = MockDatabase()
    res = await temp_queue.flush_and_sync(mock_db)
    assert res["status"] == "SUCCESS"
    assert res["synced"] == 1
    assert res["pending"] == 0

    # Backlog on disk should now be empty after successful sync
    assert len(temp_queue._read_queue()) == 0

    # DB should have the incident and alert
    assert len(mock_db.incidents.docs) == 1
    assert mock_db.incidents.docs[0]["incidentId"] == "INC-TEST-001"
    assert len(mock_db.alerts.docs) == 1


@pytest.mark.asyncio
async def test_offline_queue_idempotent_sync_no_duplicates(temp_queue):
    event_payload = {
        "incidentId": "INC-TEST-002",
        "cameraId": "BOP-01",
        "eventType": "UNKNOWN_PERSON",
        "severity": "HIGH",
        "riskScore": 65,
    }

    mock_db = MockDatabase()
    # Pre-insert into DB to simulate network interruption after insert but before queue cleanup
    await mock_db.incidents.insert_one(dict(event_payload))
    assert len(mock_db.incidents.docs) == 1

    # Enqueue same event
    await temp_queue.enqueue_event(event_payload)
    assert len(temp_queue._read_queue()) == 1

    # Flush and sync
    res = await temp_queue.flush_and_sync(mock_db)
    assert res["status"] == "SUCCESS"
    assert res["synced"] == 1

    # Verify no duplicate was inserted
    assert len(mock_db.incidents.docs) == 1


@pytest.mark.asyncio
async def test_offline_queue_retry_and_failure(temp_queue):
    event_payload = {
        "incidentId": "INC-TEST-003",
        "cameraId": "BOP-02",
        "eventType": "NIGHT_MOVEMENT",
    }
    await temp_queue.enqueue_event(event_payload)

    # Mock DB that raises an exception on insert
    failing_db = MockDatabase()
    failing_db.incidents.find_one = AsyncMock(return_value=None)
    failing_db.incidents.insert_one = AsyncMock(side_effect=Exception("Connection lost"))

    # Attempt 1 -> status RETRYING
    res1 = await temp_queue.flush_and_sync(failing_db)
    assert res1["synced"] == 0
    assert res1["pending"] == 1
    backlog = temp_queue._read_queue()
    assert backlog[0]["status"] == "RETRYING"
    assert backlog[0]["attempts"] == 1

    # Attempt 2, 3, 4
    for _ in range(3):
        await temp_queue.flush_and_sync(failing_db)

    # Attempt 5 -> status FAILED
    await temp_queue.flush_and_sync(failing_db)
    backlog = temp_queue._read_queue()
    assert backlog[0]["attempts"] == 5
    assert backlog[0]["status"] == "FAILED"


@pytest.mark.asyncio
async def test_incident_service_fallback_to_queue_on_db_exception():
    # Mock DB where insert_one fails mid-run
    failing_db = MockDatabase()
    failing_db.incidents.insert_one = AsyncMock(side_effect=RuntimeError("Mongo connection closed"))

    threat = {
        "eventType": "INTRUSION_DETECTED",
        "severity": "CRITICAL",
        "riskScore": 90,
        "explanation": "Threat detected",
        "breakdown": [],
    }

    # Calling create_incident should NOT raise an exception, but gracefully enqueue
    incident = await incident_service.create_incident(
        db=failing_db,
        camera_id="BOP-01",
        threat=threat,
    )
    assert incident is not None
    assert incident["eventType"] == "INTRUSION_DETECTED"
