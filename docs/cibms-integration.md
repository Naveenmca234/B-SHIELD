# B-SHIELD (IBVAP) — CIBMS Interoperability Contract

> **STATUS: PROPOSED / INTEROPERABILITY CONTRACT**  
> **CLASSIFICATION: INTEGRATION SPECIFICATION ONLY (NOT A LIVE CIBMS DEPLOYMENT)**  
> **VERSION: v1.0.0-draft**  
> **TARGET AUDIENCE: Border Command and Control / CIBMS Integration Engineers**

---

## 1. Overview & Purpose

**B-SHIELD (IBVAP — Intelligent Border Video Analytics Platform)** is designed to operate as an intelligent edge-to-command perimeter surveillance subsystem. To interoperate seamlessly with national Comprehensive Integrated Border Management Systems (CIBMS), B-SHIELD exposes a standardized, versioned, RESTful and WebSocket telemetry interface.

> [!IMPORTANT]
> This document defines the **proposed interoperability contract** for exchanging perimeter intrusion incidents, tamper-evident evidence references, camera surveillance health, and tracking telemetry with CIBMS command centers. It does **not** represent a live connection to a physical CIBMS grid in the demo/development environment.

---

## 2. Authentication & Authorization

All CIBMS integration requests must authenticate using standard Bearer tokens or mutually authenticated TLS (mTLS) with API key headers.

- **Header**: `Authorization: Bearer <CIBMS_JWT_TOKEN>`
- **Algorithm**: `HS256` or `RS256`
- **Required Claims**:
  - `sub`: Service account or operator identifier
  - `role`: Must be `admin`, `operator`, or `cibms_gateway`
  - `exp`: Standard expiration timestamp (UTC)

---

## 3. Standard Data Formats

- **Timestamp Format**: Strict ISO 8601 UTC string format: `YYYY-MM-DDTHH:MM:SS.ffffffZ` or `+00:00` offset (e.g., `2026-09-06T09:30:00.123456+00:00`).
- **Severity Levels**:
  - `LOW` (Risk score 0–30): Routine observation, authorized personnel, or low-priority movement.
  - `MEDIUM` (Risk score 31–60): Ambiguous perimeter activity or poor visibility anomaly requiring monitoring.
  - `HIGH` (Risk score 61–80): Virtual fence proximity, loitering, or unauthorized presence detected.
  - `CRITICAL` (Risk score 81–100): Confirmed virtual fence breach, restricted-zone crossing, or high-threat multi-cue intrusion.
- **Incident Lifecycle States**:
  - `DETECTED` → Initial sensor detection by AI engine.
  - `ALERTED` → Dispatched to operator console and CIBMS bus.
  - `ACKNOWLEDGED` → Acknowledged by border control room operator.
  - `RESPONDING` → Quick Response Team (QRT) / field patrol deployed.
  - `RESOLVED` → Incident verified and concluded.
  - `FALSE_ALARM` → Classified as benign (animal, vegetation, weather, shadow) with feedback rationale.

---

## 4. REST API Endpoints

### 4.1. List Incidents
`GET /api/v1/incidents`

**Query Parameters:**
- `status`: Filter by lifecycle state (`ALERTED`, `ACKNOWLEDGED`, `RESPONDING`, `RESOLVED`, `FALSE_ALARM`)
- `severity`: Filter by severity (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`)
- `cameraId`: Filter by outpost camera identifier
- `dateFrom`, `dateTo`: ISO 8601 UTC date bounds
- `page`: Integer (default `1`)
- `pageSize`: Integer (default `20`, max `200`)

**Response (200 OK):**
```json
{
  "items": [
    {
      "incidentId": "INC-20260906-A1B2C3",
      "cameraId": "BOP-01",
      "eventType": "INTRUSION_DETECTED",
      "severity": "CRITICAL",
      "riskScore": 88,
      "status": "ALERTED",
      "createdAt": "2026-09-06T09:30:00.123456+00:00",
      "updatedAt": "2026-09-06T09:30:00.123456+00:00",
      "trackingId": 14,
      "personStatus": "UNKNOWN",
      "confidence": 0.88,
      "visibility": "CLEAR",
      "explanation": "High-confidence unknown person detected and crossed the configured virtual fence during night-time hours",
      "breakdown": [
        { "label": "Fence Crossing", "points": 30 },
        { "label": "Unknown Person", "points": 30 },
        { "label": "Night Movement", "points": 15 },
        { "label": "High Detection Confidence", "points": 10 }
      ],
      "evidence": [
        {
          "evidenceId": "EV-INC-20260906-A1B2C3-7f8e9d0a",
          "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
          "relativePath": "INC-20260906-A1B2C3/20260906_093000_7f8e9d0a.jpg",
          "mimeType": "image/jpeg",
          "sizeBytes": 148290,
          "verificationStatus": "VERIFIED"
        }
      ]
    }
  ],
  "total": 1,
  "page": 1,
  "pageSize": 20
}
```

---

### 4.2. Get Incident Detail
`GET /api/v1/incidents/{incident_id}`

Retrieves complete incident record including status transition history, response time, resolution time, and operator feedback.

---

### 4.3. Verify Evidence Integrity
`GET /api/v1/incidents/{incident_id}/evidence/{evidence_id}/verify`

Computes live SHA-256 hash on disk and compares against immutable ledger hash.

**Response (200 OK):**
```json
{
  "evidenceId": "EV-INC-20260906-A1B2C3-7f8e9d0a",
  "incidentId": "INC-20260906-A1B2C3",
  "status": "VERIFIED",
  "computedHash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "storedHash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "verifiedAt": "2026-09-06T09:35:12.000000+00:00",
  "tampered": false
}
```

---

### 4.4. Fetch Evidence Snapshot File
`GET /api/v1/incidents/evidence/file/{incident_id}/{filename}`

Retrieves raw binary image (`image/jpeg`) protected by authenticated session.

---

### 4.5. Stream Real-Time Alerts
`GET /api/v1/alerts` or WebSocket `/ws`

Subscribes to live event stream:
- `intrusion_alert`: Real-time perimeter alerts
- `camera_health`: Camera health transitions (HEALTHY, DEGRADED, CRITICAL, OFFLINE)
- `anpr_detected`: Vehicle plate events

---

## 5. CIBMS Gateway Compliance Notes

1. **Idempotency**: All incident events carry a unique `incidentId`. If an upstream CIBMS receiver receives duplicate submissions due to network retry, it MUST deduplicate on `incidentId`.
2. **Evidence Chain-of-Custody**: Evidence snapshots MUST NOT be altered. Every verification access is appended to the audit trail log (`db.evidence_audits`).
3. **Bandwidth Adaptability**: In event-only or constrained satellite uplink mode, CIBMS consumers should consume metadata and snapshots rather than requesting continuous video feeds.
