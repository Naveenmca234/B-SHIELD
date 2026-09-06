import { useEffect, useState, useCallback } from 'react'
import { UserPlus, Trash2, Users } from 'lucide-react'
import Layout from '../components/Layout'
import { Loading, ErrorState, EmptyState } from '../components/States'
import { StatusBadge } from '../components/Badges'
import Modal from '../components/Modal'
import { ConfirmDialog } from '../components/Common'
import { timeAgo } from '../components/AlertRow'
import api from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'

export default function Persons() {
  const [persons, setPersons] = useState([])
  const [recent, setRecent] = useState({ authorized: [], unknown: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showAdd, setShowAdd] = useState(false)
  const [toDelete, setToDelete] = useState(null)
  const { status: wsStatus, on } = useWebSocket()
  const { push } = useToast()
  const { hasRole } = useAuth()
  const isAdmin = hasRole(['admin'])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [pRes, rRes] = await Promise.all([
        api.get('/persons'),
        api.get('/persons/detections/recent'),
      ])
      setPersons(pRes.data)
      setRecent(rRes.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load personnel data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => on('new_event', () => load()), [on, load])

  async function handleDelete() {
    try {
      await api.delete(`/persons/${toDelete.employeeId}`)
      push('Person removed.', 'success')
      setToDelete(null)
      load()
    } catch (e) {
      push(e.response?.data?.detail || 'Failed to remove person.', 'error')
    }
  }

  return (
    <Layout title="Persons" subtitle="Authorized personnel registry & identity detections" wsStatus={wsStatus}>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-sm font-bold text-white uppercase tracking-wide">Authorized Personnel</h2>
        {isAdmin && (
          <button onClick={() => setShowAdd(true)} className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold bg-ops-accent/15 text-ops-accent2 hover:bg-ops-accent/25 border border-ops-accent/30">
            <UserPlus className="w-3.5 h-3.5" /> Register Person
          </button>
        )}
      </div>

      <div className="glass-panel rounded-xl overflow-hidden mb-6">
        {loading ? <Loading /> : error ? <ErrorState message={error} onRetry={load} /> : persons.length === 0 ? (
          <EmptyState label="No authorized personnel registered yet." icon={Users} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-ops-border text-[11px] uppercase text-ops-muted">
                  <th className="px-4 py-3">Photo</th>
                  <th className="px-4 py-3">Employee ID</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Created</th>
                  {isAdmin && <th className="px-4 py-3">Actions</th>}
                </tr>
              </thead>
              <tbody>
                {persons.map((p) => (
                  <tr key={p.employeeId} className="border-b border-ops-border hover:bg-white/[0.03]">
                    <td className="px-4 py-3">
                      {p.photoUrl ? (
                        <img src={p.photoUrl} alt={p.name} className="w-9 h-9 rounded-full object-cover border border-ops-border" />
                      ) : (
                        <div className="w-9 h-9 rounded-full bg-white/5 flex items-center justify-center text-ops-muted text-xs">{p.name?.[0]}</div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm mono text-white">{p.employeeId}</td>
                    <td className="px-4 py-3 text-sm text-white">{p.name}</td>
                    <td className="px-4 py-3"><StatusBadge status="AUTHORIZED" /></td>
                    <td className="px-4 py-3 text-xs text-ops-muted">{p.createdAt ? new Date(p.createdAt).toLocaleDateString() : '—'}</td>
                    {isAdmin && (
                      <td className="px-4 py-3">
                        <button onClick={() => setToDelete(p)} className="p-1.5 rounded hover:bg-red-500/10 text-red-400">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-panel rounded-xl p-5">
          <h3 className="text-xs font-bold text-ops-muted uppercase mb-3">Recent Authorized Detections</h3>
          {recent.authorized.length === 0 ? <p className="text-sm text-ops-muted">No recent detections.</p> : (
            <div className="space-y-2">
              {recent.authorized.map((e) => (
                <div key={e._id} className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.03] text-sm">
                  <span className="text-ops-muted text-xs">{e.cameraId}</span>
                  <span className="text-xs text-ops-muted">{timeAgo(e.timestamp)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="glass-panel rounded-xl p-5">
          <h3 className="text-xs font-bold text-ops-muted uppercase mb-3">Recent Unknown Detections</h3>
          {recent.unknown.length === 0 ? <p className="text-sm text-ops-muted">No recent detections.</p> : (
            <div className="space-y-2">
              {recent.unknown.map((e) => (
                <div key={e._id} className="flex items-center justify-between p-2.5 rounded-lg bg-white/[0.03] text-sm">
                  <span className="text-ops-muted text-xs">{e.cameraId}</span>
                  <span className="text-xs text-ops-muted">{timeAgo(e.timestamp)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <AddPersonModal open={showAdd} onClose={() => setShowAdd(false)} onSaved={load} />
      <ConfirmDialog
        open={!!toDelete}
        title="Remove Authorized Person"
        message={`Remove ${toDelete?.name} (${toDelete?.employeeId}) from the authorized personnel database? This cannot be undone.`}
        onConfirm={handleDelete}
        onCancel={() => setToDelete(null)}
        danger
      />
    </Layout>
  )
}

function AddPersonModal({ open, onClose, onSaved }) {
  const [employeeId, setEmployeeId] = useState('')
  const [name, setName] = useState('')
  const [photo, setPhoto] = useState(null)
  const [saving, setSaving] = useState(false)
  const { push } = useToast()

  function handleFile(e) {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => setPhoto(reader.result)
    reader.readAsDataURL(file)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      await api.post('/persons', { employeeId, name, photoBase64: photo })
      push('Authorized person registered.', 'success')
      setEmployeeId(''); setName(''); setPhoto(null)
      onSaved()
      onClose()
    } catch (e) {
      push(e.response?.data?.detail || 'Failed to register person.', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Register Authorized Personnel">
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-xs text-ops-muted bg-white/5 p-3 rounded-lg">
          Use only consented demo photos. This registers a face embedding used to classify this person as AUTHORIZED on camera.
        </p>
        <div>
          <label className="block text-xs text-ops-muted mb-1">Employee ID</label>
          <input required value={employeeId} onChange={(e) => setEmployeeId(e.target.value)} placeholder="EMP004" className="w-full bg-white/5 border border-ops-border rounded-lg px-3 py-2 text-sm text-white" />
        </div>
        <div>
          <label className="block text-xs text-ops-muted mb-1">Full Name</label>
          <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="Jane Doe" className="w-full bg-white/5 border border-ops-border rounded-lg px-3 py-2 text-sm text-white" />
        </div>
        <div>
          <label className="block text-xs text-ops-muted mb-1">Consented Demo Photo (front-facing)</label>
          <input type="file" accept="image/*" onChange={handleFile} className="w-full text-xs text-ops-muted" />
          {photo && <img src={photo} alt="preview" className="mt-2 w-20 h-20 rounded-lg object-cover border border-ops-border" />}
        </div>
        <button type="submit" disabled={saving} className="w-full py-2.5 rounded-lg bg-gradient-to-r from-ops-accent to-ops-accent2 text-white font-semibold text-sm disabled:opacity-60">
          {saving ? 'Registering…' : 'Register Person'}
        </button>
      </form>
    </Modal>
  )
}
