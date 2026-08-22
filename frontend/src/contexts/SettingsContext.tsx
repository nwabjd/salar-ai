import React, { createContext, useContext, useState, useEffect } from 'react'

interface Settings {
  darkMode: boolean
  soundEffects: boolean
  notifications: boolean
  streaming: boolean
}

interface SettingsContextType {
  settings: Settings
  toggle: (key: keyof Settings) => void
}

const DEFAULTS: Settings = {
  darkMode: true,
  soundEffects: true,
  notifications: true,
  streaming: true,
}

const SettingsContext = createContext<SettingsContextType>({
  settings: DEFAULTS,
  toggle: () => {},
})

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<Settings>(() => {
    try {
      const stored = localStorage.getItem('salaar-settings')
      return stored ? { ...DEFAULTS, ...JSON.parse(stored) } : DEFAULTS
    } catch {
      return DEFAULTS
    }
  })

  useEffect(() => {
    localStorage.setItem('salaar-settings', JSON.stringify(settings))
  }, [settings])

  const toggle = (key: keyof Settings) => {
    setSettings((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  return (
    <SettingsContext.Provider value={{ settings, toggle }}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  return useContext(SettingsContext)
}
