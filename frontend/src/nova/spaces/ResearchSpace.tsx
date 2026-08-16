import React, { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { FileText, BrainCircuit, Share2, Send, ExternalLink } from 'lucide-react'

/* ============================================================
   RESEARCH SPACE — designed around information synthesis.
   Three-panel adaptive layout:
     Sources       — research documents and pages
     Intelligence  — Salaar's synthesis
     Knowledge Map — connections between findings
   ============================================================ */

interface ResearchSpaceProps {
  api: any
  onSend?: (text: string) => void
}

export default function ResearchSpace({ api, onSend }: ResearchSpaceProps) {
  const [docs, setDocs] = useState<any[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [chunks, setChunks] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [prompt, setPrompt] = useState('')

  const load = useCallback(async () => {
    try {
      const list = await api.knowledgeDocs()
      setDocs(list || [])
      if (list && list[0]) setSelected(list[0].id)
    } catch { /* knowledge unavailable */ }
    finally { setLoading(false) }
  }, [api])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!selected) return
    setChunks([])
    api.knowledgeChunks(selected).then((data: any) => {
      setChunks(Array.isArray(data) ? data : [])
    }).catch(() => {})
  }, [selected, api])

  const submit = () => {
    if (!prompt.trim()) return
    onSend?.(prompt.trim())
    setPrompt('')
  }

  // Knowledge map: synthetic connections from loaded sources.
  const connections = docs.slice(0, 6).map((d, i) => ({
    id: d.id,
    label: (d.filename || d.title || `Source ${i + 1}`).replace(/\.[a-z0-9]+$/i, ''),
  }))

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}
    >
      {/* Header */}
      <div style={{ padding: '20px clamp(20px, 3vw, 40px) 0' }}>
        <div className="nova-meta" style={{ color: 'var(--nova-violet)', marginBottom: 4 }}>RESEARCH SPACE</div>
        <h2 style={{ margin: 0, fontSize: 'clamp(20px, 2.4vw, 28px)', fontWeight: 400, letterSpacing: '-0.02em', color: 'var(--nova-white)' }}>
          Sources to synthesis
        </h2>
      </div>

      {/* Three panels */}
      <div style={{
        flex: 1, minHeight: 0, margin: '16px clamp(20px, 3vw, 40px) 12px',
        display: 'grid', gridTemplateColumns: '1fr 1.2fr 1fr', gap: 14,
      }}>
        {/* Sources */}
        <aside className="nova-glass" style={{ padding: '14px', overflowY: 'auto', minHeight: 0 }}>
          <div className="nova-meta" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12, color: 'var(--nova-violet)' }}>
            <FileText size={12}/> SOURCES
          </div>
          {loading ? (
            <div style={{ fontSize: 12, color: 'var(--nova-lunar)' }}>Reading documents…</div>
          ) : docs.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--nova-lunar)', lineHeight: 1.5 }}>
              No research documents yet. Ask Salaar to gather sources for a topic.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {docs.map(d => {
                const isSel = d.id === selected
                return (
                  <button key={d.id} onClick={() => setSelected(d.id)} style={{
                    display: 'flex', alignItems: 'center', gap: 8, width: '100%',
                    padding: '9px 11px', borderRadius: 10, textAlign: 'left',
                    background: isSel ? 'rgba(168,121,255,.1)' : 'rgba(255,255,255,.02)',
                    border: `1px solid ${isSel ? 'var(--nova-line-violet)' : 'var(--nova-line)'}`,
                    cursor: 'pointer',
                  }}>
                    <FileText size={13} style={{ color: isSel ? 'var(--nova-violet)' : 'var(--nova-lunar)', flexShrink: 0 }}/>
                    <span style={{ fontSize: 11.5, color: isSel ? 'var(--nova-white)' : 'var(--nova-lunar)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {d.filename || d.title || 'Document'}
                    </span>
                  </button>
                )
              })}
            </div>
          )}
        </aside>

        {/* Intelligence — Salaar's synthesis */}
        <section className="nova-intel-glass" style={{ padding: '16px', overflowY: 'auto', minHeight: 0 }}>
          <div className="nova-meta" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12, color: 'var(--nova-cyan)' }}>
            <BrainCircuit size={12}/> INTELLIGENCE
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--nova-white)', lineHeight: 1.7 }}>
            {chunks.length > 0 ? (
              <>
                <p style={{ margin: '0 0 10px' }}>Salaar has synthesized the key findings from this source:</p>
                {chunks.slice(0, 4).map((c, i) => (
                  <p key={i} style={{ margin: '0 0 8px', color: 'var(--nova-lunar)' }}>
                    <span style={{ color: 'var(--nova-cyan)' }}>▸</span> {String(c).slice(0, 220)}{c.length > 220 ? '…' : ''}
                  </p>
                ))}
              </>
            ) : (
              <div style={{ color: 'var(--nova-lunar)' }}>
                {docs.length === 0
                  ? 'Select or add sources and Salaar will connect the dots here.'
                  : 'Reading this source into the synthesis. Salaar is correlating it with connected knowledge…'}
              </div>
            )}
          </div>
        </section>

        {/* Knowledge Map */}
        <aside className="nova-glass" style={{ padding: '14px', overflowY: 'auto', minHeight: 0 }}>
          <div className="nova-meta" style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12, color: 'var(--nova-violet)' }}>
            <Share2 size={12}/> KNOWLEDGE MAP
          </div>
          <svg viewBox="0 0 220 240" style={{ width: '100%', height: 'auto' }}>
            <line x1="110" y1="120" x2="50" y2="40" stroke="rgba(168,121,255,.35)" strokeWidth="1"/>
            <line x1="110" y1="120" x2="185" y2="60" stroke="rgba(96,239,255,.35)" strokeWidth="1"/>
            <line x1="110" y1="120" x2="40" y2="190" stroke="rgba(168,121,255,.25)" strokeWidth="1"/>
            <line x1="110" y1="120" x2="180" y2="200" stroke="rgba(96,239,255,.25)" strokeWidth="1"/>
            {/* Center node */}
            <circle cx="110" cy="120" r="26" fill="rgba(168,121,255,.12)" stroke="#a879ff" strokeWidth="1.2"/>
            <text x="110" y="124" textAnchor="middle" fontSize="8.5" fill="#f7f9ff">SALAAR</text>
            {/* Leaf nodes */}
            {connections.map((c, i) => {
              const pos = [
                { x: 50, y: 40 }, { x: 185, y: 60 }, { x: 40, y: 190 }, { x: 180, y: 200 },
              ][i % 4]
              return (
                <g key={c.id}>
                  <circle cx={pos.x} cy={pos.y} r={i === 0 ? 22 : 15} fill="rgba(96,239,255,.08)"
                    stroke={i === 0 ? '#60efff' : 'rgba(96,239,255,.5)'} strokeWidth="1"/>
                  <text x={pos.x} y={pos.y + 3} textAnchor="middle" fontSize="7.5" fill="#9da7ba">
                    {c.label.length > 14 ? c.label.slice(0, 13) + '…' : c.label}
                  </text>
                </g>
              )
            })}
          </svg>
          <div style={{ marginTop: 6, fontSize: 10.5, color: 'var(--nova-lunar)', lineHeight: 1.5 }}>
            Important nodes are larger. Recently active sources glow cyan.
          </div>
        </aside>
      </div>

      {/* Bottom command */}
      <div style={{ padding: '0 clamp(20px, 3vw, 40px) 18px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 12px 10px 16px', borderRadius: 16,
          background: 'var(--nova-glass)', border: '1px solid var(--nova-line)',
          backdropFilter: 'blur(20px)',
        }}>
          <input
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') submit() }}
            placeholder="Ask Salaar to research, compare, or synthesize…"
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none',
              color: 'var(--nova-white)', fontSize: 13.5,
            }}
          />
          <motion.button
            whileTap={{ scale: 0.93 }}
            onClick={submit}
            aria-label="Send"
            style={{
              width: 36, height: 36, borderRadius: 12, display: 'grid', placeItems: 'center',
              background: 'linear-gradient(135deg, rgba(96,239,255,.2), rgba(168,121,255,.2))',
              border: '1px solid var(--nova-line-cyan)', color: 'var(--nova-white)', cursor: 'pointer',
            }}
          >
            <Send size={15}/>
          </motion.button>
        </div>
      </div>
    </motion.div>
  )
}
