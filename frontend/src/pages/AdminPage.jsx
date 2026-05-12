import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield, RefreshCw, MessageSquare, FileText,
  Bot, Clock, Trash2, AlertTriangle, Database
} from 'lucide-react';
import { api } from '../api';

export default function AdminPage() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [confirm, setConfirm] = useState(null);

  const fetchStats = useCallback(async () => {
    try {
      const s = await api('/admin/stats');
      setStats(s);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchStats();
    const id = setInterval(fetchStats, 15000);
    return () => clearInterval(id);
  }, [fetchStats]);

  const purgeAll = async () => {
    try { await api('/admin/cleanup/all', { method: 'POST' }); } catch { /* silent */ }
    fetchStats();
  };

  const cards = [
    { label: 'Chatbots', value: stats?.total_chatbots ?? '—', icon: Bot, color: 'var(--accent)' },
    { label: 'Documents', value: stats?.total_documents ?? '—', icon: FileText, color: 'var(--accent-green)' },
    { label: 'Messages', value: stats?.total_messages ?? '—', icon: MessageSquare, color: 'var(--accent-violet)' },
    { label: 'Status', value: stats?.system_status === 'operational' ? 'Online' : 'Error', icon: Database, color: 'var(--accent-amber)' },
  ];

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1000px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <Shield size={14} color="var(--accent)" />
            <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--accent)', letterSpacing: '0.12em', fontFamily: 'var(--font-mono)' }}>ADMIN</span>
          </div>
          <h1 style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em' }}>Administration</h1>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '4px' }}>System health and operational controls.</p>
        </div>
        <button onClick={fetchStats} className="btn btn-ghost btn-sm"><RefreshCw size={14} /> Refresh</button>
      </div>

      {/* Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '28px' }}>
        {loading ? (
          [1,2,3,4].map(i => <div key={i} className="skeleton" style={{ height: '100px' }} />)
        ) : (
          cards.map(({ label, value, icon: Icon, color }, i) => (
            <motion.div
              key={label}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.06 }}
              className="glass-panel"
              style={{ padding: '18px' }}
            >
              <Icon size={16} color={color} style={{ marginBottom: '10px' }} />
              <p style={{ fontSize: '24px', fontWeight: 800, letterSpacing: '-0.02em' }}>
                {typeof value === 'number' ? value.toLocaleString() : value}
              </p>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>{label}</p>
            </motion.div>
          ))
        )}
      </div>

      {/* Danger Zone */}
      <div className="glass-panel" style={{ padding: '22px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderColor: 'rgba(239,68,68,0.15)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '36px', height: '36px', borderRadius: 'var(--radius-sm)', background: 'rgba(239,68,68,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <AlertTriangle size={16} color="var(--accent-red)" />
          </div>
          <div>
            <p style={{ fontSize: '14px', fontWeight: 600 }}>Purge All Data</p>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Delete all documents, messages, and sessions permanently.</p>
          </div>
        </div>
        <button
          onClick={() => setConfirm({ message: 'Permanently delete ALL data? This cannot be undone.', action: purgeAll })}
          className="btn btn-danger btn-sm"
        >
          <Trash2 size={14} /> Purge
        </button>
      </div>

      {/* Confirm Modal */}
      <AnimatePresence>
        {confirm && (
          <div className="modal-backdrop" onClick={() => setConfirm(null)}>
            <motion.div
              initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
              className="modal-card" onClick={e => e.stopPropagation()}
            >
              <div style={{ display: 'flex', gap: '12px', marginBottom: '16px' }}>
                <AlertTriangle size={20} color="var(--accent-red)" style={{ flexShrink: 0, marginTop: '2px' }} />
                <div>
                  <h3 className="modal-title">Confirm Action</h3>
                  <p className="modal-body">{confirm.message}</p>
                </div>
              </div>
              <div className="modal-actions">
                <button onClick={() => setConfirm(null)} className="btn btn-ghost btn-sm">Cancel</button>
                <button onClick={async () => { await confirm.action(); setConfirm(null); }} className="btn btn-danger btn-sm">Confirm</button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
