import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const main = readFileSync(new URL('./main.tsx', import.meta.url), 'utf8')

describe('WhatsApp auto-reply control', () => {
  it('loads and updates the existing per-user backend setting', () => {
    expect(main).toContain('api.whatsappAutoReplyGet()')
    expect(main).toContain('api.whatsappAutoReplySet(nextEnabled)')
  })

  it('renders an accessible on/off switch in the WhatsApp card', () => {
    expect(main).toContain('role="switch"')
    expect(main).toContain('aria-checked={waAutoReply === true}')
    expect(main).toContain("waAutoReply ? 'On' : 'Off'")
    expect(main).toContain('Auto reply')
  })

  it('disables the switch while disconnected or saving', () => {
    expect(main).toContain("disabled={waStatus !== 'connected' || waAutoReply === null || waAutoReplySaving}")
  })
})
