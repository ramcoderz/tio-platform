import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Trash2, RefreshCw, Shield, Database, MessageSquare,
  Users, FileText, Settings, AlertTriangle, CheckCircle2,
  Clock, HardDrive,
} from 'lucide-react';
import { api } from '../api';

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

function formatDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function ConfirmModal({ message, onConfirm, onCancel }) {
  return (
    <div className="modal-backdrop" onClick={onCancel}>
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        className="modal-card"
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', alignItems: 'flex-start' }}>
          <AlertTriangle size={22} color="var(--accent-red)" style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>
            <h3 className="modal-title">Confirm Action</h3>
            <p className="modal-body" style={{ marginBottom: 0 }}>{message}</p>
          </div>
        </div>
        <div className="modal-actions">
          <button onClick={onCancel} className="btn btn-ghost btn-sm">Cancel</button>
          <button onClick={onConfirm} className="btn btn-danger btn-sm">Confirm Delete</button>
        </div>
      </motion.div>
    </div>
  );
}

export default function AdminPage() {
  const [stats,     setStats]     = useState(null);
  const [documents, setDocuments] = useState([]);
  const [retention, setRetention] = useState(4);
  const [loading,   setLoading]   = useState(true);
  const [confirm,   setConfirm]   = useState(null); // { message, action }

  const fetchAll = useCallback(async () => {
    try {
      const [s, d, cfg] = await Promise.all([
        api('/admin/stats'),
        api('/admin/documents'),
        api('/admin/config/auto_delete_hours'),
      ]);
      setStats(s);
      setDocuments(Array.isArray(d) ? d : []);
      if (cfg?.value) setRetention(parseInt(cfg.value));
    } catch { /* silent */ } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 10000);
    return () => clearInterval(id);
  }, [fetchAll]);

  const deleteDoc = async (id) => {
    await api(`/admin/documents/${id}`, { method: 'DELETE' });
    setDocuments(prev => prev.filter(d => d.id !== id));
  };

  const purgeAll = async () => {
    await api('/admin/cleanup/all', { method: 'POST' });
    setDocuments([]);
    fetchAll();
  };

  const saveRetention = async (val) => {
    setRetention(val);
    await api('/admin/config', {
      method: 'POST',
      body: JSON.stringify({ key: 'auto_delete_hours', value: val }),
    });
  };

  const db = stats?.database || {};
  const vs = stats?.vectors  || {};

  const overviewCards = [
    { label: 'Documents',   value: db.documents ?? '—', icon: FileText,      color: 'var(--accent-cyan)'   },
    { label: 'Messages',    value: db.messages  ?? '—', icon: MessageSquare,  color: 'var(--accent-violet)' },
    { label: 'Sessions',    value: db.sessions  ?? '—', icon: Users,          color: 'var(--accent-blue-light)' },
    { label: 'Vectors',     value: vs.vector_count ?? '—', icon: Database,    color: 'var(--accent-green)'  },
  ];

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1300px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: '36px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <Shield size={13} color="var(--accent-blue-light)" />
            <span style={{ fontSize: '11px', color: 'var(--accent-blue-light)', fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', fontWeight: 600 }}>ADMIN CONTROL CENTER</span>
          </div>
          <h1 style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em' }}>Administration</h1>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '6px' }}>Manage knowledge assets, sessions, and system configuration.</p>
        </div>
        <button
          onClick={fetchAll}
          className="btn btn-ghost btn-sm"
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <RefreshCw size={13} /> Refresh
        </button>
      </div>

      {/* Overview Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '14px', marginBottom: '28px' }}>
        {loading
          ? [...Array(4)].map((_, i) => <div key={i} className="skeleton" style={{ height: '110px', borderRadius: '16px' }} />)
          : overviewCards.map(({ label, value, icon: Icon, color }, i) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.07 }}
              className="glass-panel"
              style={{ padding: '20px' }}
            >
              <Icon size={18} color={color} style={{ marginBottom: '12px' }} />
              <p style={{ fontSize: '28px', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)', lineHeight: 1 }}>{Number(value).toLocaleString()}</p>
              <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>{label}</p>
            </motion.div>
          ))
        }
      </div>

      {/* Retention Policy */}
      <div className="glass-panel" style={{ padding: '22px 24px', marginBottom: '20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'var(--accent-yellow-dim)', border: '1px solid rgba(245,158,11,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Clock size={16} color="var(--accent-yellow)" />
          </div>
          <div>
            <p style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>Auto-Purge Retention</p>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Documents are automatically deleted after this period</p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
          <input
            type="number"
            min={1}
            max={720}
            value={retention}
            onChange={e => saveRetention(Number(e.target.value))}
            style={{
              width: '72px', padding: '8px 10px', borderRadius: '8px',
              background: 'rgba(255,255,255,0.06)', border: '1px solid var(--border-glass)',
              color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', fontSize: '16px',
              fontWeight: 700, textAlign: 'center',
            }}
          />
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>hours</span>
          <button
            onClick={() => setConfirm({ message: 'Permanently delete ALL documents, messages, and sessions? This cannot be undone.', action: purgeAll })}
            className="btn btn-danger btn-sm"
            style={{ marginLeft: '16px', display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Trash2 size={13} /> Purge All
          </button>
        </div>
      </div>

      {/* Document Table */}
      <div className="glass-panel" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
          <h3 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <HardDrive size={13} color="var(--accent-blue-light)" /> Document Lifecycle Control · {documents.length}
          </h3>
        </div>

        {documents.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '48px 20px', opacity: 0.4 }}>
            <FileText size={36} style={{ margin: '0 auto 12px', color: 'var(--text-muted)' }} />
            <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>No documents in the knowledge base</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Size</th>
                <th>Uploaded</th>
                <th style={{ width: '48px' }}></th>
              </tr>
            </thead>
            <tbody>
              <AnimatePresence>
                {documents.map((doc, i) => (
                  <motion.tr
                    key={doc.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ delay: i * 0.04 }}
                    style={{ borderBottom: '1px solid var(--border-subtle)' }}
                  >
                    <td style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '13px 16px' }}>
                      <FileText size={14} color="var(--accent-cyan)" />
                      <span style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '13px', maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {doc.filename}
                      </span>
                    </td>
                    <td>
                      <span className="badge badge-blue" style={{ fontFamily: 'var(--font-mono)' }}>
                        {doc.type?.split('/').pop() || '—'}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>{formatSize(doc.size)}</td>
                    <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{formatDate(doc.created_at)}</td>
                    <td style={{ textAlign: 'center', padding: '13px 12px' }}>
                      <button
                        onClick={() => setConfirm({ message: `Delete "${doc.filename}" and all its semantic vectors?`, action: () => deleteDoc(doc.id) })}
                        style={{ padding: '6px', borderRadius: '8px', background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', transition: 'all 0.15s ease', display: 'inline-flex' }}
                        onMouseEnter={e => { e.currentTarget.style.color = 'var(--accent-red)'; e.currentTarget.style.background = 'var(--accent-red-dim)'; }}
                        onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-muted)'; e.currentTarget.style.background = 'transparent'; }}
                      >
                        <Trash2 size={14} />
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </AnimatePresence>
            </tbody>
          </table>
        )}
      </div>

      {/* Confirm Modal */}
      <AnimatePresence>
        {confirm && (
          <ConfirmModal
            message={confirm.message}
            onConfirm={async () => { await confirm.action(); setConfirm(null); }}
            onCancel={() => setConfirm(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
