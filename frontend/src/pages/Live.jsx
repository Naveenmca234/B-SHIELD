import { useEffect, useState, useRef, useCallback } from 'react'
import {
  Video, Upload, Play, Square, AlertOctagon, History, Rewind, FastForward,
  Pause, Volume2, VolumeX, ShieldAlert, Activity, Sparkles, Navigation, X
} from 'lucide-react'
import Layout from '../components/Layout'
import Modal from '../components/Modal'
import { Loading, ErrorState, DemoTag } from '../components/States'
import { StatusBadge, SeverityBadge, VisibilityBadge, SurveillanceHealthBadge } from '../components/Badges'
import api, { API_URL } from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'

export default function Live() {
  const [cameras, setCameras] = useState([])
  const [selectedCam, setSelectedCam] = useState(null)
  const [detection, setDetection] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [streamMode, setStreamMode] = useState('LIVE_VIDEO') // 'LIVE_VIDEO' | 'EVENT_ONLY'

  // Rolling Replay Buffer State
  const [replayOpen, setReplayOpen] = useState(false)
  const [replayLoading, setReplayLoading] = useState(false)
  const [replayData, setReplayData] = useState(null)
  const [currentFrameIdx, setCurrentFrameIdx] = useState(0)
  const [isPlayingReplay, setIsPlayingReplay] = useState(false)

  const fileRef = useRef(null)
  const containerRef = useRef(null)
  const canvasRef = useRef(null)
  const historyTrailsRef = useRef({}) // trackId -> [{x, y}]

  const { status: wsStatus, on } = useWebSocket()
  const { push } = useToast()
  const { hasRole, token } = useAuth()
  const canOperate = hasRole(['admin', 'operator'])

  const loadCameras = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/cameras')
      setCameras(res.data)
      if (!selectedCam && res.data.length > 0) setSelectedCam(res.data[0].cameraId)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load cameras.')
    } finally {
      setLoading(false)
    }
  }, [selectedCam])

  useEffect(() => { loadCameras() }, [])

  useEffect(() => {
    const off = on('detection_update', (data) => {
      if (data.cameraId === selectedCam) setDetection(data)
    })
    const offStatus = on('camera_status', (data) => {
      setCameras((prev) => prev.map((c) => c.cameraId === data.cameraId ? { ...c, status: data.status, error: data.error } : c))
    })
    return () => { off(); offStatus() }
  }, [on, selectedCam])

  // Sync canvas size with stream container via ResizeObserver
  useEffect(() => {
    if (!containerRef.current) return
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (canvasRef.current) {
          canvasRef.current.width = entry.contentRect.width
          canvasRef.current.height = entry.contentRect.height
        }
      }
    })
    ro.observe(containerRef.current)
    return () => ro.disconnect()
  }, [])

  // Real-time Canvas Bounding Box & Vector Overlays
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    ctx.clearRect(0, 0, canvas.width, canvas.height)
    if (!detection || streamMode !== 'LIVE_VIDEO') return

    const frameW = detection.frameWidth || 640
    const frameH = detection.frameHeight || 480
    const scaleX = canvas.width / frameW
    const scaleY = canvas.height / frameH

    const objects = detection.objects || []
    const currentIds = new Set(objects.map((o) => o.trackId))

    // Prune lost tracks
    for (const id in historyTrailsRef.current) {
      if (!currentIds.has(Number(id)) && !currentIds.has(String(id))) {
        delete historyTrailsRef.current[id]
      }
    }

    objects.forEach((obj) => {
      if (!obj.bbox || obj.bbox.length < 4) return
      const [x1, y1, x2, y2] = obj.bbox
      const bx = x1 * scaleX
      const by = y1 * scaleY
      const bw = (x2 - x1) * scaleX
      const bh = (y2 - y1) * scaleY
      const cx = bx + bw / 2
      const cy = by + bh / 2

      // Track motion trail points
      const trackId = obj.trackId
      if (!historyTrailsRef.current[trackId]) {
        historyTrailsRef.current[trackId] = []
      }
      historyTrailsRef.current[trackId].push({ x: cx, y: cy })
      if (historyTrailsRef.current[trackId].length > 10) {
        historyTrailsRef.current[trackId].shift()
      }

      // Color scheme based on classification and threat level
      let strokeColor = '#38bdf8' // cyan
      let fillColor = 'rgba(56, 189, 248, 0.08)'

      if (obj.class === 'person') {
        if (obj.status === 'AUTHORIZED') {
          strokeColor = '#22c55e' // Green
          fillColor = 'rgba(34, 197, 94, 0.1)'
        } else if (obj.status === 'UNKNOWN') {
          strokeColor = '#f97316' // Orange / Amber
          fillColor = 'rgba(249, 115, 22, 0.12)'
        }
      } else if (['car', 'truck', 'bus', 'vehicle', 'motorcycle'].includes(obj.class)) {
        strokeColor = '#a855f7' // Purple
        fillColor = 'rgba(168, 85, 247, 0.1)'
      }

      if (obj.severity === 'CRITICAL' || obj.severity === 'HIGH') {
        strokeColor = '#ef4444' // Crimson
        fillColor = 'rgba(239, 68, 68, 0.14)'
      }

      // 1. Draw motion trail
      const trail = historyTrailsRef.current[trackId]
      if (trail && trail.length > 1) {
        ctx.beginPath()
        ctx.moveTo(trail[0].x, trail[0].y)
        for (let i = 1; i < trail.length; i++) {
          ctx.lineTo(trail[i].x, trail[i].y)
        }
        ctx.strokeStyle = strokeColor
        ctx.lineWidth = 1.5
        ctx.setLineDash([2, 3])
        ctx.stroke()
        ctx.setLineDash([])

        trail.forEach((pt, i) => {
          ctx.beginPath()
          ctx.arc(pt.x, pt.y, 2, 0, Math.PI * 2)
          ctx.fillStyle = strokeColor
          ctx.globalAlpha = 0.2 + (i / trail.length) * 0.8
          ctx.fill()
          ctx.globalAlpha = 1.0
        })
      }

      // 2. Draw bounding box with corner accents
      ctx.strokeStyle = strokeColor
      ctx.lineWidth = 2
      ctx.fillStyle = fillColor
      ctx.fillRect(bx, by, bw, bh)
      ctx.strokeRect(bx, by, bw, bh)

      const cLen = Math.min(10, bw / 4, bh / 4)
      ctx.lineWidth = 3
      // Top-left
      ctx.beginPath()
      ctx.moveTo(bx, by + cLen); ctx.lineTo(bx, by); ctx.lineTo(bx + cLen, by)
      ctx.stroke()
      // Top-right
      ctx.beginPath()
      ctx.moveTo(bx + bw - cLen, by); ctx.lineTo(bx + bw, by); ctx.lineTo(bx + bw, by + cLen)
      ctx.stroke()
      // Bottom-left
      ctx.beginPath()
      ctx.moveTo(bx, by + bh - cLen); ctx.lineTo(bx, by + bh); ctx.lineTo(bx + cLen, by + bh)
      ctx.stroke()
      // Bottom-right
      ctx.beginPath()
      ctx.moveTo(bx + bw - cLen, by + bh); ctx.lineTo(bx + bw, by + bh); ctx.lineTo(bx + bw, by + bh - cLen)
      ctx.stroke()

      // 3. Label badge
      let labelText = `${obj.class.toUpperCase()} #${obj.trackId}`
      if (obj.class === 'person') {
        labelText = obj.name || (obj.status ? `${obj.status} #${obj.trackId}` : `PERSON #${obj.trackId}`)
      } else if (obj.plateNumber) {
        labelText = `🚘 ${obj.plateNumber}`
      }
      const confText = obj.confidence ? ` ${Math.round(obj.confidence * 100)}%` : ''
      const fullLabel = `${labelText}${confText}`

      ctx.font = 'bold 10px monospace'
      const textMetrics = ctx.measureText(fullLabel)
      const pad = 4
      const badgeW = textMetrics.width + pad * 2
      const badgeH = 15
      const badgeY = Math.max(0, by - badgeH - 2)

      ctx.fillStyle = strokeColor
      ctx.fillRect(bx, badgeY, badgeW, badgeH)
      ctx.fillStyle = '#0a0e1a'
      ctx.fillText(fullLabel, bx + pad, badgeY + 11)

      // 4. Direction vector arrow
      const traj = obj.trajectory
      if (traj && (traj.heading || traj.vector)) {
        let angle = 0
        if (traj.heading === 'approaching') angle = Math.PI / 2
        else if (traj.heading === 'receding') angle = -Math.PI / 2
        else if (traj.heading === 'left') angle = Math.PI
        else if (traj.heading === 'right') angle = 0
        else if (traj.vector && (traj.vector.dx || traj.vector.dy)) {
          angle = Math.atan2(traj.vector.dy, traj.vector.dx)
        }

        const arrowLen = 20
        const ex = cx + Math.cos(angle) * arrowLen
        const ey = cy + Math.sin(angle) * arrowLen

        ctx.beginPath()
        ctx.moveTo(cx, cy)
        ctx.lineTo(ex, ey)
        ctx.strokeStyle = '#38bdf8'
        ctx.lineWidth = 2
        ctx.stroke()

        const tipLen = 5
        ctx.beginPath()
        ctx.moveTo(ex, ey)
        ctx.lineTo(ex - tipLen * Math.cos(angle - Math.PI / 6), ey - tipLen * Math.sin(angle - Math.PI / 6))
        ctx.moveTo(ex, ey)
        ctx.lineTo(ex - tipLen * Math.cos(angle + Math.PI / 6), ey - tipLen * Math.sin(angle + Math.PI / 6))
        ctx.stroke()
      }
    })
  }, [detection, streamMode])

  async function handleUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      await api.post('/live/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
      push('Video uploaded. Assign it to a camera under Camera Management.', 'success')
    } catch (e) {
      push(e.response?.data?.detail || 'Upload failed.', 'error')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  async function togglePipeline(camId, isOnline) {
    try {
      await api.post(`/live/${isOnline ? 'stop' : 'start'}/${camId}`)
      push(`Camera pipeline ${isOnline ? 'stopped' : 'started'}.`, 'success')
      loadCameras()
    } catch (e) {
      push(e.response?.data?.detail || 'Action failed.', 'error')
    }
  }

  // 30s Rolling Replay Buffer Loader
  async function openReplay() {
    if (!cam) return
    setReplayLoading(true)
    setReplayOpen(true)
    setIsPlayingReplay(false)
    try {
      const res = await api.get(`/live/${cam.cameraId}/replay`)
      setReplayData(res.data)
      setCurrentFrameIdx(Math.max(0, (res.data.frames?.length || 1) - 1))
    } catch (e) {
      push(e.response?.data?.detail || 'Failed to retrieve replay buffer.', 'error')
      setReplayOpen(false)
    } finally {
      setReplayLoading(false)
    }
  }

  // Replay play/pause animation
  useEffect(() => {
    let timer = null
    if (isPlayingReplay && replayData?.frames?.length > 0) {
      timer = setInterval(() => {
        setCurrentFrameIdx((prev) => (prev + 1) % replayData.frames.length)
      }, 150)
    }
    return () => clearInterval(timer)
  }, [isPlayingReplay, replayData])

  const cam = cameras.find((c) => c.cameraId === selectedCam)

  return (
    <Layout title="Live Surveillance" subtitle="Real-time AI-overlaid camera feeds & sensor telemetry" wsStatus={wsStatus}>
      {loading ? <Loading label="Loading cameras…" /> : error ? <ErrorState message={error} onRetry={loadCameras} /> : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Camera selector */}
          <div className="lg:col-span-1 glass-panel rounded-xl p-4 space-y-2 h-fit">
            <h3 className="text-xs font-bold text-ops-muted uppercase mb-2">Cameras</h3>
            {cameras.map((c) => (
              <button
                key={c.cameraId}
                onClick={() => setSelectedCam(c.cameraId)}
                className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition flex items-center justify-between ${
                  selectedCam === c.cameraId ? 'bg-ops-accent/15 border border-ops-accent/30 text-white' : 'hover:bg-white/5 text-ops-muted border border-transparent'
                }`}
              >
                <span className="truncate">{c.name}</span>
                <span className={`w-2 h-2 rounded-full ${c.status === 'ONLINE' ? 'bg-green-400' : 'bg-red-400'}`} />
              </button>
            ))}

            {canOperate && (
              <div className="pt-3 mt-3 border-t border-ops-border">
                <label className="flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg text-xs font-semibold bg-white/5 hover:bg-white/10 cursor-pointer text-ops-text">
                  <Upload className="w-3.5 h-3.5" />
                  {uploading ? 'Uploading…' : 'Upload Sample Video'}
                  <input ref={fileRef} type="file" accept=".mp4,.avi,.mov,.mkv" className="hidden" onChange={handleUpload} disabled={uploading} />
                </label>
              </div>
            )}
          </div>

          {/* Video + overlay */}
          <div className="lg:col-span-3 space-y-4">
            {!cam ? (
              <div className="glass-panel rounded-xl p-12 text-center text-ops-muted">
                <Video className="w-8 h-8 mx-auto mb-2 opacity-40" />
                No camera selected.
              </div>
            ) : (
              <>
                <div className="glass-panel rounded-xl overflow-hidden">
                  <div ref={containerRef} className="relative bg-black aspect-video flex items-center justify-center overflow-hidden">
                    {cam.status === 'ONLINE' ? (
                      streamMode === 'LIVE_VIDEO' ? (
                        <>
                          <img
                            src={`${API_URL}/live/stream/${cam.cameraId}${token ? `?token=${encodeURIComponent(token)}` : ''}`}
                            alt={cam.name}
                            className="w-full h-full object-contain"
                          />
                          {/* Real-time Canvas overlay for bounding boxes, auth badges & vector arrows */}
                          <canvas
                            ref={canvasRef}
                            className="absolute inset-0 w-full h-full pointer-events-none z-10"
                          />
                        </>
                      ) : (
                        <div className="flex flex-col items-center gap-3 text-ops-muted p-8 text-center max-w-md">
                          <div className="w-12 h-12 rounded-full bg-ops-accent/15 border border-ops-accent/30 flex items-center justify-center text-ops-accent2">
                            <Video className="w-6 h-6 opacity-80" />
                          </div>
                          <div>
                            <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-1">EVENT-ONLY MODE (LOW BANDWIDTH)</h4>
                            <p className="text-xs text-ops-muted">Continuous video streaming suspended to preserve field network bandwidth. Real-time metadata, AI triggers, and snapshot evidence remain active.</p>
                          </div>
                          <button
                            onClick={() => setStreamMode('LIVE_VIDEO')}
                            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-ops-accent text-white hover:bg-ops-accent/80 transition"
                          >
                            Switch to Live Video
                          </button>
                        </div>
                      )
                    ) : (
                      <div className="flex flex-col items-center gap-3 text-ops-muted p-8 text-center">
                        <AlertOctagon className="w-10 h-10 opacity-40" />
                        <p className="text-sm">{cam.error || 'Camera is currently offline.'}</p>
                        {cam.sourceType === 'RTSP' && <DemoTag />}
                      </div>
                    )}

                    {/* Top-left Badges */}
                    <div className="absolute top-3 left-3 flex flex-wrap items-center gap-2 z-20">
                      <StatusBadge status={cam.status} />
                      {cam.status === 'ONLINE' ? (
                        <>
                          <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${
                            streamMode === 'LIVE_VIDEO'
                              ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                              : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                          }`}>
                            {streamMode === 'LIVE_VIDEO' ? 'LIVE VIDEO' : 'EVENT-ONLY'}
                          </span>
                          {cam.health && <SurveillanceHealthBadge health={cam.health} />}
                          <VisibilityBadge status={detection?.visibility?.visibilityStatus || 'CLEAR'} />
                          {/* Audio Anomaly Badge */}
                          {detection?.audio?.is_anomaly && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1 animate-pulse">
                              <Volume2 className="w-3 h-3 text-amber-400" />
                              {detection.audio.classification === 'LOUD_IMPULSE_DETECTED' ? 'AUDIO IMPULSE' : 'LOUD AUDIO'}
                            </span>
                          )}
                        </>
                      ) : (
                        <>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-white/5 border border-ops-border text-ops-muted">
                            Visibility: UNKNOWN
                          </span>
                          {(cam.sourceType === 'RTSP' || cam.sourceType === 'VIDEO_FILE') && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 font-mono">
                              DEMO / SIMULATION
                            </span>
                          )}
                        </>
                      )}
                    </div>

                    {/* Top-right Threat Level */}
                    {cam.status === 'ONLINE' && detection && (
                      <div className="absolute top-3 right-3 z-20">
                        <SeverityBadge severity={detection.threatLevel} />
                      </div>
                    )}
                  </div>

                  {/* Camera Controls & Toolbar */}
                  <div className="p-4 flex flex-wrap items-center justify-between gap-3 border-t border-ops-border">
                    <div>
                      <h3 className="font-bold text-white text-sm">{cam.name}</h3>
                      <p className="text-xs text-ops-muted">{cam.location} • {cam.sourceType}</p>
                    </div>

                    <div className="flex items-center gap-2.5">
                      {/* 30s Rolling Replay Button */}
                      {cam.status === 'ONLINE' && (
                        <button
                          onClick={openReplay}
                          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-ops-accent/20 text-ops-accent2 hover:bg-ops-accent/30 border border-ops-accent/40 transition"
                          title="Review rolling 30-second forensic frame buffer"
                        >
                          <History className="w-3.5 h-3.5" />
                          <span>30s Replay Buffer</span>
                        </button>
                      )}

                      {cam.status === 'ONLINE' ? (
                        <div className="flex items-center rounded-lg bg-white/5 p-0.5 border border-ops-border text-xs">
                          <button
                            onClick={() => setStreamMode('LIVE_VIDEO')}
                            className={`px-2.5 py-1 rounded-md transition ${
                              streamMode === 'LIVE_VIDEO' ? 'bg-ops-accent text-white font-semibold' : 'text-ops-muted hover:text-white'
                            }`}
                          >
                            Live Video
                          </button>
                          <button
                            onClick={() => setStreamMode('EVENT_ONLY')}
                            className={`px-2.5 py-1 rounded-md transition ${
                              streamMode === 'EVENT_ONLY' ? 'bg-ops-accent text-white font-semibold' : 'text-ops-muted hover:text-white'
                            }`}
                          >
                            Event-Only
                          </button>
                        </div>
                      ) : null}

                      {canOperate && (
                        <button
                          onClick={() => togglePipeline(cam.cameraId, cam.status === 'ONLINE')}
                          className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold ${
                            cam.status === 'ONLINE' ? 'bg-red-500/15 text-red-400 hover:bg-red-500/25' : 'bg-green-500/15 text-green-400 hover:bg-green-500/25'
                          }`}
                        >
                          {cam.status === 'ONLINE' ? <Square className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                          {cam.status === 'ONLINE' ? 'Stop Pipeline' : 'Start Pipeline'}
                        </button>
                      )}
                    </div>
                  </div>
                </div>

                {/* Acoustic & Environmental Sensor Telemetry */}
                {detection?.audio && (
                  <div className="glass-panel rounded-xl p-3.5 border border-ops-border flex flex-wrap items-center justify-between gap-3 text-xs">
                    <div className="flex items-center gap-2">
                      <Volume2 className={`w-4 h-4 ${detection.audio.is_anomaly ? 'text-amber-400 animate-pulse' : 'text-ops-accent2'}`} />
                      <span className="font-bold text-white uppercase tracking-wider text-[11px]">Acoustic DSP Telemetry:</span>
                      <span className="text-ops-muted">{detection.audio.description}</span>
                    </div>
                    <div className="flex items-center gap-3 font-mono text-[11px]">
                      <span className="text-ops-muted">RMS: <span className="text-white font-bold">{detection.audio.rms_db} dBFS</span></span>
                      <span className="text-ops-muted">Centroid: <span className="text-white font-bold">{detection.audio.spectral_centroid_hz} Hz</span></span>
                      <span className="text-ops-muted">ZCR: <span className="text-white font-bold">{detection.audio.zcr}</span></span>
                    </div>
                  </div>
                )}

                {/* Trajectory & Threat Predictions Banner if active */}
                {detection?.trajectories && Object.keys(detection.trajectories).length > 0 && (
                  <div className="glass-panel rounded-xl p-4 border border-amber-500/30 bg-amber-500/5">
                    <h3 className="text-xs font-bold text-amber-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
                      Observed Movement Vectors & Virtual Fence Proximity
                    </h3>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {Object.entries(detection.trajectories).map(([trackId, traj]) => (
                        <div key={trackId} className="text-xs p-2.5 rounded bg-black/40 border border-ops-border">
                          <div className="font-mono text-ops-accent2 font-semibold">Track #{trackId}</div>
                          <div className="text-ops-muted mt-0.5">
                            Heading: {traj.heading || 'approaching'} • Velocity: {typeof traj.speed === 'number' ? `${traj.speed.toFixed(1)} px/s` : 'active'}
                          </div>
                          {traj.predictedFenceBreach && (
                            <div className="text-rose-400 font-medium mt-1">
                              ⚠ Vector projects toward perimeter boundary (~{traj.etaSeconds || 'few'}s)
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Detection overlay info panel */}
                <div className="glass-panel rounded-xl p-4">
                  <h3 className="text-xs font-bold text-ops-muted uppercase mb-3">AI Detections & Tracking</h3>
                  {!detection || !detection.objects?.length ? (
                    <p className="text-sm text-ops-muted">No objects currently detected on this feed.</p>
                  ) : (
                    <div className="space-y-2">
                      {detection.objects.map((obj) => (
                        <div key={`${obj.class}-${obj.trackId}`} className="flex items-center justify-between p-3 rounded-lg bg-white/[0.03] text-sm">
                          <div className="flex items-center gap-3">
                            <span className="font-mono text-xs text-ops-accent2">
                              {obj.class.toUpperCase()} #{obj.trackId}
                            </span>
                            <span className="text-ops-muted text-xs">Confidence: {Math.round((obj.confidence || 0) * 100)}%</span>
                            {obj.status && <StatusBadge status={obj.status} />}
                            {obj.plateNumber ? (
                              <span className="font-mono text-xs text-white bg-white/10 px-2 py-0.5 rounded flex items-center gap-1">
                                🚘 {obj.plateNumber}
                                {obj.plateStatus === 'LOW_CONFIDENCE' && <span className="text-[10px] text-amber-400">?</span>}
                              </span>
                            ) : obj.plateStatus && obj.plateStatus !== 'PLATE_NOT_LOCATED' ? (
                              <span className="font-mono text-[10px] text-ops-muted bg-white/5 px-1.5 py-0.5 rounded">
                                {obj.plateStatus === 'OCR_UNAVAILABLE' ? 'OCR N/A' : obj.plateStatus}
                              </span>
                            ) : null}
                          </div>
                          {obj.threatScore !== undefined && <SeverityBadge severity={obj.severity} />}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* 30-Second Rolling Replay Buffer Modal */}
      <Modal
        open={replayOpen}
        onClose={() => { setReplayOpen(false); setIsPlayingReplay(false); }}
        title={`30-Second Rolling Buffer Review — ${cam?.name || ''}`}
        wide
      >
        <div className="space-y-4">
          {replayLoading ? (
            <Loading label="Retrieving rolling replay frames from buffer…" />
          ) : !replayData || !replayData.frames?.length ? (
            <div className="text-center py-12 text-ops-muted text-sm">
              No frames recorded in rolling replay buffer yet. Camera must be online.
            </div>
          ) : (
            <div className="space-y-4">
              {/* Frame Viewport */}
              <div className="relative bg-black aspect-video rounded-lg overflow-hidden flex items-center justify-center border border-ops-border">
                <img
                  src={replayData.frames[currentFrameIdx]?.frame}
                  alt={`Replay frame ${currentFrameIdx}`}
                  className="w-full h-full object-contain"
                />
                <div className="absolute top-3 left-3 bg-black/70 backdrop-blur px-2.5 py-1 rounded text-xs font-mono text-white border border-white/10">
                  Frame {currentFrameIdx + 1} / {replayData.frames.length}
                </div>
                <div className="absolute top-3 right-3 bg-black/70 backdrop-blur px-2.5 py-1 rounded text-xs font-mono text-ops-accent2 border border-white/10">
                  {replayData.frames[currentFrameIdx]?.iso ? new Date(replayData.frames[currentFrameIdx].iso).toLocaleTimeString() : ''}
                </div>
              </div>

              {/* Scrubber Controls */}
              <div className="p-3 rounded-lg bg-white/5 border border-ops-border space-y-2">
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => setIsPlayingReplay(!isPlayingReplay)}
                    className="p-2 rounded-lg bg-ops-accent text-white hover:bg-ops-accent/80 transition"
                  >
                    {isPlayingReplay ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                  </button>

                  <input
                    type="range"
                    min="0"
                    max={replayData.frames.length - 1}
                    value={currentFrameIdx}
                    onChange={(e) => {
                      setIsPlayingReplay(false)
                      setCurrentFrameIdx(parseInt(e.target.value, 10))
                    }}
                    className="w-full accent-ops-accent cursor-pointer"
                  />

                  <span className="font-mono text-xs text-white min-w-[50px] text-right">
                    {Math.round((currentFrameIdx / Math.max(1, replayData.frames.length - 1)) * (replayData.durationSeconds || 30))}s
                  </span>
                </div>

                <div className="flex items-center justify-between text-[11px] text-ops-muted font-mono">
                  <span>- {replayData.durationSeconds || 30}s (Past)</span>
                  <span>Scrub back and forth to inspect pre-incident movement</span>
                  <span>Live (0s)</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </Modal>
    </Layout>
  )
}
