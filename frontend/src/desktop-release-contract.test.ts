import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const landing = readFileSync(new URL('./components/SalaarLanding.tsx', import.meta.url), 'utf8')
const releaseScript = readFileSync(new URL('../../scripts/build-release.ps1', import.meta.url), 'utf8')

describe('SALAR desktop release', () => {
  it('offers one stable Windows installer URL', () => {
    expect(landing).toContain('href="/downloads/SALAR-Setup.exe"')
    expect(landing).toContain('Download for Windows')
    expect(releaseScript).toContain('SALAR-Setup.exe')
    expect(releaseScript).toContain('Get-FileHash')
  })

  it('sets clear expectations for future platforms', () => {
    for (const platform of ['macOS', 'iOS', 'Android']) expect(landing).toContain(platform)
    expect(landing).toContain('["macOS", "MAC"]')
    expect(landing).toContain('["iOS", "IOS"]')
    expect(landing).toContain('["Android", "AND"]')
    expect(landing).toContain('Coming soon')
  })

  it('builds desktop from the shared production frontend', () => {
    expect(releaseScript).toContain('npm run build')
    expect(releaseScript).toContain('frontend\\dist')
    expect(releaseScript).toContain('desktop')
  })
})
