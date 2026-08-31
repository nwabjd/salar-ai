import { useState } from 'react'
import { Camera, Send, X } from 'lucide-react'
import { SalarApi } from '../api'

export default function VisionView({ api }: { api: SalarApi }) {
  const [prompt, setPrompt] = useState('What do you see in this screenshot? Explain in detail.')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState('')

  const capture = async () => {
    setLoading(true)
    setError('')
    try {
      setResult(await api.visionScreenshot(prompt))
    } catch (e) {
      setError((e as Error).message || 'Could not capture screenshot')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="ws-scroll ws-vision">
      <div className="ws-vision__head">
        <h2>Screenshot Intelligence</h2>
        <p>Capture the desktop or upload an image for analysis.</p>
      </div>

      <div className="ws-vision__controls">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Ask a question about the screenshot..."
          rows={3}
        />
        <button className="ws-vision__capture" onClick={capture} disabled={loading}>
          <Camera size={16} /> {loading ? 'Analyzing...' : 'Capture & Analyze'}
        </button>
      </div>

      {error && <div className="ws-vision__error">{error}</div>}
      {result && (
        <div className="ws-vision__result">
          <h3>Analysis</h3>
          <p>{result.answer || JSON.stringify(result)}</p>
        </div>
      )}
    </div>
  )
}
