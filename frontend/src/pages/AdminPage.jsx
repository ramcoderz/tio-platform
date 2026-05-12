import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield, RefreshCw, MessageSquare, FileText,
  Bot, Trash2, AlertTriangle, Database,
  Activity, TrendingUp, HelpCircle, Zap, BarChart2
} from 'lucide-react';
import { api } from '../api';

// Miniature horizontal bar for intent/domain distribution
function MiniBar({ label, value, max, color = 'var(--accent)' }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div style={{ marginBottom: '10px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
        <span style={{ fontSize: '12px', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{label.replace(/_/g, ' ')}</span>
        <span style={{ fontSize: '12px', fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>{value}</span>
      </div>
      <div style={{ height: '5px', borderRadius: '3px', background: 'var(--border)', overflow: 'hidden' }}>
        <div className="monitor-bar" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

// Metric card
function MetricCard({ label, value, sub, icon: Icon, color, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="stat-card"
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <p style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.03em', color: '#fff' }}>{value}</p>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>{label}</p>
          {sub && <p style={{ fontSize: '11px', color, marginTop: '4px', fontWeight: 600 }}>{sub}</p>}
        </div>
        <div style={{
          width: '36px', height: '36px', borderRadius: '10px',
          background: `${color}18`, display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={16} color={color} />
        </div>
      </div>
    </motion.div>
  );
}

// Unanswered query pill
function UnansweredQuery({ text }) {
  return (
    <div style={{
      padding: '8px 12px', borderRadius: '8px',
      background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.12)',
      fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.45,
      marginBottom: '6px',
    }}>
      <HelpCircle size={11} color="#F87171" style={{ marginRight: '6px', verticalAlign: 'middle' }} />
      {text}
    </div>
  );
}

const TABS = ['Overview', 'Monitoring'];
const DOMAIN_COLORS = {
  tourism: '#FBBF24', education: '#A78BFA', medical: '#F87171',
  developer: '#34D399', ecommerce: '#FB923C', general: '#94A3B8',
};

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState('Overview');
  const [stats, setStats]         = useState(null);
  const [monitoring, setMonitoring] = useState(null);
  const [loading, setLoading]     = useState(true);
  const [confirm, setConfirm]     = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [s, m] = await Promise.all([
        api('/admin/stats'),
        api('/admin/monitoring'),
      ]);
      setStats(s);
      setMonitoring(m);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 20000);
    return () => clearInterval(id);
  }, [fetchAll]);

  const purgeAll = async () => {
    try { await api('/admin/cleanup/all', { method: 'POST' }); } catch { /* silent */ }
    fetchAll();
  };

  // ── Overview cards ────────────────────────────────────────────────────────
  const overviewCards = [
    { label: 'Total Chatbots',    value: stats?.total_chatbots  ?? '—', icon: Bot,          color: 'var(--accent)',         sub: `${stats?.ready_chatbots ?? 0} ready` },
    { label: 'Documents Indexed', value: stats?.total_documents ?? '—', icon: FileText,      color: 'var(--accent-green)',   sub: null },
    { label: 'Messages Sent',     value: stats?.total_messages  ?? '—', icon: MessageSquare, color: 'var(--accent-violet)',  sub: null },
    { label: 'System Status',     value: stats?.system_status === 'operational' ? 'Online' : 'Error', icon: Database, color: stats?.system_status === 'operational' ? 'var(--accent-green)' : 'var(--accent-red)', sub: null },
  ];

  // ── Monitoring data ───────────────────────────────────────────────────────
  const m = monitoring;
  const topIntents    = Object.entries(m?.popular_intents    || {});
  const domainDist    = Object.entries(m?.domain_distribution || {});
  const maxIntent     = topIntents.length  ? Math.max(...topIntents.map(([,v]) => v))  : 1;
  const maxDomain     = domainDist.length  ? Math.max(...domainDist.map(([,v]) => v)) : 1;
  const unanswered    = m?.recent_unanswered || [];

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1100px' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '28px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <Shield size={13} color="var(--accent)" />
            <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--accent)', letterSpacing: '0.12em', fontFamily: 'var(--font-mono)' }}>ADMIN</span>
          </div>
          <h1 style={{ fontSize: '26px', fontWeight: 800, letterSpacing: '-0.02em' }}>Administration</h1>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '3px' }}>System health, operational controls, and query analytics.</p>
        </div>
        <button onClick={fetchAll} className="btn btn-ghost btn-sm"><RefreshCw size={13} /> Refresh</button>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', marginBottom: '24px', borderBottom: '1px solid var(--border)', paddingBottom: '0' }}>
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '8px 18px', fontSize: '13px', fontWeight: 600,
              color: activeTab === tab ? 'var(--accent)' : 'var(--text-muted)',
              borderBottom: activeTab === tab ? '2px solid var(--accent)' : '2px solid transparent',
              marginBottom: '-1px', transition: 'color 0.15s, border-color 0.15s',
              background: 'none', cursor: 'pointer',
            }}
          >
            {tab === 'Monitoring' ? <><Activity size={12} style={{ marginRight: '5px', verticalAlign: 'middle' }} />{tab}</> : tab}
          </button>
        ))}
      </div>

      {/* ── OVERVIEW TAB ─────────────────────────────────────────────────── */}
      {activeTab === 'Overview' && (
        <>
          {/* Stat cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '28px' }}>
            {loading ? (
              [1,2,3,4].map(i => <div key={i} className="skeleton" style={{ height: '96px' }} />)
            ) : (
              overviewCards.map((c, i) => <MetricCard key={c.label} {...c} delay={i * 0.06} />)
            )}
          </div>

          {/* Conversations */}
          <div className="glass-panel" style={{ padding: '22px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <MessageSquare size={14} color="var(--accent-violet)" />
              <span style={{ fontSize: '13px', fontWeight: 700 }}>Conversations</span>
            </div>
            <div style={{ display: 'flex', gap: '24px' }}>
              <div>
                <p style={{ fontSize: '22px', fontWeight: 800 }}>{stats?.total_conversations ?? '—'}</p>
                <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Total Sessions</p>
              </div>
              <div>
                <p style={{ fontSize: '22px', fontWeight: 800, color: 'var(--accent-green)' }}>{stats?.ready_chatbots ?? '—'}</p>
                <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Active Chatbots</p>
              </div>
            </div>
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
            <button onClick={() => setConfirm({ message: 'Permanently delete ALL data? This cannot be undone.', action: purgeAll })} className="btn btn-danger btn-sm">
              <Trash2 size={13} /> Purge
            </button>
          </div>
        </>
      )}

      {/* ── MONITORING TAB ───────────────────────────────────────────────── */}
      {activeTab === 'Monitoring' && (
        <>
          {loading ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px' }}>
              {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: '96px' }} />)}
            </div>
          ) : (
            <>
              {/* KPI row */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px', marginBottom: '20px' }}>
                <MetricCard label="Total Queries"     value={m?.total_queries ?? 0}          icon={Zap}      color="var(--accent)"         delay={0} />
                <MetricCard label="Answer Rate"       value={`${m?.answer_rate_pct ?? 100}%`} icon={TrendingUp} color="var(--accent-green)"  delay={0.05}
                  sub={`${m?.unanswered_queries ?? 0} unanswered`} />
                <MetricCard label="Avg LLM Latency"   value={`${m?.avg_llm_ms ?? 0} ms`}     icon={Activity} color="var(--accent-amber)"   delay={0.1}
                  sub={`Retrieval: ${m?.avg_retrieval_ms ?? 0} ms`} />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
                {/* Intent distribution */}
                <div className="glass-panel" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '16px' }}>
                    <BarChart2 size={13} color="var(--accent)" />
                    <span style={{ fontSize: '13px', fontWeight: 700 }}>Popular Intents</span>
                  </div>
                  {topIntents.length === 0 ? (
                    <p style={{ fontSize: '12px', color: 'var(--text-dim)' }}>No data yet. Start chatting to see intent analytics.</p>
                  ) : (
                    topIntents.map(([intent, count]) => (
                      <MiniBar key={intent} label={intent} value={count} max={maxIntent} color="var(--accent)" />
                    ))
                  )}
                </div>

                {/* Domain distribution */}
                <div className="glass-panel" style={{ padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '16px' }}>
                    <Database size={13} color="var(--accent-violet)" />
                    <span style={{ fontSize: '13px', fontWeight: 700 }}>Domain Distribution</span>
                  </div>
                  {domainDist.length === 0 ? (
                    <p style={{ fontSize: '12px', color: 'var(--text-dim)' }}>No data yet. Chatbots need to receive queries.</p>
                  ) : (
                    domainDist.map(([domain, count]) => (
                      <MiniBar key={domain} label={domain} value={count} max={maxDomain} color={DOMAIN_COLORS[domain] || 'var(--accent)'} />
                    ))
                  )}
                </div>
              </div>

              {/* Unanswered queries */}
              <div className="glass-panel" style={{ padding: '20px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '14px' }}>
                  <HelpCircle size={13} color="var(--accent-red)" />
                  <span style={{ fontSize: '13px', fontWeight: 700 }}>Recent Unanswered Queries</span>
                  <span style={{ marginLeft: 'auto', fontSize: '11px', color: 'var(--text-dim)' }}>last 10</span>
                </div>
                {unanswered.length === 0 ? (
                  <p style={{ fontSize: '12px', color: 'var(--accent-green)' }}>✓ All recent queries were answered with retrieved context.</p>
                ) : (
                  unanswered.slice(-10).reverse().map((q, i) => <UnansweredQuery key={i} text={q} />)
                )}
              </div>
            </>
          )}
        </>
      )}

      {/* Confirm Modal */}
      <AnimatePresence>
        {confirm && (
          <div className="modal-backdrop" onClick={() => setConfirm(null)}>
            <motion.div initial={{ scale: 0.92, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="modal-card" onClick={e => e.stopPropagation()}>
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
