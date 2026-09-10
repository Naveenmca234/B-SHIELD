"""
audit_service.py
----------------
Append-only audit trail logging for B-SHIELD / IBVAP.
Tracks administrative and operational actions with user identity, roles, timestamps,
target resources, IP addresses, and operational results.
Audit records cannot be modified or deleted via standard application APIs.
"""
import io
import csv
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger("ibvap.audit")


async def record_audit_event(
    db,
    user: Optional[Dict[str, Any]],
    action: str,
    target_type: str,
    target_id: Optional[str] = None,
    result: str = "SUCCESS",
    ip_address: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    failure_reason: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Appends an immutable audit event to MongoDB audit_logs collection.
    Defensive: failures to record audit logs are logged but never crash parent workflows.
    """
    if db is None:
        return None

    try:
        username = user.get("username", "anonymous") if user else "system"
        user_id = str(user.get("_id", user.get("id", ""))) if user else "system"
        role = user.get("role", "SYSTEM") if user else "SYSTEM"

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "username": username,
            "role": role,
            "action": action.upper(),
            "target_type": target_type.upper(),
            "target_id": str(target_id or ""),
            "result": result.upper(),
            "ip_address": ip_address or "internal",
            "metadata": metadata or {},
            "failure_reason": failure_reason,
        }

        await db.audit_logs.insert_one(event)
        event.pop("_id", None)
        return event
    except Exception as exc:
        logger.error("Failed to append audit event '%s': %s", action, exc)
        return None


async def get_audit_logs(
    db,
    page: int = 1,
    limit: int = 50,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    username: Optional[str] = None,
    result: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Queries audit logs with pagination, filtering, and search.
    """
    query: Dict[str, Any] = {}

    if action:
        query["action"] = action.upper()
    if target_type:
        query["target_type"] = target_type.upper()
    if username:
        query["username"] = {"$regex": username, "$options": "i"}
    if result:
        query["result"] = result.upper()

    date_filter: Dict[str, str] = {}
    if start_date:
        date_filter["$gte"] = start_date
    if end_date:
        date_filter["$lte"] = end_date
    if date_filter:
        query["timestamp"] = date_filter

    if search:
        query["$or"] = [
            {"username": {"$regex": search, "$options": "i"}},
            {"action": {"$regex": search, "$options": "i"}},
            {"target_id": {"$regex": search, "$options": "i"}},
            {"target_type": {"$regex": search, "$options": "i"}},
            {"ip_address": {"$regex": search, "$options": "i"}},
        ]

    total_count = await db.audit_logs.count_documents(query)
    skip = max(0, (page - 1) * limit)

    cursor = db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)

    return {
        "items": items,
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": max(1, (total_count + limit - 1) // limit),
    }


def generate_audit_csv(logs: List[Dict[str, Any]]) -> str:
    """Generates RFC-4180 compliant CSV from audit records."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Timestamp (UTC)",
        "Username",
        "Role",
        "Action",
        "Target Type",
        "Target ID",
        "Result",
        "IP Address",
        "Failure Reason",
    ])

    for log in logs:
        writer.writerow([
            log.get("timestamp", ""),
            log.get("username", ""),
            log.get("role", ""),
            log.get("action", ""),
            log.get("target_type", ""),
            log.get("target_id", ""),
            log.get("result", ""),
            log.get("ip_address", ""),
            log.get("failure_reason", "") or "—",
        ])

    return output.getvalue()
