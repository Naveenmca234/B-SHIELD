"""
MongoDB connection manager using Motor (async driver).
"""
from motor.motor_asyncio import AsyncIOMotorClient
from config import settings
import logging

logger = logging.getLogger("ibvap.db")


class Database:
    client = None
    db = None
    is_mock: bool = False


database = Database()


async def connect_to_mongo():
    try:
        database.client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=2000)
        database.db = database.client[settings.MONGODB_DB_NAME]
        # Force a connection check
        await database.client.admin.command("ping")
        database.is_mock = False
        logger.info("Connected to MongoDB at %s", settings.MONGODB_URI)
        await create_indexes()
    except Exception as e:
        logger.warning(
            "Local MongoDB not available (%s). Initializing embedded in-memory database for demo/evaluation...", e
        )
        try:
            import mongomock_motor
            database.client = mongomock_motor.AsyncMongoMockClient()
            database.db = database.client[settings.MONGODB_DB_NAME]
            database.is_mock = True
            logger.info("Embedded in-memory database initialized successfully.")
            from database.seed import seed_db
            await seed_db(database.db)
            logger.info("Pre-seeded demo accounts (admin, operator, viewer), sample cameras, and demo incident.")
        except Exception as me:
            logger.error("Failed to initialize embedded database: %s", me)
            database.db = None



async def close_mongo_connection():
    if database.client:
        database.client.close()


async def create_indexes():
    db = database.db
    if db is None:
        return
    try:
        await db.incidents.create_index("incidentId", unique=True)
        await db.incidents.create_index([("status", 1), ("severity", 1)])
        await db.incidents.create_index([("cameraId", 1), ("createdAt", -1)])
        await db.events.create_index("timestamp")
        await db.events.create_index("cameraId")
        await db.events.create_index("eventType")
        await db.events.create_index("severity")
        await db.plates.create_index("plateNumber")
        await db.alerts.create_index([("status", 1), ("severity", 1)])
        await db.alerts.create_index("timestamp")
        await db.users.create_index("username", unique=True)
        await db.cameras.create_index("cameraId", unique=True)
        await db.persons.create_index("employeeId", unique=True)
        await db.evidence_audits.create_index([("evidenceId", 1), ("timestamp", -1)])
        await db.feedback_logs.create_index("incidentId")
        await db.audit_logs.create_index([("timestamp", -1), ("action", 1)])
        await db.audit_logs.create_index("username")
        await db.notifications.create_index("status")
    except Exception as e:
        logger.warning("Index creation warning: %s", e)


def get_db():
    return database.db
