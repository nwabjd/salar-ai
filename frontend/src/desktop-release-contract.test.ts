import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const landing = readFileSync(new URL('./components/SalaarLanding.tsx', import.meta.url), 'utf8')
const releaseScript = readFileSync(new URL('../../scripts/build-release.ps1', import.meta.url), 'utf8')

describe('SALAR desktop release', () => {
  it('offers stable Windows and macOS download URLs', () => {
    expect(landing).toContain('href="/downloads/SALAR-Setup.exe"')
    expect(landing).toContain('Download for Windows')
    expect(landing).toContain('href="/downloads/SALAR.app.zip"')
    expect(landing).toContain('Download for macOS')
    expect(releaseScript).toContain('SALAR-Setup.exe')
    expect(releaseScript).toContain('SALAR.app.zip')
    expect(releaseScript).toContain('Get-FileHash')
  })

  it('marks macOS as available and only iOS/Android as coming soon', () => {
    expect(landing).toContain(
      '<span className="platform-icon">MAC</span><span className="platform-status available">Available now</span>'
    )
    // The macOS placeholder must no longer appear in the "coming soon" list.
    expect(landing).not.toContain('["macOS", "MAC"]')
    expect(landing).toContain('["iOS", "IOS"]')
    expect(landing).toContain('["Android", "AND"]')
    for (const platform of ['iOS', 'Android']) expect(landing).toContain(platform)
    expect(landing).toContain('Coming soon')
  })

  it('builds the desktop from the shared production frontend and zips the macOS app', () => {
    expect(releaseScript).toContain('npm run build')
    expect(releaseScript).toContain('frontend\\dist')
    expect(releaseScript).toContain('desktop')
    expect(releaseScript).toContain('bundle\\macos')
    expect(releaseScript).toContain('bundle\\nsis')
    expect(releaseScript).toContain('Compress-Archive')
  })
})