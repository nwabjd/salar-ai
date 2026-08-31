import { useEffect, useState } from 'react'
import { Rocket, RefreshCw, CheckCircle, Clock } from 'lucide-react'
import { SalarApi } from '../api'
import { onDeviceCommand } from '../device-poll'

interface CommandsViewProps {
  api: SalarApi
}

export default function CommandsView({ api }: CommandsViewProps) {
  const [commands, setCommands] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.getCommands()
      setCommands(data || [])
    } catch (e) {
      setError((e as Error).message || 'Could not load commands')
    } finally {
      setLoading(false)
    }
  }

  const approve = async (id: string) => {
    try {
      await api.approveCommand(id)
      void load()
    } catch (e) {
      setError((e as Error).message || 'Could not approve command')
    }
  }

  useEffect(() => {
    void load()
    const off = onDeviceCommand(() => { void load() })
    return off
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api])

  return (
    <div className="ws-scroll ws-mem">
      <div className="ws-mem__head">
        <div>
          <h1 className="ws-mem__title">Remote Commands</h1>
          <p className="ws-mem__sub">Approve and track commands executed on your devices.</p>
        </div>
        <button className="ws-mem__add" onClick={() => void load()}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="ws-mem__state">Loading commands…</div>
      ) : commands.length === 0 ? (
        <div className="ws-mem__state">
          <Rocket size={22} strokeWidth={1.5} />
          <p>No remote commands found.</p>
        </div>
      ) : (
        <ul className="ws-mem__list">
          {commands.map((c) => (
            <li key={c.id} className="ws-mem__item">
              <div className="ws-mem__item-icon" style={{background: 'var(--ws-accent-soft)', color: 'var(--ws-accent)'}}>
                <Rocket size={14} />
              </div>
              <div className="ws-mem__item-body">
                <div className="ws-mem__item-top">
                  <strong>{c.kind}</strong>
                  <span className="ws-mem__item-layer" style={{
                    color: c.status === 'completed' ? 'var(--ws-ok)' : 
                           c.status === 'failed' ? 'var(--ws-danger)' : 
                           c.status === 'awaiting_confirmation' ? 'var(--ws-warn)' : 'var(--ws-text-secondary)'
                  }}>
                    {c.status.replace('_', ' ')}
                  </span>
                </div>
                <p style={{fontFamily: 'monospace', fontSize: '12px'}}>{JSON.stringify(c.payload)}</p>
                {c.status === 'awaiting_confirmation' && (
                  <button className="ws-mem__add" style={{marginTop: '10px'}} onClick={() => void approve(c.id)}>
                    <CheckCircle size={14} /> Approve Command
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {error && <div className="ws-mem__error" role="alert">{error}</div>}
    </div>
  )
}
