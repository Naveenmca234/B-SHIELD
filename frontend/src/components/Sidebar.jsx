import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Video, Bell, History, Car, Users, Camera, Settings, LogOut, ShieldHalf,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, roles: ['admin', 'operator', 'viewer'] },
  { to: '/live', label: 'Live Surveillance', icon: Video, roles: ['admin', 'operator', 'viewer'] },
  { to: '/alerts', label: 'Alerts', icon: Bell, roles: ['admin', 'operator', 'viewer'] },
  { to: '/events', label: 'Events', icon: History, roles: ['admin', 'operator', 'viewer'] },
  { to: '/vehicles', label: 'Vehicles / ANPR', icon: Car, roles: ['admin', 'operator', 'viewer'] },
  { to: '/persons', label: 'Persons', icon: Users, roles: ['admin', 'operator', 'viewer'] },
  { to: '/cameras', label: 'Cameras', icon: Camera, roles: ['admin'] },
  { to: '/settings', label: 'Settings', icon: Settings, roles: ['admin'] },
]

export default function Sidebar() {
  const { user, logout, hasRole } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <aside className="w-64 shrink-0 h-screen sticky top-0 flex flex-col glass-panel border-r border-ops-border">
      <div className="px-5 py-5 border-b border-ops-border">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-ops-accent to-ops-accent2 flex items-center justify-center shadow-glow">
            <ShieldHalf className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-extrabold tracking-wide text-white leading-tight">B-SHIELD</div>
            <div className="text-[10px] text-ops-muted leading-tight">IBVAP Border Surveillance</div>
          </div>
        </div>
      </div>


      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
        {NAV_ITEMS.filter((item) => hasRole(item.roles)).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                isActive
                  ? 'bg-ops-accent/15 text-ops-accent2 border border-ops-accent/30'
                  : 'text-ops-muted hover:text-white hover:bg-white/5 border border-transparent'
              }`
            }
          >
            <item.icon className="w-4 h-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-ops-border">
        <div className="px-3 py-2 mb-2 rounded-lg bg-white/5">
          <div className="text-xs font-semibold text-white truncate">{user?.fullName || user?.username}</div>
          <div className="text-[10px] uppercase tracking-wider text-ops-accent2">{user?.role}</div>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-ops-muted hover:text-red-400 hover:bg-red-500/10 transition-all"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </div>
    </aside>
  )
}
