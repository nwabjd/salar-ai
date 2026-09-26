// Consensus Dual-Brain Mode helpers.
// The local model picker offers "Consensus (E2B + E4B)": SALAR runs both
// installed Gemma 4 brains in parallel and returns one merged answer plus an
// agreement signal (both / partial / conflict / fallback).

export const CONSENSUS_VALUE = '__consensus__'

export type ConsensusMeta = {
  used: boolean
  primary: string
  verifier: string
  agreement: 'both' | 'partial' | 'conflict' | 'fallback'
  verified_calls?: number
  discrepancies?: Array<{ type: string; tool?: string; note?: string }>
}

/** Pick the other brain when the user runs Consensus mode. Prefers the E4
 *  companion (higher tool-calling reliability) but falls back to any other
 *  installed model. */
export function pickConsensusVerifier(models: string[], primary: string): string | undefined {
  const candidates = primary ? models.filter((m) => m !== primary) : models
  if (!candidates.length) return undefined
  return (
    candidates.find((m) => m === 'salar-gemma4-e4b') ||
    candidates.find((m) => m === 'salar-gemma4-e2b') ||
    candidates[0]
  )
}

/** Short chip text appended under a local answer when Consensus mode ran. */
export function consensusChip(c?: ConsensusMeta): string {
  if (!c || !c.used) return ''
  if (c.agreement === 'both') return '\n\n[🧠 consensus: both brains agreed]'
  if (c.agreement === 'fallback') return `\n\n[⚠️ consensus: primary brain failed — answer from ${c.verifier}]`
  const n = c.discrepancies?.length ?? 0
  if (c.agreement === 'conflict') return '\n\n[⚠️ consensus: conflict — brains disagreed on a tool result]'
  return `\n\n[🧠 consensus: partial — ${n ? `${n} discrepanc${n > 1 ? 'ies' : 'y'}` : 'answers differed'}]`
}