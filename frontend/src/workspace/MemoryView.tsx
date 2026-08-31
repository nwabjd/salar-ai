import { useEffect, useState } from 'react'
import { BookOpen, Brain, Clock3, FolderKanban, KeyRound, Plus, Search, Star, Trash2 } from 'lucide-react'
import { type Memory, type Project, SalarApi } from '../api'

const LAYER_META: Record<string, { label: string; icon: typeof Brain }> = {
  'short-term': { label: 'Short-term', icon: Clock3 },
  'long-term': { label: 'Long-term', icon: BookOpen },
  project: { label: 'Project', icon: FolderKanban },
  personal: { label: 'Personal', icon: Star },
  vault: { label: 'Vault', icon: KeyRound },
}

interface MemoryViewProps {
  api: SalarApi
}

export default function MemoryView({ api }: MemoryViewProps) {
  const [memories, setMemories] = useState<Memory[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [layer, setLayer] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [formLayer, setFormLayer] = useState('long_term')
  const [formProject, setFormProject] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = async (search = query, filter = layer) => {
    setLoading(true)
    setError('')
    try {
      const items = await api.memories({ search: search || undefined, layer: filter || undefined })
      setMemories(items ?? [])
    } catch (e) {
      setError((e as Error).message || 'Could not load memories')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load('', '')
    void api.projects().then(setProjects).catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api])

  useEffect(() => {
    if (query) void load(query, layer)
  }, [query, layer])

  const save = async () => {
    if (!title.trim() || !content.trim()) return
    setSaving(true)
    setError('')
    try {
      await api.saveMemory(title.trim(), content.trim(), formLayer, [], formProject || undefined)
      setTitle('')
      setContent('')
      setFormProject('')
      setShowForm(false)
      void load('', '')
    } catch (e) {
      setError((e as Error).message || 'Could not save memory')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id: string) => {
    try {
      await api.deleteMemory(id)
      setMemories((prev) => prev.filter((m) => m.id !== id))
    } catch (e) {
      setError((e as Error).message || 'Could not delete memory')
    }
  }

  const layers = ['', 'short-term', 'long-term', 'project', 'personal', 'vault']

  return (
    <div className="ws-scroll ws-mem">
      <div className="ws-mem__head">
        <div>
          <h1 className="ws-mem__title">Memory</h1>
          <p className="ws-mem__sub">Things Salaar remembers — organized, searchable, yours.</p>
        </div>
        <button className="ws-mem__add" onClick={() => setShowForm((v) => !v)}>
          <Plus size={15} /> {showForm ? 'Close' : 'New memory'}
        </button>
      </div>

      <div className="ws-mem__tools">
        <label className="ws-mem__search">
          <Search size={14} />
          <input
            value={query}
            onChange={(e) => { setQuery(e.target.value); setLayer('') }}
            placeholder="Search memories…"
            aria-label="Search memories"
          />
        </label>
        <div className="ws-mem__filters" role="tablist" aria-label="Memory layers">
          {layers.map((l) => {
            const meta = LAYER_META[l]
            const active = layer === l && !query
            return (
              <button
                key={l || 'all'}
                className={`ws-mem__filter${active ? ' is-active' : ''}`}
                onClick={() => { setLayer(l); setQuery('') }}
                role="tab"
                aria-selected={active}
              >
                {meta ? <meta.icon size={13} /> : <Brain size={13} />}
                {l === '' ? 'All' : meta?.label ?? l}
              </button>
            )
          })}
        </div>
      </div>

      {showForm && (
        <div className="ws-mem__form">
          <div className="ws-mem__form-row">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Title (e.g. “Prefers dark UI”)"
              aria-label="Memory title"
            />
            <select value={formLayer} onChange={(e) => setFormLayer(e.target.value)} aria-label="Memory layer">
              {layers.filter((l) => l).map((l) => (
                <option key={l} value={l}>{LAYER_META[l]?.label ?? l}</option>
              ))}
            </select>
            <select value={formProject} onChange={(e) => setFormProject(e.target.value)} aria-label="Project">
              <option value="">No project</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="What should Salaar remember?"
            rows={3}
            aria-label="Memory content"
          />
          <div className="ws-mem__form-actions">
            <button className="ws-mem__save" onClick={save} disabled={saving || !title.trim() || !content.trim()}>
              {saving ? 'Saving…' : 'Save memory'}
            </button>
          </div>
        </div>
      )}

      {error && <div className="ws-mem__error" role="alert">{error}</div>}

      {loading ? (
        <div className="ws-mem__state">Loading memories…</div>
      ) : memories.length === 0 ? (
        <div className="ws-mem__state">
          <Brain size={22} strokeWidth={1.5} />
          <p>No memories yet{query ? ` matching “${query}”` : ''}.</p>
          {!query && <small>Save anything and Salaar will keep it for later.</small>}
        </div>
      ) : (
        <ul className="ws-mem__list">
          {memories.map((m) => {
            const meta = LAYER_META[m.layer] ?? { label: m.layer, icon: Brain }
            const Icon = meta.icon
            return (
              <li key={m.id} className="ws-mem__item">
                <div className="ws-mem__item-icon" title={meta.label}>
                  <Icon size={14} />
                </div>
                <div className="ws-mem__item-body">
                  <div className="ws-mem__item-top">
                    <strong>{m.title}</strong>
                    <span className="ws-mem__item-layer">{meta.label}</span>
                  </div>
                  <p>{m.content}</p>
                  <div className="ws-mem__item-meta">
                    <span>{new Date(m.created_at).toLocaleDateString()}</span>
                    {m.expired && <span className="ws-mem__expired">expired</span>}
                  </div>
                </div>
                <button className="ws-mem__delete" onClick={() => void remove(m.id)} aria-label={`Delete ${m.title}`}>
                  <Trash2 size={14} />
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}