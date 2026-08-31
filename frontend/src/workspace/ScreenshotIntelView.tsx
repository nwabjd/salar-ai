import { useEffect, useRef, useState } from 'react'
import { Camera, Copy, ExternalLink, Loader2, RefreshCw, Search, Trash2 } from 'lucide-react'
import { SalarApi } from '../api'

interface ScreenshotIntelViewProps {
  api: SalarApi
}

export default function ScreenshotIntelView({ api }: ScreenshotIntelViewProps) {
  const [history, setHistory] = useState<Array<{ id: string; prompt: string; answer: string; created: string }>>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [prompt, setPrompt] = useState('What do you see in this screenshot? Explain in detail.')
  const [running, setRunning] = useState(false)
  const [runningId, setRunningId] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.visionHistory()
      setHistory((res?.results ?? []).map((r) => ({ id: r.id, prompt: r.prompt, answer: r.answer, created: r.created_at })))
    } catch (e) {
      setError((e as Error).message || 'Could not load history')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api])

  const runScreenshot = async () => {
    setRunning(true)
    setError('')
    try {
      const res = await api.visionScreenshot(prompt.trim())
      if (res?.status === 'ok') {
        void load()
      } else {
        setError(res?.answer || 'Screenshot analysis failed')
      }
    } catch (e) {
      setError((e as Error).message || 'Screenshot failed')
    } finally {
      setRunning(false)
    }
  }

  const runUpload = async (file: File) => {
    setRunning(true)
    setError('')
    try {
      const res = await api.visionAnalyze(file, prompt.trim())
      if (res?.status === 'ok') {
        void load()
      } else {
        setError(res?.answer || 'Analysis failed')
      }
    } catch (e) {
      setError((e as Error).message || 'Upload analysis failed')
    } finally {
      setRunning(false)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) void runUpload(f)
    if (e.target) e.target.value = ''
  }

  return (
    <div className="ws-scroll ws-vis">
      <div className="ws-mem__head">
        <div>
          <h1 className="ws-mem__title">Screenshot Intel</h1>
          <p className="ws-mem__sub">Capture and analyze what's on your screen — instantly.</p>
        </div>
        <div className="ws-vis__actions">
          <label className="ws-vis__upload" htmlFor="vis-upload">
            <Camera size={14} /> Upload image
            <input id="vis-upload" type="file" accept="image/*" ref={fileInputRef} onChange={handleFileChange} style={{ display: 'none' }} />
          </label>
          <button className="ws-vis__run" onClick={runScreenshot} disabled={running || !prompt.trim()}>
            {running ? <><Loader2 size={14} className="ws-spin" /> Analyzing…</> : <><Camera size={14} /> Capture screen</>}
          </button>
        </div>
      </div>

      <div className="ws-vis__prompt">
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={2}
          placeholder="Prompt for analysis (optional)…"
          aria-label="Analysis prompt"
          disabled={running}
        />
      </div>

      {error && <div className="ws-mem__error" role="alert">{error}</div>}

      {loading ? (
        <div className="ws-mem__state">Loading history…</div>
      ) : history.length === 0 ? (
        <div className="ws-mem__state">
          <Camera size={22} strokeWidth={1.5} />
          <p>No analyses yet.</p>
          <small>Capture your screen or upload an image to get started.</small>
        </div>
      ) : (
        <ul className="ws-vis__list">
          {history.map((h) => (
            <li key={h.id} className="ws-vis__item">
              <div className="ws-vis__item-left">
                <div className="ws-vis__item-prompt">{h.prompt}</div>
                <div className="ws-vis__item-answer">{h.answer}</div>
                <div className="ws-vis__item-meta">{new Date(h.created).toLocaleString()}</div>
              </div>
              <div className="ws-vis__item-actions">
                <button className="ws-vis__icon-btn" onClick={() => navigator.clipboard.writeText(h.answer)} aria-label="Copy answer">
                  <Copy size={14} />
                </button>
                <button className="ws-vis__icon-btn" onClick={() => void load()} aria-label="Re-analyze">
                  <RefreshCw size={14} />
                </button>
                <button className="ws-vis__icon-btn ws-vis__icon-btn--danger" onClick={() => void api.deleteVision(h.id)} aria-label="Delete">
                  <Trash2 size={14} />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}