import { useEffect, useState, useCallback } from 'react'
import { Search, Car } from 'lucide-react'
import Layout from '../components/Layout'
import { Loading, ErrorState, EmptyState } from '../components/States'
import { Pagination } from '../components/Common'
import { timeAgo } from '../components/AlertRow'
import api from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'

export default function Vehicles() {
  const [data, setData] = useState({ items: [], total: 0 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState({ plateNumber: '', cameraId: '', vehicleType: '' })
  const { status: wsStatus, on } = useWebSocket()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { page, pageSize: 15 }
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v })
      const res = await api.get('/vehicles', { params })
      setData(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load vehicle records.')
    } finally {
      setLoading(false)
    }
  }, [page, filters])

  useEffect(() => { load() }, [load])
  useEffect(() => on('anpr_detected', () => { if (page === 1) load() }), [on, load, page])

  function updateFilter(key, value) {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1)
  }

  return (
    <Layout title="Vehicles / ANPR" subtitle="Detected vehicles and automatic number plate recognition" wsStatus={wsStatus}>
      <div className="glass-panel rounded-xl p-4 mb-4 flex flex-wrap gap-3">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-ops-muted" />
          <input
            placeholder="Search plate number…"
            value={filters.plateNumber}
            onChange={(e) => updateFilter('plateNumber', e.target.value)}
            className="bg-white/5 border border-ops-border rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder:text-ops-muted"
          />
        </div>
        <input placeholder="Camera ID" value={filters.cameraId} onChange={(e) => updateFilter('cameraId', e.target.value)} className="bg-white/5 border border-ops-border rounded-lg px-3 py-1.5 text-xs text-white placeholder:text-ops-muted" />
        <input placeholder="Vehicle Type" value={filters.vehicleType} onChange={(e) => updateFilter('vehicleType', e.target.value)} className="bg-white/5 border border-ops-border rounded-lg px-3 py-1.5 text-xs text-white placeholder:text-ops-muted" />
      </div>

      <div className="glass-panel rounded-xl overflow-hidden">
        {loading ? <Loading label="Loading vehicle records…" /> : error ? <ErrorState message={error} onRetry={load} /> : data.items.length === 0 ? (
          <EmptyState label="No vehicle/ANPR records yet. They will appear here as vehicles are detected." icon={Car} />
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 p-4">
              {data.items.map((v) => (
                <div key={v._id} className="rounded-xl overflow-hidden border border-ops-border bg-white/[0.02]">
                  {v.thumbnail || v.snapshot ? (
                    <img src={v.thumbnail || v.snapshot} alt="Vehicle snapshot" className="w-full aspect-video object-cover" />
                  ) : (
                    <div className="w-full aspect-video bg-black/40 flex items-center justify-center text-ops-muted">
                      <Car className="w-8 h-8 opacity-40" />
                    </div>
                  )}
                  <div className="p-3">
                    <div className="flex items-center justify-between mb-1">
                      {v.plateNumber ? (
                        <span className="mono text-sm font-bold text-white bg-white/10 px-2 py-0.5 rounded flex items-center gap-1.5">
                          {v.plateNumber}
                          {v.plateStatus === 'LOW_CONFIDENCE' && (
                            <span className="text-[10px] text-amber-400 bg-amber-500/20 px-1 py-0.2 rounded font-normal">LOW CONF</span>
                          )}
                        </span>
                      ) : (
                        <span className="text-xs px-2 py-0.5 rounded font-mono bg-white/5 text-ops-muted">
                          {v.plateStatus === 'OCR_UNAVAILABLE'
                            ? 'OCR UNAVAILABLE'
                            : v.plateStatus === 'PLATE_NOT_READ'
                            ? 'PLATE NOT READ'
                            : 'NO PLATE DETECTED'}
                        </span>
                      )}
                      <span className="text-[10px] text-ops-muted uppercase">{v.vehicleType}</span>
                    </div>
                    <div className="text-xs text-ops-muted">{v.cameraId} • {timeAgo(v.timestamp)}</div>
                    <div className="text-xs text-ops-accent2 mt-1">
                      {v.plateNumber ? `OCR Confidence: ${v.ocrConfidence}%` : (v.reason || 'No plate identified')}
                    </div>
                  </div>

                </div>
              ))}
            </div>
            <div className="px-4"><Pagination page={page} pageSize={15} total={data.total} onPageChange={setPage} /></div>
          </>
        )}
      </div>
    </Layout>
  )
}
