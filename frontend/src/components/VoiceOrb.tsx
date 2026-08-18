import { GoogleGenAI } from "@google/genai"
import { Orb } from "orb-ui"
import { createGeminiLiveAdapter } from "orb-ui/adapters"

const adapter = createGeminiLiveAdapter({
  connect: async (callbacks) => {
    const token = await fetch("/api/gemini-live-token", { method: "POST" })
      .then((response) => response.json())
    const client = new GoogleGenAI({
      apiKey: token.value,
      httpOptions: { apiVersion: "v1alpha" }
    })
    return client.live.connect({ model: token.model, config: token.config, callbacks })
  }
})

export function VoiceOrb() {
  return <Orb adapter={adapter} theme="circle" aria-label="Start Gemini assistant" />
}
