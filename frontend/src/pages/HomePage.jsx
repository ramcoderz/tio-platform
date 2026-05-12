import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Bot, MessageSquare, Plus, Zap, Globe,
  Trash2, ArrowRight, FileText, Activity
} from 'lucide-react';
import { api } from '../api';

const DOMAIN_COLORS = {
  tourism: { bg: 'rgba(52,211,153,0.12)', color: '#34D399' },
  medical: { bg: 'rgba(239,68,68,0.12)', color: '#F87171' },
  education: { bg: 'rgba(124,58,237,0.12)', color: '#A78BFA' },
  developer: { bg: 'rgba(59,130,246,0.12)', color: '#60A5FA' },
  ecommerce: { bg: 'rgba(245,158,11,0.12)', color: '#FBBF24' },
  general: { bg: 'rgba(0,198,255,0.12)', color: '#00C6FF' },
};

const STATUS_MAP = {
  ready: { label: 'Ready', cls: 'badge-green' },
  ingesting: { label: 'Ingesting', cls: 'badge-amber badge-pulse' },
  error: { label: 'Error', cls: 'badge-red' },
  pending: { label: 'Pending', cls: 'badge-gray' },
};

export default function HomePage() {
  const navigate = useNavigate();
  const [chatbots, setChatbots] = useState([]);
  const [stats, setStats] = useState({ total_chatbots: 0, total_messages: 0, total_documents: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [cb, st] = await Promise.all([api('/chatbots'), api('/admin/stats')]);
        setChatbots(cb || []);
        setStats(st);
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    load();
  }, []);

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (!confirm('Delete this chatbot and all its data?')) return;
    try {
      await api(`/chatbots/${id}`, { method: 'DELETE' });
      setChatbots(prev => prev.filter(c => c.id !== id));
    } catch { /* silent */ }
  };

  const statCards = [
    { icon: Bot, label: 'Chatbots', value: stats.total_chatbots, color: 'var(--accent)' },
    { icon: MessageSquare, label: 'Messages', value: stats.total_messages, color: 'var(--accent-violet)' },
    { icon: FileText, label: 'Documents', value: stats.total_documents, color: 'var(--accent-green)' },
    { icon: Activity, label: 'Status', value: 'Online', color: 'var(--accent-amber)' },
  ];

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '40px' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '6px' }}>
            Chatbot Builder
          </h1>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Build context-aware assistants from any website.</p>
        </div>
        <button onClick={() => navigate('/create')} className="btn btn-primary">
          <Plus size={18} /> New Chatbot
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', marginBottom: '40px' }}>
        {statCards.map(({ icon: Icon, label, value, color }, i) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            className="glass-panel"
            style={{ padding: '20px' }}
          >
            <Icon size={18} color={color} style={{ marginBottom: '10px' }} />
            <p style={{ fontSize: '24px', fontWeight: 800, letterSpacing: '-0.02em' }}>{typeof value === 'number' ? value.toLocaleString() : value}</p>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>{label}</p>
          </motion.div>
        ))}
      </div>

      {/* Chatbot Section */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
        <Activity size={16} color="var(--accent)" />
        <h3 style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>My Chatbots</h3>
      </div>

      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
          {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: '180px' }} />)}
        </div>
      ) : chatbots.length === 0 ? (
        <div className="glass-panel" style={{ padding: '60px', textAlign: 'center' }}>
          <Bot size={48} style={{ margin: '0 auto 16px', opacity: 0.15, color: 'var(--text-muted)' }} />
          <p style={{ fontSize: '16px', fontWeight: 600, marginBottom: '6px' }}>No chatbots yet</p>
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '24px' }}>Paste a URL to get started.</p>
          <button onClick={() => navigate('/create')} className="btn btn-primary btn-sm"><Plus size={16} /> Create First Chatbot</button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
          {chatbots.map((cb, i) => {
            const domain = cb.domain || 'general';
            const dc = DOMAIN_COLORS[domain] || DOMAIN_COLORS.general;
            const st = STATUS_MAP[cb.status] || STATUS_MAP.pending;
            return (
              <motion.div
                key={cb.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                whileHover={{ y: -4 }}
                className="glass-panel"
                style={{ padding: '22px', cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: '14px' }}
                onClick={() => navigate(`/chat?chatbot_id=${cb.id}`)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{
                    width: '44px', height: '44px', borderRadius: 'var(--radius-md)',
                    background: 'linear-gradient(135deg, #00C6FF, #0072FF)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}>
                    <Bot size={22} color="#050816" />
                  </div>
                  <button
                    onClick={(e) => handleDelete(e, cb.id)}
                    style={{ padding: '6px', color: 'var(--text-dim)', borderRadius: '6px', transition: 'all 0.15s' }}
                    onMouseEnter={e => { e.currentTarget.style.color = 'var(--accent-red)'; e.currentTarget.style.background = 'rgba(239,68,68,0.08)'; }}
                    onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-dim)'; e.currentTarget.style.background = 'transparent'; }}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>

                <div>
                  <h4 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '4px' }}>{cb.name}</h4>
                  {cb.website_url && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                      <Globe size={11} color="var(--text-dim)" />
                      <span style={{ fontSize: '12px', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '220px' }}>{cb.website_url}</span>
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className={`badge ${st.cls}`}>{st.label}</span>
                  {cb.domain && <span className="badge" style={{ background: dc.bg, color: dc.color, textTransform: 'capitalize' }}>{cb.domain}</span>}
                </div>

                <div style={{ marginTop: 'auto', display: 'flex', gap: '8px' }}>
                  <button className="btn btn-ghost btn-sm" style={{ flex: 1 }} onClick={e => { e.stopPropagation(); navigate(`/chat?chatbot_id=${cb.id}`); }}>
                    <MessageSquare size={14} /> Chat
                  </button>
                  <button className="btn btn-ghost btn-sm" onClick={e => { e.stopPropagation(); navigate(`/files?chatbot_id=${cb.id}`); }}>
                    <FileText size={14} />
                  </button>
                </div>
              </motion.div>
            );
          })}
        </div>
      )}
    </div>
  );
}
