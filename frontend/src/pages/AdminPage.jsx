import { useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield, RefreshCw, MessageSquare, FileText,
  Bot, Trash2, AlertTriangle, Database,
  Activity, TrendingUp, HelpCircle, Zap, BarChart2,
  Terminal, Search, ChevronRight, Layers, Cpu
} from 'lucide-react';
import { api } from '../api';

function MiniBar({ label, value, max, color = 'var(--accent)' }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div style={{ marginBottom: '16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
        <span style={{ fontSize: '13px', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{label.replace(/_/g, ' ')}</span>
        <span style={{ fontSize: '13px', fontWeight: 700, color, fontFamily: 'var(--font-mono)' }}>{value}</span>
      </div>
      <div style={{ height: '6px', borderRadius: '3px', background: 'rgba(255,255,255,0.05)', overflow: 'hidden' }}>
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          style={{ height: '100%', background: color, boxShadow: `0 0 10px ${color}44` }} 
        />
      </div>
    </div>
  );
}

function MetricCard({ label, value, sub, icon: Icon, color, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="glass-panel"
      style={{ padding: '24px', position: 'relative', overflow: 'hidden' }}
    >
      <div style={{ position: 'absolute', top: 0, right: 0, width: '60px', height: '60px', background: `radial-gradient(circle at top right, ${color}10, transparent)`, pointerEvents: 'none' }} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <p className="font-heading" style={{ fontSize: '32px', fontWeight: 800, letterSpacing: '-0.04em', color: '#fff' }}>{value}</p>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>{label}</p>
          {sub && <p style={{ fontSize: '11px', color, marginTop: '6px', fontWeight: 700, letterSpacing: '0.05em' }}>{sub}</p>}
        </div>
        <div style={{
          width: '44px', height: '44px', borderRadius: '12px',
          background: `${color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: `0 8px 20px ${color}15`
        }}>
          <Icon size={20} color={color} />
        </div>
      </div>
    </motion.div>
  );
}

const TABS = ['Overview', 'Monitoring', 'Logs'];
const DOMAIN_COLORS = {
  tourism: '#34D399', education: '#A78BFA', medical: '#F87171',
  developer: '#3B82F6', ecommerce: '#FBBF24', general: '#94A3B8',
};

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState('Overview');
  const [stats, setStats]         = useState(null);
  const [logs, setLogs]           = useState([]);
  const [chatbots, setChatbots]   = useState([]);
  const [loading, setLoading]     = useState(true);
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
    { label: 'Authorized Users', value: stats?.users ?? 0, icon: Shield, color: '#3B82F6' },
    { label: 'Intelligence Cores', value: stats?.chatbots ?? 0, icon: Bot, color: '#00C6FF' },
    { label: 'Neural Interactions', value: stats?.messages ?? 0, icon: MessageSquare, color: '#A78BFA' },
    { label: 'System Uptime', value: '99.9%', icon: Activity, color: '#10B981' },
  ];

  return (
    <div style={{ padding: '40px 60px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header Portal */}
      <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '40px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
            <div className="glass-panel" style={{ padding: '6px', borderRadius: '8px' }}>
               <Shield size={16} color="var(--accent)" />
            </div>
            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent)', letterSpacing: '0.15em', fontFamily: 'var(--font-mono)' }}>SYSTEM OPERATOR</span>
          </div>
          <h1 className="text-premium" style={{ fontSize: '36px', fontWeight: 800 }}>Neural Control Center</h1>
          <p style={{ fontSize: '15px', color: 'var(--text-secondary)', marginTop: '6px' }}>Advanced orchestration and monitoring of the TiO Intelligence Platform.</p>
        </div>
        <button onClick={fetchAll} className="btn btn-ghost" style={{ borderRadius: '12px' }}>
          <RefreshCw size={18} className={loading ? 'animate-spin' : ''} style={{ marginRight: '8px' }} /> Synchronize Data
        </button>
      </header>

      {/* Modern Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '40px', background: 'rgba(255,255,255,0.02)', padding: '6px', borderRadius: '16px', width: 'fit-content' }}>
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className="btn"
            style={{
              padding: '10px 24px', borderRadius: '12px',
              background: activeTab === tab ? 'var(--accent-gradient)' : 'transparent',
              color: activeTab === tab ? '#03050c' : 'var(--text-secondary)',
              boxShadow: activeTab === tab ? '0 4px 15px rgba(0,198,255,0.2)' : 'none'
            }}
          >
            {tab}
          </button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {activeTab === 'Overview' && (
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.98 }} key="overview">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '40px' }}>
              {overviewCards.map((c, i) => <MetricCard key={c.label} {...c} delay={i * 0.08} />)}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: '32px' }}>
              {/* Pipeline Monitor */}
              <div className="glass-panel" style={{ padding: '32px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
                  <h3 className="font-heading" style={{ fontSize: '18px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Activity size={20} color="var(--accent)" /> Pipeline Distribution
                  </h3>
                  <div className="badge badge-cyan">Real-time</div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {chatbots.map(cb => (
                    <motion.div 
                      key={cb.id} 
                      whileHover={{ x: 6 }}
                      style={{ 
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center', 
                        padding: '16px', borderRadius: '16px', background: 'rgba(255,255,255,0.02)',
                        border: '1px solid var(--border)'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'var(--accent-gradient)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <Bot size={16} color="#03050c" />
                        </div>
                        <div>
                          <p style={{ fontSize: '14px', fontWeight: 700 }}>{cb.name}</p>
                          <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{cb.domain || 'General'}</p>
                        </div>
                      </div>
                      <div className="badge" style={{ 
                        background: cb.status === 'ready' ? 'rgba(16,185,129,0.1)' : 'rgba(0,198,255,0.1)',
                        color: cb.status === 'ready' ? '#34D399' : 'var(--accent)',
                        borderColor: cb.status === 'ready' ? 'rgba(16,185,129,0.2)' : 'rgba(0,198,255,0.2)'
                      }}>
                        {cb.status}
                      </div>
                    </motion.div>
                  ))}
                  {chatbots.length === 0 && (
                    <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-dim)' }}>
                      <Layers size={32} style={{ opacity: 0.1, margin: '0 auto 12px' }} />
                      <p>No active cores detected.</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Infrastructure */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <div className="glass-panel" style={{ padding: '28px' }}>
                  <h4 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '24px' }}>Hardware Status</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    {[
                      { label: 'Neural Engine', value: 'Ollama Llama3', color: 'var(--accent)' },
                      { label: 'Vector Database', value: 'ChromaDB Core', color: '#34D399' },
                      { label: 'Knowledge Ingestion', value: 'Active', color: '#10B981' },
                      { label: 'Memory Allocation', value: 'Optimized', color: '#A78BFA' }
                    ].map(item => (
                      <div key={item.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>{item.label}</span>
                        <span style={{ fontSize: '13px', fontWeight: 700, color: item.color }}>{item.value}</span>
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: '32px', padding: '16px', borderRadius: '12px', background: 'rgba(0,198,255,0.05)', border: '1px solid rgba(0,198,255,0.1)', textAlign: 'center' }}>
                     <span style={{ fontSize: '11px', fontWeight: 800, color: 'var(--accent)', letterSpacing: '0.1em' }}>CLUSTER STABLE</span>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === 'Logs' && (
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }} key="logs">
            <div className="glass-panel" style={{ height: '700px', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(255,255,255,0.02)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <Terminal size={18} color="var(--text-muted)" />
                  <span className="font-heading" style={{ fontSize: '14px', fontWeight: 700 }}>Neural Stream</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#34D399', boxShadow: '0 0 10px #34D399' }} />
                  <span style={{ fontSize: '11px', fontWeight: 800, color: '#34D399' }}>SYNCHRONIZED</span>
                </div>
              </div>
              <div style={{ flex: 1, overflowY: 'auto', padding: '24px', fontFamily: 'var(--font-mono)', fontSize: '12px', background: '#020308' }} className="custom-scrollbar">
                {logs.map((log, i) => (
                  <div key={i} style={{ 
                    padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.03)', 
                    display: 'flex', gap: '16px', color: log.level === 'ERROR' ? '#F87171' : log.level === 'WARNING' ? '#FBBF24' : '#94A3B8'
                  }}>
                    <span style={{ opacity: 0.3, width: '90px', flexShrink: 0 }}>{new Date(log.timestamp * 1000).toLocaleTimeString()}</span>
                    <span style={{ fontWeight: 800, width: '60px', flexShrink: 0 }}>[{log.level}]</span>
                    <span style={{ color: 'var(--accent)', opacity: 0.9, width: '150px', flexShrink: 0, overflow: 'hidden', textOverflow: 'ellipsis' }}>{log.name}</span>
                    <span style={{ whiteSpace: 'pre-wrap', lineHeight: 1.6, flex: 1 }}>{log.message}</span>
                  </div>
                ))}
                <div ref={logEndRef} />
              </div>
            </div>
          </motion.div>
        )}

        {activeTab === 'Monitoring' && (
          <motion.div initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.98 }} key="monitoring">
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 400px', gap: '32px' }}>
              <div className="glass-panel" style={{ padding: '32px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
                  <h3 className="font-heading" style={{ fontSize: '18px' }}>Domain Routing Intelligence</h3>
                  <div className="badge badge-cyan">Live Data</div>
                </div>
                {(() => {
                  const domainData = stats?.monitor?.domain_distribution || {};
                  const maxVal = Math.max(...Object.values(domainData), 1);
                  const allDomains = ['tourism', 'education', 'medical', 'developer', 'ecommerce', 'general'];
                  const activeDomains = allDomains.filter(d => (domainData[d] || 0) > 0);
                  const displayDomains = activeDomains.length > 0 ? activeDomains : allDomains;
                  return (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
                      <div>
                        {displayDomains.slice(0, Math.ceil(displayDomains.length / 2)).map(d => (
                          <MiniBar key={d} label={d} value={domainData[d] || 0} max={maxVal} color={DOMAIN_COLORS[d]} />
                        ))}
                      </div>
                      <div>
                        {displayDomains.slice(Math.ceil(displayDomains.length / 2)).map(d => (
                          <MiniBar key={d} label={d} value={domainData[d] || 0} max={maxVal} color={DOMAIN_COLORS[d]} />
                        ))}
                      </div>
                    </div>
                  );
                })()}
                {stats?.monitor?.total_queries > 0 && (
                  <div style={{ marginTop: '24px', padding: '12px 16px', borderRadius: '12px', background: 'rgba(0,198,255,0.04)', border: '1px solid rgba(0,198,255,0.1)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Total Queries</span>
                      <span style={{ fontWeight: 700, color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>{stats.monitor.total_queries}</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginTop: '6px' }}>
                      <span style={{ color: 'var(--text-muted)' }}>Answer Rate</span>
                      <span style={{ fontWeight: 700, color: '#34D399', fontFamily: 'var(--font-mono)' }}>{stats.monitor.answer_rate_pct}%</span>
                    </div>
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <div className="glass-panel" style={{ padding: '32px' }}>
                  <h3 className="font-heading" style={{ fontSize: '16px', marginBottom: '24px' }}>Latency Analysis</h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                    <div>
                      <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Retrieval Overhead</p>
                      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px' }}>
                        <p style={{ fontSize: '32px', fontWeight: 800, lineHeight: 1 }}>{stats?.monitor?.avg_retrieval_ms ?? '—'}</p>
                        <p style={{ fontSize: '14px', color: 'var(--text-dim)', fontWeight: 600 }}>ms</p>
                        <TrendingUp size={16} color="#34D399" style={{ marginBottom: '4px' }} />
                      </div>
                    </div>
                    <div>
                      <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>LLM Generation</p>
                      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px' }}>
                        <p style={{ fontSize: '32px', fontWeight: 800, lineHeight: 1 }}>{stats?.monitor?.avg_llm_ms ?? '—'}</p>
                        <p style={{ fontSize: '14px', color: 'var(--text-dim)', fontWeight: 600 }}>ms</p>
                      </div>
                    </div>
                    <div>
                      <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Avg Citations / Query</p>
                      <div style={{ display: 'flex', alignItems: 'flex-end', gap: '8px' }}>
                        <p style={{ fontSize: '32px', fontWeight: 800, lineHeight: 1 }}>{stats?.monitor?.avg_citations_per_query ?? '—'}</p>
                        <p style={{ fontSize: '14px', color: 'var(--text-dim)', fontWeight: 600 }}>chunks</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Popular Intents */}
                {stats?.monitor?.popular_intents && Object.keys(stats.monitor.popular_intents).length > 0 && (
                  <div className="glass-panel" style={{ padding: '28px' }}>
                    <h4 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '16px' }}>Top Skills Used</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {Object.entries(stats.monitor.popular_intents).slice(0, 5).map(([skill, count]) => (
                        <div key={skill} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontSize: '13px', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>{skill.replace(/_/g, ' ')}</span>
                          <span style={{ fontSize: '13px', fontWeight: 700, color: 'var(--accent)', fontFamily: 'var(--font-mono)' }}>{count}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Unanswered Queries */}
            {stats?.monitor?.recent_unanswered?.length > 0 && (
              <div className="glass-panel" style={{ padding: '28px', marginTop: '32px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
                  <HelpCircle size={18} color="#FBBF24" />
                  <h4 style={{ fontSize: '14px', fontWeight: 700 }}>Unanswered Queries</h4>
                  <span className="badge badge-amber" style={{ marginLeft: 'auto' }}>{stats.monitor.unanswered_queries} total</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {stats.monitor.recent_unanswered.map((q, i) => (
                    <div key={i} style={{ padding: '8px 12px', borderRadius: '8px', background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.1)', fontSize: '13px', color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                      {q}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </motion.div>
        )}

      </AnimatePresence>
    </div>
  );
}
