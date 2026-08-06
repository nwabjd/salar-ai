import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../api';

interface KnowledgeDoc {
  id: string;
  filename: string;
  chunk_count: number;
  status: string;
  created_at: string;
}

interface SearchResult {
  content: string;
  document: string;
  chunk_index: number;
}

interface KnowledgeBaseProps {
  workspaceId: string | null;
}

export default function KnowledgeBase({ workspaceId }: KnowledgeBaseProps) {
  const [documents, setDocuments] = useState<KnowledgeDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchCount, setSearchCount] = useState(0);
  const [searching, setSearching] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const searchTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const fetchDocuments = useCallback(async () => {
    try {
      setLoading(true);
      const docs = await api.knowledgeDocs();
      setDocuments(docs);
    } catch {
      setError('Failed to load documents');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (workspaceId) fetchDocuments();
  }, [workspaceId, fetchDocuments]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    try {
      await api.uploadKnowledge(file);
      await fetchDocuments();
    } catch {
      setError('Upload failed. Please try again.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (id: string) => {
    setDeletingId(id);
    setError(null);
    try {
      await api.deleteKnowledge(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
      setConfirmDeleteId(null);
    } catch {
      setError('Delete failed. Please try again.');
    } finally {
      setDeletingId(null);
    }
  };

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    setSearchQuery(query);

    if (searchTimeout.current) clearTimeout(searchTimeout.current);

    if (!query.trim()) {
      setSearchResults([]);
      setSearchCount(0);
      return;
    }

    searchTimeout.current = setTimeout(async () => {
      setSearching(true);
      try {
        const data = await api.searchKnowledge(query, 5);
        setSearchResults(data.results || []);
        setSearchCount(data.count || 0);
      } catch {
        setSearchResults([]);
        setSearchCount(0);
      } finally {
        setSearching(false);
      }
    }, 400);
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  const statusColor = (status: string) => {
    switch (status) {
      case 'ready': return '#4ade80';
      case 'processing': return '#facc15';
      case 'error': return '#ef4444';
      default: return '#888';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, padding: '0 0 24px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: '#e4e4e7' }}>
          Knowledge Base
        </h3>
        <label
          style={{
            padding: '6px 14px',
            borderRadius: 6,
            background: uploading ? '#3a1e8e' : '#5227FF',
            color: '#fff',
            fontSize: 13,
            fontWeight: 500,
            cursor: uploading ? 'wait' : 'pointer',
            opacity: uploading ? 0.7 : 1,
            transition: 'opacity 0.15s',
          }}
        >
          {uploading ? 'Uploading…' : '+ Upload'}
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.pdf"
            onChange={handleUpload}
            disabled={uploading}
            style={{ display: 'none' }}
          />
        </label>
      </div>

      {/* Search */}
      <input
        type="text"
        value={searchQuery}
        onChange={handleSearch}
        placeholder="Search knowledge base…"
        style={{
          width: '100%',
          padding: '8px 12px',
          borderRadius: 6,
          border: '1px solid var(--line, #2a2a2e)',
          background: '#1a1a1f',
          color: '#e4e4e7',
          fontSize: 13,
          outline: 'none',
          boxSizing: 'border-box',
        }}
      />

      {/* Search Results */}
      {searchQuery.trim() && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ fontSize: 12, color: '#888' }}>
            {searching ? 'Searching…' : `${searchCount} result${searchCount !== 1 ? 's' : ''}`}
          </span>
          {searchResults.map((r, i) => (
            <div
              key={i}
              style={{
                padding: '10px 12px',
                borderRadius: 6,
                border: '1px solid var(--line, #2a2a2e)',
                background: '#1a1a1f',
              }}
            >
              <p style={{ margin: 0, fontSize: 13, color: '#d4d4d8', lineHeight: 1.5 }}>
                {r.content}
              </p>
              <span style={{ fontSize: 11, color: '#666', marginTop: 6, display: 'block' }}>
                {r.document} · chunk {r.chunk_index}
              </span>
            </div>
          ))}
          {!searching && searchResults.length === 0 && (
            <p style={{ margin: 0, fontSize: 13, color: '#666' }}>No results found.</p>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          style={{
            padding: '8px 12px',
            borderRadius: 6,
            background: '#3b1520',
            border: '1px solid #5c2230',
            color: '#f87171',
            fontSize: 13,
          }}
        >
          {error}
        </div>
      )}

      {/* Document List */}
      {loading ? (
        <p style={{ margin: 0, fontSize: 13, color: '#666' }}>Loading documents…</p>
      ) : documents.length === 0 ? (
        <div
          style={{
            padding: '32px 0',
            textAlign: 'center',
            color: '#555',
            fontSize: 13,
          }}
        >
          No documents uploaded yet. Upload .txt, .md, or .pdf files to get started.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {documents.map((doc) => (
            <div
              key={doc.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 12px',
                borderRadius: 6,
                border: '1px solid var(--line, #2a2a2e)',
                background: '#1a1a1f',
              }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: 1, minWidth: 0 }}>
                <span style={{ fontSize: 13, color: '#e4e4e7', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {doc.filename}
                </span>
                <span style={{ fontSize: 11, color: '#666' }}>
                  {doc.chunk_count} chunk{doc.chunk_count !== 1 ? 's' : ''} · {formatDate(doc.created_at)} ·{' '}
                  <span style={{ color: statusColor(doc.status) }}>{doc.status}</span>
                </span>
              </div>

              {confirmDeleteId === doc.id ? (
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    disabled={deletingId === doc.id}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 4,
                      border: 'none',
                      background: '#5c2230',
                      color: '#f87171',
                      fontSize: 12,
                      cursor: deletingId === doc.id ? 'wait' : 'pointer',
                    }}
                  >
                    {deletingId === doc.id ? '…' : 'Confirm'}
                  </button>
                  <button
                    onClick={() => setConfirmDeleteId(null)}
                    style={{
                      padding: '4px 10px',
                      borderRadius: 4,
                      border: '1px solid var(--line, #2a2a2e)',
                      background: 'transparent',
                      color: '#888',
                      fontSize: 12,
                      cursor: 'pointer',
                    }}
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setConfirmDeleteId(doc.id)}
                  title="Delete document"
                  style={{
                    padding: '4px 8px',
                    borderRadius: 4,
                    border: '1px solid var(--line, #2a2a2e)',
                    background: 'transparent',
                    color: '#666',
                    fontSize: 12,
                    cursor: 'pointer',
                    flexShrink: 0,
                  }}
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
