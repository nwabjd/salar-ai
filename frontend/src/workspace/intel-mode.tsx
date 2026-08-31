import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

export type IntelMode =
  | 'auto'
  | 'fast'
  | 'think'
  | 'deep'
  | 'code'
  | 'research'
  | 'vision'
  | 'video'
  | 'translate'
  | 'supernova'

export interface IntelModeInfo {
  id: IntelMode
  name: string
  hint: string
}

export const INTEL_MODES: IntelModeInfo[] = [
  { id: 'auto', name: 'AUTO', hint: 'Adaptive — Salaar picks the best path.' },
  { id: 'fast', name: 'FAST', hint: 'Quick responses for simple requests.' },
  { id: 'think', name: 'THINK', hint: 'Reasoned, step-by-step answers.' },
  { id: 'deep', name: 'DEEP', hint: 'Heavy research & long-form analysis.' },
  { id: 'code', name: 'CODE', hint: 'Engineering-focused precision.' },
  { id: 'research', name: 'RESEARCH', hint: 'Gather, compare and cite sources.' },
  { id: 'vision', name: 'VISION', hint: 'Understand images and diagrams.' },
  { id: 'video', name: 'VIDEO', hint: 'Process video and motion content.' },
  { id: 'translate', name: 'TRANSLATE', hint: 'Translate between languages.' },
  { id: 'supernova', name: 'SUPERNOVA', hint: 'Full-spectrum agentic power.' },
]

const MODE_HINTS: Record<IntelMode, string> = {
  auto: '',
  fast: 'Answer quickly and concisely.',
  think: 'Work through the problem step by step before answering.',
  deep: 'Give an exhaustive, deeply researched, long-form answer.',
  code: 'Answer like a senior software engineer; prefer correct, idiomatic code.',
  research: 'Ground your answer in verifiable sources and call out uncertainty.',
  vision: 'Pay close attention to any images, screenshots or diagrams included.',
  video: 'Pay close attention to any video or motion content referenced.',
  translate: 'Translate precisely and preserve tone and meaning.',
  supernova: 'You have full workspace autonomy. Act as a capable agent and get the job done.',
}

const KEY = 'salaar.intel-mode'

interface IntelModeCtx {
  mode: IntelMode
  setMode: (m: IntelMode) => void
  info: IntelModeInfo
  /** whether FAST mode should request a fast response path */
  fast: boolean
  /** capability hint injected into the prompt prefix */
  prefix: string
}

const Ctx = createContext<IntelModeCtx | null>(null)

function readInitial(): IntelMode {
  try {
    const raw = localStorage.getItem(KEY)
    if (raw && INTEL_MODES.some((m) => m.id === raw)) return raw as IntelMode
  } catch {
    /* ignore */
  }
  return 'auto'
}

export function IntelModeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<IntelMode>(readInitial)

  useEffect(() => {
    try {
      localStorage.setItem(KEY, mode)
    } catch {
      /* ignore */
    }
  }, [mode])

  const value = useMemo<IntelModeCtx>(() => {
    const info = INTEL_MODES.find((m) => m.id === mode) ?? INTEL_MODES[0]
    return {
      mode,
      setMode,
      info,
      fast: mode === 'fast',
      prefix: MODE_HINTS[mode],
    }
  }, [mode])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useIntelMode(): IntelModeCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useIntelMode must be used within IntelModeProvider')
  return ctx
}