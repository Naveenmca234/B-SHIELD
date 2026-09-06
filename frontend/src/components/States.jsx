import { Loader2, AlertTriangle, Inbox } from 'lucide-react'

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-ops-muted gap-3">
      <Loader2 className="w-6 h-6 animate-spin text-ops-accent" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export function ErrorState({ message = 'Something went wrong.', onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
      <AlertTriangle className="w-8 h-8 text-red-400" />
      <p className="text-sm text-ops-muted max-w-md">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 px-4 py-1.5 text-xs font-semibold rounded-md bg-ops-accent/15 text-ops-accent border border-ops-accent/30 hover:bg-ops-accent/25 transition">
          Retry
        </button>
      )}
    </div>
  )
}

export function EmptyState({ label = 'No data available.', icon: Icon = Inbox }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-ops-muted">
      <Icon className="w-8 h-8 opacity-40" />
      <span className="text-sm">{label}</span>
    </div>
  )
}

export function DemoTag() {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold tracking-wider bg-ops-accent2/15 text-ops-accent2 border border-ops-accent2/30">
      DEMO / SIMULATION
    </span>
  )
}
