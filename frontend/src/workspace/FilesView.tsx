import { useEffect, useRef, useState } from 'react'
import { Boxes, FileSearch, Loader2, RefreshCw, Search, Trash2, Upload } from 'lucide-react'
import { SalarApi } from '../api'

interface FileItem {
  id: string
  filename: string
  media_type: string
  project_id?: string
  created_at: string
}

interface SearchResult {
  id: string
  source: string
  title: string
  source_id: string
  snippet: string
  score: number
}

interface FilesViewProps {
  api: SalarApi
}

export default function FilesView({ api }: FilesViewProps) {
  const [files, setFiles] = useState<FileItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [selected, setSelected] = useState<FileItem | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const items = await api.documents()
      setFiles(items ?? [])
    } catch (e) {
      setError((e as Error).message || 'Could not load files')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api])

  const runSearch = async () => {
    if (!query.trim()) return
    setSearching(true)
    setError('')
    try {
      const res = await api.semanticSearch(query.trim())
      setResults(res?.results ?? [])
    } catch (e) {
      setError((e as Error).message || 'Search failed')
    } finally {
      setSearching(false)
    }
  }

  const handleUpload = async (file: File) => {
    setUploading(true)
    setError('')
    try {
      await api.uploadDocument(file)
      void load()
    } catch (e) {
      setError((e as Error).message || 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (id: string) => {
    setError('')
    try {
      await api.deleteDocument(id)
      void load()
    } catch (e) {
      setError((e as Error).message || 'Delete failed')
    }
  }

  const viewFile = async (file: FileItem) => {
    setSelected(file)
  }

  return (
    <div className="ws-scroll ws-files">
      <div className="ws-files__head">
        <div>
          <h1 className="ws-files__title">Files</h1>
          <p className="ws-files__sub">Your document library with semantic search, uploads, and extraction.</p>
        </div>
        <div className="ws-files__actions">
          <button
            className="ws-files__upload"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? <><Loader2 size={14} className="ws-spin" /> Uploading…</> : <><Upload size={14} /> Upload File</>}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            hidden
            accept=".txt,.md,.pdf,.docx,.py,.js,.ts,.tsx,.jsx,.json,.html,.css"
            onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) void handleUpload(f)
              e.target.value = ''
            }}
          />
        </div>
      </div>

      {error && <div className="ws-files__error" role="alert">{error}</div>}

      <section className="ws-files__search">
        <div className="ws-files__searchbar">
          <Search size={15} className="ws-files__search-icon" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void runSearch()}
            placeholder="Search across files, knowledge, and memories…"
            aria-label="Semantic search"
          />
          <button className="ws-files__search-btn" onClick={() => void runSearch()} disabled={searching}>
            {searching ? <Loader2 size={13} className="ws-spin" /> : <FileSearch size={13} />}
            Search
          </button>
        </div>

        {results.length > 0 && (
          <div className="ws-files__results">
            <div className="ws-files__results-head">
              <span>{results.length} semantic result{results.length === 1 ? '' : 's'}</span>
              <button className="ws-files__clear" onClick={() => setResults([])}>Clear</button>
            </div>
            <ul className="ws-files__result-list">
              {results.map((r) => (
                <li key={r.id} className="ws-files__result-item">
                  <div className="ws-files__result-top">
                    <span className="ws-files__result-source">{r.source}</span>
                    {r.title && <strong>{r.title}</strong>}
                    <span className="ws-files__result-score">{(r.score * 100).toFixed(0)}%</span>
                  </div>
                  <p>{r.snippet}</p>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="ws-files__library">
        <div className="ws-files__library-head">
          <h3>Document Library</h3>
          <button className="ws-files__refresh" onClick={() => void load()}><RefreshCw size={13} /> Refresh</button>
        </div>

        {loading ? (
          <div className="ws-files__state"><Loader2 size={18} className="ws-spin" /> Loading files…</div>
        ) : files.length === 0 ? (
          <div className="ws-files__state">
            <Boxes size={22} strokeWidth={1.5} />
            <p>No files yet.</p>
            <small>Upload a document to start building your private library.</small>
          </div>
        ) : (
          <ul className="ws-files__list">
            {files.map((f) => (
              <li key={f.id} className={`ws-files__item${selected?.id === f.id ? ' is-active' : ''}`}>
                <div className="ws-files__item-click" onClick={() => void viewFile(f)}>
                  <div className="ws-files__item-icon"><Boxes size={15} /></div>
                  <div className="ws-files__item-info">
                    <strong>{f.filename}</strong>
                    <span>{f.media_type} • {new Date(f.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <button className="ws-files__item-delete" onClick={() => void handleDelete(f.id)} aria-label={`Delete ${f.filename}`}>
                  <Trash2 size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {selected && selected.filename && (
        <section className="ws-files__preview">
          <div className="ws-files__preview-head">
            <h3>{selected.filename}</h3>
            <button className="ws-files__clear" onClick={() => setSelected(null)}>Close</button>
          </div>
          <p className="ws-files__preview-text">
            {(selected as any).text || 'No extracted text available.'}
          </p>
        </section>
      )}
    </div>
  )
}