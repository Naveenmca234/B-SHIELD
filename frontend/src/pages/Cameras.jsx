import { useEffect, useState, useCallback } from 'react'
import { Plus, Edit2, Trash2, MapPin, Shield, Camera as CameraIcon } from 'lucide-react'
import Layout from '../components/Layout'
import { Loading, ErrorState, EmptyState, DemoTag } from '../components/States'
import { StatusBadge, SurveillanceHealthBadge } from '../components/Badges'
import Modal from '../components/Modal'
import { ConfirmDialog } from '../components/Common'
import FenceEditor from '../components/FenceEditor'
import api from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import { useToast } from '../context/ToastContext'

const EMPTY_FORM = {
  cameraId: '', name: '', location: '', sourceType: 'WEBCAM', rtspUrl: '', videoFile: '',
  riskLevel: 'MEDIUM', nightStart: '18:30', nightEnd: '06:00', enabled: true,
  latitude: '', longitude: '', mapZone: '',
}


export default function Cameras() {
  const [cameras, setCameras] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [editingCam, setEditingCam] = useState(null)
  const [toDelete, setToDelete] = useState(null)
  const [fenceCam, setFenceCam] = useState(null)
  const { status: wsStatus, on } = useWebSocket()
  const { push } = useToast()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/cameras')
      setCameras(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load cameras.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => on('camera_status', () => load()), [on, load])

  async function handleDelete() {
    try {
      await api.delete(`/cameras/${toDelete.cameraId}`)
      push('Camera removed.', 'success')
      setToDelete(null)
      load()
    } catch (e) { push(e.response?.data?.detail || 'Failed to delete camera.', 'error') }
  }

  async function saveFence(points) {
    try {
      await api.post('/fences', { cameraId: fenceCam.cameraId, zoneName: 'RESTRICTED ZONE', points })
      push('Virtual fence saved.', 'success')
      setFenceCam(null)
      load()
    } catch (e) { push(e.response?.data?.detail || 'Failed to save fence.', 'error') }
  }

  return (
    <Layout title="Camera Management" subtitle="Configure CCTV, webcam, and RTSP sources" wsStatus={wsStatus}>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-sm font-bold text-white uppercase tracking-wide">Cameras</h2>
        <button onClick={() => { setEditingCam(null); setShowForm(true) }} className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold bg-ops-accent/15 text-ops-accent2 hover:bg-ops-accent/25 border border-ops-accent/30">
          <Plus className="w-3.5 h-3.5" /> Add Camera
        </button>
      </div>

      {loading ? <Loading /> : error ? <ErrorState message={error} onRetry={load} /> : cameras.length === 0 ? (
        <EmptyState label="No cameras configured. Add one to get started." icon={CameraIcon} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {cameras.map((c) => (
            <div key={c.cameraId} className="glass-panel rounded-xl p-4 flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="font-bold text-white text-sm">{c.name}</h3>
                    <div className="flex items-center gap-1 text-[11px] text-ops-muted mt-0.5"><MapPin className="w-3 h-3" /> {c.location}</div>
                  </div>
                  <div className="flex flex-col items-end gap-1">
                    <StatusBadge status={c.status} />
                    {c.health && <SurveillanceHealthBadge health={c.health} />}
                  </div>
                </div>

                <div className="flex flex-wrap gap-1.5 my-3">
                  <span className="text-[10px] px-2 py-0.5 rounded bg-white/5 text-ops-muted">{c.sourceType}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-white/5 text-ops-muted">Risk: {c.riskLevel}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-white/5 text-ops-muted">Night: {c.nightStart}–{c.nightEnd}</span>
                  {c.sourceType === 'RTSP' && c.status !== 'ONLINE' && <DemoTag />}
                </div>

                {/* Coverage gap or degradation warnings */}
                {c.health?.isCoverageGap && (
                  <div className="p-2.5 rounded bg-red-950/40 border border-red-500/40 text-[11px] text-red-300 font-medium mb-3">
                    ⚠ High Priority: Perimeter Coverage Gap Detected
                  </div>
                )}
                {c.health?.reasons?.length > 0 && !c.health?.isCoverageGap && (
                  <div className="p-2 rounded bg-amber-950/30 border border-amber-500/30 text-[10px] text-amber-300 mb-3">
                    {c.health.reasons.join('; ')}
                  </div>
                )}
              </div>

              <div className="flex gap-2 mt-3 pt-3 border-t border-ops-border">
                <button onClick={() => { setEditingCam(c); setShowForm(true) }} className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold bg-white/5 hover:bg-white/10 text-ops-text">
                  <Edit2 className="w-3.5 h-3.5" /> Edit
                </button>
                <button onClick={() => setFenceCam(c)} className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold bg-red-500/10 hover:bg-red-500/20 text-red-400">
                  <Shield className="w-3.5 h-3.5" /> Fence
                </button>
                <button onClick={() => setToDelete(c)} className="p-1.5 rounded-lg bg-white/5 hover:bg-red-500/10 text-red-400">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <CameraForm open={showForm} onClose={() => setShowForm(false)} camera={editingCam} onSaved={load} />

      <Modal open={!!fenceCam} onClose={() => setFenceCam(null)} title={`Virtual Fence — ${fenceCam?.name}`} wide>
        {fenceCam && <FenceEditor camera={fenceCam} initialPoints={fenceCam.fence || []} onSave={saveFence} />}
      </Modal>

      <ConfirmDialog
        open={!!toDelete}
        title="Delete Camera"
        message={`Delete camera "${toDelete?.name}"? Its pipeline will be stopped and configuration removed.`}
        onConfirm={handleDelete}
        onCancel={() => setToDelete(null)}
        danger
      />
    </Layout>
  )
}

function CameraForm({ open, onClose, camera, onSaved }) {
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const { push } = useToast()
  const isEdit = !!camera

  useEffect(() => {
    setForm(camera ? {
      cameraId: camera.cameraId, name: camera.name, location: camera.location,
      sourceType: camera.sourceType, rtspUrl: camera.rtspUrl || '', videoFile: camera.videoFile || '',
      riskLevel: camera.riskLevel, nightStart: camera.nightStart, nightEnd: camera.nightEnd, enabled: camera.enabled,
      latitude: camera.latitude !== undefined && camera.latitude !== null ? camera.latitude : '',
      longitude: camera.longitude !== undefined && camera.longitude !== null ? camera.longitude : '',
      mapZone: camera.mapZone || '',
    } : EMPTY_FORM)
  }, [camera, open])


  function update(key, value) { setForm((f) => ({ ...f, [key]: value })) }

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      if (isEdit) {
        await api.put(`/cameras/${camera.cameraId}`, form)
        push('Camera updated.', 'success')
      } else {
        await api.post('/cameras', form)
        push('Camera created.', 'success')
      }
      onSaved()
      onClose()
    } catch (e) {
      push(e.response?.data?.detail || 'Failed to save camera.', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title={isEdit ? 'Edit Camera' : 'Add Camera'} wide>
      <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-4">
        <FormField label="Camera Name">
          <input required value={form.name} onChange={(e) => update('name', e.target.value)} className="input" />
        </FormField>
        <FormField label="Camera ID">
          <input required disabled={isEdit} value={form.cameraId} onChange={(e) => update('cameraId', e.target.value)} placeholder="BOP-04" className="input disabled:opacity-50" />
        </FormField>
        <FormField label="Location" full>
          <input required value={form.location} onChange={(e) => update('location', e.target.value)} className="input" />
        </FormField>
        <FormField label="Source Type">
          <select value={form.sourceType} onChange={(e) => update('sourceType', e.target.value)} className="input">
            <option value="WEBCAM">WEBCAM</option>
            <option value="VIDEO_FILE">VIDEO FILE</option>
            <option value="RTSP">RTSP</option>
          </select>
        </FormField>
        <FormField label="Risk Level">
          <select value={form.riskLevel} onChange={(e) => update('riskLevel', e.target.value)} className="input">
            <option value="LOW">LOW</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="HIGH">HIGH</option>
          </select>
        </FormField>
        {form.sourceType === 'RTSP' && (
          <FormField label="RTSP URL" full>
            <input value={form.rtspUrl} onChange={(e) => update('rtspUrl', e.target.value)} placeholder="rtsp://user:pass@host:554/stream" className="input" />
          </FormField>
        )}
        {form.sourceType === 'VIDEO_FILE' && (
          <FormField label="Video Filename (uploaded via Live Surveillance)" full>
            <input value={form.videoFile} onChange={(e) => update('videoFile', e.target.value)} placeholder="sample_perimeter.mp4" className="input" />
          </FormField>
        )}
        <FormField label="Night Start">
          <input type="time" value={form.nightStart} onChange={(e) => update('nightStart', e.target.value)} className="input" />
        </FormField>
        <FormField label="Night End">
          <input type="time" value={form.nightEnd} onChange={(e) => update('nightEnd', e.target.value)} className="input" />
        </FormField>
        <FormField label="Latitude (Optional Decimal)">
          <input type="number" step="any" value={form.latitude} onChange={(e) => update('latitude', e.target.value ? parseFloat(e.target.value) : null)} placeholder="e.g. 32.7157" className="input" />
        </FormField>
        <FormField label="Longitude (Optional Decimal)">
          <input type="number" step="any" value={form.longitude} onChange={(e) => update('longitude', e.target.value ? parseFloat(e.target.value) : null)} placeholder="e.g. 74.8580" className="input" />
        </FormField>
        <FormField label="Perimeter Sector / Map Zone" full>
          <input value={form.mapZone} onChange={(e) => update('mapZone', e.target.value)} placeholder="e.g. Sector-Alpha-North" className="input" />
        </FormField>
        <FormField label="Enabled" full>
          <label className="flex items-center gap-2 text-sm text-ops-text">
            <input type="checkbox" checked={form.enabled} onChange={(e) => update('enabled', e.target.checked)} className="accent-ops-accent w-4 h-4" />
            Camera pipeline is active
          </label>
        </FormField>


        <div className="col-span-2 mt-2">
          <button type="submit" disabled={saving} className="w-full py-2.5 rounded-lg bg-gradient-to-r from-ops-accent to-ops-accent2 text-white font-semibold text-sm disabled:opacity-60">
            {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Create Camera'}
          </button>
        </div>
      </form>
      <style>{`.input { width: 100%; background: rgba(255,255,255,0.05); border: 1px solid #1c2438; border-radius: 8px; padding: 8px 12px; font-size: 13px; color: white; }`}</style>
    </Modal>
  )
}

function FormField({ label, children, full }) {
  return (
    <div className={full ? 'col-span-2' : ''}>
      <label className="block text-xs text-ops-muted mb-1">{label}</label>
      {children}
    </div>
  )
}
