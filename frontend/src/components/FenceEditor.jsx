import { useRef, useState, useEffect } from 'react'
import { RotateCcw, Save } from 'lucide-react'
import { API_URL } from '../services/api'

/**
 * Interactive virtual fence polygon editor. Click to add points on top of
 * the camera's live/still frame; points are stored normalized (0-1) so
 * they remain valid at any resolution.
 */
export default function FenceEditor({ camera, initialPoints = [], onSave }) {
  const containerRef = useRef(null)
  const [points, setPoints] = useState(initialPoints)
  const [imgError, setImgError] = useState(false)

  useEffect(() => { setPoints(initialPoints) }, [camera?.cameraId])

  function handleClick(e) {
    const rect = containerRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left) / rect.width
    const y = (e.clientY - rect.top) / rect.height
    setPoints((p) => [...p, { x: Math.max(0, Math.min(1, x)), y: Math.max(0, Math.min(1, y)) }])
  }

  function reset() { setPoints([]) }

  const pathStr = points.map((p) => `${p.x * 100},${p.y * 100}`).join(' ')

  return (
    <div>
      <div
        ref={containerRef}
        onClick={handleClick}
        className="relative aspect-video bg-black rounded-lg overflow-hidden cursor-crosshair border border-ops-border"
      >
        {camera?.status === 'ONLINE' && !imgError ? (
          <img src={`${API_URL}/live/stream/${camera.cameraId}`} className="w-full h-full object-cover pointer-events-none" onError={() => setImgError(true)} />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-ops-muted text-xs">
            Camera offline — click anywhere to place fence points against this placeholder frame.
          </div>
        )}

        <svg className="absolute inset-0 w-full h-full pointer-events-none" viewBox="0 0 100 100" preserveAspectRatio="none">
          {points.length >= 3 && (
            <polygon points={pathStr} fill="rgba(239,68,68,0.2)" stroke="#ef4444" strokeWidth="0.5" />
          )}
          {points.length > 0 && points.length < 3 && (
            <polyline points={pathStr} fill="none" stroke="#ef4444" strokeWidth="0.5" />
          )}
          {points.map((p, i) => (
            <circle key={i} cx={p.x * 100} cy={p.y * 100} r="1.2" fill="#ef4444" />
          ))}
        </svg>

        {points.length >= 3 && (
          <div className="absolute top-2 left-2 px-2 py-1 rounded bg-red-500/80 text-white text-[10px] font-bold">
            RESTRICTED ZONE
          </div>
        )}
      </div>

      <div className="flex items-center justify-between mt-3">
        <span className="text-xs text-ops-muted">{points.length} point{points.length !== 1 ? 's' : ''} placed (minimum 3 to form a zone)</span>
        <div className="flex gap-2">
          <button onClick={reset} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white/5 hover:bg-white/10 text-ops-text">
            <RotateCcw className="w-3.5 h-3.5" /> Reset
          </button>
          <button
            onClick={() => onSave(points)}
            disabled={points.length < 3}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-ops-accent/20 text-ops-accent2 hover:bg-ops-accent/30 disabled:opacity-40 border border-ops-accent/30"
          >
            <Save className="w-3.5 h-3.5" /> Save Fence
          </button>
        </div>
      </div>
    </div>
  )
}
