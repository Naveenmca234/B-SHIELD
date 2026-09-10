import { useEffect, useState, useCallback } from 'react'
import { Search } from 'lucide-react'
import Layout from '../components/Layout'
import { Loading, ErrorState, EmptyState } from '../components/States'
import { SeverityBadge, StatusBadge, formatEventType } from '../components/Badges'
import IncidentDetail from '../components/IncidentDetail'
import { Pagination } from '../components/Common'
import { timeAgo } from '../components/AlertRow'
import api from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'

export default function Events() {
  const [data, setData] = useState({ items: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [filters, setFilters] = useState({ severity: '', eventType: '', personStatus: '', vehicleType: '', plateNumber: '', cameraId: '' })
  const [selected, setSelected] = useState(null)
  const { status: wsStatus, on } = useWebSocket()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { page, pageSize: 15 }
      if (search) params.search = search
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v })
      const res = await api.get('/events', { params })
      setData(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load events.')
    } finally {
      setLoading(false)
    }
  }, [page, search, filters])

  useEffect(() => { load() }, [load])
  useEffect(() => on('new_event', () => { if (page === 1) load() }), [on, load, page])

  function updateFilter(key, value) {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1)
  }

  return (
    <Layout title="Event History" subtitle="Complete surveillance event log with evidence" wsStatus={wsStatus}>
      <div className="glass-panel rounded-xl p-4 mb-4 space-y-3">
        <div className="relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ops-muted" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
            placeholder="Search events by type, camera, or explanation…"
            className="w-full bg-white/5 border border-ops-border rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder:text-ops-muted"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <input placeholder="Camera ID" value={filters.cameraId} onChange={(e) => updateFilter('cameraId', e.target.value)} className="bg-white/5 border border-ops-border rounded-lg px-3 py-1.5 text-xs text-white placeholder:text-ops-muted" />
          <select value={filters.severity} onChange={(e) => updateFilter('severity', e.target.value)} className="bg-white/5 border border-ops-border rounded-lg px-3 py-1.5 text-xs text-white">
            <option value="">All Severities</option>
            {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <select value={filters.personStatus} onChange={(e) => updateFilter('personStatus', e.target.value)} className="bg-white/5 border border-ops-border rounded-lg px-3 py-1.5 text-xs text-white">
            <option value="">All Person Status</option>
            <option value="AUTHORIZED">Authorized</option>
            <option value="UNKNOWN">Unknown</option>
          </select>
          <input placeholder="Vehicle Type" value={filters.vehicleType} onChange={(e) => updateFilter('vehicleType', e.target.value)} className="bg-white/5 border border-ops-border rounded-lg px-3 py-1.5 text-xs text-white placeholder:text-ops-muted" />
          <input placeholder="Plate Number" value={filters.plateNumber} onChange={(e) => updateFilter('plateNumber', e.target.value)} className="bg-white/5 border border-ops-border rounded-lg px-3 py-1.5 text-xs text-white placeholder:text-ops-muted" />
        </div>
      </div>

      <div className="glass-panel rounded-xl overflow-hidden">
        {loading ? <Loading label="Loading events…" /> : error ? <ErrorState message={error} onRetry={load} /> : data.items.length === 0 ? (
          <EmptyState label="No events match the current search/filters." />
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-ops-border text-[11px] uppercase text-ops-muted">
                    <th className="px-4 py-3">Event Type</th>
                    <th className="px-4 py-3">Camera</th>
                    <th className="px-4 py-3">Time</th>
                    <th className="px-4 py-3">Person</th>
                    <th className="px-4 py-3">Vehicle / Plate</th>
                    <th className="px-4 py-3">Severity</th>
                    <th className="px-4 py-3">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((e) => (
                    <tr key={e._id} onClick={() => setSelected(e)} className="border-b border-ops-border hover:bg-white/[0.03] cursor-pointer transition-colors">
                      <td className="px-4 py-3 text-sm font-medium text-white">{formatEventType(e.eventType)}</td>
                      <td className="px-4 py-3 text-sm text-ops-muted">
                        <div>{e.cameraName || e.cameraId}</div>
                        {e.location && <div className="text-[11px] text-ops-subtle">{e.location}</div>}
                      </td>
                      <td className="px-4 py-3 text-xs text-ops-muted">{timeAgo(e.timestamp)}</td>
                      <td className="px-4 py-3">{e.personStatus ? <StatusBadge status={e.personStatus} /> : <span className="text-ops-muted text-xs">—</span>}</td>
                      <td className="px-4 py-3 text-xs text-ops-muted">{e.plateNumber || e.vehicleType || '—'}</td>
                      <td className="px-4 py-3"><SeverityBadge severity={e.severity} /></td>
                      <td className="px-4 py-3 text-sm font-bold text-white">{e.riskScore}</td>
                    </tr>
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
