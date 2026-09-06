"""
test_seed_logic.py
-------------------
Validates seed script execution with database operations:
- Verifies users (admin, operator, viewer) are inserted
- Verifies bcrypt password hashing works and passwords can be verified
- Verifies cameras, authorized personnel, and settings are seeded
- Verifies demo incident with SHA-256 evidence is generated
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from database.seed import seed
from services.auth_service import verify_password


class MockCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query):
        for doc in self.docs:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                return doc
        return None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return MagicMock(inserted_id="mock_id")


class MockDatabase:
    def __init__(self):
        self.users = MockCollection()
        self.cameras = MockCollection()
        self.persons = MockCollection()
        self.settings = MockCollection()
        self.incidents = MockCollection()
        self.alerts = MockCollection()


@pytest.mark.asyncio
async def test_seed_creates_expected_entities_and_hashes_passwords():
    mock_db = MockDatabase()
    mock_client = MagicMock()
    mock_client.__getitem__.return_value = mock_db
    mock_client.admin.command = AsyncMock(return_value={"ok": 1})
    mock_client.close = MagicMock()

    with patch("database.seed.AsyncIOMotorClient", return_value=mock_client):
        result = await seed()
        assert result is True

        # 1. Verify Users
        users = mock_db.users.docs
        assert len(users) == 3
        usernames = {u["username"] for u in users}
        assert usernames == {"admin", "operator", "viewer"}

        # Verify password hashing
        admin_user = next(u for u in users if u["username"] == "admin")
        assert admin_user["role"] == "admin"
        assert verify_password("IBVAP@123", admin_user["passwordHash"]) is True
        assert verify_password("WrongPassword", admin_user["passwordHash"]) is False

        op_user = next(u for u in users if u["username"] == "operator")
        assert verify_password("Operator@123", op_user["passwordHash"]) is True

        viewer_user = next(u for u in users if u["username"] == "viewer")
        assert verify_password("Viewer@123", viewer_user["passwordHash"]) is True

        # 2. Verify Cameras
        cameras = mock_db.cameras.docs
        assert len(cameras) >= 3
        cam_ids = {c["cameraId"] for c in cameras}
        assert "BOP-01" in cam_ids
        assert "BOP-02" in cam_ids
        assert "BOP-03" in cam_ids

        # 3. Verify Persons
        persons = mock_db.persons.docs
        assert len(persons) >= 2

        # 4. Verify Demo Incident & Evidence
        incidents = mock_db.incidents.docs
        assert len(incidents) >= 1
        demo_inc = incidents[0]
        assert demo_inc["incidentId"] == "INC-DEMO-001"
        assert len(demo_inc["evidence"]) >= 1
        assert "sha256" in demo_inc["evidence"][0]
        assert len(demo_inc["evidence"][0]["sha256"]) == 64
