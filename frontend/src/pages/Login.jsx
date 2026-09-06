import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldHalf, Lock, User, Loader2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const { login, loading, error } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    const ok = await login(username, password)
    if (ok) navigate('/dashboard')
  }

  function fillDemo(role) {
    if (role === 'admin') { setUsername('admin'); setPassword('IBVAP@123') }
    if (role === 'operator') { setUsername('operator'); setPassword('Operator@123') }
    if (role === 'viewer') { setUsername('viewer'); setPassword('Viewer@123') }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden">
      <div className="absolute inset-0 opacity-20 pointer-events-none">
        <div className="absolute top-0 left-1/4 w-96 h-96 bg-ops-accent rounded-full blur-[120px]" />
        <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-ops-accent2 rounded-full blur-[120px]" />
      </div>

      <div className="relative w-full max-w-md">
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-ops-accent to-ops-accent2 flex items-center justify-center shadow-glow mb-4">
            <ShieldHalf className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">B-SHIELD</h1>
          <p className="text-sm font-semibold text-ops-accent2 mt-1">AI-Powered Intelligent Border Surveillance</p>
          <p className="text-xs text-ops-muted mt-0.5">IBVAP — Intelligent Border Video Analytics Platform</p>
          <p className="text-xs text-ops-text/80 mt-2 italic">
            "Transforming Existing CCTV into Intelligent Border Surveillance."
          </p>
        </div>


        <form onSubmit={handleSubmit} className="glass-panel rounded-2xl p-7 shadow-glass border border-ops-border">
          <h2 className="text-white font-bold mb-5">Command Center Access</h2>

          {error && (
            <div className="mb-4 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-xs">
              {error}
            </div>
          )}

          <div className="mb-4">
            <label className="block text-xs font-medium text-ops-muted mb-1.5">Username</label>
            <div className="relative">
              <User className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ops-muted" />
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full bg-white/5 border border-ops-border rounded-lg pl-10 pr-3 py-2.5 text-sm text-white focus:outline-none focus:border-ops-accent focus:ring-1 focus:ring-ops-accent transition"
                placeholder="Enter username"
                required
              />
            </div>
          </div>

          <div className="mb-5">
            <label className="block text-xs font-medium text-ops-muted mb-1.5">Password</label>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ops-muted" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-white/5 border border-ops-border rounded-lg pl-10 pr-3 py-2.5 text-sm text-white focus:outline-none focus:border-ops-accent focus:ring-1 focus:ring-ops-accent transition"
                placeholder="Enter password"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-gradient-to-r from-ops-accent to-ops-accent2 text-white font-semibold text-sm hover:opacity-90 transition flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {loading ? 'Authenticating…' : 'Sign In'}
          </button>

          <div className="mt-6 pt-5 border-t border-ops-border">
            <p className="text-[11px] text-ops-muted mb-2 text-center">Demo credentials (click to autofill)</p>
            <div className="grid grid-cols-3 gap-2">
              <button type="button" onClick={() => fillDemo('admin')} className="text-[11px] py-1.5 rounded-md bg-white/5 hover:bg-white/10 text-ops-text">Admin</button>
              <button type="button" onClick={() => fillDemo('operator')} className="text-[11px] py-1.5 rounded-md bg-white/5 hover:bg-white/10 text-ops-text">Operator</button>
              <button type="button" onClick={() => fillDemo('viewer')} className="text-[11px] py-1.5 rounded-md bg-white/5 hover:bg-white/10 text-ops-text">Viewer</button>
            </div>
          </div>
        </form>
      </div>
    </div>
  )
}
