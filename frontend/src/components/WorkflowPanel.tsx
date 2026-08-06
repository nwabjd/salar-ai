import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api';

interface Workflow {
  id: string;
  name: string;
  description?: string;
  trigger_type: string;
  trigger_config: Record<string, unknown>;
  actions: Array<{ type: string; params: Record<string, unknown> }>;
  is_enabled: boolean;
  run_count: number;
  last_run_at?: string;
}

interface WorkflowRun {
  id: string;
  trigger_event: string;
  status: string;
  result_log?: string;
  started_at: string;
  finished_at?: string;
}

interface Props {
  workspaceId: string | null;
}

const TRIGGER_TYPES = [
  { value: 'keyword', label: 'Keyword Match', configHint: '{"keyword": "deploy"}' },
  { value: 'schedule', label: 'Schedule', configHint: '{"cron": "0 9 * * *"}' },
  { value: 'email_received', label: 'Email Received', configHint: '{"from": "boss@company.com"}' },
  { value: 'file_created', label: 'File Created', configHint: '{"path": "/uploads/*.pdf"}' },
];

export default function WorkflowPanel({ workspaceId }: Props) {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [runsMap, setRunsMap] = useState<Record<string, WorkflowRun[]>>({});
  const [runsLoading, setRunsLoading] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState('');
  const [formDesc, setFormDesc] = useState('');
  const [formTriggerType, setFormTriggerType] = useState('keyword');
  const [formTriggerConfig, setFormTriggerConfig] = useState('{"keyword": ""}');
  const [formActions, setFormActions] = useState('[{"type": "send_notification", "params": {"title": "", "message": ""}}]');
  const [formError, setFormError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  const fetchWorkflows = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    try {
      const data = await api.workflows();
      setWorkflows(data);
    } catch (err) {
      console.error('Failed to fetch workflows:', err);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    fetchWorkflows();
  }, [fetchWorkflows]);

  const handleToggle = async (id: string) => {
    try {
      const updated = await api.toggleWorkflow(id);
      setWorkflows(prev => prev.map(w => w.id === id ? { ...w, ...updated } : w));
    } catch (err) {
      console.error('Toggle failed:', err);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteWorkflow(id);
      setWorkflows(prev => prev.filter(w => w.id !== id));
      setConfirmDelete(null);
      if (expandedId === id) setExpandedId(null);
    } catch (err) {
      console.error('Delete failed:', err);
    }
  };

  const handleExpand = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(id);
    if (!runsMap[id]) {
      setRunsLoading(id);
      try {
        const data = await api.workflowRuns(id);
        setRunsMap(prev => ({ ...prev, [id]: data.runs || [] }));
      } catch (err) {
        console.error('Failed to fetch runs:', err);
        setRunsMap(prev => ({ ...prev, [id]: [] }));
      } finally {
        setRunsLoading(null);
      }
    }
  };

  const handleCreate = async () => {
    setFormError('');
    let parsedConfig;
    let parsedActions;
    try {
      parsedConfig = JSON.parse(formTriggerConfig);
    } catch {
      setFormError('Trigger config is not valid JSON');
      return;
    }
    try {
      parsedActions = JSON.parse(formActions);
      if (!Array.isArray(parsedActions)) {
        setFormError('Actions must be a JSON array');
        return;
      }
    } catch {
      setFormError('Actions is not valid JSON');
      return;
    }
    try {
      const data = {
        name: formName,
        description: formDesc || undefined,
        trigger_type: formTriggerType,
        trigger_config: parsedConfig,
        actions: parsedActions,
      };
      const created = await api.createWorkflow(data);
      setWorkflows(prev => [...prev, created]);
      setShowForm(false);
      setFormName('');
      setFormDesc('');
      setFormTriggerType('keyword');
      setFormTriggerConfig('{"keyword": ""}');
      setFormActions('[{"type": "send_notification", "params": {"title": "", "message": ""}}]');
    } catch (err: any) {
      setFormError(err?.message || 'Failed to create workflow');
    }
  };

  const triggerTypeColor = (tt: string) => {
    switch (tt) {
      case 'keyword': return '#60a5fa';
      case 'schedule': return '#a78bfa';
      case 'email_received': return '#34d399';
      case 'file_created': return '#fbbf24';
      default: return '#9ca3af';
    }
  };

  const statusColor = (s: string) => {
    switch (s) {
      case 'success': return '#34d399';
      case 'error': return '#f87171';
      case 'running': return '#fbbf24';
      default: return '#9ca3af';
    }
  };

  const panelStyle: React.CSSProperties = {
    background: '#1a1a2e',
    border: '1px solid #2d2d4a',
    borderRadius: 8,
    padding: 20,
    color: '#e0e0e0',
    fontFamily: "'Inter', -apple-system, sans-serif",
    maxHeight: '100%',
    overflow: 'auto',
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    background: '#12122a',
    border: '1px solid #3d3d5c',
    borderRadius: 6,
    padding: '8px 12px',
    color: '#e0e0e0',
    fontSize: 14,
    outline: 'none',
    boxSizing: 'border-box',
  };

  const btnStyle = (variant: 'primary' | 'danger' | 'ghost'): React.CSSProperties => ({
    border: 'none',
    borderRadius: 6,
    padding: '6px 14px',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    color: variant === 'primary' ? '#fff' : variant === 'danger' ? '#fff' : '#a0a0c0',
    background: variant === 'primary' ? '#4f46e5' : variant === 'danger' ? '#dc2626' : 'transparent',
    transition: 'opacity 0.15s',
  });

  if (!workspaceId) {
    return (
      <div style={{ ...panelStyle, textAlign: 'center', padding: 40, color: '#6b6b8d' }}>
        Select a workspace to manage workflows.
      </div>
    );
  }

  return (
    <div style={panelStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#f0f0ff' }}>Workflows</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          style={btnStyle('primary')}
        >
          {showForm ? 'Cancel' : '+ New Workflow'}
        </button>
      </div>

      {showForm && (
        <div style={{
          background: '#12122a',
          border: '1px solid #3d3d5c',
          borderRadius: 8,
          padding: 16,
          marginBottom: 16,
        }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#f0f0ff', marginBottom: 12 }}>Create New Workflow</div>
          <label style={labelStyle}>Name</label>
          <input
            style={inputStyle}
            value={formName}
            onChange={e => setFormName(e.target.value)}
            placeholder="e.g. Auto-deploy on keyword"
          />
          <label style={labelStyle}>Description (optional)</label>
          <input
            style={inputStyle}
            value={formDesc}
            onChange={e => setFormDesc(e.target.value)}
            placeholder="What does this workflow do?"
          />
          <label style={labelStyle}>Trigger Type</label>
          <select
            style={{ ...inputStyle, cursor: 'pointer' }}
            value={formTriggerType}
            onChange={e => {
              setFormTriggerType(e.target.value);
              const hint = TRIGGER_TYPES.find(t => t.value === e.target.value);
              if (hint) setFormTriggerConfig(hint.configHint);
            }}
          >
            {TRIGGER_TYPES.map(t => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <label style={labelStyle}>Trigger Config (JSON)</label>
          <textarea
            style={{ ...inputStyle, fontFamily: "'JetBrains Mono', 'Fira Code', monospace", minHeight: 60, resize: 'vertical' }}
            value={formTriggerConfig}
            onChange={e => setFormTriggerConfig(e.target.value)}
            spellCheck={false}
          />
          <label style={labelStyle}>Actions (JSON Array)</label>
          <textarea
            style={{ ...inputStyle, fontFamily: "'JetBrains Mono', 'Fira Code', monospace", minHeight: 100, resize: 'vertical' }}
            value={formActions}
            onChange={e => setFormActions(e.target.value)}
            spellCheck={false}
          />
          {formError && <div style={{ color: '#f87171', fontSize: 13, marginTop: 8 }}>{formError}</div>}
          <div style={{ marginTop: 12 }}>
            <button onClick={handleCreate} style={btnStyle('primary')}>Create Workflow</button>
          </div>
        </div>
      )}

      {loading && <div style={{ color: '#6b6b8d', fontSize: 14, padding: 20, textAlign: 'center' }}>Loading workflows...</div>}

      {!loading && workflows.length === 0 && (
        <div style={{ color: '#6b6b8d', fontSize: 14, padding: 40, textAlign: 'center' }}>
          No workflows yet. Create one to get started.
        </div>
      )}

      {workflows.map(w => (
        <div key={w.id} style={{
          background: '#12122a',
          border: '1px solid #2d2d4a',
          borderRadius: 8,
          marginBottom: 10,
          overflow: 'hidden',
        }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              padding: '12px 16px',
              cursor: 'pointer',
              gap: 12,
            }}
            onClick={() => handleExpand(w.id)}
          >
            <div style={{ flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <span style={{ fontSize: 15, fontWeight: 600, color: '#f0f0ff' }}>{w.name}</span>
                <span style={{
                  fontSize: 11,
                  fontWeight: 600,
                  padding: '2px 8px',
                  borderRadius: 4,
                  color: triggerTypeColor(w.trigger_type),
                  background: `${triggerTypeColor(w.trigger_type)}15`,
                  border: `1px solid ${triggerTypeColor(w.trigger_type)}30`,
                }}>
                  {w.trigger_type}
                </span>
              </div>
              {w.description && (
                <div style={{ fontSize: 13, color: '#8080a0', marginBottom: 4 }}>{w.description}</div>
              )}
              <div style={{ display: 'flex', gap: 16, fontSize: 12, color: '#6b6b8d' }}>
                <span>Runs: {w.run_count}</span>
                {w.last_run_at && (
                  <span>Last: {new Date(w.last_run_at).toLocaleString()}</span>
                )}
              </div>
            </div>

            <div
              onClick={e => e.stopPropagation()}
              style={{ display: 'flex', alignItems: 'center', gap: 8 }}
            >
              <button
                onClick={() => handleToggle(w.id)}
                style={{
                  width: 40,
                  height: 22,
                  borderRadius: 11,
                  border: 'none',
                  background: w.is_enabled ? '#4f46e5' : '#3d3d5c',
                  cursor: 'pointer',
                  position: 'relative',
                  transition: 'background 0.2s',
                  flexShrink: 0,
                }}
              >
                <div style={{
                  width: 16,
                  height: 16,
                  borderRadius: '50%',
                  background: '#fff',
                  position: 'absolute',
                  top: 3,
                  left: w.is_enabled ? 21 : 3,
                  transition: 'left 0.2s',
                }} />
              </button>

              {confirmDelete === w.id ? (
                <div style={{ display: 'flex', gap: 4 }}>
                  <button onClick={() => handleDelete(w.id)} style={btnStyle('danger')}>Confirm</button>
                  <button onClick={() => setConfirmDelete(null)} style={btnStyle('ghost')}>Cancel</button>
                </div>
              ) : (
                <button
                  onClick={() => setConfirmDelete(w.id)}
                  style={{ ...btnStyle('danger'), opacity: 0.7 }}
                >
                  Delete
                </button>
              )}
            </div>
          </div>

          {expandedId === w.id && (
            <div style={{ borderTop: '1px solid #2d2d4a', padding: '12px 16px' }}>
              <div style={{ fontSize: 13, fontWeight: 600, color: '#a0a0c0', marginBottom: 8 }}>Recent Runs</div>

              {runsLoading === w.id && (
                <div style={{ fontSize: 12, color: '#6b6b8d', padding: 10 }}>Loading runs...</div>
              )}

              {runsLoading !== w.id && (!runsMap[w.id] || runsMap[w.id].length === 0) && (
                <div style={{ fontSize: 12, color: '#6b6b8d', padding: 10 }}>No runs yet.</div>
              )}

              {runsLoading !== w.id && runsMap[w.id] && runsMap[w.id].map(run => (
                <div key={run.id} style={{
                  background: '#1a1a2e',
                  border: '1px solid #2d2d4a',
                  borderRadius: 6,
                  padding: '8px 12px',
                  marginBottom: 6,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <div style={{
                      width: 8,
                      height: 8,
                      borderRadius: '50%',
                      background: statusColor(run.status),
                      flexShrink: 0,
                    }} />
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#e0e0e0' }}>{run.status}</span>
                    <span style={{ fontSize: 11, color: '#6b6b8d', marginLeft: 'auto' }}>
                      {new Date(run.started_at).toLocaleString()}
                    </span>
                  </div>
                  {run.trigger_event && (
                    <div style={{ fontSize: 12, color: '#8080a0', marginBottom: 2 }}>
                      Trigger: {run.trigger_event}
                    </div>
                  )}
                  {run.result_log && (
                    <pre style={{
                      fontSize: 11,
                      color: '#6b6b8d',
                      margin: 0,
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-all',
                      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                      maxHeight: 120,
                      overflow: 'auto',
                    }}>{run.result_log}</pre>
                  )}
                  {run.finished_at && (
                    <div style={{ fontSize: 11, color: '#5a5a7d', marginTop: 4 }}>
                      Finished: {new Date(run.finished_at).toLocaleString()}
                    </div>
                  )}
                </div>
              ))}

              <div style={{ borderTop: '1px solid #2d2d4a', marginTop: 8, paddingTop: 8 }}>
                <div style={{ fontSize: 11, color: '#5a5a7d', marginBottom: 4 }}>Config</div>
                <pre style={{
                  fontSize: 11,
                  color: '#8080a0',
                  margin: 0,
                  fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                  whiteSpace: 'pre-wrap',
                  background: '#0d0d1a',
                  padding: 8,
                  borderRadius: 4,
                  maxHeight: 80,
                  overflow: 'auto',
                }}>{JSON.stringify(w.trigger_config, null, 2)}</pre>
                <div style={{ fontSize: 11, color: '#5a5a7d', marginTop: 8, marginBottom: 4 }}>Actions</div>
                <pre style={{
                  fontSize: 11,
                  color: '#8080a0',
                  margin: 0,
                  fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
                  whiteSpace: 'pre-wrap',
                  background: '#0d0d1a',
                  padding: 8,
                  borderRadius: 4,
                  maxHeight: 120,
                  overflow: 'auto',
                }}>{JSON.stringify(w.actions, null, 2)}</pre>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: 13,
  fontWeight: 600,
  color: '#a0a0c0',
  marginTop: 12,
  marginBottom: 4,
};
