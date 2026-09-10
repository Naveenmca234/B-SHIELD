export function SeverityBadge({ severity }) {
  const styles = {
    LOW: 'bg-green-500/15 text-green-400 border-green-500/30',
    MEDIUM: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
    HIGH: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
    CRITICAL: 'bg-red-500/15 text-red-400 border-red-500/30 animate-pulse-slow',
  }
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold border ${styles[severity] || styles.LOW}`}>
      {severity}
    </span>
  )
}

export function StatusBadge({ status }) {
  const isAuthorized = status === 'AUTHORIZED'
  const isOnline = status === 'ONLINE'
  const isOffline = status === 'OFFLINE'

  if (status === 'AUTHORIZED' || status === 'UNKNOWN') {
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${
        isAuthorized ? 'bg-green-500/15 text-green-400 border-green-500/30' : 'bg-orange-500/15 text-orange-400 border-orange-500/30'
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${isAuthorized ? 'bg-green-400' : 'bg-orange-400'}`} />
        {isAuthorized ? 'AUTHORIZED PERSON' : 'UNKNOWN PERSON'}
      </span>
    )
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${
      isOnline ? 'bg-green-500/15 text-green-400 border-green-500/30' : 'bg-red-500/15 text-red-400 border-red-500/30'
    }`}>
      <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-green-400 live-dot' : 'bg-red-400'}`} />
      {status}
    </span>
  )
}

export function VisibilityBadge({ status }) {
  const styles = {
    CLEAR: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
    MODERATE: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
    POOR: 'bg-red-500/15 text-red-400 border-red-500/30',
  }
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-md text-xs font-semibold border ${styles[status] || styles.MODERATE}`}>
      Visibility: {status}
    </span>
  )
}

export function SurveillanceHealthBadge({ health }) {
  if (!health) return null
  const state = health.healthState || health.status || 'HEALTHY'
  const styles = {
    HEALTHY: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    DEGRADED: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    CRITICAL: 'bg-rose-500/15 text-rose-400 border-rose-500/30 animate-pulse',
    OFFLINE: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
  }
  return (
    <div className="inline-flex items-center gap-1.5">
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${styles[state] || styles.OFFLINE}`}>
        <span className={`w-1.5 h-1.5 rounded-full ${state === 'HEALTHY' ? 'bg-emerald-400' : state === 'DEGRADED' ? 'bg-amber-400' : state === 'CRITICAL' ? 'bg-rose-400' : 'bg-slate-400'}`} />
        {state}
        {state !== 'OFFLINE' && health.fps > 0 && <span className="text-[10px] font-mono opacity-80">({health.fps} FPS)</span>}
      </span>
      {health.coverageGap && (
        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-600/30 text-red-300 border border-red-500/40 uppercase">
          Coverage Gap
        </span>
      )}
    </div>
  )
}

export function formatEventType(type) {
  const map = {
    'INTRUSION_DETECTED': 'Virtual Fence Intrusion',
    'LOITERING_DETECTED': 'Perimeter Loitering Detected',
    'UNKNOWN_PERSON': 'Unknown Person Detected',
    'NIGHT_MOVEMENT': 'Night-time Movement Detected',
    'POSSIBLE_INTRUSION': 'Possible Perimeter Intrusion',
    'VEHICLE_DETECTED': 'Vehicle Detected',
  }
  return map[type] || (type ? type.replace(/_/g, ' ') : 'Security Incident')
}


