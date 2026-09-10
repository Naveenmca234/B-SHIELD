# B-SHIELD

## AI-Powered Intelligent Border Surveillance

**Technical Platform Name:** IBVAP — Intelligent Border Video Analytics Platform  
**Primary End User:** Border Security Control Room Operator  
**Core Purpose:** AI-assisted border/perimeter video surveillance that detects and tracks people/vehicles, identifies authorized/unknown persons where supported, detects virtual-fence activity and abnormal movement, evaluates explainable risk, generates alerts, preserves tamper-evident evidence, supports incident response, and provides surveillance/camera health information.

> **"Transforming Existing CCTV into Intelligent Border Surveillance."**

---

### Quick Demonstration Launcher (Windows)
Run the one-command demo launcher from PowerShell:
```powershell
.\scripts\run_demo.ps1
```
Or double-click `scripts\run_demo.bat`.

---

## 1. Executive Summary & Architecture


```
CCTV / Webcam / RTSP / Uploaded Video
            │
            ▼
   OpenCV frame capture
            │
            ▼
  Object Detection (YOLOv8 if available, else OpenCV HOG/Haar fallback)
            │
            ▼
  Multi-Object Tracking (SimplifiedByteTrack — IoU-based ID association)
            │
            ▼
  Face Recognition (person) ─── ANPR / OCR (vehicle)
            │
            ▼
  Night + Motion + Visibility + Virtual-Fence analysis
            │
            ▼
  Multi-Cue Threat Engine → Risk Score (0-100) + Severity + Explanation
            │
            ▼
  WebSocket broadcast ──────────────► React Dashboard (real-time)
            │
            ▼
     MongoDB event/alert logging
```

**Design honesty note (please read):** Full YOLOv8 + real ByteTrack + dlib
face-recognition embeddings are the "gold standard" for each of these
stages, but they require large model downloads and/or compiled native
dependencies (dlib in particular can take 10+ minutes to build and isn't
reliably installable in every environment). To guarantee this project
**runs out of the box with zero extra downloads**, each AI module is built
so that:

- **Detection** (`ai/detector.py`) automatically uses YOLOv8 (`ultralytics`)
  if it's installed and weights can be loaded — otherwise it falls back to
  OpenCV's built-in HOG person detector + Haar vehicle cascade (ships with
  `opencv-python`, no download required). Both paths return the exact same
  detection schema, so nothing else in the pipeline needs to change.
- **Tracking** (`ai/tracker.py`) implements `SimplifiedByteTrack`, a real,
  working IoU-based greedy-matching tracker — the same core association
  idea ByteTrack is built on, without the Kalman-filter/native dependency
  overhead. It maintains stable IDs across frames exactly as required.
- **Face recognition** (`ai/face_recognition.py`) does real face
  *detection* (Haar cascade) and computes a real, deterministic classical
  feature-vector "embedding" (histogram + gradient descriptor) compared via
  cosine distance — genuinely different for different faces, with zero
  native compilation required. It is explicitly written to be swapped for
  `face_recognition`/dlib ResNet embeddings with no changes to any caller.
- **ANPR** (`ai/anpr.py`) does real plate region localization (edge +
  contour geometry) and real OCR via `pytesseract`, which requires the
  `tesseract-ocr` system binary — see Troubleshooting below if it's missing.
- **Visibility, motion, virtual fence, and the threat engine** are all 100%
  real, fully working OpenCV/geometry/scoring code — nothing simulated.

Anywhere the platform cannot do something for real (e.g., an RTSP camera
that isn't reachable in your environment), the UI clearly labels it
**DEMO / SIMULATION** rather than pretending it works, per the platform's
core UI-integrity requirement.

---

## 2. Tech Stack

**Backend:** Python 3.11, FastAPI (Lifespan context), WebSocket, Pydantic v2, JWT (python-jose), native bcrypt, Motor (async MongoDB), OpenCV, ReportLab (PDF Dossiers), pytesseract (ANPR), NumPy (FFT Audio DSP).

**Frontend:** React 18, Vite, Tailwind CSS, React Router, Axios, Recharts, Lucide React, i18n English/Hindi localization.

**Database:** MongoDB 6.x+.

**DevOps & Deployment:** Docker multi-stage builds, Docker Compose, GitHub Actions CI, PowerShell & Bash automation scripts.

---

## 3. Folder Structure

```
ibvap/
├── frontend/                  React 18 + Vite + Tailwind dashboard
│   ├── src/
│   │   ├── components/        Sidebar, Header, PerimeterMap, IncidentDetail, Canvas overlays
│   │   ├── pages/             Login, Dashboard, Live, Alerts, Events, Vehicles, Persons, Cameras, Settings
│   │   ├── context/           Auth, Toast, and I18n providers
│   │   ├── hooks/             useWebSocket
│   │   └── services/          api.js (Axios client)
│   ├── nginx.conf             Production Nginx web server config
│   └── Dockerfile             Multi-stage build & serve container
├── backend/
│   ├── main.py                FastAPI app with lifespan manager & CORS
│   ├── config.py              Environment settings (.env)
│   ├── routes/                REST endpoints (incidents, live, auth, cameras, alerts, ...)
│   ├── services/              video_pipeline, pdf_service, audio_detector, notifications_service, auth_service, camera_manager
│   ├── ai/                    multi_cue_engine, detector, tracker, face_recognition, anpr, intrusion, prediction
│   ├── database/              mongodb.py, seed.py
│   ├── tests/                 pytest suite (incident lifecycle, RBAC, hash verification)
│   └── Dockerfile             Python 3.11-slim container with OpenCV & Tesseract
├── docs/
│   └── judge-qa.md            Technical Evaluation & Defense Q&A
├── scripts/
│   ├── run_demo.ps1           Windows PowerShell autonomous demo runner
│   ├── run_demo.bat           Windows Command prompt demo launcher
│   └── run_demo.sh            Linux / macOS Bash demo launcher
├── .github/workflows/
│   └── ci.yml                 GitHub Actions CI workflow
├── docker-compose.yml         Full-stack container orchestration
├── .dockerignore
├── .env.example
└── README.md
```

---

## 4. Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- **MongoDB** 6.x+ (local install or MongoDB Atlas)
- *(Optional, for full ANPR OCR)* the `tesseract-ocr` system package
- *(Optional, for full YOLOv8 detection)* `pip install ultralytics` — the
  platform runs fully without this, using the OpenCV fallback detector

---

## 5. Setup

### 5.1 MongoDB

Install and start MongoDB locally, e.g. on Ubuntu:

```bash
sudo apt-get install -y mongodb
sudo systemctl start mongod
```

Or use a free MongoDB Atlas cluster and set `MONGODB_URI` accordingly.

### 5.2 Environment variables

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:
- `MONGODB_URI` — your MongoDB connection string
- `JWT_SECRET` — generate one with:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

### 5.3 Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Optional — enables real YOLOv8 detection instead of the OpenCV fallback:
# pip install ultralytics

# Seed demo users, cameras, and authorized personnel:
python -m database.seed

# Run the API server:
uvicorn main:app --reload --port 8000
```

The API will be live at `http://localhost:8000`. Interactive docs at
`http://localhost:8000/docs`.

### 5.4 Frontend

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be live at `http://localhost:5173`.

(Optional) create `frontend/.env` to point at a non-default backend:
```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000/ws
```

---

## 6. Demo Login

| Role     | Username   | Password        | Permissions |
|----------|------------|------------------|-------------|
| Admin    | `admin`    | `IBVAP@123`      | Full system access, camera/user/fence/threat configuration |
| Operator | `operator` | `Operator@123`   | Live view, alerts, ANPR, acknowledge/resolve incidents |
| Viewer   | `viewer`   | `Viewer@123`     | Read-only dashboard, live view, alerts, event history |

Passwords are bcrypt-hashed in MongoDB — never stored or exposed in
plaintext, and never present in frontend source. Auth is stateless JWT
(default 8-hour expiry, configurable via `JWT_EXPIRE_MINUTES`).

---

## 7. Using Each Camera Source

### Webcam
Create a camera with **Source Type = WEBCAM** under Camera Management (a
demo one, `BOP-01`, is seeded automatically). The backend opens local
device index 0 via OpenCV. Only one process can hold a webcam at a time.

### Uploaded video
1. Go to **Live Surveillance → Upload Sample Video** (operator/admin only).
2. Note the returned filename.
3. Create or edit a camera with **Source Type = VIDEO FILE** and paste that
   filename into the "Video Filename" field. The pipeline loops the file
   automatically once it reaches the end.

### RTSP
Create a camera with **Source Type = RTSP** and enter the full RTSP URL
(e.g. `rtsp://user:pass@192.168.1.50:554/stream1`). If the stream is
unreachable in your environment (very likely on a laptop with no real
border camera), the camera card will show **OFFLINE** with a
**DEMO / SIMULATION** tag rather than pretending to have live footage —
per the platform's no-fake-functionality requirement.

---

## 8. Configuring a Virtual Fence

1. Go to **Cameras → [camera] → Fence**.
2. Click at least 3 points directly on the live/placeholder frame to draw
   a restricted-zone polygon.
3. Click **Save Fence**. Points are stored normalized (0–1), so the zone
   stays correct at any resolution.
4. When a tracked person's foot-point falls inside the polygon, an
   `INTRUSION_DETECTED` event/alert is generated and the fence is drawn as
   an overlay on the live view.

---

## 9. Registering Authorized Demo Personnel

1. Go to **Persons → Register Person** (admin only).
2. Enter an Employee ID and name, and upload a **consented**, clear,
   front-facing demo photo.
3. The backend detects the face and stores a feature-vector "embedding."
4. On live camera feeds, any detected face is compared against all
   registered embeddings. A close match → **AUTHORIZED PERSON**; no match
   → **UNKNOWN PERSON** (never "criminal" — see Section 1).

---

## 10. How Threat Scoring Works

Every relevant contextual cue adds points to a 0–100 risk score
(`backend/ai/multi_cue_engine.py`):

| Cue                  | Default weight |
|-----------------------|----------------|
| Unknown person         | +30 |
| Night movement          | +15 |
| Fence crossing           | +30 |
| Vehicle nearby            | +10 |
| High-risk camera zone      | +15 |
| Predictive trajectory      | +15 |

Severity bands: **0–30 LOW · 31–60 MEDIUM · 61–80 HIGH · 81–100 CRITICAL**.

All weights are configurable live under **Settings → Threat Score
Configuration** (admin only) and take effect on the next processed frame.

**Predictive Trajectory Analysis:** Movement vectors are smoothed over
recent observations and projected forward toward virtual boundaries. It
flags observable velocity and trajectory intersections without speculating
on human intent.

**Poor visibility never causes a critical alert by itself.** When
visibility is `POOR` and no person is directly detected, the engine only
raises `POSSIBLE_INTRUSION` if **at least two** independent supporting cues
(motion, zone activity, vehicle/bicycle presence) are also present — it
never claims to have detected an invisible person.

Every score returned by the API includes a `breakdown` array (which cues
fired and how many points each contributed) and a plain-English
`explanation`, so operators can always see exactly why an alert fired.

---

## 11. Tamper-Evident Evidence Storage

IBVAP persists critical event frames as disk-backed files under
`snapshots/<incident_id>/` and calculates an immediate cryptographic
**SHA-256 integrity hash**.

- **Tamper Verification:** Operators can verify any preserved evidence file directly from the control room UI or via `POST /incidents/{id}/verify-evidence`. The server recalculates the SHA-256 hash from the disk file and confirms `VERIFIED` or flags `INTEGRITY_FAILED` if even a single byte was altered.
- **Path Traversal Defense:** Evidence retrieval verifies that all requested file paths strictly resolve within the canonical snapshot directory, blocking path traversal attacks.

---

## 12. Surveillance Health & Coverage Gap Intelligence

Cameras dynamically report four surveillance health states:
- **HEALTHY** (FPS >= 15, clear optics, live stream)
- **DEGRADED** (intermittent frame delay, environmental haze, moderate blur/contrast loss)
- **CRITICAL** (severe contrast loss, optical glare, frame stall > 5s)
- **OFFLINE** (stream disconnect, camera hardware unreachable)

When a camera goes offline or critically degrades, IBVAP triggers a
**Perimeter Coverage Gap** warning on the Command Center dashboard and
Cameras page, detailing the exact root cause so field technicians can be
dispatched immediately.

---

## 13. Incident Lifecycle & Response Metrics

Incidents follow a formal state machine:
`DETECTED` → `ALERTED` → `ACKNOWLEDGED` → `RESPONDING` → `RESOLVED`

- **Response Metrics:** IBVAP automatically tracks `responseTimeSeconds` (time from alert generation to first operator acknowledgment) and `resolutionTimeSeconds`.
- **Batch Actions:** Operators can select multiple active alerts and apply batch acknowledge or batch resolve operations with one click.
- **False Alarm Feedback:** Operators can provide structured feedback (`VALID_THREAT`, `FALSE_POSITIVE`, `ENVIRONMENTAL_NOISE`) with notes for continuous system tuning.

---

## 14. Automated Testing & Verification

IBVAP includes a comprehensive automated test suite with **33 passing unit and integration tests** covering all critical security and analytics modules:

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
```

| Test Module | Coverage | Status |
|---|---|---|
| `test_visibility.py` | Brightness, contrast, blur metrics, status classification (CLEAR/MODERATE/POOR) | PASS |
| `test_intrusion.py` | Ray-casting point-in-polygon algorithm, bounding box foot-point projection | PASS |
| `test_multi_cue_engine.py` | Threat weighting, score bounding [0, 100], explainability breakdown, authorized person adjustments | PASS |
| `test_prediction.py` | Segment intersection, trajectory velocity calculation, restricted zone breach projection | PASS |
| `test_evidence_integrity.py` | SHA-256 cryptographic hashing, disk verification, tampering detection, path traversal rejection | PASS |
| `test_api_auth_rbac.py` | Password hashing (bcrypt), JWT generation/expiration, RBAC route guards, live stream token auth | PASS |
| `test_night_detector.py` | Scene luminance computation, day vs night classification | PASS |
| `test_health_service.py` | Camera health state computation, latency tracking, coverage gap diagnosis | PASS |

Frontend bundle verification:
```bash
cd frontend
npm run build
```

---

## 15. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Dashboard shows "Database unavailable" | MongoDB isn't running or `MONGODB_URI` is wrong. Check `mongod` status. |
| Login fails with correct demo credentials | Did you run `python -m database.seed`? |
| Webcam camera stays OFFLINE | Another app is holding the webcam, or no webcam is present (common on servers/VMs) — this is expected and correctly reported, not a bug. |
| RTSP camera stays OFFLINE | Expected if no real RTSP camera is reachable from this machine/network — shown as DEMO/SIMULATION rather than faked. |
| ANPR never returns a plate number | `tesseract-ocr` isn't installed on the host. Install it (`sudo apt-get install tesseract-ocr` on Ubuntu, or the equivalent for your OS) and restart the backend. |
| Detection feels "classical"/less accurate than expected | You're on the OpenCV HOG/Haar fallback. Run `pip install ultralytics` inside the backend venv and restart — YOLOv8 will be used automatically, no code changes needed. |
| WebSocket won't connect | Confirm the backend is running and `VITE_WS_URL` matches its host/port; browsers require the JWT as a query param on WS handshakes (already handled). |

---

## 16. Known Limitations

- The bundled tracker, face-matching, and vehicle-detection paths are
  classical-CV, not deep-learning, unless `ultralytics`/YOLO weights are
  installed — this is a deliberate, clearly documented trade-off for
  zero-dependency runnability (see Section 1).
- ANPR accuracy depends heavily on plate angle, lighting, and the quality
  of the installed Tesseract build; it is a real OCR pipeline but not
  production-grade commercial ANPR.
- RTSP support is implemented and functional against any reachable RTSP
  URL, but no real border CCTV hardware is included — unreachable streams
  correctly show OFFLINE / DEMO-SIMULATION rather than fabricated footage.
- Face recognition uses classical Haar + descriptor matching by default;
  for deep-learning ResNet embeddings, standard weights can be mounted.

---

## 17. Security Architecture

- Passwords are hashed with bcrypt (salt rounds generated per user); plaintext passwords are never stored or logged.
- Auth is stateless JWT, validated on every protected REST route, WebSocket handshake, and live MJPEG video stream.
- All configuration secrets live in `.env` (gitignored) and are validated on startup (`validate_security_config()`); production environments reject default secrets.
- Snapshots are saved to disk with SHA-256 checksums, and path traversal attempts (`../`) are blocked with HTTP 400.
- Every mutating REST route enforces strict role-based access control (`require_admin` / `require_operator` / `require_any`).
- A single failed/misconfigured camera cannot crash the API — its pipeline fails independently, queues events to disk if DB drops, and reports `OFFLINE` with root-cause reasons.

---

## 18. Edge-Ready Software Architecture & Offline Queue

B-SHIELD incorporates a durable local disk queue backlog (`services/offline_queue.py`) providing edge-ready resilience:
- **Zero Silent Failure:** If MongoDB becomes temporarily unavailable mid-run or during network drop, active camera processing pipelines continue uninterrupted.
- **Durable File Backlog:** Events, incidents, and vehicle plate detections are serialized to `snapshots/offline_queue/` with unique event IDs.
- **Idempotent Background Synchronization:** An asynchronous worker (`start_worker`) continuously monitors database connectivity, syncing pending records without creating duplicate incidents once the database connection recovers.

---

## 19. Low-Bandwidth / Event-Only Mode

In bandwidth-constrained forward operating locations, continuous MJPEG streaming can saturate field satellite or tactical radios. B-SHIELD provides a first-class **Event-Only Mode**:
- **Operation:** Suspends the continuous video stream while keeping AI inference, real-time metadata, and tamper-evident snapshot capture fully active.
- **Operator Control:** Operators can switch between `LIVE VIDEO` and `EVENT-ONLY` mode directly from the Live Surveillance console with one click.

---

## 20. CIBMS Interoperability Contract

For integration into national Comprehensive Integrated Border Management Systems (CIBMS), B-SHIELD exposes a standardized, versioned REST and WebSocket telemetry specification:
- Complete documentation: [docs/cibms-integration.md](docs/cibms-integration.md)
- Standardized ISO 8601 UTC timestamps, four-tier severity classifications (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), and immutable SHA-256 evidence verification.
- *Classification Note:* The interface is officially defined as a **PROPOSED / INTEROPERABILITY CONTRACT**, not an active production connection to physical military infrastructure.

---

## 21. Future Scope (Planned Enhancements)

- **Optional Thermal / IR Sensor Fusion:** Ingest long-wave infrared (LWIR) camera streams alongside visible spectrum optical sensors.
- **Acoustic Sensor Triangulation:** Integrate seismic and acoustic perimeter sensors for multi-modal perimeter alerts.
- **Federated Edge Learning:** Privacy-preserving distributed model fine-tuning across border outposts.
- **Physical CIBMS Grid Gateway:** Certified hardware gateway integration with national border command networks.


