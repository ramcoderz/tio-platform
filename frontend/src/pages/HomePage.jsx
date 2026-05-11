import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { 
  Bot, Activity, ArrowRight, Zap, 
  MessageSquare, Users, Globe, ExternalLink,
  Plus, Settings, MoreVertical, Trash2
} from "lucide-react";
import { motion } from "framer-motion";
import { api } from "../api";

export default function HomePage() {
  const navigate = useNavigate();
  const [chatbots, setChatbots] = useState([]);
  const [stats, setStats] = useState({ total_chatbots: 0, total_messages: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [cbData, statsData] = await Promise.all([
          api("/chatbots"),
          api("/admin/stats")
        ]);
        setChatbots(cbData || []);
        setStats(statsData);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  const handleDelete = async (id) => {
    if (!confirm("Are you sure you want to delete this chatbot?")) return;
    try {
      await api(`/chatbots/${id}`, "DELETE");
      setChatbots(chatbots.filter(cb => cb.id !== id));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div style={{ padding: '40px', maxWidth: '1400px', margin: '0 auto' }}>
      
      {/* Header */}
      <div style={{ marginBottom: '48px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '32px', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '8px' }}>
            Chatbot Builder Platform
          </h1>
          <p style={{ fontSize: '15px', color: '#64748b' }}>Design, build, and deploy context-aware assistants in minutes.</p>
        </div>
        <button 
          onClick={() => navigate("/create")} 
          style={{ 
            padding: '12px 24px', borderRadius: '12px', background: 'linear-gradient(135deg, #00C6FF, #0072FF)', 
            color: '#050816', fontWeight: 700, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px' 
          }}
        >
          <Plus size={18} /> New Chatbot
        </button>
      </div>

      {/* Stats Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '24px', marginBottom: '48px' }}>
        <DashboardStat icon={Bot} label="Total Chatbots" value={stats.total_chatbots} color="#00C6FF" />
        <DashboardStat icon={MessageSquare} label="Total Messages" value={stats.total_messages} color="#7C3AED" />
        <DashboardStat icon={Users} label="Active Users" value="1" color="#10B981" />
        <DashboardStat icon={Zap} label="Engine Status" value="Online" color="#F59E0B" />
      </div>

      {/* Chatbots List */}
      <section>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Activity size={20} color="#00C6FF" />
            <h3 style={{ fontSize: '14px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#64748b' }}>My Active Chatbots</h3>
          </div>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '60px', color: '#64748b' }}>Loading your chatbots...</div>
        ) : chatbots.length === 0 ? (
          <div className="glass-panel" style={{ padding: '60px', textAlign: 'center' }}>
            <Bot size={48} style={{ margin: '0 auto 16px', opacity: 0.2 }} />
            <p style={{ color: '#64748b', marginBottom: '20px' }}>No chatbots found. Start by creating your first assistant.</p>
            <button onClick={() => navigate("/create")} className="btn-primary" style={{ padding: '10px 20px', borderRadius: '8px' }}>Create Chatbot</button>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '24px' }}>
            {chatbots.map(cb => (
              <ChatbotCard key={cb.id} chatbot={cb} onDelete={() => handleDelete(cb.id)} />
            ))}
          </div>
        )}
      </section>

    </div>
  );
}

function DashboardStat({ icon: Icon, label, value, color }) {
  return (
    <div className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: `${color}10`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={20} color={color} />
        </div>
        <ArrowRight size={14} color="#334155" />
      </div>
      <div>
        <p style={{ fontSize: '11px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</p>
        <p style={{ fontSize: '24px', fontWeight: 800 }}>{value}</p>
      </div>
    </div>
  );
}

function ChatbotCard({ chatbot, onDelete }) {
  const navigate = useNavigate();
  return (
    <motion.div 
      whileHover={{ y: -4 }}
      className="glass-panel" 
      style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px', position: 'relative' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'linear-gradient(135deg, #00C6FF, #0072FF)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Bot size={24} color="#050816" />
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button 
            onClick={onDelete}
            style={{ background: 'transparent', border: 'none', color: '#ef4444', opacity: 0.5, cursor: 'pointer' }}
          >
            <Trash2 size={16} />
          </button>
          <button style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer' }}>
            <MoreVertical size={16} />
          </button>
        </div>
      </div>

      <div>
        <h4 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '4px' }}>{chatbot.name}</h4>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Globe size={12} color="#64748b" />
          <span style={{ fontSize: '12px', color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{chatbot.website_url || "No website"}</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ 
          fontSize: '11px', fontWeight: 700, padding: '4px 8px', borderRadius: '4px',
          background: chatbot.status === 'ready' ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)',
          color: chatbot.status === 'ready' ? '#10B981' : '#F59E0B',
          textTransform: 'uppercase'
        }}>
          {chatbot.status}
        </span>
        {chatbot.domain && (
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#00C6FF', background: 'rgba(0,198,255,0.1)', padding: '4px 8px', borderRadius: '4px', textTransform: 'capitalize' }}>
            {chatbot.domain}
          </span>
        )}
      </div>

      <div style={{ marginTop: 'auto', display: 'flex', gap: '10px' }}>
        <button 
          onClick={() => navigate(`/chat?chatbot_id=${chatbot.id}`)}
          style={{ 
            flex: 1, padding: '10px', borderRadius: '8px', background: 'rgba(255,255,255,0.05)', 
            border: '1px solid rgba(255,255,255,0.1)', color: '#fff', fontSize: '13px', fontWeight: 600, 
            cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px'
          }}
        >
          <MessageSquare size={14} /> Open Chat
        </button>
        <button 
          onClick={() => navigate(`/files?chatbot_id=${chatbot.id}`)}
          style={{ 
            padding: '10px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', 
            border: '1px solid rgba(255,255,255,0.05)', color: '#64748b', cursor: 'pointer' 
          }}
        >
          <Settings size={14} />
        </button>
      </div>
    </motion.div>
  );
}
