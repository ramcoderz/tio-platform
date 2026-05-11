import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Home, Upload, MessageSquare, Plus,
  Zap, Settings, Shield, LogOut, FileText, Bot
} from 'lucide-react';
import { useAppCtx } from '../context/AppContext';
import { useChatStore } from '../store';
import { useNavigate } from 'react-router-dom';

const navItems = [
  { icon: Home, label: 'Home', path: '/' },
  { icon: Plus, label: 'Create Chatbot', path: '/create' },
  { icon: MessageSquare, label: 'Chats', path: '/chat' },
  { icon: FileText, label: 'Files', path: '/files' },
  { icon: Settings, label: 'Admin', path: '/admin' },
  { icon: Shield, label: 'Settings', path: '/settings' },
];

export default function AppShell({ children }) {
  const location = useLocation();
  const { user, logout } = useAppCtx();
  const navigate = useNavigate();
  const { sessionId, setSessionId } = useChatStore();

  const [chatbots, setChatbots] = useState([]);

  useEffect(() => {
    const fetchChatbots = async () => {
      try {
        const { api } = await import('../api');
        const data = await api('/chatbots');
        setChatbots(data || []);
      } catch (err) {
        console.error("Failed to fetch chatbots:", err);
      }
    };
    fetchChatbots();
  }, [location.pathname]);

  const switchChatbot = (id) => {
    // Navigate to chat with this chatbot
    navigate(`/chat?chatbot_id=${id}`);
  };

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: '#050816' }}>
      {/* Sidebar */}
      <div style={{
        width: '280px',
        display: 'flex',
        flexDirection: 'column',
        borderRight: '1px solid rgba(255,255,255,0.08)',
        background: 'rgba(5, 8, 22, 0.92)',
        backdropFilter: 'blur(20px)',
        flexShrink: 0,
      }}>
        {/* Logo & New Chatbot */}
        <div style={{ padding: '24px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '32px' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'linear-gradient(135deg, #00C6FF, #0072FF)', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 15px rgba(0,198,255,0.4)' }}>
              <Zap size={18} color="#050816" />
            </div>
            <span style={{ fontSize: '18px', fontWeight: 800, letterSpacing: '-0.02em', background: 'linear-gradient(to right, #fff, #94a3b8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>TiO Builder</span>
          </div>

          <button 
            onClick={() => navigate('/create')}
            style={{ 
              width: '100%', 
              padding: '12px', 
              borderRadius: '12px', 
              background: 'linear-gradient(135deg, rgba(0,198,255,0.1) 0%, rgba(0,114,255,0.1) 100%)',
              border: '1px solid rgba(0,198,255,0.3)',
              color: '#00C6FF',
              fontWeight: 600,
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
              cursor: 'pointer',
              transition: 'all 0.3s ease',
              boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
            }}
          >
            <Plus size={16} /> Create New Chatbot
          </button>
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '0 12px 20px', overflowY: 'auto' }} className="custom-scrollbar">
          <p style={{ paddingLeft: '12px', fontSize: '11px', fontWeight: 700, color: '#64748b', letterSpacing: '0.1em', marginBottom: '12px', textTransform: 'uppercase' }}>Builder Platform</p>
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link key={item.path} to={item.path} style={{ textDecoration: 'none', display: 'block', marginBottom: '2px' }}>
                <motion.div
                  whileHover={{ x: 3 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 30 }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '10px 16px',
                    borderRadius: '10px',
                    background: isActive ? 'rgba(0,198,255,0.08)' : 'transparent',
                    color: isActive ? '#00C6FF' : '#64748b',
                    fontWeight: isActive ? 600 : 500,
                    fontSize: '14px',
                    transition: 'all 0.2s ease',
                    border: `1px solid ${isActive ? 'rgba(0,198,255,0.15)' : 'transparent'}`,
                  }}
                >
                  <Icon size={18} style={{ opacity: isActive ? 1 : 0.7 }} />
                  {item.label}
                </motion.div>
              </Link>
            );
          })}

          <div style={{ marginTop: '24px' }}>
            <p style={{ paddingLeft: '12px', fontSize: '11px', fontWeight: 700, color: '#64748b', letterSpacing: '0.1em', marginBottom: '12px', textTransform: 'uppercase' }}>My Chatbots</p>
            {chatbots.length === 0 ? (
               <p style={{ paddingLeft: '12px', fontSize: '12px', color: 'rgba(255,255,255,0.2)' }}>No chatbots built yet</p>
            ) : (
              chatbots.map((cb) => (
                <div 
                  key={cb.id} 
                  onClick={() => switchChatbot(cb.id)}
                  style={{ 
                    padding: '8px 16px', 
                    borderRadius: '8px', 
                    cursor: 'pointer', 
                    fontSize: '13px', 
                    color: '#94a3b8',
                    background: 'transparent',
                    marginBottom: '2px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    transition: 'all 0.2s'
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.03)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                >
                  <Bot size={14} opacity={0.5} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {cb.name}
                  </span>
                </div>
              ))
            )}
          </div>
        </nav>

        {/* Status & User */}
        <div style={{ padding: '16px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', padding: '8px 12px', background: 'rgba(16,185,129,0.06)', borderRadius: '8px', border: '1px solid rgba(16,185,129,0.15)' }}>
            <div style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#10B981', boxShadow: '0 0 8px #10B981' }} />
            <span style={{ fontSize: '11px', color: '#10B981', fontWeight: 600 }}>TiO Engine Online</span>
          </div>

          <div style={{ background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '12px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: '50%', flexShrink: 0,
              background: 'linear-gradient(135deg, #00C6FF, #0072FF)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#050816', fontWeight: 700, fontSize: '13px',
            }}>
              {user?.username?.slice(0, 2).toUpperCase() || 'U?'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontWeight: 600, fontSize: '13px', color: '#fff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user?.username || 'Guest'}
              </p>
              <p style={{ fontSize: '11px', color: '#64748b' }}>
                {user?.role || 'Builder'}
              </p>
            </div>
            <button
              onClick={logout}
              style={{ padding: '7px', borderRadius: '8px', background: 'transparent', border: 'none', cursor: 'pointer', color: '#64748b' }}
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main style={{ flex: 1, overflowY: 'auto', position: 'relative' }}>
        {children}
      </main>
    </div>
  );
}
