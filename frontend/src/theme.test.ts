import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const theme = readFileSync(new URL('./theme.css', import.meta.url), 'utf8')
const main = readFileSync(new URL('./main.tsx', import.meta.url), 'utf8')

describe('approved SALAR visual system', () => {
  it('locks the dark canvas and exact effect colors', () => {
    expect(theme).toContain('--canvas: #050308')
    expect(main).toContain("['#5227FF','#FF9FFC','#B497CF']")
    expect(main).toContain('color="#fc42ff" colorTwo="#42fcff"')
  })

  it('excludes legacy warm palette and login portal', () => {
    for (const legacy of ['#edc9bd', '#f0d1c7', '#f5d8cb']) expect(theme).not.toContain(legacy)
    expect(main).not.toContain('type="email"')
    expect(main).not.toContain('Enter SALAR')
  })
})
