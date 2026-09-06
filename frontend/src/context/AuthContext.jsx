import { createContext, useContext, useState, useCallback } from 'react'
import api from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('ibvap_token'))
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('ibvap_user')
    return stored ? JSON.parse(stored) : null
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const login = useCallback(async (username, password) => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.post('/auth/login', { username, password })
      localStorage.setItem('ibvap_token', res.data.access_token)
      localStorage.setItem('ibvap_user', JSON.stringify(res.data.user))
      setToken(res.data.access_token)
      setUser(res.data.user)
      return true
    } catch (e) {
      setError(e.response?.data?.detail || 'Login failed. Please try again.')
      return false
    } finally {
      setLoading(false)
    }
  }, [])

  const logout = useCallback(async () => {
    try { await api.post('/auth/logout') } catch (e) { /* ignore */ }
    localStorage.removeItem('ibvap_token')
    localStorage.removeItem('ibvap_user')
    setToken(null)
    setUser(null)
  }, [])

  const hasRole = useCallback((roles) => {
    if (!user) return false
    if (!roles || roles.length === 0) return true
    return roles.includes(user.role)
  }, [user])

  return (
    <AuthContext.Provider value={{ user, token, login, logout, loading, error, hasRole }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
