import { useEffect, useState, useCallback } from 'react'
import { Save } from 'lucide-react'
import Layout from '../components/Layout'
import { Loading, ErrorState } from '../components/States'
import api from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'
import { useToast } from '../context/ToastContext'

export default function Settings() {
  const [form, setForm] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const { status: wsStatus } = useWebSocket()
  const { push } = useToast()

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/settings')
      setForm(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to load settings.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  function update(key, value) { setForm((f) => ({ ...f, [key]: value })) }

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    try {
      await api.put('/settings', form)
      push('Settings saved successfully.', 'success')
      load()
    } catch (e) {
      push(e.response?.data?.detail || 'Failed to save settings.', 'error')
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Layout title="Settings" wsStatus={wsStatus}><Loading /></Layout>
  if (error) return <Layout title="Settings" wsStatus={wsStatus}><ErrorState message={error} onRetry={load} /></Layout>

  return (
    <Layout title="Settings" subtitle="Threat scoring, visibility thresholds, and system configuration" wsStatus={wsStatus}>
      <form onSubmit={handleSubmit} className="max-w-3xl space-y-6">
        <Section title="Threat Score Configuration" desc="Weights are added together to compute the 0-100 risk score. Changes apply to newly processed frames.">
          <div className="grid grid-cols-2 gap-4">
            <NumField label="Unknown Person Weight" value={form.weightUnknownPerson} onChange={(v) => update('weightUnknownPerson', v)} />
            <NumField label="Night Movement Weight" value={form.weightNightMovement} onChange={(v) => update('weightNightMovement', v)} />
            <NumField label="Fence Crossing Weight" value={form.weightFenceCrossing} onChange={(v) => update('weightFenceCrossing', v)} />
            <NumField label="Vehicle Nearby Weight" value={form.weightVehicleNearby} onChange={(v) => update('weightVehicleNearby', v)} />
            <NumField label="High-Risk Zone Weight" value={form.weightHighRiskZone} onChange={(v) => update('weightHighRiskZone', v)} />
          </div>
        </Section>

        <Section title="Night Hours" desc="Default hours used when a camera does not specify its own.">
          <div className="grid grid-cols-2 gap-4">
            <FormField label="Night Start">
              <input type="time" value={form.nightStart} onChange={(e) => update('nightStart', e.target.value)} className="input" />
            </FormField>
            <FormField label="Night End">
              <input type="time" value={form.nightEnd} onChange={(e) => update('nightEnd', e.target.value)} className="input" />
            </FormField>
          </div>
        </Section>

        <Section title="Visibility Thresholds" desc="Visibility score (0-100) boundaries for CLEAR / MODERATE / POOR classification.">
          <div className="grid grid-cols-2 gap-4">
            <NumField label="Clear Threshold" value={form.visibilityClearThreshold} onChange={(v) => update('visibilityClearThreshold', v)} />
            <NumField label="Moderate Threshold" value={form.visibilityModerateThreshold} onChange={(v) => update('visibilityModerateThreshold', v)} />
          </div>
        </Section>

        <Section title="Alert Cooldown" desc="Minimum seconds between duplicate alerts of the same type on the same camera (debouncing).">
          <NumField label="Cooldown (seconds)" value={form.alertCooldownSeconds} onChange={(v) => update('alertCooldownSeconds', v)} />
        </Section>

        <Section title="System Settings" desc="Connection endpoints and detection defaults.">
          <div className="grid grid-cols-2 gap-4">
            <FormField label="API URL">
              <input value={form.apiUrl} onChange={(e) => update('apiUrl', e.target.value)} className="input" />
            </FormField>
            <FormField label="WebSocket URL">
              <input value={form.websocketUrl} onChange={(e) => update('websocketUrl', e.target.value)} className="input" />
            </FormField>
            <FormField label="Upload Directory">
              <input value={form.uploadDir} onChange={(e) => update('uploadDir', e.target.value)} className="input" />
            </FormField>
            <NumField label="Detection Confidence Threshold" step="0.05" value={form.detectionConfidenceThreshold} onChange={(v) => update('detectionConfidenceThreshold', v)} />
          </div>
        </Section>

        <button type="submit" disabled={saving} className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-ops-accent to-ops-accent2 text-white font-semibold text-sm disabled:opacity-60">
          <Save className="w-4 h-4" /> {saving ? 'Saving…' : 'Save Settings'}
        </button>
      </form>
      <style>{`.input { width: 100%; background: rgba(255,255,255,0.05); border: 1px solid #1c2438; border-radius: 8px; padding: 8px 12px; font-size: 13px; color: white; }`}</style>
    </Layout>
  )
}

function Section({ title, desc, children }) {
  return (
    <div className="glass-panel rounded-xl p-5">
      <h3 className="text-sm font-bold text-white mb-1">{title}</h3>
      {desc && <p className="text-xs text-ops-muted mb-4">{desc}</p>}
      {children}
    </div>
  )
}

function FormField({ label, children }) {
  return (
    <div>
      <label className="block text-xs text-ops-muted mb-1">{label}</label>
      {children}
    </div>
  )
}

function NumField({ label, value, onChange, step = 1 }) {
  return (
    <FormField label={label}>
      <input type="number" step={step} value={value ?? ''} onChange={(e) => onChange(Number(e.target.value))} className="input" />
    </FormField>
  )
}
