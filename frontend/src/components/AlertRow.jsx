import { Eye, CheckCircle2, ShieldCheck } from 'lucide-react'
import { SeverityBadge, formatEventType } from './Badges'

function timeAgo(iso) {
  if (!iso) return '—'
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return new Date(iso).toLocaleString()
}

export default function AlertRow({ alert, onView, onAcknowledge, onResolve, canAct, selected, onToggleSelect }) {
  const isSelected = !!selected
  const idLabel = alert.incidentId || (alert._id?.length > 12 ? alert._id.slice(-6) : alert._id)

  return (
    <tr className={`border-b border-ops-border hover:bg-white/[0.03] transition-colors ${isSelected ? 'bg-ops-accent/10' : ''}`}>
      <td className="px-4 py-3">
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => onToggleSelect && onToggleSelect(alert._id)}
          className="accent-ops-accent w-4 h-4 rounded cursor-pointer"
        />
      </td>
      <td className="px-4 py-3 text-xs font-mono text-ops-muted">{idLabel}</td>
      <td className="px-4 py-3 text-sm font-medium text-white">
        <div>{formatEventType(alert.alertType || alert.eventType)}</div>
        {alert.isDemoIncident && (
          <span className="text-[9px] font-bold text-amber-400 bg-amber-500/15 px-1.5 py-0.5 rounded border border-amber-500/30">
            DEMO RECORD
          </span>
        )}
      </td>
      <td className="px-4 py-3"><SeverityBadge severity={alert.severity} /></td>
      <td className="px-4 py-3 text-xs text-ops-muted">
        <span className="font-semibold text-white/90">{alert.cameraId}</span>
        {(alert.location || alert.cameraName) && (
          <div className="text-[10px] text-ops-muted truncate max-w-[140px]">{alert.location || alert.cameraName}</div>
        )}
      </td>
      <td className="px-4 py-3 text-xs text-ops-muted">{timeAgo(alert.timestamp || alert.createdAt)}</td>
      <td className="px-4 py-3 text-sm font-bold text-white">{alert.riskScore}<span className="text-ops-muted text-xs">/100</span></td>
      <td className="px-4 py-3">
        <div className="flex flex-col gap-0.5">
          <span className={`text-xs font-semibold px-2 py-0.5 rounded w-fit ${
            alert.status === 'NEW' || alert.status === 'DETECTED' || alert.status === 'ALERTED' ? 'bg-red-500/15 text-red-400' :
            alert.status === 'ACKNOWLEDGED' || alert.status === 'RESPONDING' ? 'bg-yellow-500/15 text-yellow-400' :
            'bg-green-500/15 text-green-400'
          }`}>{alert.status}</span>
          {(alert.responseTimeSeconds !== undefined && alert.responseTimeSeconds !== null) && (
            <span className="text-[10px] text-ops-muted font-mono">
              Ack: {alert.responseTimeSeconds}s
            </span>
          )}
          {(alert.metrics?.resolutionTimeSeconds !== undefined || alert.resolutionTimeSeconds !== undefined) && (
            <span className="text-[10px] text-ops-muted font-mono">
              Res: {alert.resolutionTimeSeconds ?? alert.metrics?.resolutionTimeSeconds}s
            </span>
          )}
        </div>
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <button onClick={() => onView(alert)} title="View" className="p-1.5 rounded hover:bg-white/10 text-ops-accent2">
            <Eye className="w-4 h-4" />
          </button>
          {canAct && (alert.status === 'NEW' || alert.status === 'DETECTED' || alert.status === 'ALERTED') && (
            <button onClick={() => onAcknowledge(alert)} title="Acknowledge" className="p-1.5 rounded hover:bg-white/10 text-yellow-400">
              <CheckCircle2 className="w-4 h-4" />
            </button>
          )}
          {canAct && alert.status !== 'RESOLVED' && alert.status !== 'FALSE_ALARM' && (
            <button onClick={() => onResolve(alert)} title="Resolve" className="p-1.5 rounded hover:bg-white/10 text-green-400">
              <ShieldCheck className="w-4 h-4" />
            </button>
          )}
        </div>
      </td>
    </tr>
  )
}

export { timeAgo }
