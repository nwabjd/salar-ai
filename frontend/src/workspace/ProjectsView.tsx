import { useEffect, useState } from 'react'
import { Calendar, FolderKanban, Plus, Target, Trash2 } from 'lucide-react'
import { type Project, SalarApi } from '../api'

const STATUS_COLORS: Record<string, string> = {
  active: 'var(--ws-ok)',
  completed: 'var(--ws-accent)',
  archived: 'var(--ws-text-tertiary)',
}

interface ProjectsViewProps {
  api: SalarApi
}

export default function ProjectsView({ api }: ProjectsViewProps) {
  const [projects, setProjects] = useState<Project[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [selected, setSelected] = useState<Project | null>(null)
  const [goalInput, setGoalInput] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const items = await api.projects()
      setProjects(items ?? [])
    } catch (e) {
      setError((e as Error).message || 'Could not load projects')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api])

  const create = async () => {
    if (!name.trim()) return
    setSaving(true)
    setError('')
    try {
      const p = await api.createProject({ name: name.trim(), description: description.trim() })
      setProjects((prev) => [p, ...prev])
      setName('')
      setDescription('')
      setShowForm(false)
    } catch (e) {
      setError((e as Error).message || 'Could not create project')
    } finally {
      setSaving(false)
    }
  }

  const remove = async (id: string) => {
    try {
      await api.deleteProject(id)
      setProjects((prev) => prev.filter((p) => p.id !== id))
      if (selectedId === id) { setSelectedId(null); setSelected(null) }
    } catch (e) {
      setError((e as Error).message || 'Could not delete project')
    }
  }

  const select = async (id: string) => {
    if (selectedId === id) { setSelectedId(null); setSelected(null); return }
    setSelectedId(id)
    try {
      setSelected(await api.project(id))
    } catch { setError('Could not load project details') }
  }

  const addGoal = async () => {
    if (!selected || !goalInput.trim()) return
    const goals = [...(selected.goals || []), goalInput.trim()]
    try {
      const updated = await api.updateProject(selected.id, { goals })
      setSelected(updated)
      setGoalInput('')
      setProjects((prev) => prev.map((p) => p.id === updated.id ? updated : p))
    } catch { setError('Could not add goal') }
  }

  const removeGoal = async (idx: number) => {
    if (!selected) return
    const goals = selected.goals.filter((_, i) => i !== idx)
    try {
      const updated = await api.updateProject(selected.id, { goals })
      setSelected(updated)
      setProjects((prev) => prev.map((p) => p.id === updated.id ? updated : p))
    } catch { setError('Could not remove goal') }
  }

  return (
    <div className="ws-scroll ws-mem">
      <div className="ws-mem__head">
        <div>
          <h1 className="ws-mem__title">Projects</h1>
          <p className="ws-mem__sub">Group conversations, goals and context into living workspaces.</p>
        </div>
        <button className="ws-mem__add" onClick={() => setShowForm((v) => !v)}>
          <Plus size={15} /> {showForm ? 'Close' : 'New project'}
        </button>
      </div>

      {showForm && (
        <div className="ws-mem__form">
          <div className="ws-mem__form-row">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Project name" aria-label="Project name" />
          </div>
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What is this project about?" rows={2} aria-label="Project description" />
          <div className="ws-mem__form-actions">
            <button className="ws-mem__save" onClick={create} disabled={saving || !name.trim()}>
              {saving ? 'Creating…' : 'Create project'}
            </button>
          </div>
        </div>
      )}

      {error && <div className="ws-mem__error" role="alert">{error}</div>}

      <div className="ws-prj">
        <div className="ws-prj__list">
          {loading ? (
            <div className="ws-mem__state">Loading projects…</div>
          ) : projects.length === 0 ? (
            <div className="ws-mem__state">
              <FolderKanban size={22} strokeWidth={1.5} />
              <p>No projects yet.</p>
              <small>Create your first project to organize conversations and goals.</small>
            </div>
          ) : (
            projects.map((p) => (
              <button
                key={p.id}
                className={`ws-prj__card${selectedId === p.id ? ' is-active' : ''}`}
                onClick={() => void select(p.id)}
              >
                <div className="ws-prj__card-top">
                  <div className="ws-prj__dot" style={{ background: STATUS_COLORS[p.status] ?? 'var(--ws-text-tertiary)' }} />
                  <strong>{p.name}</strong>
                </div>
                <p>{p.description || 'No description'}</p>
                <div className="ws-prj__card-meta">
                  {p.goals?.length ? <span><Target size={11} /> {p.goals.length} goals</span> : null}
                  {p.deadline && <span><Calendar size={11} /> {new Date(p.deadline).toLocaleDateString()}</span>}
                </div>
                <button className="ws-mem__delete" onClick={(e) => { e.stopPropagation(); void remove(p.id) }} aria-label={`Delete ${p.name}`}>
                  <Trash2 size={14} />
                </button>
              </button>
            ))
          )}
        </div>

        {selected && (
          <div className="ws-prj__detail">
            <div className="ws-prj__detail-head">
              <h2>{selected.name}</h2>
              <span className="ws-prj__status" style={{ borderColor: STATUS_COLORS[selected.status] ?? 'var(--ws-line)' }}>
                {selected.status}
              </span>
            </div>
            <p className="ws-prj__desc">{selected.description || 'No description.'}</p>
            <div className="ws-prj__goals">
              <h3><Target size={13} /> Goals</h3>
              {selected.goals?.length ? (
                <ul>
                  {selected.goals.map((g, i) => (
                    <li key={i}>
                      <span>{g}</span>
                      <button onClick={() => void removeGoal(i)} aria-label={`Remove goal: ${g}`}>×</button>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="ws-prj__empty-goals">No goals yet — add one below.</p>
              )}
              <div className="ws-prj__goal-add">
                <input
                  value={goalInput}
                  onChange={(e) => setGoalInput(e.target.value)}
                  placeholder="Add a goal…"
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); void addGoal() } }}
                  aria-label="New goal"
                />
                <button onClick={() => void addGoal()} disabled={!goalInput.trim()}>Add</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}