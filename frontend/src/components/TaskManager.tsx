import React, { useState, useEffect, useCallback } from 'react';
import { api } from '../api';

type TaskStatus = 'todo' | 'in_progress' | 'done' | 'archived';
type Priority = 'low' | 'medium' | 'high' | 'urgent';

interface Task {
  id: string;
  title: string;
  description?: string;
  priority?: Priority;
  status: TaskStatus;
  due_date?: string;
  workspace_id?: string;
}

interface TaskStats {
  total: number;
  todo: number;
  in_progress: number;
  done: number;
  archived: number;
}

interface Props {
  workspaceId: string | null;
}

const STATUS_ORDER: TaskStatus[] = ['todo', 'in_progress', 'done', 'archived'];
const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: 'Todo',
  in_progress: 'In Progress',
  done: 'Done',
  archived: 'Archived',
};

const PRIORITY_STYLES: Record<Priority, { bg: string; color: string }> = {
  low: { bg: 'rgba(128,128,128,0.2)', color: '#aaa' },
  medium: { bg: 'rgba(59,130,246,0.2)', color: '#60a5fa' },
  high: { bg: 'rgba(249,115,22,0.2)', color: '#fb923c' },
  urgent: { bg: 'rgba(239,68,68,0.2)', color: '#f87171' },
};

const COLUMN_STYLE: React.CSSProperties = {
  flex: 1,
  minWidth: 220,
  background: 'rgba(255,255,255,0.03)',
  border: '1px solid var(--line, #333)',
  borderRadius: 8,
  display: 'flex',
  flexDirection: 'column',
  maxHeight: 520,
};

const CARD_STYLE: React.CSSProperties = {
  background: 'rgba(255,255,255,0.05)',
  border: '1px solid var(--line, #333)',
  borderRadius: 6,
  padding: '10px 12px',
  marginBottom: 8,
  cursor: 'default',
};

const HEADER_STYLE: React.CSSProperties = {
  padding: '8px 12px',
  fontWeight: 600,
  fontSize: 13,
  textTransform: 'uppercase',
  letterSpacing: 0.5,
  color: '#ccc',
  borderBottom: '1px solid var(--line, #333)',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
};

const STAT_STYLE: React.CSSProperties = {
  display: 'flex',
  gap: 16,
  padding: '10px 0',
  fontSize: 13,
  color: '#999',
};

const BTN_BASE: React.CSSProperties = {
  border: 'none',
  borderRadius: 4,
  padding: '4px 8px',
  fontSize: 12,
  cursor: 'pointer',
  fontWeight: 500,
};

const INPUT_STYLE: React.CSSProperties = {
  width: '100%',
  padding: '6px 8px',
  fontSize: 13,
  borderRadius: 4,
  border: '1px solid var(--line, #333)',
  background: 'rgba(255,255,255,0.06)',
  color: '#eee',
  outline: 'none',
  marginBottom: 6,
};

const SELECT_STYLE: React.CSSProperties = {
  ...INPUT_STYLE,
  marginBottom: 0,
  width: 'auto',
  flex: 1,
};

function formatDate(d?: string) {
  if (!d) return null;
  const dt = new Date(d);
  if (isNaN(dt.getTime())) return null;
  return dt.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

export default function TaskManager({ workspaceId }: Props) {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [stats, setStats] = useState<TaskStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [newTitle, setNewTitle] = useState('');
  const [newPriority, setNewPriority] = useState<Priority>('medium');
  const [newDue, setNewDue] = useState('');
  const [descDraft, setDescDraft] = useState<Record<string, string>>({});

  const fetchAll = useCallback(async () => {
    try {
      setLoading(true);
      const [taskList, taskStats] = await Promise.all([
        api.tasks({ workspace_id: workspaceId ?? undefined }),
        api.taskStats(),
      ]);
      setTasks(taskList);
      setStats(taskStats);
    } catch (e) {
      console.error('TaskManager fetch error', e);
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;
    try {
      await api.createTask({
        title: newTitle.trim(),
        priority: newPriority,
        due_date: newDue || undefined,
        workspace_id: workspaceId ?? undefined,
      });
      setNewTitle('');
      setNewDue('');
      setNewPriority('medium');
      fetchAll();
    } catch (e) {
      console.error('Create task failed', e);
    }
  };

  const handleMove = async (id: string, current: TaskStatus) => {
    const idx = STATUS_ORDER.indexOf(current);
    if (idx < 0 || idx >= STATUS_ORDER.length - 1) return;
    const next = STATUS_ORDER[idx + 1];
    try {
      await api.setTaskStatus(id, next);
      setTasks(prev => prev.map(t => t.id === id ? { ...t, status: next } : t));
      setStats(prev => prev ? { ...prev, [current]: prev[current] - 1, [next]: prev[next] + 1 } : prev);
    } catch (e) {
      console.error('Move task failed', e);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await api.deleteTask(id);
      const removed = tasks.find(t => t.id === id);
      setTasks(prev => prev.filter(t => t.id !== id));
      if (removed && stats) {
        setStats({ ...stats, [removed.status]: stats[removed.status] - 1, total: stats.total - 1 });
      }
    } catch (e) {
      console.error('Delete task failed', e);
    }
  };

  const tasksByStatus = (status: TaskStatus) => tasks.filter(t => t.status === status);

  return (
    <div style={{ padding: 16, color: '#eee', height: '100%', display: 'flex', flexDirection: 'column' }}>
      {stats && (
        <div style={STAT_STYLE}>
          <span>Total: <b style={{ color: '#fff' }}>{stats.total}</b></span>
          {STATUS_ORDER.map(s => (
            <span key={s}>
              {STATUS_LABELS[s]}: <b style={{ color: '#fff' }}>{stats[s]}</b>
            </span>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: 12, flex: 1, overflow: 'hidden' }}>
        {STATUS_ORDER.map(status => (
          <div key={status} style={COLUMN_STYLE}>
            <div style={HEADER_STYLE}>
              <span>{STATUS_LABELS[status]}</span>
              <span style={{ fontSize: 12, color: '#666' }}>{tasksByStatus(status).length}</span>
            </div>

            {status === 'todo' && (
              <form onSubmit={handleCreate} style={{ padding: '10px 10px 6px' }}>
                <input
                  placeholder="New task title"
                  value={newTitle}
                  onChange={e => setNewTitle(e.target.value)}
                  style={INPUT_STYLE}
                />
                <div style={{ display: 'flex', gap: 6 }}>
                  <select value={newPriority} onChange={e => setNewPriority(e.target.value as Priority)} style={SELECT_STYLE}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </select>
                  <input
                    type="date"
                    value={newDue}
                    onChange={e => setNewDue(e.target.value)}
                    style={{ ...INPUT_STYLE, width: 'auto', marginBottom: 0, flex: 1 }}
                  />
                </div>
                <button
                  type="submit"
                  disabled={!newTitle.trim()}
                  style={{
                    ...BTN_BASE,
                    width: '100%',
                    marginTop: 6,
                    background: newTitle.trim() ? '#5227FF' : 'rgba(82,39,255,0.3)',
                    color: '#fff',
                  }}
                >
                  Add Task
                </button>
              </form>
            )}

            <div style={{ flex: 1, overflowY: 'auto', padding: status === 'todo' ? '6px 10px 10px' : 10 }}>
              {loading ? (
                <div style={{ color: '#666', fontSize: 12, textAlign: 'center', marginTop: 24 }}>Loading...</div>
              ) : tasksByStatus(status).length === 0 ? (
                <div style={{ color: '#555', fontSize: 12, textAlign: 'center', marginTop: 24 }}>
                  No tasks
                </div>
              ) : (
                tasksByStatus(status).map(task => (
                  <div key={task.id} style={CARD_STYLE}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6 }}>
                      <span style={{ fontWeight: 500, fontSize: 13, lineHeight: 1.3, flex: 1 }}>{task.title}</span>
                      <button
                        onClick={() => handleDelete(task.id)}
                        title="Delete"
                        style={{ ...BTN_BASE, background: 'transparent', color: '#666', fontSize: 14, padding: '0 2px', lineHeight: 1 }}
                      >
                        ×
                      </button>
                    </div>

                    {task.description && (
                      <div style={{ fontSize: 11, color: '#888', marginTop: 4, lineHeight: 1.3 }}>
                        {task.description.length > 80 ? task.description.slice(0, 80) + '…' : task.description}
                      </div>
                    )}

                    <div style={{ display: 'flex', gap: 6, alignItems: 'center', marginTop: 8, flexWrap: 'wrap' }}>
                      {task.priority && (
                        <span style={{
                          fontSize: 11,
                          fontWeight: 500,
                          padding: '2px 7px',
                          borderRadius: 4,
                          background: PRIORITY_STYLES[task.priority].bg,
                          color: PRIORITY_STYLES[task.priority].color,
                        }}>
                          {task.priority}
                        </span>
                      )}
                      {task.due_date && (
                        <span style={{ fontSize: 11, color: '#777' }}>
                          {formatDate(task.due_date)}
                        </span>
                      )}
                    </div>

                    <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
                      {status !== 'archived' && status !== 'done' && (
                        <button
                          onClick={() => handleMove(task.id, status)}
                          style={{ ...BTN_BASE, background: '#5227FF', color: '#fff' }}
                        >
                          → {STATUS_LABELS[STATUS_ORDER[STATUS_ORDER.indexOf(status) + 1]]}
                        </button>
                      )}
                      {status === 'done' && (
                        <button
                          onClick={() => handleMove(task.id, status)}
                          style={{ ...BTN_BASE, background: '#5227FF', color: '#fff' }}
                        >
                          → Archive
                        </button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
