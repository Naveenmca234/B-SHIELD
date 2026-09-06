import { useEffect, useState, useRef, useCallback } from 'react'
import { Video, Upload, Play, Square, AlertOctagon } from 'lucide-react'
import Layout from '../components/Layout'
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
  const fileRef = useRef(null)
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

  const cam = cameras.find((c) => c.cameraId === selectedCam)

  return (
    <Layout title="Live Surveillance" subtitle="Real-time AI-overlaid camera feeds" wsStatus={wsStatus}>
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
                  <div className="relative bg-black aspect-video flex items-center justify-center">
                    {cam.status === 'ONLINE' ? (
                      streamMode === 'LIVE_VIDEO' ? (
                        <img
                          src={`${API_URL}/live/stream/${cam.cameraId}${token ? `?token=${encodeURIComponent(token)}` : ''}`}
                          alt={cam.name}
                          className="w-full h-full object-contain"
                        />
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

                    <div className="absolute top-3 left-3 flex flex-wrap items-center gap-2">
                      <StatusBadge status={cam.status} />
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded font-semibold border ${
                        cam.status !== 'ONLINE'
                          ? 'bg-red-500/10 text-red-400 border-red-500/20'
                          : streamMode === 'LIVE_VIDEO'
                          ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                          : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      }`}>
                        {cam.status !== 'ONLINE' ? 'OFFLINE' : streamMode === 'LIVE_VIDEO' ? 'LIVE VIDEO' : 'EVENT-ONLY'}
                      </span>
                      {cam.health && <SurveillanceHealthBadge health={cam.health} />}
                      {detection && <VisibilityBadge status={detection.visibility?.visibilityStatus} />}
                    </div>
                    {detection && (
                      <div className="absolute top-3 right-3">
                        <SeverityBadge severity={detection.threatLevel} />
                      </div>
                    )}
                  </div>

                  <div className="p-4 flex flex-wrap items-center justify-between gap-3 border-t border-ops-border">
                    <div>
                      <h3 className="font-bold text-white text-sm">{cam.name}</h3>
                      <p className="text-xs text-ops-muted">{cam.location} • {cam.sourceType}</p>
                    </div>

                    <div className="flex items-center gap-3">
                      {cam.status === 'ONLINE' && (
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
                      )}

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
                  <h3 className="text-xs font-bold text-ops-muted uppercase mb-3">AI Detections</h3>
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
                              <span className="mono text-xs text-white bg-white/10 px-2 py-0.5 rounded flex items-center gap-1">
                                🚘 {obj.plateNumber}
                                {obj.plateStatus === 'LOW_CONFIDENCE' && <span className="text-[10px] text-amber-400">?</span>}
                              </span>
                            ) : obj.plateStatus && obj.plateStatus !== 'PLATE_NOT_LOCATED' ? (
                              <span className="mono text-[10px] text-ops-muted bg-white/5 px-1.5 py-0.5 rounded">
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
    </Layout>
  )
}
