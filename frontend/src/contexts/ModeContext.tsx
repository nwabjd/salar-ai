import React, { createContext, useContext, useState, useEffect } from 'react'

export type SalaarMode = 'coder' | 'analyst' | 'generalist'

interface ModeContextType {
  mode: SalaarMode
  setMode: (mode: SalaarMode) => void
}

const MODE_KEY = 'salaar.mode'
const DEFAULT_MODE: SalaarMode = 'generalist'

const ModeContext = createContext<ModeContextType>({ mode: DEFAULT_MODE, setMode: () => {} })

export function ModeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<SalaarMode>(() => {
    try {
      const stored = localStorage.getItem(MODE_KEY)
      if (stored === 'coder' || stored === 'analyst' || stored === 'generalist') return stored
    } catch {}
    return DEFAULT_MODE
  })

  const setMode = (m: SalaarMode) => {
    setModeState(m)
    try { localStorage.setItem(MODE_KEY, m) } catch {}
  }

  return <ModeContext.Provider value={{ mode, setMode }}>{children}</ModeContext.Provider>
}

export function useMode() {
  return useContext(ModeContext)
}

export const MODE_INFO: Record<SalaarMode, { label: string; description: string; icon: string; prompt: string }> = {
  coder: {
    label: 'Coder',
    description: 'Code, debug, architecture',
    icon: '{ }',
    prompt: 'You are Salaar in Coder mode. Focus on code, technical solutions, debugging. Be precise, include code examples, explain architecture decisions.',
  },
  analyst: {
    label: 'Analyst',
    description: 'Research, data, reasoning',
    icon: '📊',
    prompt: 'You are Salaar in Analyst mode. Focus on data analysis, research, structured reasoning. Provide thorough analysis with evidence, break down complex problems.',
  },
  generalist: {
    label: 'Generalist',
    description: 'Everything else',
    icon: '✨',
    prompt: '',
  },
}
