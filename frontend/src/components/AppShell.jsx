import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Home, Plus, MessageSquare, FileText,
  Shield, Settings, Zap, LogOut, Bot,
  Sun, Moon, Menu, X, ChevronRight
} from 'lucide-react';
import { useAppCtx } from '../context/AppContext';

const NAV_ITEMS = [
  { icon: Home, label: 'Home', path: '/' },
  { icon: Plus, label: 'Create Chatbot', path: '/create' },
  { icon: MessageSquare, label: 'Chats', path: '/chat' },
  { icon: FileText, label: 'Files', path: '/files' },
];

const BOTTOM_ITEMS = [
  { icon: Shield, label: 'Admin', path: '/admin' },
  { icon: Settings, label: 'Settings', path: '/settings' },
];

export default function AppShell({ children }) {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, theme, toggleTheme } = useAppCtx();
  const [chatbots, setChatbots] = useState([]);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    const fetchChatbots = async () => {
      try {
        const { api } = await import('../api');
        const data = await api('/chatbots');
        setChatbots(data || []);
      } catch (err) { /* silent */ }
    };
    fetchChatbots();
  }, [location.pathname]);

  // Auto-collapse on medium screens
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1024px)');
    const handler = (e) => setCollapsed(e.matches);
    handler(mq);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  const isAuth = location.pathname === '/login' || location.pathname === '/register';
  if (isAuth) return <>{children}</>;

  const sidebarWidth = collapsed ? 72 : 260;

  const renderNavItem = (item, isActive) => {
    const Icon = item.icon;
    return (
      <Link key={item.path} to={item.path} style={{ textDecoration: 'none', display: 'block', marginBottom: '2px' }} onClick={() => setMobileOpen(false)}>
        <motion.div
          whileHover={{ x: collapsed ? 0 : 3 }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          title={collapsed ? item.label : undefined}
          style={{
            display: 'flex', alignItems: 'center', gap: '12px',
            padding: collapsed ? '10px' : '10px 14px',
            justifyContent: collapsed ? 'center' : 'flex-start',
            borderRadius: 'var(--radius-sm)',
            background: isActive ? 'rgba(0,198,255,0.08)' : 'transparent',
            color: isActive ? 'var(--accent)' : 'var(--text-muted)',
            fontWeight: isActive ? 600 : 500, fontSize: '14px',
            transition: 'all 0.15s ease',
            borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent',
          }}
        >
          <Icon size={18} style={{ opacity: isActive ? 1 : 0.65, flexShrink: 0 }} />
          {!collapsed && item.label}
        </motion.div>
      </Link>
    );
  };

  const sidebarContent = (
    <>
      {/* Logo */}
      <div style={{ padding: collapsed ? '20px 12px' : '20px', display: 'flex', alignItems: 'center', gap: '10px', justifyContent: collapsed ? 'center' : 'flex-start' }}>
        <div style={{
          width: '32px', height: '32px', borderRadius: '8px', flexShrink: 0,
          background: 'linear-gradient(135deg, #00C6FF, #0072FF)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 0 12px rgba(0,198,255,0.3)'
        }}>
          <Zap size={16} color="#050816" />
        </div>
        {!collapsed && (
          <span style={{ fontSize: '17px', fontWeight: 800, letterSpacing: '-0.02em', color: '#fff' }}>TiO</span>
        )}
      </div>

      {/* New Chatbot Button */}
      <div style={{ padding: collapsed ? '0 8px 16px' : '0 16px 16px' }}>
        <button
          onClick={() => { navigate('/create'); setMobileOpen(false); }}
          className="btn btn-primary btn-sm"
          style={{ width: '100%', justifyContent: 'center', fontSize: collapsed ? '0' : '13px', padding: collapsed ? '10px' : undefined }}
        >
          <Plus size={16} />
          {!collapsed && 'New Chatbot'}
        </button>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, padding: collapsed ? '0 8px' : '0 12px', overflowY: 'auto' }} className="custom-scrollbar">
        {!collapsed && (
          <p style={{ padding: '0 6px', fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.12em', marginBottom: '8px', textTransform: 'uppercase' }}>
            Platform
          </p>
        )}
        {NAV_ITEMS.map(item => renderNavItem(item, location.pathname === item.path))}

        {/* Chatbot List */}
        <div style={{ marginTop: '20px' }}>
          {!collapsed && (
            <p style={{ padding: '0 6px', fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.12em', marginBottom: '8px', textTransform: 'uppercase' }}>
              My Chatbots
            </p>
          )}
          {chatbots.length === 0 ? (
            !collapsed && <p style={{ padding: '0 6px', fontSize: '12px', color: 'var(--text-dim)' }}>No chatbots yet</p>
          ) : (
            chatbots.map(cb => (
              <div
                key={cb.id}
                onClick={() => { navigate(`/chat?chatbot_id=${cb.id}`); setMobileOpen(false); }}
                title={collapsed ? cb.name : undefined}
                style={{
                  padding: collapsed ? '8px' : '7px 10px',
                  borderRadius: '6px', cursor: 'pointer',
                  fontSize: '13px', color: 'var(--text-secondary)',
                  display: 'flex', alignItems: 'center', gap: '8px',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  marginBottom: '1px', transition: 'background 0.15s'
                }}
                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
              >
                <Bot size={14} style={{ opacity: 0.5, flexShrink: 0 }} />
                {!collapsed && (
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{cb.name}</span>
                )}
              </div>
            ))
          )}
        </div>
      </nav>

      {/* Bottom Section */}
      <div style={{ borderTop: '1px solid var(--border-light)', padding: collapsed ? '12px 8px' : '12px 12px' }}>
        {BOTTOM_ITEMS.map(item => renderNavItem(item, location.pathname === item.path))}

        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          title={collapsed ? 'Toggle Theme' : undefined}
          style={{
            width: '100%', padding: collapsed ? '10px' : '8px 14px', marginTop: '4px',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--bg-hover)', border: '1px solid var(--border-light)',
            color: 'var(--text-secondary)', display: 'flex', alignItems: 'center',
            justifyContent: collapsed ? 'center' : 'flex-start',
            gap: '10px', fontSize: '12px', fontWeight: 500
          }}
        >
          {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
          {!collapsed && (theme === 'dark' ? 'Light Mode' : 'Dark Mode')}
        </button>

        {/* User Card */}
        {user && (
          <div style={{
            marginTop: '10px', padding: collapsed ? '8px' : '10px',
            borderRadius: 'var(--radius-sm)', background: 'var(--bg-hover)',
            display: 'flex', alignItems: 'center', gap: '10px',
            justifyContent: collapsed ? 'center' : 'flex-start'
          }}>
            <div style={{
              width: '30px', height: '30px', borderRadius: '50%', flexShrink: 0,
              background: 'linear-gradient(135deg, #00C6FF, #0072FF)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#050816', fontWeight: 700, fontSize: '11px'
            }}>
              {user.username?.slice(0, 2).toUpperCase()}
            </div>
            {!collapsed && (
              <>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontWeight: 600, fontSize: '12px', color: '#fff', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user.username}</p>
                  <p style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{user.role || 'Builder'}</p>
                </div>
                <button onClick={logout} style={{ padding: '4px', color: 'var(--text-muted)' }}><LogOut size={14} /></button>
              </>
            )}
          </div>
        )}
      </div>
    </>
  );

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      {/* Mobile hamburger */}
      <button
        className="hide-desktop"
        onClick={() => setMobileOpen(true)}
        style={{
          position: 'fixed', top: '16px', left: '16px', zIndex: 60,
          width: '40px', height: '40px', borderRadius: 'var(--radius-sm)',
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          display: 'none', alignItems: 'center', justifyContent: 'center', color: '#fff'
        }}
      >
        <Menu size={20} />
      </button>

      {/* Desktop Sidebar */}
      <div className="hide-mobile" style={{
        width: `${sidebarWidth}px`, display: 'flex', flexDirection: 'column',
        borderRight: '1px solid var(--border-light)', background: 'var(--bg-secondary)',
        flexShrink: 0, transition: 'width 0.2s ease', overflow: 'hidden'
      }}>
        {sidebarContent}
      </div>

      {/* Mobile Drawer */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
              style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 70 }}
            />
            <motion.div
              initial={{ x: -280 }} animate={{ x: 0 }} exit={{ x: -280 }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              style={{
                position: 'fixed', top: 0, left: 0, bottom: 0, width: '280px',
                background: 'var(--bg-secondary)', zIndex: 80,
                display: 'flex', flexDirection: 'column',
                borderRight: '1px solid var(--border)'
              }}
            >
              <button
                onClick={() => setMobileOpen(false)}
                style={{ position: 'absolute', top: '16px', right: '16px', color: 'var(--text-muted)', padding: '4px' }}
              >
                <X size={20} />
              </button>
              {sidebarContent}
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Main Content */}
      <main style={{ flex: 1, overflowY: 'auto', position: 'relative' }} className="custom-scrollbar">
        {children}
      </main>
    </div>
  );
}
