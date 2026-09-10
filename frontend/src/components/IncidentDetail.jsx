import { useState } from 'react'
import Modal from './Modal'
import { SeverityBadge, StatusBadge, VisibilityBadge, formatEventType } from './Badges'
import { ShieldCheck, ShieldAlert, CheckCircle2, Clock, ThumbsDown, ArrowUpRight, Loader2, FileDown } from 'lucide-react'
import api, { API_URL } from '../services/api'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'

const LIFECYCLE_STEPS = ['DETECTED', 'ALERTED', 'ACKNOWLEDGED', 'RESPONDING', 'RESOLVED']

export default function IncidentDetail({ open, onClose, incident, onUpdated }) {
  const { user } = useAuth()
  const canAct = user?.role === 'admin' || user?.role === 'operator'
  const [verifying, setVerifying] = useState(false)
  const [verifyResult, setVerifyResult] = useState(null)
  const [transitioning, setTransitioning] = useState(false)
  const [exportingPdf, setExportingPdf] = useState(false)
  const [showFeedback, setShowFeedback] = useState(false)
  const [feedbackClass, setFeedbackClass] = useState('FALSE_ALARM')
  const [feedbackReason, setFeedbackReason] = useState('animal')
  const { push } = useToast()


  if (!incident) return null

  const evidence = incident.evidence?.[0] || {}
  const sha256 = evidence.sha256 || incident.sha256
  const trajectory = incident.trajectory || {}
  const token = localStorage.getItem('ibvap_token')
  const snapshotUrl = incident.snapshot || incident.thumbnail || (
    evidence.relativePath ? `${API_URL}/incidents/evidence/file/${evidence.relativePath}${token ? `?token=${encodeURIComponent(token)}` : ''}` : null
  )

  async function handleTransition(newStatus) {
    setTransitioning(true)
    try {
      if (newStatus === 'ACKNOWLEDGED') {
        await api.put(`/alerts/${incident.incidentId || incident._id}/acknowledge`)
      } else if (newStatus === 'RESOLVED') {
        await api.put(`/alerts/${incident.incidentId || incident._id}/resolve`)
      } else {
        await api.put(`/incidents/${incident.incidentId || incident._id}/transition`, { status: newStatus })
      }
      push(`Incident successfully transitioned to ${newStatus}.`, 'success')
      if (onUpdated) onUpdated()
      onClose()
    } catch (e) {
      push(e.response?.data?.detail || 'Transition failed.', 'error')
    } finally {
      setTransitioning(false)
    }
  }

  async function handleVerifyHash() {
    if (!incident.incidentId || !sha256) {
      push('No cryptographic evidence hash found for this incident.', 'error')
      return
    }
    setVerifying(true)
    try {
      const res = await api.get(`/incidents/${incident.incidentId}/evidence/${sha256}/verify`)
      setVerifyResult(res.data)
      if (res.data.status === 'VERIFIED') {
        push('Evidence cryptographically verified: SHA-256 hash matches disk payload.', 'success')
      } else if (res.data.status === 'FILE_NOT_FOUND') {
        push('INTEGRITY FAILURE: Evidence file missing from disk.', 'error')
      } else {
        push('INTEGRITY WARNING: Evidence payload hash does not match stored hash!', 'error')
      }
    } catch (e) {
      push(e.response?.data?.detail || 'Evidence verification failed.', 'error')
    } finally {
      setVerifying(false)
    }
  }

  async function handleDownloadPdf() {
    setExportingPdf(true)
    try {
      const incId = incident.incidentId || incident._id
      const res = await api.get(`/incidents/${incId}/report.pdf`, {
        responseType: 'blob',
      })
      const blobUrl = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
      const link = document.createElement('a')
      link.href = blobUrl
      link.setAttribute('download', `Incident_${incId}_Dossier.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(blobUrl)
      push('Incident PDF dossier generated and downloaded successfully.', 'success')
    } catch (e) {
      push(e.response?.data?.detail || 'Failed to generate PDF dossier.', 'error')
    } finally {
      setExportingPdf(false)
    }
  }

  async function handleFeedbackSubmit(e) {
    e.preventDefault()
    try {
      await api.post(`/incidents/${incident.incidentId}/feedback`, {
        classification: feedbackClass,
        reason: feedbackClass === 'FALSE_ALARM' ? feedbackReason : null,
      })
      push('Operator feedback recorded successfully.', 'success')
      setShowFeedback(false)
      if (onUpdated) onUpdated()
    } catch (e) {
      push(e.response?.data?.detail || 'Failed to submit feedback.', 'error')
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`${incident.incidentId || 'INCIDENT'} — ${incident.cameraId}${incident.location ? ` (${incident.location})` : ''}`}
      wide
    >
      <div className="space-y-5">
        {/* Badges & Status */}
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ops-border pb-3">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={incident.severity} />
            <StatusBadge status={incident.status || 'ALERTED'} />
            {incident.isDemoIncident && (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                DEMO RECORD
              </span>
            )}
            {incident.personStatus && <StatusBadge status={incident.personStatus} />}
            {incident.visibility && <VisibilityBadge status={incident.visibility} />}
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={handleDownloadPdf}
              disabled={exportingPdf}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-semibold bg-ops-accent/20 text-ops-accent2 hover:bg-ops-accent/30 border border-ops-accent/40 transition disabled:opacity-50"
              title="Download official PDF Incident Dossier"
            >
              {exportingPdf ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <FileDown className="w-3.5 h-3.5" />
              )}
              <span>{exportingPdf ? 'Generating...' : 'Export PDF'}</span>
            </button>

            {incident.responseTimeSeconds !== null && incident.responseTimeSeconds !== undefined && (
              <div className="flex items-center gap-1 text-xs text-ops-muted font-mono">
                <Clock className="w-3.5 h-3.5 text-ops-accent2" />
                Response: <span className="text-white font-bold">{incident.responseTimeSeconds}s</span>
                {incident.resolutionTimeSeconds !== null && (
                  <>
                    {' '}• Resolution: <span className="text-white font-bold">{incident.resolutionTimeSeconds}s</span>
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Incident Lifecycle Timeline Stepper */}
        <div className="bg-white/[0.02] p-3 rounded-xl border border-ops-border">
          <div className="text-[10px] font-bold uppercase text-ops-muted tracking-wider mb-2.5">
            Operational Lifecycle
          </div>
          <div className="flex items-center justify-between relative">
            {LIFECYCLE_STEPS.map((step, idx) => {
              const currIdx = LIFECYCLE_STEPS.indexOf(incident.status || 'ALERTED')
              const isPast = idx <= (currIdx === -1 ? 1 : currIdx)
              const isCurrent = (incident.status || 'ALERTED') === step
              return (
                <div key={step} className="flex flex-col items-center z-10">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-mono font-bold transition-all ${
                      isCurrent
                        ? 'bg-ops-accent text-white shadow-glow'
                        : isPast
                        ? 'bg-ops-accent2/20 text-ops-accent2 border border-ops-accent2/40'
                        : 'bg-white/5 text-ops-muted border border-ops-border'
                    }`}
                  >
                    {idx + 1}
                  </div>
                  <span
                    className={`text-[9px] mt-1 tracking-tight font-semibold ${
                      isCurrent ? 'text-white' : isPast ? 'text-ops-text' : 'text-ops-muted'
                    }`}
                  >
                    {step}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Incident Response Controls (Admin/Operator only) */}
        {canAct && (
          <div className="bg-white/[0.04] p-3 rounded-xl border border-ops-border flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[10px] uppercase font-bold text-ops-muted tracking-wider">Operator Response Actions</div>
              <div className="text-xs text-white/80 mt-0.5">
                Current Status: <span className="font-bold text-white">{incident.status || 'ALERTED'}</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {(incident.status === 'ALERTED' || incident.status === 'DETECTED' || incident.status === 'NEW') && (
                <button
                  onClick={() => handleTransition('ACKNOWLEDGED')}
                  disabled={transitioning}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-amber-600 hover:bg-amber-500 text-white transition flex items-center gap-1.5 shadow"
                >
                  {transitioning && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Acknowledge Incident
                </button>
              )}
              {incident.status === 'ACKNOWLEDGED' && (
                <>
                  <button
                    onClick={() => handleTransition('RESPONDING')}
                    disabled={transitioning}
                    className="px-3 py-1.5 rounded-lg text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white transition flex items-center gap-1.5 shadow"
                  >
                    {transitioning && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Dispatch Response
                  </button>
                  <button
                    onClick={() => handleTransition('RESOLVED')}
                    disabled={transitioning}
                    className="px-3 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition flex items-center gap-1.5 shadow"
                  >
                    {transitioning && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                    Resolve
                  </button>
                </>
              )}
              {incident.status === 'RESPONDING' && (
                <button
                  onClick={() => handleTransition('RESOLVED')}
                  disabled={transitioning}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition flex items-center gap-1.5 shadow"
                >
                  {transitioning && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  Resolve Incident
                </button>
              )}
              {incident.status === 'RESOLVED' && (
                <span className="text-xs text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-4 h-4" /> Incident Resolved
                </span>
              )}
            </div>
          </div>
        )}

        {/* Evidence Snapshot */}
        {snapshotUrl && (
          <div className="space-y-1.5">
            <img
              src={snapshotUrl}
              alt="Evidence Snapshot"
              className="w-full max-h-72 object-contain bg-black rounded-lg border border-ops-border"
            />
          </div>
        )}

        {/* Details Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs bg-white/[0.02] p-3.5 rounded-lg border border-ops-border">
          <Field label="Incident Type" value={formatEventType(incident.eventType || incident.alertType)} />
          <Field label="Camera Outpost" value={`${incident.cameraId}${incident.cameraName ? ` — ${incident.cameraName}` : ''}`} />
          <Field label="Location / Zone" value={incident.location || incident.zone || 'Restricted Perimeter Sector'} />
          <Field
            label="Timestamp"
            value={incident.createdAt || incident.timestamp ? new Date(incident.createdAt || incident.timestamp).toLocaleTimeString() : '—'}
          />
          <Field label="Tracking ID" value={incident.trackingId ? `#${incident.trackingId}` : '—'} />
          <Field label="Risk Score" value={`${incident.riskScore ?? 0} / 100`} />
          <Field label="Vehicle Type" value={incident.vehicleType || 'None'} />
          <Field label="Plate Number" value={incident.plateNumber || 'None'} />
          <Field
            label="AI Confidence"
            value={incident.confidence ? `${Math.round(incident.confidence * 100)}%` : 'Standard'}
          />
        </div>

        {/* Predictive Trajectory Card (if present) */}
        {trajectory.status && trajectory.status !== 'NO_CONFLICT' && (
          <div className="p-3 rounded-lg bg-ops-accent/10 border border-ops-accent/30 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ArrowUpRight className="w-4 h-4 text-ops-accent2" />
              <div>
                <span className="font-bold text-white">Predictive Trajectory: </span>
                <span className="text-ops-accent2 font-semibold">{trajectory.status}</span>
                <p className="text-[11px] text-ops-muted mt-0.5">{trajectory.explanation}</p>
              </div>
            </div>
            {trajectory.velocity > 0 && (
              <span className="font-mono text-[10px] text-white bg-white/10 px-2 py-1 rounded">
                Speed: {trajectory.velocity} u/s
              </span>
            )}
          </div>
        )}

        {/* Risk Score Breakdown */}
        {incident.breakdown && incident.breakdown.length > 0 && (
          <div>
            <h4 className="text-xs font-bold text-ops-muted uppercase mb-2">Risk Score Breakdown</h4>
            <div className="space-y-1 text-xs">
              {incident.breakdown.map((b, i) => (
                <div key={i} className="flex items-center justify-between bg-white/[0.03] px-3 py-1.5 rounded-lg">
                  <span className="text-ops-text">{b.label}</span>
                  <span className="font-mono text-ops-accent2 font-semibold">+{b.points}</span>
                </div>
              ))}
              <div className="flex items-center justify-between px-3 py-1.5 border-t border-ops-border font-bold">
                <span className="text-white">Calculated Risk</span>
                <span className="text-white">{incident.riskScore} / 100</span>
              </div>
            </div>
          </div>
        )}

        {/* AI Transparent Explanation */}
        {incident.explanation && (
          <div>
            <h4 className="text-xs font-bold text-ops-muted uppercase mb-1.5">AI Explanation</h4>
            <p className="text-xs text-ops-text bg-white/[0.03] p-3 rounded-lg leading-relaxed border border-ops-border/60">
              {incident.explanation}
            </p>
          </div>
        )}

        {/* Tamper-Evident SHA-256 Verification Section */}
        {sha256 && (
          <div className="p-3 rounded-xl border border-ops-border bg-white/[0.02] space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-ops-accent2" />
                <span className="text-xs font-bold text-white uppercase tracking-wider">
                  Tamper-Evident Evidence Hash
                </span>
              </div>
              <button
                onClick={handleVerifyHash}
                disabled={verifying}
                className="px-2.5 py-1 rounded text-xs font-semibold bg-ops-accent/20 text-ops-accent2 hover:bg-ops-accent/30 border border-ops-accent/40"
              >
                {verifying ? 'Verifying...' : 'Verify Cryptographic Hash'}
              </button>
            </div>
            <div className="font-mono text-[10px] text-ops-muted truncate bg-black/40 p-2 rounded border border-ops-border">
              SHA-256: <span className="text-white select-all">{sha256}</span>
            </div>

            {verifyResult && (
              <div
                className={`flex items-center gap-2 text-xs p-2 rounded font-semibold ${
                  verifyResult.status === 'VERIFIED'
                    ? 'bg-green-500/15 text-green-400 border border-green-500/30'
                    : 'bg-red-500/15 text-red-400 border border-red-500/30'
                }`}
              >
                {verifyResult.status === 'VERIFIED' ? (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Cryptographic Verification Passed — Evidence Unaltered on Disk</span>
                  </>
                ) : verifyResult.status === 'FILE_NOT_FOUND' ? (
                  <>
                    <ShieldAlert className="w-4 h-4" />
                    <span>Integrity Failure — Evidence file not found on disk!</span>
                  </>
                ) : (
                  <>
                    <ShieldAlert className="w-4 h-4" />
                    <span>Integrity Failure — Computed Hash Mismatches Stored Record!</span>
                  </>
                )}
              </div>
            )}
          </div>
        )}

        {/* Operator Feedback / False Alarm Feedback (Admin / Operator Only) */}
        {canAct && (
          <>
            <div className="pt-2 border-t border-ops-border flex items-center justify-between">
              <button
                onClick={() => setShowFeedback(!showFeedback)}
                className="flex items-center gap-1.5 text-xs text-ops-muted hover:text-white transition"
              >
                <ThumbsDown className="w-3.5 h-3.5" />
                {showFeedback ? 'Hide Feedback Form' : 'Log False Alarm / Feedback'}
              </button>
            </div>

            {showFeedback && (
              <form onSubmit={handleFeedbackSubmit} className="p-3 rounded-lg bg-white/5 border border-ops-border space-y-3 text-xs">
                <div className="font-bold text-white">Operator Feedback Classification</div>
                <div className="flex gap-3">
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="fb_class"
                      value="GENUINE"
                      checked={feedbackClass === 'GENUINE'}
                      onChange={(e) => setFeedbackClass(e.target.value)}
                    />
                    Genuine Incident
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="fb_class"
                      value="FALSE_ALARM"
                      checked={feedbackClass === 'FALSE_ALARM'}
                      onChange={(e) => setFeedbackClass(e.target.value)}
                    />
                    False Alarm
                  </label>
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="fb_class"
                      value="UNCERTAIN"
                      checked={feedbackClass === 'UNCERTAIN'}
                      onChange={(e) => setFeedbackClass(e.target.value)}
                    />
                    Uncertain
                  </label>
                </div>

                {feedbackClass === 'FALSE_ALARM' && (
                  <div>
                    <label className="text-[11px] text-ops-muted block mb-1">Reason for False Alarm:</label>
                    <select
                      value={feedbackReason}
                      onChange={(e) => setFeedbackReason(e.target.value)}
                      className="bg-white/10 border border-ops-border rounded px-2.5 py-1 text-white text-xs w-full"
                    >
                      <option value="animal">Animal / Wildlife</option>
                      <option value="vegetation">Wind-blown Vegetation / Trees</option>
                      <option value="weather">Heavy Rain / Weather</option>
                      <option value="shadow">Shadow / Optical Glare</option>
                      <option value="lighting">Sudden Lighting Change</option>
                      <option value="vehicle">Permitted Vehicle Outside Perimeter</option>
                      <option value="tracking_error">Tracking ID Re-association Error</option>
                      <option value="other">Other Operational Cause</option>
                    </select>
                  </div>
                )}

                <button
                  type="submit"
                  className="px-3 py-1.5 bg-ops-accent text-white rounded font-semibold text-xs hover:bg-ops-accent/80"
                >
                  Submit Feedback
                </button>
              </form>
            )}
          </>
        )}
      </div>
    </Modal>
  )
}

function Field({ label, value }) {
  return (
    <div>
      <div className="text-[10px] uppercase text-ops-muted font-semibold mb-0.5">{label}</div>
      <div className="text-white font-medium truncate">{value}</div>
    </div>
  )
}
