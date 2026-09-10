# B-SHIELD (IBVAP) — Technical Evaluation & Defense Q&A

**Product Name:** B-SHIELD  
**Technical System:** IBVAP — Intelligent Border Video Analytics Platform  
**Target Users:** Border Outpost Command Centers, Law Enforcement & Perimeter Security Duty Officers  

---

### Q1: How does B-SHIELD operate under degraded field connectivity or complete network disconnects?
**Technical Reality & Architecture:**  
Remote border outposts frequently encounter satellite drops, fiber cuts, and hostile electronic warfare/jamming. B-SHIELD is architected as an **edge-first, offline-resilient platform**:
1. **Local Edge Queue (`backend/services/offline_queue.py`):** When the central database connection is lost, incoming surveillance incidents, evidence records, and ANPR plate logs are automatically buffered into a local, durable on-disk queue with monotonic sequencing.
2. **Exponential Backoff Reconnection Worker:** A persistent background worker monitors network and database connectivity. Upon link restoration, buffered events are synchronized in chronological order without duplicate emission or data loss.
3. **Event-Only Mode (Bandwidth Preservation):** Operators can toggle cameras into `EVENT_ONLY` mode via the UI, which completely suspends continuous MJPEG/RTSP video streaming over the WAN (saving 95%+ bandwidth) while keeping real-time edge AI inference, metadata broadcast, and cryptographic snapshot capture 100% active.

---

### Q2: Why is MongoDB used alongside filesystem storage for video and evidence?
**Technical Reality & Architecture:**  
Storing multi-megabyte JPEG snapshots or high-bitrate video chunks directly inside database documents (e.g. Base64 strings or BSON binary blobs) leads to severe memory bloat, storage fragmentation, slow index traversal, and database cache thrashing.
- **Storage Tier Separation:**
  - **Filesystem / Object Storage (`snapshots/`, `uploads/persons/`, `sample_videos/`):** High-throughput binary image frames and video streams are stored directly on the operating system filesystem (or mounted network storage / S3 / GCS buckets in scaled environments).
  - **MongoDB Database:** Stores structured metadata, bounding box coordinates, optical confidence scores, state machine history, and cryptographic SHA-256 hashes.
- **Forensic Reference:** Every incident record points to a deterministic relative path and its immutable SHA-256 checksum.

---

### Q3: How is tamper-evident evidence cryptographic integrity guaranteed?
**Technical Reality & Architecture:**  
In military and law enforcement jurisdictions, digital evidence must be admissible in court with an unbroken, verifiable chain of custody.
1. **Immediate Ingestion Hashing (`backend/services/evidence_service.py`):** The instant a video frame triggers an alert threshold, the binary byte array is hashed using SHA-256 *before* and *as* it is written to persistent disk storage.
2. **Immutable Record:** The computed SHA-256 checksum is stored permanently in the incident document.
3. **Real-Time On-Demand Verification Endpoint (`GET /incidents/{id}/evidence/{sha256}/verify`):** Whenever an investigator or duty officer clicks "Verify Cryptographic Hash" (or invokes the API), the server streams the raw bytes directly off the disk, computes a fresh SHA-256 hash using chunked streaming, and compares it against the stored value.
4. **Defensive Status Reporting:** If the file has been modified by even 1 bit, status returns `TAMPERED`. If deleted, it returns `FILE_NOT_FOUND` (with `tampered=True`). Every verification event is logged with operator identity into the tamper-evident evidence audit trail.

---

### Q4: How is operator alert fatigue prevented?
**Technical Reality & Architecture:**  
Surveillance operators experience severe fatigue and high miss-rates when bombarded with hundreds of repetitive alerts triggered by wild animals, swaying foliage, or rapid lighting changes.
1. **Per-Intruder Dynamic Cooldown (`ALERT_COOLDOWN_SECONDS`):** Alerts are keyed by `(cameraId, eventType, trackId)`. If an intruder remains in view for 3 minutes, the platform alerts once and updates live tracking without re-triggering duplicate critical alert chimes every 100 milliseconds.
2. **Closed-Loop Ground Truth Feedback (`backend/routes/incidents.py`):** Operators classify past alerts as `GENUINE`, `FALSE_ALARM` (with categories: wildlife, vegetation, lighting, vehicle outside perimeter, tracking re-association), or `UNCERTAIN`.
3. **Explainable Threat Thresholding:** Pure optical detections with low confidence (<0.4) automatically incur risk score deductions rather than false trigger spikes.

---

### Q5: Why is explainable multi-cue scoring chosen over end-to-end black-box deep learning?
**Technical Reality & Architecture:**  
End-to-end deep neural networks that directly output "Threat / No Threat" are black boxes: when they issue a false alarm (or miss an intrusion), defense operators cannot diagnose *why*.
- **Explainable Multi-Cue Fusion Engine (`backend/ai/multi_cue_engine.py`):**
  - **Deterministic Rule & Weight Matrix:** Combines independent, inspectable signals:
    - Optical Object Classification & Confidence (Person / Vehicle / Bicycle)
    - Identity Authentication (Authorized Personnel Facial Embedding Match vs Unknown)
    - Geospatial Boundary Intersection (Virtual Fence Polygon Crossing)
    - Predictive Trajectory Projection (Movement vector heading toward restricted line)
    - Loitering & Dwell Time Analysis (Time spent motionless or circling inside perimeter)
    - Environmental & Temporal Cues (Low light, night-time movement, optical fog/rain)
    - Acoustic DSP Signals (RMS impulse or sustained engine noise)
  - **Human-Readable Output:** Every incident includes a total score (0–100), severity (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), and a line-item point breakdown (e.g. `Unknown Person: +30`, `Fence Crossing: +30`, `High Detection Confidence: +10`).

---

### Q6: How does B-SHIELD handle camera occlusion, lens tampering, and weather degradation?
**Technical Reality & Architecture:**  
Hostile actors may spray-paint lenses, turn off IR illuminators, or cut power lines; environmental fog, sandstorms, and blizzards also degrade optical surveillance.
1. **Surveillance Health Engine (`backend/services/health_service.py`):** Evaluates every frame stream for:
   - **Signal Loss / Frozen Feeds:** Heartbeat tracking flags feeds exceeding 5.0 seconds without fresh frames as `FROZEN` or `OFFLINE`.
   - **Lens Tampering & Occlusion:** Variance analysis detects sudden uniform gray/black frames (spray paint, physical blocking, cut lines).
   - **Coverage Gap Detection:** When a critical camera drops offline or degrades, the system flags a "Perimeter Coverage Gap" and increases risk weighting on adjacent outpost cameras.
2. **Visibility Analysis (`backend/ai/visibility.py`):** Computes contrast ratio and Laplacian edge variance to classify atmospheric conditions into `CLEAR`, `MODERATE`, or `POOR`. Under `POOR` visibility, optical thresholds are adapted and secondary cues (audio, motion, trajectory) take priority.

---

### Q7: What are the latency characteristics of the real-time pipeline?
**Technical Reality & Architecture:**  
- **Frame Pipeline Offloading:** OpenCV video decoding and YOLO / HOG optical feature extraction are executed via thread-pool offloading (`asyncio.to_thread`) so CPU compute spikes never block the asyncio event loop or delay HTTP/WebSocket communications.
- **Frame-Skipping Architecture:** High-speed capture runs continuously at native camera FPS to preserve fluid rolling buffer review; full multi-cue deep inference executes on every 3rd frame, achieving a steady 15–30 FPS throughput with sub-100ms end-to-end detection latency on standard commodity x86 hardware.
- **WebSocket Streaming:** Real-time detections, bounding boxes, trajectory vectors, and camera health state are broadcast over WebSockets instantly upon frame computation.

---

### Q8: How is strict role-based access control (RBAC) enforced across API and UI?
**Technical Reality & Architecture:**  
B-SHIELD enforces role segregation across three operational levels:
- **`admin`**: Full permissions — add/edit/delete cameras, calibrate virtual fences, configure threat weights, manage personnel rosters, review full system audit logs.
- **`operator`**: Tactical command center duties — acknowledge/resolve alerts, transition incident lifecycles, log false-alarm feedback, trigger manual alarms, review live feeds and 30s rolling buffers. Cannot alter camera configurations or delete audit logs.
- **`viewer`**: Read-only oversight — monitor dashboards, view live feeds, inspect incident dossiers, verify cryptographic evidence hashes. All mutation endpoints (`POST`, `PUT`, `DELETE`) return `HTTP 403 Forbidden`.
- **Enforcement:** Enforced at both FastAPI route dependency level (`require_admin`, `require_operator`, `require_any`) and client UI level (`hasRole` guards, disabled buttons, hidden management actions).

---

### Q9: What are the current architectural limitations and future hardware roadmap?
**Honest Technical Assessment:**  
1. **Audio Sensor Scope:** Current audio intelligence implements classical DSP (RMS energy, Zero Crossing Rate, and Spectral Centroid via FFT) for acoustic anomalies (`LOUD_IMPULSE_DETECTED`, `SUSTAINED_LOUD_AUDIO`). We explicitly reject classifying specific weapons or gunshots until calibrated acoustic sensor arrays with microsecond Time-Difference-of-Arrival (TDOA) triangulation hardware are physically integrated.
2. **Edge Hardware Acceleration:** Current implementation runs OpenCV, HOG, and YOLO on CPU with multi-threading. Production field deployments target NVIDIA Jetson Orin / AGX edge hardware with TensorRT quantization for ultra-low power consumption (<25W) at remote solar-powered border poles.
3. **PTZ Slew-to-Cue:** Future iterations will support Pelco-D / ONVIF PTZ camera slew-to-cue protocols to automatically pivot optical zoom lenses toward intrusion coordinates computed by fixed perimeter cameras.
