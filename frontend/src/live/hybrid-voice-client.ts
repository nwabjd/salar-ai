type VoiceClient = {
  start(): Promise<void>
  sendText(text: string): void
  stop(): void
}

export class HybridVoiceClient implements VoiceClient {
  private active: VoiceClient
  private usingFallback = false
  private fallbackStart: Promise<void> | null = null

  constructor(
    private readonly native: VoiceClient,
    private readonly fallback: VoiceClient,
  ) {
    this.active = native
  }

  async start(): Promise<void> {
    try {
      await this.native.start()
    } catch {
      await this.activateFallback()
    }
  }

  async activateFallback(): Promise<void> {
    if (this.usingFallback) return this.fallbackStart || Promise.resolve()
    this.usingFallback = true
    this.native.stop()
    this.active = this.fallback
    this.fallbackStart = this.fallback.start()
    await this.fallbackStart
  }

  sendText(text: string): void {
    this.active.sendText(text)
  }

  stop(): void {
    this.native.stop()
    if (this.usingFallback) this.fallback.stop()
  }
}
