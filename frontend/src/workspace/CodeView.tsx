import { useState } from 'react'
import { Play, Loader2 } from 'lucide-react'
import { SalarApi } from '../api'

interface CodeViewProps {
  api: SalarApi
}

export default function CodeView({ api }: CodeViewProps) {
  const [code, setCode] = useState('print("Hello SALAR")')
  const [output, setOutput] = useState('')
  const [running, setRunning] = useState(false)

  const runCode = async () => {
    setRunning(true)
    setOutput('Running...')
    try {
      const res = await api.codeExecute(code)
      setOutput(res.stdout || res.stderr || 'No output')
    } catch (e) {
      setOutput(`Error: ${e}`)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="ws-scroll ws-mem">
      <div className="ws-mem__head">
        <div>
          <h1 className="ws-mem__title">Code</h1>
          <p className="ws-mem__sub">Execute Python in a secure sandbox.</p>
        </div>
      </div>
      <div className="ws-mem__form" style={{ gap: '15px' }}>
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          rows={10}
          style={{ fontFamily: 'monospace', fontSize: '13px' }}
        />
        <button className="ws-mem__save" onClick={runCode} disabled={running}>
          {running ? <Loader2 size={14} className="ws-spin" /> : <Play size={14} />} Run
        </button>
      </div>
      <div className="ws-mem__result" style={{ marginTop: '20px', padding: '15px', background: 'var(--ws-bg-primary)', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
        {output}
      </div>
    </div>
  )
}
