import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Plus, Trash2, Copy, Brain, Zap, FileText, FolderOpen } from 'lucide-react'

/* ============================================================
   MEMORY VIEW — Long-term facts, project context, learned patterns.
   Structure:
     1. Header with search + add
     2. Layer tabs (short/long/semantic)
     3. Memory cards with inline edit/delete
   ============================================================ */

type MemoryLayer = 'short_term' | 'long_term' | 'semantic'

interface MemoryItem {
  id: string
  title: string
  content: string
  layer: MemoryLayer
  created_at: string
  project_id?: string
}

const MOCK_MEMORIES: MemoryItem[] = [
  { id: '1', title: 'User prefers dark mode', content: 'Default to dark theme on all new sessions', layer: 'long_term', created_at: new Date().toISOString() },
  { id: '2', title: 'MoonLink IT - pricing context', content: 'RAM modules: Kingston 16GB DDR5 AED 189, Corsair 32GB DDR4 AED 349, G.Skill 64GB DDR5 AED 549', layer: 'long_term', created_at: new Date().toISOString() },
  { id: '3', title: 'Active project: Salaar Nova', content: 'Building the quantum intelligence interface for Salaar AI', layer: 'semantic', created_at: new Date().toISOString() },
  { id: '4', title: 'NIM model routing', content: 'Laguna XS for coding, Nemotron 3.5 Ultra for deep reasoning, Omni for multimodal', layer: 'long_term', created_at: new Date().toISOString() },
  { id: '5', title: 'User likes light theme #e61359', content: 'Brand pink for accents, white background, crystalline orb style', layer: 'long_term', created_at: new Date().toISOString() },
]

const LAYER_LABELS: Record<MemoryLayer, string> = {
  short_term: 'Short-term',
  long_term: 'Long-term',
  semantic: 'Semantic',
}
const LAYER_ICONS: Record<MemoryLayer, React.ReactNode> = {
  short_term: <Zap size={14} />,
  long_term: <Brain size={14} />,
  semantic: <FolderOpen size={14} />,
}

export function MemoryView({ api }: { api: any }) {
  const [layer, setLayer] = useState<MemoryLayer>('long_term')
  const [search, setSearch] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [newContent, setNewContent] = useState('')
  const [newLayer, setNewLayer] = useState<MemoryLayer>('long_term')

  const filtered = MOCK_MEMORIES.filter(m =>
    m.layer === layer && (m.title.toLowerCase().includes(search.toLowerCase()) || m.content.toLowerCase().includes(search.toLowerCase()))
  )

  const handleAdd = async () => {
    if (!newTitle.trim() || !newContent.trim()) return
    try {
      await api.saveMemory(newTitle, newContent, newLayer)
      setShowAdd(false)
      setNewTitle('')
      setNewContent('')
      // In real app, would refetch
    } catch (e) {
      console.error('Save memory failed:', e)
    }
  }

  const handleDelete = async (id: string) => {
    // In real app: await api.deleteMemory(id)
    console.log('Delete memory:', id)
  }

  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      gap: 16,
      padding: '24px 32px',
      overflow: 'auto',
    }}>
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}
      >
        <div>
          <h1 style={{ fontSize: 'clamp(28px, 3.5vw, 36px)', fontWeight: 300, letterSpacing: '-0.03em' }}>Memory</h1>
          <p style={{ fontSize: 13.5, color: 'var(--nova-lunar)', marginTop: 4 }}>
            {LAYER_LABELS[layer]} · {filtered.length} {filtered.length === 1 ? 'memory' : 'memories'}
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ position: 'relative', width: 280 }}>
            <Search style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', width: 16, height: 16, color: 'var(--nova-lunar)', pointerEvents: 'none' }} />
            <input
              type="text"
              placeholder="Search memories…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 14px 10px 40px',
                borderRadius: 12,
                border: '1px solid var(--nova-line)',
                background: 'var(--nova-glass)',
                backdropFilter: 'blur(12px)',
                color: 'var(--nova-white)',
                fontSize: 13.5,
                outline: 'none',
              }}
            />
          </div>
          <button
            onClick={() => setShowAdd(!showAdd)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '10px 16px', borderRadius: 12,
              background: 'linear-gradient(135deg, var(--nova-cyan), #6a7bff)',
              border: 'none', color: '#051018',
              fontWeight: 600, fontSize: 13, cursor: 'pointer',
              boxShadow: '0 4px 16px rgba(96,239,255,.3)',
            }}
          >
            <Plus size={16} /> Add
          </button>
        </div>
      </motion.div>

      {/* Layer tabs */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1], delay: 0.06 }}
        style={{ display: 'flex', gap: 6, padding: 4, borderRadius: 14, background: 'var(--nova-glass)', border: '1px solid var(--nova-line)' }}
      >
        {(['short_term', 'long_term', 'semantic'] as MemoryLayer[]).map(l => (
          <button
            key={l}
            onClick={() => { setLayer(l); setSearch('') }}
            style={{
              flex: 1,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              padding: '10px 16px', borderRadius: 10,
              border: 'none', background: layer === l ? 'rgba(96,239,255,.12)' : 'transparent',
              color: layer === l ? 'var(--nova-cyan)' : 'var(--nova-lunar)',
              fontSize: 12.5, fontWeight: layer === l ? 600 : 400,
              cursor: 'pointer', transition: 'all 0.18s',
            }}
          >
            {LAYER_ICONS[l]} {LAYER_LABELS[l]}
          </button>
        ))}
      </motion.div>

      {/* Add form */}
      <AnimatePresence>
        {showAdd && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column', gap: 12, padding: 16, borderRadius: 14, background: 'var(--nova-glass)', border: '1px solid var(--nova-line-cyan)' }}
          >
            <input
              placeholder="Title"
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
              style={{ padding: '12px 16px', borderRadius: 10, border: '1px solid var(--nova-line)', background: 'rgba(255,255,255,.04)', color: 'var(--nova-white)', fontSize: 14, outline: 'none' }}
            />
            <textarea
              placeholder="Content"
              value={newContent}
              onChange={e => setNewContent(e.target.value)}
              rows={4}
              style={{ padding: '12px 16px', borderRadius: 10, border: '1px solid var(--nova-line)', background: 'rgba(255,255,255,.04)', color: 'var(--nova-white)', fontSize: 14, outline: 'none', resize: 'vertical', fontFamily: 'inherit' }}
            />
            <select
              value={newLayer}
              onChange={e => setNewLayer(e.target.value as MemoryLayer)}
              style={{ padding: '10px 14px', borderRadius: 10, border: '1px solid var(--nova-line)', background: 'rgba(255,255,255,.04)', color: 'var(--nova-white)', fontSize: 13.5, outline: 'none' }}
            >
              <option value="short_term">Short-term</option>
              <option value="long_term">Long-term</option>
              <option value="semantic">Semantic</option>
            </select>
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
              <button
                onClick={() => { setShowAdd(false); setNewTitle(''); setNewContent('') }}
                style={{ padding: '10px 18px', borderRadius: 10, border: '1px solid var(--nova-line)', background: 'transparent', color: 'var(--nova-lunar)', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={handleAdd}
                style={{ padding: '10px 18px', borderRadius: 10, border: 'none', background: 'linear-gradient(135deg, var(--nova-cyan), #6a7bff)', color: '#051018', fontWeight: 600, cursor: 'pointer' }}
              >
                Save Memory
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Memory list */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay: 0.12 }}
        style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10, minHeight: 0 }}
      >
        {filtered.length === 0 ? (
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, color: 'var(--nova-lunar)', padding: 40 }}>
            <FileText size={48} style={{ opacity: 0.3 }} />
            <p style={{ fontSize: 15 }}>No memories in this layer yet</p>
            <p style={{ fontSize: 12.5 }}>Click "Add" to create your first memory</p>
          </div>
        ) : (
          <AnimatePresence mode="popLayout">
            {filtered.map((mem, i) => (
              <motion.div
                key={mem.id}
                layout
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, x: 20 }}
                transition={{ duration: 0.3, delay: i * 0.03 }}
                style={{
                  display: 'flex', alignItems: 'flex-start', gap: 14,
                  padding: '16px 18px', borderRadius: 14,
                  background: 'var(--nova-glass)', border: '1px solid var(--nova-line)',
                  backdropFilter: 'blur(12px)',
                }}
              >
                <div style={{ flexShrink: 0, width: 36, height: 36, borderRadius: 10, display: 'grid', placeItems: 'center', background: 'rgba(96,239,255,.12)', color: 'var(--nova-cyan)' }}>
                  {LAYER_ICONS[mem.layer]}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                    <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--nova-white)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{mem.title}</h3>
                    <span style={{ fontSize: 10.5, padding: '2px 8px', borderRadius: 6, background: 'rgba(96,239,255,.1)', color: 'var(--nova-cyan)', fontWeight: 500 }}>{LAYER_LABELS[mem.layer]}</span>
                    <button
                      onClick={() => navigator.clipboard.writeText(mem.content)}
                      title="Copy content"
                      style={{ padding: 6, borderRadius: 8, background: 'transparent', border: 'none', color: 'var(--nova-lunar)', cursor: 'pointer', opacity: 0.6 }}
                    >
                      <Copy size={14} />
                    </button>
                    <button
                      onClick={() => handleDelete(mem.id)}
                      title="Delete memory"
                      style={{ padding: 6, borderRadius: 8, background: 'transparent', border: 'none', color: 'var(--nova-lunar)', cursor: 'pointer', opacity: 0.6 }}
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                  <p style={{ fontSize: 12.5, color: 'var(--nova-lunar)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{mem.content}</p>
                  <p style={{ fontSize: 10.5, color: 'var(--nova-lunar)', marginTop: 8, opacity: 0.7 }}>
                    Created {new Date(mem.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                  </p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </motion.div>
    </div>
  )
}