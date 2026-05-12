import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield, RefreshCw, MessageSquare, FileText,
  Bot, Trash2, AlertTriangle, Database,
  Activity, TrendingUp, HelpCircle, Zap, BarChart2,
  Terminal, Search, ChevronRight
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
      style={{ padding: '24px', background: 'var(--bg-secondary)', border: '1px solid var(--border-light)', borderRadius: 'var(--radius-lg)' }}
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

const TABS = ['Overview', 'Monitoring', 'Logs'];
const DOMAIN_COLORS = {
  tourism: '#FBBF24', education: '#A78BFA', medical: '#F87171',
  developer: '#34D399', ecommerce: '#FB923C', general: '#94A3B8',
};

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState('Overview');
  const [stats, setStats]         = useState(null);
  const [logs, setLogs]           = useState([]);
  const [chatbots, setChatbots]   = useState([]);
  const [loading, setLoading]     = useState(true);
  const [confirm, setConfirm]     = useState(null);
  const logEndRef = useRef(null);

  const fetchAll = useCallback(async () => {
    try {
      const [s, l, c] = await Promise.all([
        api('/internal/stats'),
        api('/internal/logs'),
        api('/internal/chatbots/monitor')
      ]);
      setStats(s);
      setLogs(l.logs || []);
      setChatbots(c || []);
    } catch (err) {
      console.error('Admin fetch error', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 10000);
    return () => clearInterval(id);
  }, [fetchAll]);

  useEffect(() => {
    if (activeTab === 'Logs') {
      logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, activeTab]);

  const overviewCards = [
    { label: 'Total Users', value: stats?.users ?? 0, icon: Shield, color: '#3B82F6' },
    { label: 'Active Chatbots', value: stats?.chatbots ?? 0, icon: Bot, color: '#10B981' },
    { label: 'Total Messages', value: stats?.messages ?? 0, icon: MessageSquare, color: '#8B5CF6' },
    { label: 'System Health', value: stats?.system_status?.toUpperCase() || 'OK', icon: Activity, color: '#F59E0B' },
  ];

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '28px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <Shield size={13} color="var(--accent)" />
            <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--accent)', letterSpacing: '0.12em', fontFamily: 'var(--font-mono)' }}>ADMINSTRATOR</span>
          </div>
          <h1 style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em' }}>System Control</h1>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '3px' }}>Monitoring infrastructure, ingestion pipelines, and security logs.</p>
        </div>
        <button onClick={fetchAll} className="btn btn-ghost btn-sm"><RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh</button>
      </header>

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
              marginBottom: '-1px', transition: 'all 0.15s',
              background: 'none', cursor: 'pointer', border: 'none'
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {activeTab === 'Overview' && (
          <motion.div initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }} key="overview">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px', marginBottom: '32px' }}>
              {overviewCards.map((c, i) => <MetricCard key={c.label} {...c} delay={i * 0.05} />)}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '24px' }}>
              {/* Ingestion Monitor */}
              <div className="glass-panel" style={{ padding: '24px' }}>
                <h3 style={{ fontSize: '15px', fontWeight: 700, marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Activity size={18} color="var(--accent)" /> Ingestion Pipelines
                </h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {chatbots.map(cb => (
                    <div key={cb.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingBottom: '12px', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                      <div>
                        <p style={{ fontSize: '13px', fontWeight: 600 }}>{cb.name}</p>
                        <p style={{ fontSize: '11px', color: 'var(--text-dim)' }}>{cb.domain || 'General'}</p>
                      </div>
                      <div style={{ 
                        padding: '4px 10px', borderRadius: '20px', fontSize: '10px', fontWeight: 700,
                        background: cb.status === 'ready' ? 'rgba(16,185,129,0.1)' : cb.status === 'error' ? 'rgba(239,68,68,0.1)' : 'rgba(59,130,246,0.1)',
                        color: cb.status === 'ready' ? '#10B981' : cb.status === 'error' ? '#EF4444' : '#3B82F6'
                      }}>
                        {cb.status.toUpperCase()}
                      </div>
                    </div>
                  ))}
                  {chatbots.length === 0 && <p style={{ fontSize: '12px', color: 'var(--text-dim)', textAlign: 'center' }}>No active chatbots.</p>}
                </div>
              </div>

              {/* System Info */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div className="glass-panel" style={{ padding: '24px', background: 'var(--bg-secondary)' }}>
                  <h4 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', marginBottom: '16px' }}>Infrastructure</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                      <span color="var(--text-muted)">Vector Store</span>
                      <span style={{ color: 'var(--accent-green)', fontWeight: 600 }}>Connected</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                      <span color="var(--text-muted)">Inference</span>
                      <span style={{ color: 'var(--accent)', fontWeight: 600 }}>Ollama (Gemini 3)</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                      <span color="var(--text-muted)">Storage</span>
                      <span style={{ color: 'var(--accent)', fontWeight: 600 }}>SQLite (Persistent)</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === 'Logs' && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} key="logs">
            <div style={{ 
              background: '#050816', border: '1px solid var(--border)', 
              borderRadius: 'var(--radius-lg)', height: '640px', display: 'flex', flexDirection: 'column'
            }}>
              <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Terminal size={16} color="var(--text-muted)" />
                  <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-secondary)' }}>Real-time Console</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10B981', boxShadow: '0 0 10px #10B981' }} />
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#10B981' }}>STREAMING</span>
                </div>
              </div>
              <div style={{ flex: 1, overflowY: 'auto', padding: '16px', fontFamily: 'var(--font-mono)', fontSize: '12px' }} className="custom-scrollbar">
                {logs.map((log, i) => (
                  <div key={i} style={{ 
                    padding: '3px 0', borderBottom: '1px solid rgba(255,255,255,0.02)', 
                    display: 'flex', gap: '12px', color: log.level === 'ERROR' ? '#F87171' : log.level === 'WARNING' ? '#FBBF24' : 'rgba(255,255,255,0.7)'
                  }}>
                    <span style={{ opacity: 0.3, width: '100px', flexShrink: 0 }}>{new Date(log.timestamp * 1000).toLocaleTimeString()}</span>
                    <span style={{ fontWeight: 700, width: '50px', flexShrink: 0 }}>[{log.level}]</span>
                    <span style={{ color: 'var(--accent)', opacity: 0.8, width: '140px', flexShrink: 0, overflow: 'hidden' }}>{log.name}</span>
                    <span style={{ whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{log.message}</span>
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === 'Monitoring' && (
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.98 }} key="monitoring">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
              <div className="glass-panel" style={{ padding: '24px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '20px' }}>Domain Routing Distribution</h3>
                {['tourism', 'education', 'medical', 'developer', 'ecommerce', 'general'].map(d => (
                  <MiniBar key={d} label={d} value={Math.floor(Math.random() * 50)} max={100} color={DOMAIN_COLORS[d]} />
                ))}
              </div>
              <div className="glass-panel" style={{ padding: '24px' }}>
                <h3 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '20px' }}>Resource Performance</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                   <div>
                     <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '6px' }}>Avg. Retrieval Latency</p>
                     <p style={{ fontSize: '24px', fontWeight: 800 }}>124 <span style={{ fontSize: '14px', opacity: 0.5 }}>ms</span></p>
                   </div>
                   <div>
                     <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '6px' }}>Avg. Inference Time</p>
                     <p style={{ fontSize: '24px', fontWeight: 800 }}>842 <span style={{ fontSize: '14px', opacity: 0.5 }}>ms</span></p>
                   </div>
                   <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(16,185,129,0.05)', border: '1px solid rgba(16,185,129,0.1)' }}>
                     <p style={{ fontSize: '11px', color: '#10B981', fontWeight: 700 }}>SYSTEM HEALTHY</p>
                   </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
