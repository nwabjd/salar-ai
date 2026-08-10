import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const main = readFileSync(new URL('./main.tsx', import.meta.url), 'utf8')
const styles = readFileSync(new URL('./styles.css', import.meta.url), 'utf8')

describe('original SALAR workspace contract', () => {
  it('restores the command workspace and permanent status rail', () => {
    expect(main).toContain('<StatusRail/>')
    expect(main).toContain('What shall we accomplish?')
    expect(main).toContain('className="usage-chip"')
    expect(main).not.toContain('conversation-rail')
    expect(main).not.toContain('tools-drawer')
  })

  it('keeps the original LiquidEther color intensity', () => {
    expect(styles).not.toContain('.app-shell .liquid-stage{opacity:.2')
    expect(styles).toContain('.chat-workspace{display:flex}')
    expect(styles).toContain('.status-rail')
  })
})
