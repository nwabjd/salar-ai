import React, { useCallback, useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Folder, FileText, ChevronRight, ChevronDown, Send, GitBranch, AlertCircle, Bot } from 'lucide-react'

/* ============================================================
   DEVELOPMENT SPACE — adaptive workspace when dev work is active.
   Layout:
     Left:   Project navigator (file tree)
     Center: Current work (code / preview)
     Right:  Salaar context panel (task, errors, agents, build)
     Bottom: command interface
   ============================================================ */

interface TreeNode {
  name: string
  type: 'dir' | 'file'
  path: string
  children?: TreeNode[]
}

interface DevSpaceProps {
  api: any
  onSend?: (text: string) => void
}

function flattenTree(root: TreeNode[], prefix = ''): TreeNode[] {
  const out: TreeNode[] = []
  for (const n of root) {
    out.push({ ...n })
    if (n.type === 'dir' && n.children) {
      out.push(...flattenTree(n.children, n.path))
    }
  }
  return out
}

function isCodeFile(name: string): boolean {
  return /\.(ts|tsx|js|jsx|py|rs|go|json|css|html|md|vue|svelte)$/i.test(name)
}

export default function DevSpace({ api, onSend }: DevSpaceProps) {
  const [root, setRoot] = useState<TreeNode[]>([])
  const [files, setFiles] = useState<TreeNode[]>([])
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<TreeNode | null>(null)
  const [content, setContent] = useState('')
  const [loading, setLoading] = useState(true)
  const [prompt, setPrompt] = useState('')
  const [error, setError] = useState('')

  const loadRoot = useCallback(async () => {
    try {
      const tree = await api.fileTree('', 2)
      setRoot(tree || [])
      setFiles(flattenTree(tree || []))
      // Auto-select the first code file.
      const all = flattenTree(tree || [])
      const firstCode = all.find(n => n.type === 'file' && isCodeFile(n.name))
      if (firstCode) setSelected(firstCode)
    } catch {
      setError('File system unavailable')
    } finally {
      setLoading(false)
    }
  }, [api])

  useEffect(() => { loadRoot() }, [loadRoot])

  const toggleDir = (path: string) => {
    setExpanded(prev => {
      const next = new Set(prev)
      if (next.has(path)) next.delete(path)
      else next.add(path)
      return next
    })
  }

  const openFile = async (node: TreeNode) => {
    setSelected(node)
    setContent('')
    try {
      const data = await api.fileRead(node.path)
      setContent(typeof data === 'string' ? data : data?.content ?? JSON.stringify(data, null, 2))
    } catch {
      setContent('// Unable to read file')
    }
  }

  const submit = () => {
    if (!prompt.trim()) return
    onSend?.(prompt.trim())
    setPrompt('')
  }

  // Render the navigator tree.
  const renderNode = (node: TreeNode, depth: number): React.ReactNode => {
    const isDir = node.type === 'dir'
    const isOpen = expanded.has(node.path)
    const children = isDir && isOpen && node.children ? node.children : []
    return (
      <div key={node.path}>
        <button
          onClick={() => isDir ? toggleDir(node.path) : openFile(node)}
          style={{
            display: 'flex', alignItems: 'center', gap: 6, width: '100%',
            padding: '4px 8px', border: 'none', background: 'transparent',
            color: selected?.path === node.path ? 'var(--nova-cyan)' : 'var(--nova-lunar)',
            cursor: 'pointer', fontSize: 12, textAlign: 'left', borderRadius: 8,
          }}
        >
          <span style={{ width: 12, flexShrink: 0, display: 'flex', justifyContent: 'center' }}>
            {isDir ? (isOpen ? <ChevronDown size={12}/> : <ChevronRight size={12}/>) : null}
          </span>
          <span style={{ color: isDir ? 'var(--nova-violet)' : 'var(--nova-lunar)', flexShrink: 0 }}>
            {isDir ? <Folder size={13}/> : <FileText size={13}/>}
          </span>
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{node.name}</span>
        </button>
        {children.map(c => renderNode(c, depth + 1))}
      </div>
    )
  }

  const codeFiles = files.filter(f => f.type === 'file' && isCodeFile(f.name))

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}
    >
      {/* Space header */}
      <div style={{ padding: '20px clamp(20px, 3vw, 40px) 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div className="nova-meta" style={{ color: 'var(--nova-cyan)', marginBottom: 4 }}>DEVELOPMENT SPACE</div>
          <h2 style={{ margin: 0, fontSize: 'clamp(20px, 2.4vw, 28px)', fontWeight: 400, letterSpacing: '-0.02em', color: 'var(--nova-white)' }}>
            {selected?.path || 'Working directory'}
          </h2>
        </div>
        <span style={{
          display: 'flex', alignItems: 'center', gap: 6,
          fontSize: 10, letterSpacing: '.12em', textTransform: 'uppercase',
          color: 'var(--nova-mint)', padding: '5px 12px', borderRadius: 10,
          border: '1px solid rgba(120,244,197,.3)', background: 'rgba(120,244,197,.06)',
        }}>
          <GitBranch size={12}/> BUILD READY
        </span>
      </div>

      {error && <div style={{ color: 'var(--nova-coral)', fontSize: 12, padding: '8px 40px' }}>{error}</div>}

      {/* Three-pane workspace */}
      <div style={{
        flex: 1, minHeight: 0, margin: '16px clamp(20px, 3vw, 40px) 12px',
        display: 'grid', gridTemplateColumns: '230px 1fr 250px', gap: 14,
      }}>
        {/* Left: navigator */}
        <aside className="nova-glass" style={{ padding: '12px 10px', overflowY: 'auto', minHeight: 0 }}>
          <div className="nova-meta" style={{ padding: '0 8px 10px', color: 'var(--nova-violet)' }}>PROJECT</div>
          {loading ? (
            <div style={{ padding: 16, fontSize: 12, color: 'var(--nova-lunar)' }}>Reading files…</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              {root.map(n => renderNode(n, 0))}
            </div>
          )}
        </aside>

        {/* Center: work area */}
        <section className="nova-solid" style={{ minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {selected ? (
            <>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '8px 14px', borderBottom: '1px solid var(--nova-line)',
                fontSize: 11, color: 'var(--nova-lunar)', overflowX: 'auto', whiteSpace: 'nowrap',
              }}>
                {codeFiles.slice(0, 8).map(f => (
                  <button key={f.path} onClick={() => openFile(f)} style={{
                    padding: '4px 10px', borderRadius: 8, cursor: 'pointer',
                    background: selected?.path === f.path ? 'rgba(96,239,255,.1)' : 'transparent',
                    border: `1px solid ${selected?.path === f.path ? 'var(--nova-line-cyan)' : 'var(--nova-line)'}`,
                    color: selected?.path === f.path ? 'var(--nova-cyan)' : 'var(--nova-lunar)',
                    fontSize: 11,
                  }}>
                    {f.name}
                  </button>
                ))}
              </div>
              <pre style={{
                flex: 1, margin: 0, padding: '16px 18px', overflow: 'auto',
                fontSize: 12.5, lineHeight: 1.6, color: '#c7d0e0',
                fontFamily: 'var(--nova-font-mono)',
                whiteSpace: 'pre',
              }}>
                {content || '// Loading…'}
              </pre>
            </>
          ) : (
            <div style={{ flex: 1, display: 'grid', placeItems: 'center', color: 'var(--nova-lunar)', fontSize: 13 }}>
              Select a file from the navigator.
            </div>
          )}
        </section>

        {/* Right: Salaar context panel */}
        <aside className="nova-glass" style={{ padding: '14px 14px', overflowY: 'auto', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <div className="nova-meta" style={{ marginBottom: 8, color: 'var(--nova-violet)' }}>CURRENT TASK</div>
            <div style={{ fontSize: 12.5, color: 'var(--nova-white)', lineHeight: 1.5 }}>
              Building the Salaar Nova interface across the new design system.
            </div>
          </div>

          <div>
            <div className="nova-meta" style={{ marginBottom: 8, color: 'var(--nova-violet)' }}>ACTIVE AGENTS</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[
                { role: 'Architect', action: 'Planning application shell', state: 'active' },
                { role: 'Designer', action: 'Building Home interface', state: 'active' },
                { role: 'QA', action: 'Waiting', state: 'waiting' },
              ].map(a => (
                <div key={a.role} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 10px', borderRadius: 10,
                  background: 'rgba(255,255,255,.03)', border: '1px solid var(--nova-line)',
                }}>
                  <span style={{
                    width: 22, height: 22, borderRadius: 7, display: 'grid', placeItems: 'center',
                    background: 'rgba(168,121,255,.12)', color: 'var(--nova-violet)', fontSize: 10,
                  }}>
                    <Bot size={12}/>
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 11, color: 'var(--nova-white)', fontWeight: 600 }}>{a.role}</div>
                    <div style={{ fontSize: 9.5, color: 'var(--nova-lunar)' }}>{a.action}</div>
                  </div>
                  <span style={{
                    width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                    background: a.state === 'active' ? 'var(--nova-cyan)' : 'var(--nova-amber)',
                    boxShadow: a.state === 'active' ? 'var(--nova-glow-cyan)' : undefined,
                  }}/>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="nova-meta" style={{ marginBottom: 8, color: 'var(--nova-violet)' }}>SIGNALS</div>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '9px 12px', borderRadius: 10,
              background: 'rgba(255,204,117,.05)', border: '1px solid rgba(255,204,117,.2)',
              fontSize: 11, color: 'var(--nova-amber)', lineHeight: 1.4,
            }}>
              <AlertCircle size={13} style={{ flexShrink: 0 }}/>
              No blockers detected. Build is green.
            </div>
          </div>
        </aside>
      </div>

      {/* Bottom command interface */}
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
            placeholder="Ask Salaar to change code, explain a file, or run a task…"
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
