import { useEffect, useState } from 'react'
import { Rocket, Trash2, Loader2, Play } from 'lucide-react'
import { SalarApi } from '../api'

interface AutomationsViewProps {
  api: SalarApi
}

export default function AutomationsView({ api }: AutomationsViewProps) {
  const [automations, setAutomations] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.workflows()
      setAutomations(data || [])
    } catch (e) {
      setError((e as Error).message || 'Could not load automations')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [api])

  return (
    <div className="ws-scroll ws-mem">
      <div className="ws-mem__head">
        <div>
          <h1 className="ws-mem__title">Automations</h1>
          <p className="ws-mem__sub">Wire Salaar to your systems — workflows and background agents.</p>
        </div>
      </div>

      {loading ? (
        <div className="ws-mem__state">Loading automations…</div>
      ) : automations.length === 0 ? (
        <div className="ws-mem__state">
          <Rocket size={22} strokeWidth={1.5} />
          <p>No automations defined yet.</p>
        </div>
      ) : (
        <ul className="ws-mem__list">
          {automations.map((a) => (
            <li key={a.id} className="ws-mem__item">
              <div className="ws-mem__item-icon" style={{background: 'var(--ws-accent-soft)', color: 'var(--ws-accent)'}}>
                <Rocket size={14} />
              </div>
              <div className="ws-mem__item-body">
                <div className="ws-mem__item-top">
                  <strong>{a.name || 'Unnamed Workflow'}</strong>
                  <span className="ws-mem__item-layer" style={{color: a.enabled ? 'var(--ws-ok)' : 'var(--ws-text-tertiary)'}}>
                    {a.enabled ? 'Enabled' : 'Disabled'}
                  </span>
                </div>
                <p>{a.description || 'No description'}</p>
              </div>
              <button className="ws-mem__delete" onClick={() => void api.testWorkflow(a.id)} aria-label={`Test ${a.name}`}>
                <Play size={14} />
              </button>
              <button className="ws-mem__delete" onClick={() => void api.deleteWorkflow(a.id)} aria-label={`Delete ${a.name}`}>
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <div className="ws-mem__error" role="alert">{error}</div>}
    </div>
  )
}
