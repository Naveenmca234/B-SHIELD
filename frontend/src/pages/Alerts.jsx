import { useEffect, useState, useCallback } from 'react'
import Layout from '../components/Layout'
import { Loading, ErrorState, EmptyState } from '../components/States'
import AlertRow from '../components/AlertRow'
import IncidentDetail from '../components/IncidentDetail'
import { Pagination } from '../components/Common'
import api from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'
import { Filter } from 'lucide-react'

const SEVERITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
const ALERT_TYPES = [
  'UNKNOWN_PERSON', 'INTRUSION_DETECTED', 'NIGHT_MOVEMENT', 'VEHICLE_DETECTED',
  'ANPR_DETECTED', 'POSSIBLE_INTRUSION', 'VISIBILITY_DEGRADED', 'HIGH_THREAT', 'CRITICAL_THREAT',
]
const STATUSES = ['ALERTED', 'ACKNOWLEDGED', 'RESPONDING', 'RESOLVED', 'FALSE_ALARM']

export default function Alerts() {
  const [data, setData] = useState({ items: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ severity: '', alertType: '', status: '', cameraId: '' })
  const [selected, setSelected] = useState(null)
  const [selectedIds, setSelectedIds] = useState([])
  const [batchLoading, setBatchLoading] = useState(false)
  const { status: wsStatus, on } = useWebSocket()
  const { push } = useToast()
  const { hasRole } = useAuth()
  const canAct = hasRole(['admin', 'operator'])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { page, pageSize: 15 }
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v })
      const res = await api.get('/alerts', { params })
      setData(res.data)
      setSelectedIds([])
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load alerts.')
    } finally {
      setLoading(false)
    }
  }, [page, filters])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const off = on('new_alert', () => { if (page === 1) load() })
    const offUpd = on('alert_updated', () => load())
    return () => { off(); offUpd() }
  }, [on, load, page])

  async function handleAcknowledge(alert) {
    try {
      await api.put(`/alerts/${alert._id}/acknowledge`)
      push('Alert acknowledged.', 'success')
      load()
    } catch (e) { push(e.response?.data?.detail || 'Action failed.', 'error') }
  }

  async function handleResolve(alert) {
    try {
      await api.put(`/alerts/${alert._id}/resolve`)
      push('Alert resolved.', 'success')
      load()
    } catch (e) { push(e.response?.data?.detail || 'Action failed.', 'error') }
  }

  function toggleSelectId(id) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    )
  }

  function toggleSelectAll() {
    if (selectedIds.length === data.items.length) {
      setSelectedIds([])
    } else {
      setSelectedIds(data.items.map((i) => i._id))
    }
  }

  async function handleBatchAction(action) {
    if (!selectedIds.length) return
    setBatchLoading(true)
    const targetStatus = action === 'ACKNOWLEDGE' ? 'ACKNOWLEDGED' : (action === 'RESOLVE' ? 'RESOLVED' : action)
    try {
      await api.post('/incidents/batch-action', { incidentIds: selectedIds, status: targetStatus, action })
      push(`Batch ${action.toLowerCase()} applied to ${selectedIds.length} incident(s).`, 'success')
      setSelectedIds([])
      load()
    } catch (e) {
      push(e.response?.data?.detail || 'Batch action failed.', 'error')
    } finally {
      setBatchLoading(false)
    }
  }

  function updateFilter(key, value) {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1)
  }

  const allSelected = data.items.length > 0 && selectedIds.length === data.items.length

  return (
    <Layout title="Alerts & Incidents" subtitle="Real-time security alerts requiring operator response" wsStatus={wsStatus}>
      {/* Filters */}
      <div className="glass-panel rounded-xl p-4 mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5 text-xs text-ops-muted font-semibold"><Filter className="w-3.5 h-3.5" /> Filters:</div>
        <select value={filters.severity} onChange={(e) => updateFilter('severity', e.target.value)} className="bg-white/5 border border-ops-border rounded-lg px-3 py-1.5 text-xs text-white">
          <option value="">All Severities</option>
          {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={filters.alertType} onChange={(e) => updateFilter('alertType', e.target.value)} className="bg-white/5 border border-ops-border rounded-lg px-3 py-1.5 text-xs text-white">
          <option value="">All Types</option>
          {ALERT_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={filters.status} onChange={(e) => updateFilter('status', e.target.value)} className="bg-white/5 border border-ops-border rounded-lg px-3 py-1.5 text-xs text-white">
          <option value="">All Statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <input
          placeholder="Camera ID"
          value={filters.cameraId}
          onChange={(e) => updateFilter('cameraId', e.target.value)}
          className="bg-white/5 border border-ops-border rounded-lg px-3 py-1.5 text-xs text-white placeholder:text-ops-muted"
        />
      </div>

      {/* Batch Action Toolbar */}
      {selectedIds.length > 0 && canAct && (
        <div className="glass-panel rounded-xl p-3 mb-4 flex items-center justify-between border border-ops-accent/40 bg-ops-accent/10 animate-fade-in">
          <div className="text-xs font-semibold text-white">
            <span className="font-mono text-ops-accent2">{selectedIds.length}</span> alert(s) selected
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => handleBatchAction('ACKNOWLEDGE')}
              disabled={batchLoading}
              className="px-3 py-1.5 rounded-lg bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 text-xs font-semibold disabled:opacity-50"
            >
              Acknowledge All
            </button>
            <button
              onClick={() => handleBatchAction('RESOLVE')}
              disabled={batchLoading}
              className="px-3 py-1.5 rounded-lg bg-green-500/20 text-green-400 hover:bg-green-500/30 text-xs font-semibold disabled:opacity-50"
            >
              Resolve All
            </button>
            <button
              onClick={() => setSelectedIds([])}
              className="px-2.5 py-1.5 rounded-lg bg-white/5 text-ops-muted hover:text-white text-xs"
            >
              Clear
            </button>
          </div>
        </div>
      )}

      <div className="glass-panel rounded-xl overflow-hidden">
        {loading ? <Loading label="Loading alerts…" /> : error ? <ErrorState message={error} onRetry={load} /> : data.items.length === 0 ? (
          <EmptyState label="No alerts match the current filters." />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-ops-border text-[11px] uppercase text-ops-muted">
                    <th className="px-4 py-3 w-8">
                      <input
                        type="checkbox"
                        checked={allSelected}
                        onChange={toggleSelectAll}
                        className="accent-ops-accent w-4 h-4 rounded cursor-pointer"
                      />
                    </th>
                    <th className="px-4 py-3">ID</th>
                    <th className="px-4 py-3">Type</th>
                    <th className="px-4 py-3">Severity</th>
                    <th className="px-4 py-3">Camera</th>
                    <th className="px-4 py-3">Time</th>
                    <th className="px-4 py-3">Risk Score</th>
                    <th className="px-4 py-3">Status</th>
                    <th className="px-4 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((a) => (
                    <AlertRow
                      key={a._id}
                      alert={a}
                      selected={selectedIds.includes(a._id)}
                      onToggleSelect={toggleSelectId}
                      onView={setSelected}
                      onAcknowledge={handleAcknowledge}
                      onResolve={handleResolve}
                      canAct={canAct}
                    />
                  ))}
                </tbody>
              </table>
            </div>
            <div className="px-4"><Pagination page={page} pageSize={15} total={data.total} onPageChange={setPage} /></div>
          </>
        )}
      </div>

      <IncidentDetail open={!!selected} onClose={() => setSelected(null)} incident={selected} />
    </Layout>
  )
}
