import pytest
from datetime import datetime, timedelta
from fastapi import HTTPException
from services.incident_service import IncidentService, ALLOWED_TRANSITIONS, calculate_duration_seconds


class MockAsyncCollection:
    def __init__(self, data=None):
        self.data = data or {}

    async def find_one(self, query):
        for k, v in query.items():
            for doc in self.data.values():
                if doc.get(k) == v:
                    return doc
        return None

    async def insert_one(self, doc):
        key = doc.get("incidentId") or str(len(self.data) + 1)
        self.data[key] = doc

    async def update_one(self, query, update):
        target = await self.find_one(query)
        if not target:
            return
        if "$set" in update:
            target.update(update["$set"])
        if "$push" in update:
            for k, val in update["$push"].items():
                target.setdefault(k, []).append(val)


class MockDatabase:
    def __init__(self):
        self.incidents = MockAsyncCollection()
        self.alerts = MockAsyncCollection()


def test_calculate_duration():
    t1 = "2026-09-05T12:00:00"
    t2 = "2026-09-05T12:01:30"
    assert calculate_duration_seconds(t1, t2) == 90
    assert calculate_duration_seconds(None, t2) is None


@pytest.mark.asyncio
async def test_incident_lifecycle_transitions():
    db = MockDatabase()
    service = IncidentService()

    # 1. Create incident
    threat = {
        "eventType": "INTRUSION_DETECTED",
        "severity": "CRITICAL",
        "riskScore": 95,
        "explanation": "Virtual fence crossed at night.",
        "breakdown": [{"label": "Fence Crossing", "points": 30}],
    }
    doc = await service.create_incident(db, camera_id="BOP-01", threat=threat)
    inc_id = doc["incidentId"]
    assert doc["status"] == "ALERTED"
    assert len(doc["statusHistory"]) == 1

    # 2. Transition ALERTED -> ACKNOWLEDGED
    upd1 = await service.transition_incident(
        db, inc_id, new_status="ACKNOWLEDGED", username="operator1", user_role="operator"
    )
    assert upd1["status"] == "ACKNOWLEDGED"
    assert upd1["acknowledgedBy"] == "operator1"
    assert len(upd1["statusHistory"]) == 2

    # 3. Transition ACKNOWLEDGED -> RESPONDING
    upd2 = await service.transition_incident(
        db, inc_id, new_status="RESPONDING", username="operator1", user_role="operator"
    )
    assert upd2["status"] == "RESPONDING"
    assert len(upd2["statusHistory"]) == 3

    # 4. Transition RESPONDING -> RESOLVED
    upd3 = await service.transition_incident(
        db, inc_id, new_status="RESOLVED", username="operator1", user_role="operator"
    )
    assert upd3["status"] == "RESOLVED"
    assert upd3["resolvedBy"] == "operator1"
    assert upd3["resolutionTimeSeconds"] is not None
    assert len(upd3["statusHistory"]) == 4

    # 5. Invalid transition from RESOLVED -> ALERTED (must fail)
    with pytest.raises(HTTPException) as exc:
        await service.transition_incident(
            db, inc_id, new_status="ALERTED", username="operator1", user_role="operator"
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_false_alarm_feedback():
    db = MockDatabase()
    service = IncidentService()

    threat = {"eventType": "POSSIBLE_INTRUSION", "severity": "MEDIUM", "riskScore": 50, "explanation": "", "breakdown": []}
    doc = await service.create_incident(db, camera_id="BOP-02", threat=threat)
    inc_id = doc["incidentId"]

    # Transition to FALSE_ALARM
    upd = await service.transition_incident(
        db, inc_id, new_status="FALSE_ALARM", username="operator2", user_role="operator", reason="Animal on perimeter"
    )
    assert upd["status"] == "FALSE_ALARM"

    # Record structured feedback
    res_fb = await service.record_feedback(
        db, inc_id, classification="FALSE_ALARM", reason="animal", notes="Stray dog near fence", operator="operator2"
    )
    assert res_fb["status"] == "RECORDED"
    assert res_fb["feedback"]["classification"] == "FALSE_ALARM"
    assert res_fb["feedback"]["reason"] == "animal"
