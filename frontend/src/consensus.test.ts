import { describe, expect, it } from 'vitest'
import { CONSENSUS_VALUE, consensusChip, pickConsensusVerifier } from './consensus'
import type { ConsensusMeta } from './consensus'

describe('Consensus Dual-Brain helpers', () => {
  it('picks the E4B companion when both brains are installed', () => {
    expect(pickConsensusVerifier(['salar-gemma4-e2b', 'salar-gemma4-e4b'], 'salar-gemma4-e2b')).toBe('salar-gemma4-e4b')
  })

  it('never picks the primary as the verifier', () => {
    expect(pickConsensusVerifier(['salar-gemma4-e2b', 'salar-gemma4-e4b'], 'salar-gemma4-e4b')).toBe('salar-gemma4-e2b')
  })

  it('falls back to any other installed model', () => {
    expect(pickConsensusVerifier(['a', 'b'], 'a')).toBe('b')
  })

  it('returns undefined when no other brain exists', () => {
    expect(pickConsensusVerifier(['solo'], 'solo')).toBeUndefined()
  })

  it('renders a chip for each agreement level', () => {
    const meta = (agreement: ConsensusMeta['agreement']): ConsensusMeta => ({ used: true, primary: 'p', verifier: 'v', agreement })
    expect(consensusChip(meta('both'))).toContain('both brains agreed')
    expect(consensusChip(meta('partial'))).toContain('partial')
    expect(consensusChip(meta('conflict'))).toContain('conflict')
    expect(consensusChip(meta('fallback'))).toContain('primary brain failed')
  })

  it('counts discrepancies in the partial chip', () => {
    expect(consensusChip({ used: true, primary: 'p', verifier: 'v', agreement: 'partial', discrepancies: [{ type: 'warning' }, { type: 'warning' }] })).toContain('2 discrepancies')
  })

  it('renders nothing when consensus was not used', () => {
    expect(consensusChip(undefined)).toBe('')
    expect(consensusChip({ ...({ used: false } as ConsensusMeta) })).toBe('')
  })

  it('exposes a sentinel value distinct from any model name', () => {
    expect(CONSENSUS_VALUE).toBe('__consensus__')
  })
})