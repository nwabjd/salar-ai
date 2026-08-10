import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const main = readFileSync(new URL('./main.tsx', import.meta.url), 'utf8')
const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8')

describe('Ambient Companion workspace contract', () => {
  it('provides focused conversation history and compact tools', () => {
    expect(main).toContain('New conversation')
    expect(main).toContain('Recent conversations')
    expect(main).toContain('Tools')
    expect(main).toContain('How can I help?')
    expect(main).not.toContain('<StatusRail/>')
  })

  it('ships responsive rails, drawers, and an anchored composer', () => {
    expect(styles).toContain('.conversation-rail')
    expect(styles).toContain('.tools-drawer')
    expect(styles).toContain('.profile-menu')
    expect(styles).toContain('@media(max-width:900px)')
    expect(styles).toContain('@media(max-width:640px)')
  })
})
