import { createContext, useContext, useState, useEffect } from 'react'

const translations = {
  en: {
    dashboard: 'Dashboard',
    live: 'Live Surveillance',
    alerts: 'Security Alerts',
    events: 'Audit Logs',
    vehicles: 'Vehicle ANPR',
    persons: 'Personnel Roster',
    cameras: 'Outpost Feeds',
    settings: 'System Settings',
    logout: 'Log Out',
    systemLive: 'SYSTEM LIVE',
    disconnected: 'DISCONNECTED',
    critical: 'CRITICAL',
    high: 'HIGH',
    medium: 'MEDIUM',
    low: 'LOW',
  },
  hi: {
    dashboard: 'डैशबोर्ड (Dashboard)',
    live: 'लाइव निगरानी (Live)',
    alerts: 'सुरक्षा अलर्ट (Alerts)',
    events: 'ऑडिट लॉग (Audit)',
    vehicles: 'वाहन पहचान (ANPR)',
    persons: 'कार्मिक रोस्टर (Personnel)',
    cameras: 'कैमरा चौकियां (Cameras)',
    settings: 'सिस्टम सेटिंग्स (Settings)',
    logout: 'लॉग आउट (Logout)',
    systemLive: 'सिस्टम सक्रिय (LIVE)',
    disconnected: 'संपर्क टूटा (OFFLINE)',
    critical: 'अति-गंभीर (CRITICAL)',
    high: 'उच्च (HIGH)',
    medium: 'मध्यम (MEDIUM)',
    low: 'सामान्य (LOW)',
  },
}

const I18nContext = createContext({
  lang: 'en',
  setLang: () => {},
  t: (k) => k,
})

export function I18nProvider({ children }) {
  const [lang, setLang] = useState(() => localStorage.getItem('ibvap_lang') || 'en')

  useEffect(() => {
    localStorage.setItem('ibvap_lang', lang)
  }, [lang])

  function t(key) {
    return translations[lang]?.[key] || translations.en[key] || key
  }

  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  )
}

export function useI18n() {
  return useContext(I18nContext)
}
