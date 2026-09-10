import { useEffect, useState, useCallback } from 'react'
import {
  Camera as CameraIcon, Users, Car, EyeOff, Bell, AlertTriangle, Wifi, ShieldAlert, Clock, CheckCircle, Activity,
} from 'lucide-react'
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import Layout from '../components/Layout'
import KpiCard from '../components/KpiCard'
import CameraCard from '../components/CameraCard'
import PerimeterMap from '../components/PerimeterMap'
import IncidentDetail from '../components/IncidentDetail'
import { Loading, ErrorState, EmptyState } from '../components/States'
import { SeverityBadge, StatusBadge, formatEventType } from '../components/Badges'
import { timeAgo } from '../components/AlertRow'
import api from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import { useNavigate } from 'react-router-dom'
import { useToast } from '../context/ToastContext'
import { useAuth } from '../context/AuthContext'

const SEVERITY_COLORS = { LOW: '#22c55e', MEDIUM: '#eab308', HIGH: '#f97316', CRITICAL: '#ef4444' }

export default function Dashboard() {
  const { user } = useAuth()
  const canAct = user?.role === 'admin' || user?.role === 'operator'
  const [stats, setStats] = useState(null)
  const [charts, setCharts] = useState(null)
  const [cameras, setCameras] = useState([])
  const [alerts, setAlerts] = useState([])
  const [liveByCamera, setLiveByCamera] = useState({})
  const [selectedIncident, setSelectedIncident] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const { status: wsStatus, on } = useWebSocket()
  const { push } = useToast()
  const navigate = useNavigate()

  const loadAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [statsRes, chartsRes, camsRes, alertsRes] = await Promise.all([
        api.get('/dashboard/stats'),
        api.get('/dashboard/charts'),
        api.get('/cameras'),
        api.get('/alerts', { params: { pageSize: 6 } }),
      ])
      setStats(statsRes.data)
      setCharts(chartsRes.data)
      setCameras(camsRes.data)
      setAlerts(alertsRes.data.items)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load dashboard data.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadAll() }, [loadAll])

  useEffect(() => {
    const offDetect = on('detection_update', (data) => {
      setLiveByCamera((prev) => ({
        ...prev,
        [data.cameraId]: {
          people: data.peopleCount,
          vehicles: data.vehicleCount,
          unknown: data.unknownCount,
          threatLevel: data.threatLevel,
          health: data.health,
        },
      }))
    })

    const offAlert = on('new_alert', (alert) => {
      setAlerts((prev) => [alert, ...prev].slice(0, 8))
      setStats((prev) =>
        prev
          ? {
              ...prev,
              activeAlerts: prev.activeAlerts + 1,
              criticalAlerts: prev.criticalAlerts + (alert.severity === 'CRITICAL' ? 1 : 0),
            }
          : prev
      )
      if (alert.severity === 'CRITICAL') {
        push(`CRITICAL ALERT: ${alert.alertType || 'Intrusion'} on camera ${alert.cameraId}!`, 'error')
      }
    })

    const offCamStatus = on('camera_status', (data) => {
      setCameras((prev) =>
        prev.map((c) =>
          c.cameraId === data.cameraId ? { ...c, status: data.status, error: data.error, health: data.health } : c
        )
      )
    })

    return () => {
      offDetect()
      offAlert()
      offCamStatus()
    }
  }, [on, push])

  const criticalIncident = alerts.find((a) => a.severity === 'CRITICAL' && a.status !== 'RESOLVED' && a.status !== 'FALSE_ALARM')

  async function handleQuickTransition(id, newStatus) {
    try {
      if (newStatus === 'ACKNOWLEDGED') {
        await api.put(`/alerts/${id}/acknowledge`)
      } else if (newStatus === 'RESOLVED') {
        await api.put(`/alerts/${id}/resolve`)
      } else {
        await api.put(`/incidents/${id}/transition`, { status: newStatus })
      }
      push(`Incident updated to ${newStatus}.`, 'success')
      loadAll()
    } catch (e) {
      push(e.response?.data?.detail || 'Action failed.', 'error')
    }
  }

  if (loading) return <Layout title="B-SHIELD" wsStatus={wsStatus}><Loading label="Loading command center…" /></Layout>
  if (error) return <Layout title="B-SHIELD" wsStatus={wsStatus}><ErrorState message={error} onRetry={loadAll} /></Layout>

  return (
    <Layout
      title="B-SHIELD"
      subtitle="AI-Powered Intelligent Border Surveillance (IBVAP Command Center)"
      wsStatus={wsStatus}
      alertCount={stats?.unacknowledgedAlerts ?? stats?.activeAlerts}
    >

      {/* Top Critical Alert Banner */}
      {criticalIncident && (
        <div className="mb-6 p-4 rounded-xl bg-red-500/15 border-2 border-red-500/50 shadow-glow flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5 min-w-0">
            <div className="w-10 h-10 rounded-lg bg-red-500 flex items-center justify-center text-white shrink-0">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-extrabold text-white text-sm tracking-wide">
                  CRITICAL SURVEILLANCE INTRUSION
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-red-500 text-white">
                  {criticalIncident.cameraId}
                </span>
                {criticalIncident.isDemoIncident && (
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    DEMO RECORD
                  </span>
                )}
                <StatusBadge status={criticalIncident.status || 'ALERTED'} />
              </div>
              <div className="text-xs text-red-200 mt-0.5 font-mono">
                {criticalIncident.incidentId || criticalIncident._id?.slice(-6)} • {criticalIncident.location || criticalIncident.cameraName || criticalIncident.cameraId} • {timeAgo(criticalIncident.createdAt || criticalIncident.timestamp)}
              </div>
              <p className="text-xs text-white/90 mt-1 font-medium leading-snug">
                {criticalIncident.explanation || 'Immediate response required for high-risk perimeter intrusion.'}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <button
              onClick={() => setSelectedIncident(criticalIncident)}
              className="px-3 py-1.5 rounded-lg text-xs font-bold bg-white/10 hover:bg-white/20 text-white border border-white/20 transition"
            >
              Examine Incident
            </button>
            {canAct && (criticalIncident.status === 'ALERTED' || criticalIncident.status === 'DETECTED' || criticalIncident.status === 'NEW') && (
              <button
                onClick={() => handleQuickTransition(criticalIncident.incidentId || criticalIncident._id, 'ACKNOWLEDGED')}
                className="px-4 py-1.5 rounded-lg text-xs font-bold bg-amber-600 hover:bg-amber-500 text-white shadow-lg transition"
              >
                Acknowledge
              </button>
            )}
            {canAct && criticalIncident.status === 'ACKNOWLEDGED' && (
              <>
                <button
                  onClick={() => handleQuickTransition(criticalIncident.incidentId || criticalIncident._id, 'RESPONDING')}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white shadow-lg transition"
                >
                  Dispatch Response
                </button>
                <button
                  onClick={() => handleQuickTransition(criticalIncident.incidentId || criticalIncident._id, 'RESOLVED')}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg transition"
                >
                  Resolve
                </button>
              </>
            )}
            {canAct && criticalIncident.status === 'RESPONDING' && (
              <button
                onClick={() => handleQuickTransition(criticalIncident.incidentId || criticalIncident._id, 'RESOLVED')}
                className="px-4 py-1.5 rounded-lg text-xs font-bold bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg transition"
              >
                Resolve Incident
              </button>
            )}
          </div>
        </div>
      )}

      {/* Top Control Room KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3.5 mb-6">
        <KpiCard label="Active Incidents" value={stats.activeAlerts} icon={Bell} tone={stats.activeAlerts > 0 ? 'warning' : 'neutral'} />
        <KpiCard label="Critical Alerts" value={stats.criticalAlerts} icon={AlertTriangle} tone={stats.criticalAlerts > 0 ? 'danger' : 'neutral'} />
        <KpiCard label="Cameras Online" value={stats.onlineCameras} icon={Wifi} tone="success" />
        <KpiCard label="Degraded Feeds" value={stats.degradedCameras} icon={Activity} tone={stats.degradedCameras > 0 ? 'warning' : 'neutral'} />
        <KpiCard label="Coverage Gaps" value={stats.coverageGaps} icon={EyeOff} tone={stats.coverageGaps > 0 ? 'danger' : 'neutral'} />
        <KpiCard label="Avg Response" value={stats.avgResponseTimeSeconds != null ? `${stats.avgResponseTimeSeconds}s` : '—'} icon={Clock} />
        <KpiCard label="Resolved Today" value={stats.incidentsResolved} icon={CheckCircle} tone="success" />
      </div>

      {/* Operational Grid & Priority Incidents */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-6">
        {/* Perimeter Map */}
        <div className="lg:col-span-7 h-[360px]">
          <PerimeterMap
            cameras={cameras}
            activeIncidents={alerts.filter((a) => a.status !== 'RESOLVED')}
            onSelectCamera={(camId) => navigate('/live')}
          />
        </div>

        {/* Priority Incident Feed */}
        <div className="lg:col-span-5 glass-panel rounded-xl p-4 flex flex-col h-[360px]">
          <div className="flex items-center justify-between mb-3 border-b border-ops-border pb-2.5">
            <h2 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-ops-accent2" />
              Priority Incident Feed
            </h2>
            <button onClick={() => navigate('/alerts')} className="text-[11px] text-ops-accent2 hover:underline">
              View All
            </button>
          </div>

          <div className="flex-1 overflow-y-auto space-y-2 pr-1">
            {alerts.length === 0 ? (
              <EmptyState label="No security alerts active." />
            ) : (
              alerts.map((a) => (
                <div
                  key={a._id || a.incidentId}
                  onClick={() => setSelectedIncident(a)}
                  className="p-2.5 rounded-lg bg-white/[0.02] hover:bg-white/[0.05] border border-ops-border/60 transition cursor-pointer flex items-center justify-between"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <SeverityBadge severity={a.severity} />
                    <div className="min-w-0">
                      <div className="text-xs font-bold text-white truncate" title={formatEventType(a.eventType || a.alertType)}>
                        {formatEventType(a.eventType || a.alertType)}
                      </div>
                      <div className="text-[10px] text-ops-muted">
                        {a.incidentId ? `${a.incidentId} • ` : ''}{a.location || a.cameraId} • {timeAgo(a.timestamp || a.createdAt)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-white">
                      {a.riskScore}<span className="text-[10px] text-ops-muted">/100</span>
                    </span>
                    <StatusBadge status={a.status || 'ALERTED'} />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Camera Surveillance Health Overview */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <CameraIcon className="w-4 h-4 text-ops-accent2" />
            Surveillance Feeds & Sensor Health
          </h2>
          <button onClick={() => navigate('/cameras')} className="text-[11px] text-ops-accent2 hover:underline">
            Manage Outposts
          </button>
        </div>

        {cameras.length === 0 ? (
          <EmptyState label="No cameras configured." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {cameras.map((cam) => (
              <CameraCard
                key={cam.cameraId}
                camera={cam}
                live={liveByCamera[cam.cameraId]}
                onClick={() => navigate('/live')}
              />
            ))}
          </div>
        )}
      </div>

      {/* Analytics Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="glass-panel rounded-xl p-4">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-3">Incidents by Severity</h3>
          <ResponsiveContainer width="100%" height={190}>
            <PieChart>
              <Pie data={charts.alertsBySeverity} dataKey="count" nameKey="severity" innerRadius={45} outerRadius={70} paddingAngle={3}>
                {charts.alertsBySeverity.map((entry) => (
                  <Cell key={entry.severity} fill={SEVERITY_COLORS[entry.severity]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: '#101627', border: '1px solid #1c2438', borderRadius: 8, fontSize: 11 }} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="glass-panel rounded-xl p-4">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-3">Perimeter Activity (7 Days)</h3>
          <ResponsiveContainer width="100%" height={190}>
            <LineChart data={charts.eventsOverTime}>
              <CartesianGrid stroke="#1c2438" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fontSize: 9, fill: '#7b8499' }} />
              <YAxis tick={{ fontSize: 9, fill: '#7b8499' }} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#101627', border: '1px solid #1c2438', borderRadius: 8, fontSize: 11 }} />
              <Line type="monotone" dataKey="count" stroke="#2f7bff" strokeWidth={2} dot={{ r: 2.5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="glass-panel rounded-xl p-4">
          <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-3">Personnel Identification</h3>
          <ResponsiveContainer width="100%" height={190}>
            <BarChart data={charts.personStatus}>
              <CartesianGrid stroke="#1c2438" strokeDasharray="3 3" />
              <XAxis dataKey="status" tick={{ fontSize: 10, fill: '#7b8499' }} />
              <YAxis tick={{ fontSize: 9, fill: '#7b8499' }} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#101627', border: '1px solid #1c2438', borderRadius: 8, fontSize: 11 }} />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                <Cell fill="#22c55e" />
                <Cell fill="#f97316" />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Extended Analytics Row: 24h Hourly Distribution & Sector Trends */}
      {charts && (charts.hourlyDistribution || charts.cameraDistribution) && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          <div className="glass-panel rounded-xl p-4">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-3">24-Hour Threat Distribution</h3>
            <ResponsiveContainer width="100%" height={190}>
              <BarChart data={charts.hourlyDistribution || []}>
                <CartesianGrid stroke="#1c2438" strokeDasharray="3 3" />
                <XAxis dataKey="hour" tick={{ fontSize: 9, fill: '#7b8499' }} interval={2} />
                <YAxis tick={{ fontSize: 9, fill: '#7b8499' }} allowDecimals={false} />
                <Tooltip contentStyle={{ background: '#101627', border: '1px solid #1c2438', borderRadius: 8, fontSize: 11 }} />
                <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="glass-panel rounded-xl p-4">
            <h3 className="text-xs font-bold text-white uppercase tracking-wider mb-3">Incident Distribution by Sector / Camera</h3>
            <ResponsiveContainer width="100%" height={190}>
              <BarChart data={charts.cameraDistribution || []}>
                <CartesianGrid stroke="#1c2438" strokeDasharray="3 3" />
                <XAxis dataKey="camera" tick={{ fontSize: 10, fill: '#7b8499' }} />
                <YAxis tick={{ fontSize: 9, fill: '#7b8499' }} allowDecimals={false} />
                <Tooltip contentStyle={{ background: '#101627', border: '1px solid #1c2438', borderRadius: 8, fontSize: 11 }} />
                <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Incident Detail Modal with Lifecycle and SHA-256 Verification */}
      <IncidentDetail
        open={!!selectedIncident}
        onClose={() => setSelectedIncident(null)}
        incident={selectedIncident}
        onUpdated={loadAll}
      />
    </Layout>
  )
}
