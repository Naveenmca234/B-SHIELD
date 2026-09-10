"""
notifications_service.py
------------------------
Asynchronous, fault-isolated notification dispatch service for B-SHIELD (IBVAP).
Supports:
- Email (SMTP with TLS)
- SMS Gateway / Webhook
- Push Dispatch

CRITICAL ISOLATION RULE:
Notification dispatch is ALWAYS fire-and-forget (non-blocking). Network errors,
unreachable SMTP servers, or invalid credentials MUST NEVER block or fail the
primary surveillance pipeline, incident creation, or HTTP API responses.
"""
import asyncio
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional

import httpx

from config import settings

logger = logging.getLogger("ibvap.notifications")


class NotificationService:
    """Asynchronous notification dispatcher with total fault isolation."""

    @staticmethod
    def _format_incident_email(incident: Dict[str, Any]) -> str:
        inc_id = incident.get("incidentId", "N/A")
        cam_id = incident.get("cameraId", "N/A")
        event_type = incident.get("eventType", "SECURITY_ALERT")
        severity = incident.get("severity", "MEDIUM")
        score = incident.get("riskScore", incident.get("risk_score", "N/A"))
        time_str = incident.get("createdAt", incident.get("timestamp", "N/A"))
        loc = incident.get("location", cam_id)

        return f"""
===================================================================
B-SHIELD (IBVAP) — PRIORITY SECURITY NOTIFICATION
===================================================================

An operational security incident has been registered by the AI surveillance pipeline:

Incident ID:     {inc_id}
Sector / Camera: {cam_id} ({loc})
Event Type:      {event_type}
Severity:        {severity}
Assessed Risk:   {score} / 100
Timestamp:       {time_str}

Summary:
{incident.get('explanation', 'Real-time multi-cue threat engine trigger.')}

===================================================================
CONFIDENTIAL // BORDER DEFENSE & SURVEILLANCE OPERATIONS
Control Center Portal: {settings.FRONTEND_URL}
===================================================================
"""

    async def _send_smtp_email_async(self, recipient: str, subject: str, body: str):
        """Dispatches email via SMTP in thread pool to prevent blocking asyncio loop."""
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            logger.debug("SMTP not configured; notification skipped.")
            return

        def _do_send():
            msg = MIMEMultipart()
            msg["From"] = settings.SMTP_FROM
            msg["To"] = recipient
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)

        try:
            await asyncio.to_thread(_do_send)
            logger.info("Notification email delivered to %s", recipient)
        except Exception as e:
            logger.warning("SMTP notification delivery failed (isolated): %s", e)

    async def _send_webhook_sms_async(self, incident: Dict[str, Any]):
        """Dispatches SMS or Webhook alert payload to external gateway."""
        if not settings.SMS_WEBHOOK_URL:
            return

        payload = {
            "source": "B-SHIELD",
            "incidentId": incident.get("incidentId"),
            "severity": incident.get("severity"),
            "cameraId": incident.get("cameraId"),
            "eventType": incident.get("eventType"),
            "riskScore": incident.get("riskScore"),
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(settings.SMS_WEBHOOK_URL, json=payload)
                logger.info("SMS Webhook alert dispatched: status %d", res.status_code)
        except Exception as e:
            logger.warning("SMS webhook delivery failed (isolated): %s", e)

    def dispatch_incident_alerts(self, incident: Dict[str, Any], recipient: Optional[str] = None):
        """
        Public entrypoint: Dispatches alerts asynchronously in a detached background task.
        Guaranteed non-blocking.
        """
        if not settings.NOTIFICATION_ENABLED:
            return

        async def _runner():
            subject = f"[{incident.get('severity', 'ALERT')}] B-SHIELD Alert: {incident.get('incidentId', 'Incident')}"
            body = self._format_incident_email(incident)
            target_email = recipient or "duty-officer@b-shield.internal"

            await asyncio.gather(
                self._send_smtp_email_async(target_email, subject, body),
                self._send_webhook_sms_async(incident),
                return_exceptions=True,
            )

        try:
            asyncio.create_task(_runner())
        except Exception as e:
            logger.warning("Failed to schedule background notification task: %s", e)


notifications_service = NotificationService()
