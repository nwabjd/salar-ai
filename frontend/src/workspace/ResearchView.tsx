import { useEffect, useState } from 'react'
import { BookOpen, CheckCircle2, ExternalLink, FileSearch, Loader2, Search, Send, Sparkles } from 'lucide-react'
import { type ResearchReport, SalarApi } from '../api'

interface ResearchViewProps {
  api: SalarApi
}

export default function ResearchView({ api }: ResearchViewProps) {
  const [reports, setReports] = useState<ResearchReport[]>([])
  const [selected, setSelected] = useState<ResearchReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [goal, setGoal] = useState('')
  const [running, setRunning] = useState(false)
  const [docResults, setDocResults] = useState<any[]>([])
  const [searchTerm, setSearchTerm] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const data = await api.researchList()
      const items = data?.results ?? []
      setReports(items)
      if (items.length > 0 && !selected) setSelected(items[0])
    } catch (e) {
      setError((e as Error).message || 'Could not load research reports')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api])

  const run = async () => {
    if (!goal.trim() || running) return
    setRunning(true)
    setError('')
    try {
      const report = await api.researchRun(goal.trim())
      setGoal('')
      setReports((prev) => [report, ...prev])
      setSelected(report)
    } catch (e) {
      setError((e as Error).message || 'Research failed')
    } finally {
      setRunning(false)
    }
  }

  const searchDocs = async (term: string) => {
    setSearchTerm(term)
    if (!term.trim()) { setDocResults([]); return }
    try {
      const res = await api.searchKnowledge(term.trim(), 6)
      setDocResults(Array.isArray(res) ? res : [])
    } catch { setDocResults([]) }
  }

  const openReport = async (id: string) => {
    try {
      const report = await api.researchGet(id)
      setSelected(report)
    } catch (e) {
      setError((e as Error).message || 'Could not open report')
    }
  }

  const synthesis = selected?.synthesis
  const findings = selected?.findings ?? selected?.agents ?? []

  return (
    <div className="ws-scroll ws-res">
      <div className="ws-mem__head">
        <div>
          <h1 className="ws-mem__title">Research</h1>
          <p className="ws-mem__sub">Launch independent agents that gather, compare and cite sources.</p>
        </div>
      </div>

      <div className="ws-res__composer">
        <textarea
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          rows={2}
          placeholder="What do you want researched? e.g. “Compare privacy tradeoffs of local vs cloud AI assistants”"
          aria-label="Research question"
          onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); void run() } }}
        />
        <button className="ws-res__run" onClick={run} disabled={running || !goal.trim()}>
          {running ? <><Loader2 size={14} className="ws-spin" /> Researching…</> : <><Send size={14} /> Researcher</>}
        </button>
      </div>

      <div className="ws-res__search">
        <Search size={13} />
        <input
          value={searchTerm}
          onChange={(e) => void searchDocs(e.target.value)}
          placeholder="Search your knowledge base…"
          aria-label="Search knowledge base"
        />
      </div>

      {docResults.length > 0 && (
        <div className="ws-res__docs">
          <h3><BookOpen size={13} /> Knowledge matches</h3>
          <ul>
            {docResults.slice(0, 4).map((r) => (
              <li key={r.chunk_id}>
                <strong>{r.document_filename}</strong>
                <span>{r.content}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && <div className="ws-mem__error" role="alert">{error}</div>}

      <div className="ws-res__layout">
        <aside className="ws-res__list">
          {loading ? (
            <div className="ws-mem__state">Loading reports…</div>
          ) : reports.length === 0 ? (
            <div className="ws-mem__state">
              <FileSearch size={22} strokeWidth={1.5} />
              <p>No reports yet.</p>
              <small>Ask a research question above to get started.</small>
            </div>
          ) : (
            reports.map((r) => (
              <button
                key={r.id}
                className={`ws-res__report${selected?.id === r.id ? ' is-active' : ''}`}
                onClick={() => void openReport(r.id)}
              >
                <div className="ws-res__report-top">
                  <strong>{r.goal}</strong>
                  <span className={`ws-res__badge ws-res__badge--${r.status}`}>{r.status}</span>
                </div>
                {(r.synthesis?.confidence || r.created_at) && (
                  <div className="ws-res__report-meta">
                    {r.synthesis?.confidence && <span>Confidence: {r.synthesis.confidence}</span>}
                    {r.created_at && <span>{new Date(r.created_at).toLocaleDateString()}</span>}
                  </div>
                )}
              </button>
            ))
          )}
        </aside>

        <section className="ws-res__detail">
          {!selected ? (
            <div className="ws-mem__state">
              <Sparkles size={22} strokeWidth={1.5} />
              <p>Select a report to view its findings.</p>
            </div>
          ) : (
            <>
              <div className="ws-res__detail-head">
                <h2>{selected.goal}</h2>
                <span className={`ws-res__badge ws-res__badge--${selected.status}`}>{selected.status}</span>
              </div>

              {selected.error && <div className="ws-mem__error">{selected.error}</div>}

              {synthesis?.synthesis && (
                <div className="ws-res__synthesis">
                  <h3><Sparkles size={13} /> Synthesis</h3>
                  <p>{synthesis.synthesis}</p>
                  {synthesis.confidence && (
                    <span className="ws-res__conf">Confidence: {synthesis.confidence}</span>
                  )}
                  {synthesis.consensus_points?.length ? (
                    <div className="ws-res__points">
                      <strong>Consensus</strong>
                      <ul>
                        {synthesis.consensus_points.slice(0, 6).map((c, i) => (
                          <li key={i}><CheckCircle2 size={12} /> {c}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {synthesis.contradictions?.length ? (
                    <div className="ws-res__points ws-res__points--warn">
                      <strong>Contradictions</strong>
                      <ul>
                        {synthesis.contradictions.slice(0, 5).map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {synthesis.unresolved?.length ? (
                    <div className="ws-res__points ws-res__points--warn">
                      <strong>Unresolved</strong>
                      <ul>
                        {synthesis.unresolved.slice(0, 4).map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {(synthesis.sources_cited ?? []).length ? (
                    <div className="ws-res__points">
                      <strong>Sources cited</strong>
                      <ul>
                        {(synthesis.sources_cited ?? []).slice(0, 6).map((s, i) => (
                          <li key={i}><ExternalLink size={11} /> {s}</li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              )}

              {findings.length > 0 && (
                <div className="ws-res__findings">
                  <h3><FileSearch size={13} /> Agent findings</h3>
                  <ul>
                    {findings.map((f, i) => (
                      <li key={i} className="ws-res__finding">
                        <strong>{f.agent}</strong>
                        <p>{f.finding}</p>
                        {f.sources?.length ? (
                          <div className="ws-res__src">
                            {f.sources.slice(0, 3).map((s, j) => (
                              <span key={j}>{s}</span>
                            ))}
                          </div>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  )
}