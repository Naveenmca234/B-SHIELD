import { useState } from 'react'
import { MapPin, Users, Car, Eye, AlertOctagon } from 'lucide-react'
import { StatusBadge, SeverityBadge, VisibilityBadge } from './Badges'
import { DemoTag } from './States'
import { API_URL } from '../services/api'

export default function CameraCard({ camera, live, onClick }) {
  const [imgError, setImgError] = useState(false)
  const isOnline = camera.status === 'ONLINE'
  const threatLevel = live?.threatLevel || 'LOW'

  return (
    <div
      onClick={onClick}
      className="glass-panel rounded-xl overflow-hidden shadow-glass hover:border-ops-accent/40 border border-ops-border transition-all cursor-pointer group"
    >
      <div className="relative aspect-video bg-black flex items-center justify-center overflow-hidden">
        {isOnline && !imgError ? (
          <img
            src={`${API_URL}/live/stream/${camera.cameraId}`}
            alt={camera.name}
            className="w-full h-full object-cover"
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="flex flex-col items-center gap-2 text-ops-muted">
            <AlertOctagon className="w-8 h-8 opacity-40" />
            <span className="text-xs">{camera.error || 'Camera Offline'}</span>
            {camera.sourceType === 'RTSP' && <DemoTag />}
          </div>
        )}

        <div className="absolute top-2 left-2">
          <StatusBadge status={camera.status} />
        </div>
        <div className="absolute top-2 right-2">
          <SeverityBadge severity={threatLevel} />
        </div>
        {camera.sourceType === 'RTSP' && isOnline === false && (
          <div className="absolute bottom-2 left-2"><DemoTag /></div>
        )}
      </div>

      <div className="p-4">
        <div className="flex items-start justify-between mb-2">
          <div>
            <h3 className="font-bold text-white text-sm">{camera.name}</h3>
            <div className="flex items-center gap-1 text-[11px] text-ops-muted mt-0.5">
              <MapPin className="w-3 h-3" /> {camera.location}
            </div>
          </div>
          <span className="text-[10px] font-mono text-ops-muted bg-white/5 px-1.5 py-0.5 rounded">{camera.cameraId}</span>
        </div>

        <div className="flex items-center gap-4 text-xs text-ops-muted mt-3">
          <div className="flex items-center gap-1"><Users className="w-3.5 h-3.5" /> {live?.people ?? 0}</div>
          <div className="flex items-center gap-1"><Car className="w-3.5 h-3.5" /> {live?.vehicles ?? 0}</div>
          <div className="flex items-center gap-1"><Eye className="w-3.5 h-3.5" /> {live?.unknown ?? 0} unknown</div>
        </div>
      </div>
    </div>
  )
}
