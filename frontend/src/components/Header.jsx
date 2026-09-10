import { useEffect, useState } from 'react'
import { Wifi, WifiOff, Bell, Radio } from 'lucide-react'
import { useI18n } from '../context/I18nContext'

export default function Header({ title, subtitle, wsStatus = 'DISCONNECTED', alertCount = 0 }) {
  const [now, setNow] = useState(new Date())
  const { lang, setLang, t } = useI18n()

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const connected = wsStatus === 'CONNECTED'

  return (
    <header className="sticky top-0 z-30 glass-panel border-b border-ops-border px-6 py-4 flex items-center justify-between">
      <div>
        <h1 className="text-lg font-bold text-white tracking-tight">{title}</h1>
        {subtitle && <p className="text-xs text-ops-muted mt-0.5">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-5">
        <div className="hidden md:flex items-center gap-2 text-xs text-ops-muted mono">
          <Radio className="w-3.5 h-3.5 text-ops-accent2" />
          {now.toLocaleDateString()} &nbsp;
          <span className="text-white">{now.toLocaleTimeString()}</span>
        </div>

        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold border ${
          connected
            ? 'bg-green-500/15 text-green-400 border-green-500/30'
            : 'bg-red-500/15 text-red-400 border-red-500/30'
        }`}>
          {connected ? <Wifi className="w-3.5 h-3.5" /> : <WifiOff className="w-3.5 h-3.5" />}
          {connected ? t('systemLive') : t('disconnected')}
        </div>

        {/* Language switcher */}
        <button
          onClick={() => setLang(lang === 'en' ? 'hi' : 'en')}
          className="px-2 py-0.5 rounded text-[11px] font-bold font-mono bg-white/5 hover:bg-white/10 text-ops-accent2 border border-ops-border transition"
          title="Switch Language / भाषा बदलें"
        >
          {lang === 'en' ? 'EN | हिन्दी' : 'हिन्दी | EN'}
        </button>

        <div className="relative" title={alertCount > 0 ? `${alertCount} Unacknowledged Security Alert(s)` : 'No Unacknowledged Alerts'}>
          <Bell className="w-4.5 h-4.5 text-ops-muted" />
          {alertCount > 0 && (
            <span className="absolute -top-2 -right-2 w-4 h-4 rounded-full bg-red-500 text-[9px] font-bold flex items-center justify-center text-white">
              {alertCount > 9 ? '9+' : alertCount}
            </span>
          )}
        </div>
      </div>
    </header>
  )
}
