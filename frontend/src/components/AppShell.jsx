import { useState, useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Home, BarChart3, Upload, MessageSquare, ListTodo, Layout, Plus,
  Brain, Settings, Shield, LogOut, Zap, Layers, Network
} from 'lucide-react';
import { useAppCtx } from '../context/AppContext';
import { useChatStore } from '../store';
import { useNavigate } from 'react-router-dom';

const navItems = [
  { icon: Home, label: 'Home', path: '/' },
  { icon: Upload, label: 'Add Files', path: '/upload' },
  { icon: Layout, label: 'Projects', path: '/projects' },
  { icon: MessageSquare, label: 'Chat', path: '/chat' },
  { icon: ListTodo, label: 'Tasks', path: '/tasks' },
  { icon: Layers, label: 'Memory', path: '/memory' },
  { icon: Settings, label: 'Admin', path: '/admin' },
];

export default function AppShell({ children }) {
  const location = useLocation();
  const { user, logout } = useAppCtx();
  const navigate = useNavigate();
  const { sessionId, setSessionId, clearSession } = useChatStore();

  const handleNewSession = () => {
    clearSession();
    navigate('/chat');
  };
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    const fetchSessions = async () => {
      try {
        const { api } = await import('../api');
        const data = await api('/chat/sessions');
        setSessions(data || []);
      } catch (err) {
        console.error("Failed to fetch sessions:", err);
      }
    };
    fetchSessions();
  }, [sessionId]);

  const switchSession = (id) => {
    setSessionId(id);
    localStorage.setItem("tio_session_id", id);
    navigate('/chat');
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
        {/* Logo & New Chat */}
        <div style={{ padding: '24px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '32px' }}>
            <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 15px rgba(37,99,235,0.4)' }}>
              <Zap size={18} color="#050816" />
            </div>
            <span style={{ fontSize: '18px', fontWeight: 800, letterSpacing: '-0.02em', background: 'linear-gradient(to right, #fff, #94a3b8)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>TiO Intelligence</span>
          </div>

          <button 
            onClick={handleNewSession}
            style={{ 
              width: '100%', 
              padding: '12px', 
              borderRadius: '12px', 
              background: 'linear-gradient(135deg, rgba(37,99,235,0.1) 0%, rgba(6,182,212,0.1) 100%)',
              border: '1px solid rgba(37,99,235,0.3)',
              color: 'var(--accent-blue-light)',
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
            <Plus size={16} /> New Intelligence Session
          </button>
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, padding: '0 12px 20px', overflowY: 'auto' }} className="custom-scrollbar">
          <p style={{ paddingLeft: '12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: '12px', textTransform: 'uppercase' }}>Workspace</p>
          {navItems.filter(item => {
            if ((item.path === '/admin' || item.path === '/audit') && user?.role !== 'admin') {
              return false;
            }
            return true;
          }).map((item) => {
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
                    background: isActive ? 'rgba(37,99,235,0.08)' : 'transparent',
                    color: isActive ? 'var(--accent-blue-light)' : '#64748b',
                    fontWeight: isActive ? 600 : 500,
                    fontSize: '14px',
                    transition: 'all 0.2s ease',
                    border: `1px solid ${isActive ? 'rgba(37,99,235,0.15)' : 'transparent'}`,
                  }}
                >
                  <Icon size={18} style={{ opacity: isActive ? 1 : 0.7 }} />
                  {item.label}
                </motion.div>
              </Link>
            );
          })}

          <div style={{ marginTop: '24px' }}>
            <p style={{ paddingLeft: '12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', letterSpacing: '0.1em', marginBottom: '12px', textTransform: 'uppercase' }}>Recent Sessions</p>
            {sessions.length === 0 ? (
               <p style={{ paddingLeft: '12px', fontSize: '12px', color: 'rgba(255,255,255,0.2)' }}>No history yet</p>
            ) : (
              sessions.slice(0, 10).map((s) => (
                <div 
                  key={s.session_id} 
                  onClick={() => switchSession(s.session_id)}
                  style={{ 
                    padding: '8px 16px', 
                    borderRadius: '8px', 
                    cursor: 'pointer', 
                    fontSize: '13px', 
                    color: s.session_id === sessionId ? 'var(--accent-cyan)' : '#94a3b8',
                    background: s.session_id === sessionId ? 'rgba(6,182,212,0.08)' : 'transparent',
                    marginBottom: '2px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    transition: 'all 0.2s'
                  }}
                >
                  <MessageSquare size={14} opacity={0.5} />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {s.session_id.slice(0, 12)}...
                  </span>
                </div>
              ))
            )}
          </div>
        </nav>

        {/* Status & User */}
        <div style={{ padding: '16px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
          {/* Online Status */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px', padding: '8px 12px', background: 'rgba(16,185,129,0.06)', borderRadius: '8px', border: '1px solid rgba(16,185,129,0.15)' }}>
            <div style={{ width: '7px', height: '7px', borderRadius: '50%', background: '#10B981', boxShadow: '0 0 8px #10B981', animation: 'pulse-green 2s infinite' }} />
            <span style={{ fontSize: '11px', color: '#10B981', fontWeight: 600, letterSpacing: '0.04em' }}>TiO Online · Model Ready</span>
          </div>

          {/* User Card */}
          <div className="glass-panel" style={{ padding: '12px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: '50%', flexShrink: 0,
              background: 'linear-gradient(135deg, #7C3AED, #00E5FF)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#fff', fontWeight: 700, fontSize: '13px',
            }}>
              {user?.username?.slice(0, 2).toUpperCase() || 'U?'}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {user?.username || 'Guest'}
              </p>
              <p style={{ fontSize: '11px', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                {user?.role || 'Operator'}
              </p>
            </div>
            <button
              onClick={logout}
              title="Logout"
              style={{ padding: '7px', borderRadius: '8px', background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', transition: 'all 0.15s ease' }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(239,68,68,0.15)'; e.currentTarget.style.color = '#EF4444'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-secondary)'; }}
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main style={{ flex: 1, overflowY: 'auto', position: 'relative' }} className="custom-scrollbar">
        {children}
      </main>
    </div>
  );
}
