import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import { I18nProvider } from './context/I18nContext'
import ProtectedRoute from './components/ProtectedRoute'
import { Loading } from './components/States'

const Login = lazy(() => import('./pages/Login'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Live = lazy(() => import('./pages/Live'))
const Alerts = lazy(() => import('./pages/Alerts'))
const Events = lazy(() => import('./pages/Events'))
const Vehicles = lazy(() => import('./pages/Vehicles'))
const Persons = lazy(() => import('./pages/Persons'))
const Cameras = lazy(() => import('./pages/Cameras'))
const Settings = lazy(() => import('./pages/Settings'))

export default function App() {
  return (
    <AuthProvider>
      <I18nProvider>
        <ToastProvider>
          <BrowserRouter>
            <Suspense fallback={<div className="h-screen flex items-center justify-center bg-ops-bg"><Loading label="Loading B-SHIELD Command System…" /></div>}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
                <Route path="/live" element={<ProtectedRoute><Live /></ProtectedRoute>} />
                <Route path="/alerts" element={<ProtectedRoute><Alerts /></ProtectedRoute>} />
                <Route path="/events" element={<ProtectedRoute><Events /></ProtectedRoute>} />
                <Route path="/vehicles" element={<ProtectedRoute><Vehicles /></ProtectedRoute>} />
                <Route path="/persons" element={<ProtectedRoute><Persons /></ProtectedRoute>} />
                <Route path="/cameras" element={<ProtectedRoute roles={['admin']}><Cameras /></ProtectedRoute>} />
                <Route path="/settings" element={<ProtectedRoute roles={['admin']}><Settings /></ProtectedRoute>} />
                <Route path="/" element={<Navigate to="/dashboard" replace />} />
                <Route path="*" element={<Navigate to="/dashboard" replace />} />
              </Routes>
            </Suspense>
          </BrowserRouter>
        </ToastProvider>
      </I18nProvider>
    </AuthProvider>
  )
}
