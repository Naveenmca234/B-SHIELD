"""
offline_queue.py
----------------
Offline-resilient event queuing and synchronization service for IBVAP.
Preserves local surveillance events during network/database interruptions
and synchronizes idempotently once connectivity is restored.
"""
import os
import json
import uuid
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from config import settings

logger = logging.getLogger("ibvap.offline_queue")


class OfflineEventQueue:
    def __init__(self, queue_dir: Optional[str] = None):
        self.queue_dir = queue_dir or os.path.join(settings.UPLOAD_DIR, "offline_queue")
        os.makedirs(self.queue_dir, exist_ok=True)
        self.queue_file = os.path.join(self.queue_dir, "event_backlog.json")
        self._lock = asyncio.Lock()
        self._sync_task: Optional[asyncio.Task] = None

    def _read_queue(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.queue_file):
            return []
        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Error reading offline event queue: %s", e)
            return []

    def _write_queue(self, queue: List[Dict[str, Any]]):
        try:
            tmp_file = f"{self.queue_file}.tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(queue, f, indent=2, default=str)
            os.replace(tmp_file, self.queue_file)
        except Exception as e:
            logger.error("Failed to write offline event queue: %s", e)

    async def enqueue_event(self, event_data: Dict[str, Any]) -> str:
        """Enqueues an event when database connectivity is temporarily degraded."""
        async with self._lock:
            queue = self._read_queue()
            event_id = event_data.get("incidentId") or event_data.get("eventId") or str(uuid.uuid4())
            record = {
                "queueId": str(uuid.uuid4()),
                "eventId": event_id,
                "data": event_data,
                "status": "PENDING",  # PENDING | RETRYING | SYNCED | FAILED
                "attempts": 0,
                "enqueuedAt": datetime.now(timezone.utc).isoformat(),
                "lastAttemptAt": None,
                "error": None,
            }
            queue.append(record)
            self._write_queue(queue)
            logger.info("Enqueued event %s to offline queue. Backlog size: %d", event_id, len(queue))
            return event_id

    async def flush_and_sync(self, db) -> Dict[str, Any]:
        """
        Synchronizes queued events idempotently to MongoDB.
        A retry will NOT create duplicate incidents because incidentId is unique.
        """
        if db is None:
            return {"synced": 0, "pending": len(self._read_queue()), "status": "DB_UNAVAILABLE"}

        async with self._lock:
            queue = self._read_queue()
            if not queue:
                return {"synced": 0, "pending": 0, "status": "QUEUE_EMPTY"}

            remaining = []
            synced_count = 0

            for item in queue:
                item["attempts"] += 1
                item["lastAttemptAt"] = datetime.now(timezone.utc).isoformat()
                event_doc = item["data"]
                event_id = item["eventId"]

                try:
                    # Determine collection based on document type
                    if "incidentId" in event_doc:
                        existing = await db.incidents.find_one({"incidentId": event_id})
                        if not existing:
                            # Strip any _id if present from local serializations
                            doc_copy = dict(event_doc)
                            doc_copy.pop("_id", None)
                            await db.incidents.insert_one(doc_copy)

                            # Also sync to alerts collection for backward compatibility
                            legacy_alert = dict(doc_copy)
                            legacy_alert["alertType"] = doc_copy.get("eventType")
                            if "evidence" in doc_copy and doc_copy["evidence"]:
                                legacy_alert["snapshotPath"] = doc_copy["evidence"][0].get("relativePath")
                            await db.alerts.insert_one(legacy_alert)
                    elif "plateNumber" in event_doc:
                        existing = await db.plates.find_one({
                            "plateNumber": event_doc["plateNumber"],
                            "timestamp": event_doc.get("timestamp"),
                        })
                        if not existing:
                            doc_copy = dict(event_doc)
                            doc_copy.pop("_id", None)
                            await db.plates.insert_one(doc_copy)
                    else:
                        existing = await db.events.find_one({"eventId": event_id})
                        if not existing:
                            doc_copy = dict(event_doc)
                            doc_copy.pop("_id", None)
                            await db.events.insert_one(doc_copy)

                    synced_count += 1
                    item["status"] = "SYNCED"
                except Exception as e:
                    logger.warning("Failed to sync queued event %s: %s", event_id, e)
                    item["status"] = "RETRYING" if item["attempts"] < 5 else "FAILED"
                    item["error"] = str(e)
                    remaining.append(item)

            self._write_queue(remaining)
            logger.info("Offline sync complete: %d synced, %d remaining in queue.", synced_count, len(remaining))
            return {"synced": synced_count, "pending": len(remaining), "status": "SUCCESS"}

    async def run_sync_worker(self, get_db_func, interval_seconds: float = 5.0):
        """Continuously runs in the background, flushing queued events whenever MongoDB is online."""
        logger.info("Starting offline event sync worker (interval: %.1fs)", interval_seconds)
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                db = get_db_func()
                if db is not None:
                    backlog = self._read_queue()
                    if backlog:
                        await self.flush_and_sync(db)
            except asyncio.CancelledError:
                logger.info("Offline event sync worker stopped.")
                break
            except Exception as e:
                logger.warning("Error in background offline sync worker: %s", e)

    def start_worker(self, get_db_func, interval_seconds: float = 5.0):
        if self._sync_task is None or self._sync_task.done():
            self._sync_task = asyncio.create_task(self.run_sync_worker(get_db_func, interval_seconds))

    def stop_worker(self):
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            self._sync_task = None


offline_queue = OfflineEventQueue()

