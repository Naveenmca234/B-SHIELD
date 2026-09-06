import { useState } from 'react'
import { Shield, AlertTriangle, Video, Wifi, WifiOff } from 'lucide-react'

// Demo outpost perimeter coordinates (normalized layout for visual command center)
const DEMO_COORDINATES = {
  'BOP-01': { x: 22, y: 35, name: 'Outpost North Alpha' },
  'BOP-02': { x: 50, y: 25, name: 'Central Sector Ridge' },
  'BOP-03': { x: 78, y: 40, name: 'East River Watch' },
  'BOP-04': { x: 45, y: 70, name: 'South Gate Perimeter' },
}

export default function PerimeterMap({ cameras = [], activeIncidents = [], onSelectCamera }) {
  const [hoveredCam, setHoveredCam] = useState(null)

  // Map cameras to positions
  const mappedCameras = cameras.map((cam, idx) => {
    const coords = DEMO_COORDINATES[cam.cameraId] || {
      x: 20 + ((idx * 28) % 70),
      y: 30 + ((idx * 25) % 50),
      name: cam.name,
    }
    const camIncidents = activeIncidents.filter((inc) => inc.cameraId === cam.cameraId)
    const isCritical = camIncidents.some((i) => i.severity === 'CRITICAL')
    const health = cam.health?.healthState || (cam.status === 'ONLINE' ? 'HEALTHY' : 'OFFLINE')
    return {
      ...cam,
      coords,
      incidents: camIncidents,
      isCritical,
      health,
    }
  })

  return (
    <div className="glass-panel rounded-xl p-4 flex flex-col h-full border border-ops-border">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-ops-accent2" />
          <span className="text-xs font-bold uppercase tracking-wider text-white">
            Perimeter Security Grid
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold bg-ops-accent/20 text-ops-accent2 border border-ops-accent/30">
            DEMO PERIMETER
          </span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-ops-muted">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-400"></span> Healthy
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-yellow-400"></span> Degraded
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-400"></span> Gap / Critical
          </span>
        </div>
      </div>

      <div className="relative flex-1 min-h-[260px] bg-ops-bg/80 rounded-lg overflow-hidden border border-ops-border/60">
        {/* Grid Background Pattern */}
        <div
          className="absolute inset-0 opacity-15"
          style={{
            backgroundImage:
              'linear-gradient(#2a3b5c 1px, transparent 1px), linear-gradient(90deg, #2a3b5c 1px, transparent 1px)',
            backgroundSize: '24px 24px',
          }}
        />

        {/* Perimeter Boundary Line */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none">
          {/* Virtual Border Line */}
          <line x1="5" y1="15" x2="95" y2="25" stroke="#3b82f6" strokeWidth="0.8" strokeDasharray="2,2" />
          <line x1="95" y1="25" x2="85" y2="85" stroke="#3b82f6" strokeWidth="0.8" strokeDasharray="2,2" />
          <line x1="85" y1="85" x2="10" y2="75" stroke="#3b82f6" strokeWidth="0.8" strokeDasharray="2,2" />
          <line x1="10" y1="75" x2="5" y2="15" stroke="#3b82f6" strokeWidth="0.8" strokeDasharray="2,2" />
        </svg>

        {/* Camera Nodes */}
        {mappedCameras.map((cam) => {
          const { x, y } = cam.coords
          const isSelected = hoveredCam?.cameraId === cam.cameraId
          const hasIncident = cam.incidents.length > 0

          let ringColor = 'border-green-500 bg-green-500/20 text-green-400'
          if (cam.health === 'DEGRADED') ringColor = 'border-yellow-500 bg-yellow-500/20 text-yellow-400'
          if (cam.health === 'CRITICAL' || cam.status === 'OFFLINE')
            ringColor = 'border-red-500 bg-red-500/20 text-red-400'

          return (
            <div
              key={cam.cameraId}
              className="absolute -translate-x-1/2 -translate-y-1/2 cursor-pointer z-10 transition-transform duration-200 hover:scale-125"
              style={{ left: `${x}%`, top: `${y}%` }}
              onClick={() => onSelectCamera && onSelectCamera(cam.cameraId)}
              onMouseEnter={() => setHoveredCam(cam)}
              onMouseLeave={() => setHoveredCam(null)}
            >
              {/* Pulse effect if active incident or critical gap */}
              {(hasIncident || cam.isCritical) && (
                <span className="absolute -inset-2 rounded-full animate-ping bg-red-500/40" />
              )}

              <div
                className={`w-7 h-7 rounded-full border-2 flex items-center justify-center shadow-lg backdrop-blur-md ${ringColor}`}
              >
                {cam.status === 'ONLINE' ? (
                  <Video className="w-3.5 h-3.5" />
                ) : (
                  <WifiOff className="w-3.5 h-3.5" />
                )}
              </div>

              <div className="absolute top-8 left-1/2 -translate-x-1/2 whitespace-nowrap bg-ops-bg/90 px-1.5 py-0.5 rounded border border-ops-border text-[9px] font-mono text-white pointer-events-none">
                {cam.cameraId}
              </div>
            </div>
          )
        })}

        {/* Hover Tooltip Card */}
        {hoveredCam && (
          <div
            className="absolute z-20 pointer-events-none bg-ops-card border border-ops-border p-3 rounded-lg shadow-xl text-xs w-52"
            style={{
              left: `${Math.min(75, Math.max(15, hoveredCam.coords.x))}%`,
              top: `${Math.min(70, Math.max(20, hoveredCam.coords.y + 12))}%`,
            }}
          >
            <div className="font-bold text-white flex items-center justify-between">
              <span>{hoveredCam.cameraId}</span>
              <span
                className={`text-[9px] px-1.5 py-0.2 rounded font-mono ${
                  hoveredCam.status === 'ONLINE' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                }`}
              >
                {hoveredCam.status}
              </span>
            </div>
            <div className="text-[11px] text-ops-muted mt-0.5">{hoveredCam.name}</div>
            <div className="mt-2 text-[10px] space-y-1 border-t border-ops-border pt-1.5">
              <div className="flex justify-between">
                <span className="text-ops-muted">Health:</span>
                <span className="font-bold text-white">{hoveredCam.health}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ops-muted">Active Alerts:</span>
                <span className="font-bold text-ops-accent2">{hoveredCam.incidents.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ops-muted">Zone:</span>
                <span className="font-mono text-white">{hoveredCam.mapZone || 'Demo Outpost'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ops-muted">GPS Pos:</span>
                <span className="font-mono text-ops-muted">
                  {hoveredCam.latitude && hoveredCam.longitude
                    ? `${hoveredCam.latitude.toFixed(4)}, ${hoveredCam.longitude.toFixed(4)}`
                    : 'NOT CONFIGURED'}
                </span>
              </div>
              {hoveredCam.health?.reasons && (
                <div className="text-[9px] text-ops-muted italic mt-1">
                  {hoveredCam.health.reasons[0]}
                </div>
              )}

            </div>
          </div>
        )}
      </div>
    </div>
  )
}
