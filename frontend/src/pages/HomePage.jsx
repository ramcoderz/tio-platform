import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Bot, MessageSquare, Plus, Zap, Globe,
  Trash2, ArrowRight, FileText, Activity, Layers, Cpu
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
    if (!confirm('Delete this intelligence core? This action cannot be undone.')) return;
    try {
      await api(`/chatbots/${id}`, { method: 'DELETE' });
      setChatbots(prev => prev.filter(c => c.id !== id));
    } catch (err) {
      alert(`Failed to delete chatbot: ${err.message || 'Unknown error'}`);
    }
  };

  const statCards = [
    { icon: Bot, label: 'Active Cores', value: stats.total_chatbots, color: 'var(--accent)' },
    { icon: MessageSquare, label: 'Interactions', value: stats.total_messages, color: '#A78BFA' },
    { icon: Layers, label: 'Knowledge Base', value: stats.total_documents, color: '#34D399' },
    { icon: Cpu, label: 'Neural Status', value: 'Optimized', color: '#FBBF24' },
  ];

  return (
    <div style={{ padding: '40px 60px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header Portal */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '60px' }}>
        <div>
          <div className="badge badge-cyan" style={{ marginBottom: '12px' }}>Workspace Overview</div>
          <h1 className="text-premium" style={{ fontSize: '42px', fontWeight: 800, lineHeight: 1.1, marginBottom: '12px' }}>
            Intelligence Dashboard
          </h1>
          <p style={{ fontSize: '16px', color: 'var(--text-secondary)', maxWidth: '600px' }}>
            Orchestrate autonomous agents, manage ingestion pipelines, and monitor real-time AI interactions across your ecosystem.
          </p>
        </div>
        <button onClick={() => navigate('/create')} className="btn btn-primary" style={{ height: '52px', borderRadius: '16px', padding: '0 28px' }}>
          <Plus size={20} /> Deploy New Core
        </button>
      </div>

      {/* Analytics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '60px' }}>
        {statCards.map(({ icon: Icon, label, value, color }, i) => (
          <motion.div
            key={label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1, duration: 0.5 }}
            className="glass-panel"
            style={{ padding: '28px', borderLeft: `2px solid ${color}33` }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
              <div style={{ padding: '8px', background: `${color}15`, borderRadius: '10px' }}>
                <Icon size={20} color={color} />
              </div>
              <Activity size={14} color="var(--text-dim)" />
            </div>
            <p style={{ fontSize: '32px', fontWeight: 800, letterSpacing: '-0.03em', marginBottom: '4px' }}>
              {typeof value === 'number' ? value.toLocaleString() : value}
            </p>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</p>
          </motion.div>
        ))}
      </div>

      {/* Intelligence Grid */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
        <Layers size={20} color="var(--accent)" />
        <h3 className="font-heading" style={{ fontSize: '20px' }}>Deployed Intelligence Cores</h3>
      </div>

      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: '24px' }}>
          {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height: '220px', borderRadius: '24px' }} />)}
        </div>
      ) : chatbots.length === 0 ? (
        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="glass-panel" 
          style={{ padding: '80px', textAlign: 'center', borderStyle: 'dashed', borderWidth: '2px' }}
        >
          <div className="flex-center" style={{ marginBottom: '24px' }}>
             <Bot size={64} style={{ opacity: 0.2 }} />
          </div>
          <h3 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '8px' }}>No Active Intelligence</h3>
          <p style={{ color: 'var(--text-muted)', marginBottom: '32px', maxWidth: '400px', margin: '0 auto 32px' }}>
            Your workspace is currently empty. Initialize your first chatbot by providing a knowledge source URL.
          </p>
          <button onClick={() => navigate('/create')} className="btn btn-primary"><Plus size={18} /> Initialize First Core</button>
        </motion.div>
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
                transition={{ delay: i * 0.08 }}
                whileHover={{ y: -8, boxShadow: '0 20px 40px rgba(0,0,0,0.4)' }}
                className="glass-panel"
                style={{ padding: '32px', cursor: 'pointer', display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}
                onClick={() => navigate(`/chat?chatbot_id=${cb.id}`)}
              >
                {/* Visual Accent */}
                <div style={{ position: 'absolute', top: 0, right: 0, width: '100px', height: '100px', background: `radial-gradient(circle at top right, ${dc.color}15, transparent)`, pointerEvents: 'none' }} />

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                  <div style={{
                    width: '52px', height: '52px', borderRadius: '16px',
                    background: 'linear-gradient(135deg, #00C6FF, #0072FF)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    boxShadow: '0 8px 20px rgba(0,198,255,0.2)'
                  }}>
                    <Bot size={28} color="#03050c" />
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button
                      onClick={(e) => handleDelete(e, cb.id)}
                      className="btn btn-ghost"
                      style={{ padding: '8px', borderRadius: '10px' }}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                <div style={{ marginBottom: '24px' }}>
                  <h4 style={{ fontSize: '20px', fontWeight: 800, marginBottom: '6px' }}>{cb.name}</h4>
                  {cb.website_url && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Globe size={12} color="var(--text-dim)" />
                      <span style={{ fontSize: '13px', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cb.website_url}</span>
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '28px' }}>
                  <div className={`badge ${st.cls}`} style={{ fontSize: '10px' }}>{st.label}</div>
                  <div className="badge" style={{ borderColor: dc.color, color: dc.color, background: `${dc.color}08`, textTransform: 'capitalize' }}>{domain}</div>
                </div>

                <div style={{ marginTop: 'auto', display: 'flex', gap: '12px' }}>
                  <button className="btn btn-primary" style={{ flex: 1, borderRadius: '12px' }} onClick={e => { e.stopPropagation(); navigate(`/chat?chatbot_id=${cb.id}`); }}>
                    Enter Core <ArrowRight size={16} style={{ marginLeft: '4px' }} />
                  </button>
                  <button className="btn btn-ghost" style={{ padding: '0 16px', borderRadius: '12px' }} onClick={e => { e.stopPropagation(); navigate(`/files?chatbot_id=${cb.id}`); }}>
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
