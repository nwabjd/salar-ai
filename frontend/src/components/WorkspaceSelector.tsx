import React, { useState, useEffect } from 'react'
import { api } from '../api'

type Workspace = { id: string; name: string; icon: string; color: string; is_default: boolean }

export function WorkspaceSelector({ current, onChange }: { current: string | null; onChange: (id: string | null) => void }) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [open, setOpen] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [newName, setNewName] = useState('')
  const [newIcon, setNewIcon] = useState('📁')

  useEffect(() => { load() }, [])

  async function load() {
    try {
      const w = await api.workspaces()
      setWorkspaces(w)
    } catch {}
  }

  async function create() {
    if (!newName.trim()) return
    try {
      const r = await api.createWorkspace({ name: newName, icon: newIcon })
      setWorkspaces(prev => [...prev, r])
      setNewName(''); setShowCreate(false)
      onChange(r.id)
    } catch {}
  }

  const currentWs = workspaces.find(w => w.id === current) || workspaces.find(w => w.is_default)

  return (
    <div className="ws-selector">
      <button className="ws-current" onClick={() => setOpen(!open)}>
        <span>{currentWs?.icon || '📁'}</span>
        <span>{currentWs?.name || 'All'}</span>
        <small>▾</small>
      </button>
      {open && (
        <div className="ws-dropdown">
          <button className={`ws-item ${!current ? 'active' : ''}`} onClick={() => { onChange(null); setOpen(false) }}>
            <span>📋</span><span>All Workspaces</span>
          </button>
          {workspaces.map(w => (
            <button key={w.id} className={`ws-item ${current === w.id ? 'active' : ''}`} onClick={() => { onChange(w.id); setOpen(false) }}>
              <span>{w.icon}</span><span>{w.name}</span>
              {w.is_default && <small>default</small>}
            </button>
          ))}
          {!showCreate ? (
            <button className="ws-item ws-create" onClick={() => setShowCreate(true)}>
              <span>+</span><span>New Workspace</span>
            </button>
          ) : (
            <div className="ws-create-form">
              <input value={newIcon} onChange={e => setNewIcon(e.target.value)} style={{width:40}} maxLength={2}/>
              <input value={newName} onChange={e => setNewName(e.target.value)} placeholder="Workspace name" autoFocus onKeyDown={e => e.key === 'Enter' && create()}/>
              <button onClick={create}>Create</button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
