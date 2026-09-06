export default function KpiCard({ label, value, icon: Icon, tone = 'default', suffix }) {
  const toneStyles = {
    default: 'text-ops-accent2',
    danger: 'text-red-400',
    warning: 'text-orange-400',
    success: 'text-green-400',
  }
  return (
    <div className="glass-panel rounded-xl p-4 flex items-center justify-between shadow-glass hover:border-ops-accent/30 transition-colors">
      <div>
        <div className="text-xs text-ops-muted font-medium mb-1">{label}</div>
        <div className="text-2xl font-extrabold text-white">
          {value}
          {suffix && <span className="text-sm text-ops-muted font-medium ml-1">{suffix}</span>}
        </div>
      </div>
      {Icon && (
        <div className={`w-10 h-10 rounded-lg bg-white/5 flex items-center justify-center ${toneStyles[tone]}`}>
          <Icon className="w-5 h-5" />
        </div>
      )}
    </div>
  )
}
