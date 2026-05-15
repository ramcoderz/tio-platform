import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Bot, MessageSquare, Plus, Zap, Globe,
  Trash2, ArrowRight, FileText, Activity, Layers, Cpu, Settings, RefreshCw, BarChart2
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
  ready: { label: 'Operational', cls: 'badge-cyan' },
  ingesting: { label: 'Processing', cls: 'badge-pulse' },
  error: { label: 'Fault', cls: 'badge-red' },
  pending: { label: 'Standby', cls: 'badge-gray' },
};

export default function DashboardPage() {
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

  const [deleteError, setDeleteError] = useState(null);

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (!confirm('Delete this intelligence core? This action cannot be undone.')) return;
    setDeleteError(null);
    try {
      await api(`/chatbots/${id}`, { method: 'DELETE' });
      setChatbots(prev => prev.filter(c => c.id !== id));
    } catch (err) {
      const msg = err.message || 'Delete failed. Please try again.';
      setDeleteError(msg);
      alert(`Failed to delete chatbot: ${msg}`);
    }
  };

  const handleReindex = async (e, id) => {
    e.stopPropagation();
    try {
      await api(`/chatbots/${id}/reingest`, { method: 'POST' });
      setChatbots(prev => prev.map(c => c.id === id ? { ...c, status: 'ingesting' } : c));
    } catch { /* silent */ }
  };

  const statCards = [
    { icon: Bot, label: 'Active Cores', value: stats.total_chatbots, color: '#3B82F6' },
    { icon: MessageSquare, label: 'Total Chats', value: stats.total_messages, color: '#A78BFA' },
    { icon: Layers, label: 'Knowledge Base', value: stats.total_documents, color: '#34D399' },
    { icon: Zap, label: 'Throughput', value: 'High', color: '#FBBF24' },
  ];

  return (
    <div style={{ padding: '40px 60px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '60px' }}>
        <div>
          <div className="badge badge-cyan" style={{ marginBottom: '12px' }}>Production Workspace</div>
          <h1 className="text-premium" style={{ fontSize: '42px', fontWeight: 800, lineHeight: 1.1, marginBottom: '12px' }}>
            Contextual Dashboard
          </h1>
          <p style={{ fontSize: '16px', color: 'var(--text-secondary)', maxWidth: '600px' }}>
            Manage your AI-powered website copilots, monitor real-time ingestion, and analyze interaction quality.
          </p>
        </div>
        <button onClick={() => navigate('/create')} className="btn btn-primary" style={{ height: '52px', borderRadius: '16px', padding: '0 28px' }}>
          <Plus size={20} /> Create New Chatbot
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '60px' }}>
        {statCards.map(({ icon: Icon, label, value, color }, i) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1 }}
            className="glass-panel"
            style={{ padding: '28px', borderLeft: `2px solid ${color}33` }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
              <div style={{ padding: '8px', background: `${color}15`, borderRadius: '10px' }}>
                <Icon size={20} color={color} />
              </div>
            </div>
            <p style={{ fontSize: '32px', fontWeight: 800, letterSpacing: '-0.03em', marginBottom: '4px' }}>
              {typeof value === 'number' ? value.toLocaleString() : value}
            </p>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500, textTransform: 'uppercase' }}>{label}</p>
          </motion.div>
        ))}
      </div>

      {/* Chatbots */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
        <Activity size={20} color="var(--accent)" />
        <h3 className="font-heading" style={{ fontSize: '20px' }}>Intelligence Cores</h3>
      </div>

      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: '24px' }}>
          {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: '280px', borderRadius: '24px' }} />)}
        </div>
      ) : chatbots.length === 0 ? (
        <div className="glass-panel" style={{ padding: '100px', textAlign: 'center', borderStyle: 'dashed' }}>
          <Bot size={48} style={{ opacity: 0.2, marginBottom: '20px' }} />
          <h3 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '8px' }}>No Chatbots Found</h3>
          <p style={{ color: 'var(--text-muted)', marginBottom: '32px' }}>Start by indexing a website or uploading documents.</p>
          <button onClick={() => navigate('/create')} className="btn btn-primary">Get Started</button>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: '24px' }}>
          {chatbots.map((cb, i) => {
            const domain = cb.domain || 'general';
            const dc = DOMAIN_COLORS[domain] || DOMAIN_COLORS.general;
            const st = STATUS_MAP[cb.status] || STATUS_MAP.pending;
            return (
              <motion.div
                key={cb.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="glass-panel"
                style={{ padding: '32px', cursor: 'pointer', display: 'flex', flexDirection: 'column' }}
                onClick={() => navigate(`/chat?chatbot_id=${cb.id}`)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                  <div style={{
                    width: '48px', height: '48px', borderRadius: '14px',
                    background: 'linear-gradient(135deg, #6366f1, #a855f7)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: '0 8px 16px rgba(99,102,241,0.2)'
                  }}>
                    <Bot size={24} color="#fff" />
                  </div>
                  <div style={{ display: 'flex', gap: '4px' }}>
                    <button onClick={(e) => { e.stopPropagation(); navigate(`/chatbot/${cb.id}`); }} className="btn btn-ghost" style={{ padding: '8px' }}>
                      <BarChart2 size={16} />
                    </button>
                    <button onClick={(e) => handleReindex(e, cb.id)} className="btn btn-ghost" style={{ padding: '8px' }} title="Re-index Knowledge">
                      <RefreshCw size={16} className={cb.status === 'ingesting' ? 'animate-spin' : ''} />
                    </button>
                    <button onClick={(e) => handleDelete(e, cb.id)} className="btn btn-ghost" style={{ padding: '8px', color: '#ef4444' }}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                <div style={{ marginBottom: '24px' }}>
                  <h4 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '4px' }}>{cb.name}</h4>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', opacity: 0.6 }}>
                    <Globe size={12} />
                    <span style={{ fontSize: '12px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cb.website_url || 'Internal Knowledge'}</span>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px', marginBottom: '28px' }}>
                  <div className={`badge ${st.cls}`} style={{ fontSize: '10px' }}>{st.label}</div>
                  <div className="badge" style={{ borderColor: dc.color, color: dc.color, background: `${dc.color}08`, textTransform: 'capitalize' }}>{domain}</div>
                </div>

                <div style={{ marginTop: 'auto', display: 'flex', gap: '10px' }}>
                  <button className="btn btn-primary" style={{ flex: 1 }} onClick={e => { e.stopPropagation(); navigate(`/chat?chatbot_id=${cb.id}`); }}>
                    Enter Chat
                  </button>
                  <button className="btn btn-ghost" onClick={e => { e.stopPropagation(); navigate(`/files?chatbot_id=${cb.id}`); }}>
                    <FileText size={18} />
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
