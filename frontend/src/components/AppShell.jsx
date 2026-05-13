import { useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Home, Plus, MessageSquare, FileText,
  Shield, Settings, Zap, LogOut, Bot,
  Sun, Moon, Menu, X, ChevronRight, Layers, Activity
} from 'lucide-react';
import { useAppCtx } from '../context/AppContext';

const NAV_ITEMS = [
  { icon: Home, label: 'Dashboard', path: '/' },
  { icon: MessageSquare, label: 'Neural Chat', path: '/chat' },
  { icon: Layers, label: 'Knowledge Base', path: '/files' },
  { icon: Plus, label: 'Deploy Core', path: '/create' },
];

const BOTTOM_ITEMS = [
  { icon: Shield, label: 'Command Center', path: '/admin' },
  { icon: Settings, label: 'Configuration', path: '/settings' },
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

  const isAuth = location.pathname === '/login' || location.pathname === '/register';
  const isChat = location.pathname === '/chat';

  // For /chat, we use a more integrated layout, so we might want a thinner sidebar or hide it
  const sidebarWidth = collapsed ? 80 : 280;

  if (isAuth) return <>{children}</>;

  const renderNavItem = (item, isActive) => {
    const Icon = item.icon;
    return (
      <Link key={item.path} to={item.path} style={{ textDecoration: 'none', display: 'block', marginBottom: '4px' }} onClick={() => setMobileOpen(false)}>
        <motion.div
          whileHover={{ x: collapsed ? 0 : 4, background: 'rgba(255,255,255,0.03)' }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          style={{
            display: 'flex', alignItems: 'center', gap: '14px',
            padding: collapsed ? '12px' : '12px 16px',
            justifyContent: collapsed ? 'center' : 'flex-start',
            borderRadius: '16px',
            background: isActive ? 'var(--accent-gradient)' : 'transparent',
            color: isActive ? '#03050c' : 'var(--text-secondary)',
            fontWeight: isActive ? 700 : 500, fontSize: '14px',
            transition: 'all 0.2s ease',
            boxShadow: isActive ? '0 8px 20px rgba(0,198,255,0.2)' : 'none'
          }}
        >
          <Icon size={20} style={{ flexShrink: 0 }} />
          {!collapsed && <span>{item.label}</span>}
        </motion.div>
      </Link>
    );
  };

  const sidebarContent = (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', padding: '24px 16px' }}>
      {/* Brand */}
      <div style={{ padding: '0 8px', marginBottom: '40px', display: 'flex', alignItems: 'center', gap: '14px', justifyContent: collapsed ? 'center' : 'flex-start' }}>
        <div style={{
          width: '40px', height: '40px', borderRadius: '12px', flexShrink: 0,
          background: 'var(--premium-gradient)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: '0 10px 25px rgba(0,198,255,0.3)'
        }}>
          <Zap size={20} color="#03050c" />
        </div>
        {!collapsed && (
          <span className="text-premium" style={{ fontSize: '24px', fontWeight: 900, letterSpacing: '-0.03em' }}>TiO</span>
        )}
      </div>

      {/* Navigation Groups */}
      <nav style={{ flex: 1, overflowY: 'auto' }} className="custom-scrollbar">
        {!collapsed && (
          <p style={{ padding: '0 16px', fontSize: '11px', fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.15em', marginBottom: '16px', textTransform: 'uppercase' }}>
            System Core
          </p>
        )}
        {NAV_ITEMS.map(item => renderNavItem(item, location.pathname === item.path))}

        <div style={{ marginTop: '40px' }}>
          {!collapsed && (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 16px', marginBottom: '16px' }}>
               <p style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-dim)', letterSpacing: '0.15em', textTransform: 'uppercase' }}>Intelligence</p>
               <Activity size={12} color="var(--text-dim)" />
            </div>
          )}
          {chatbots.slice(0, 5).map(cb => (
            <div
              key={cb.id}
              onClick={() => { navigate(`/chat?chatbot_id=${cb.id}`); setMobileOpen(false); }}
              className="nav-link"
              style={{
                padding: collapsed ? '12px' : '10px 16px',
                borderRadius: '12px', cursor: 'pointer',
                fontSize: '13px', color: 'var(--text-muted)',
                display: 'flex', alignItems: 'center', gap: '12px',
                justifyContent: collapsed ? 'center' : 'flex-start',
                marginBottom: '2px', transition: 'all 0.2s'
              }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; e.currentTarget.style.color = '#fff'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-muted)'; }}
            >
              <Bot size={16} style={{ opacity: 0.5, flexShrink: 0 }} />
              {!collapsed && (
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 500 }}>{cb.name}</span>
              )}
            </div>
          ))}
        </div>
      </nav>

      {/* Footer Tools */}
      <div style={{ marginTop: 'auto', paddingTop: '24px', borderTop: '1px solid var(--border)' }}>
        {/* Theme Toggle */}
        <button
          onClick={toggleTheme}
          className="nav-link"
          style={{
            width: '100%', padding: collapsed ? '12px' : '12px 16px',
            borderRadius: '16px', display: 'flex', alignItems: 'center', gap: '14px',
            justifyContent: collapsed ? 'center' : 'flex-start',
            color: 'var(--text-secondary)', background: 'transparent', border: 'none',
            cursor: 'pointer', marginBottom: '8px'
          }}
        >
          {theme === 'dark' ? <Sun size={20} /> : <Moon size={20} />}
          {!collapsed && <span>{theme === 'dark' ? 'Light Mode' : 'Dark Mode'}</span>}
        </button>

        {BOTTOM_ITEMS.filter(item => item.label !== 'Command Center' || user?.role === 'admin').map(item => renderNavItem(item, location.pathname === item.path))}

        <div style={{
          marginTop: '20px', padding: collapsed ? '12px' : '16px',
          borderRadius: '20px', background: 'var(--bg-accent)',
          border: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', gap: '12px',
          justifyContent: collapsed ? 'center' : 'flex-start'
        }}>
          <div style={{
            width: '36px', height: '36px', borderRadius: '12px', flexShrink: 0,
            background: 'var(--accent-gradient)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#03050c', fontWeight: 800, fontSize: '13px'
          }}>
            {user?.username?.slice(0, 1).toUpperCase()}
          </div>
          {!collapsed && (
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user?.username}</p>
              <button onClick={logout} style={{ fontSize: '11px', color: 'var(--accent)', fontWeight: 600, background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}>Disconnect</button>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      {/* Mobile Trigger */}
      <button
        className="hide-desktop"
        onClick={() => setMobileOpen(true)}
        style={{
          position: 'fixed', top: '24px', left: '24px', zIndex: 60,
          width: '44px', height: '44px', borderRadius: '14px',
          background: 'rgba(255,255,255,0.05)', backdropFilter: 'blur(10px)',
          border: '1px solid rgba(255,255,255,0.1)',
          display: 'none', alignItems: 'center', justifyContent: 'center', color: '#fff'
        }}
      >
        <Menu size={20} />
      </button>

      {/* Desktop Navigation */}
      <motion.div 
        className="hide-mobile" 
        animate={{ width: sidebarWidth }}
        style={{
          display: 'flex', flexDirection: 'column',
          borderRight: '1px solid var(--border)', background: 'var(--bg-secondary)',
          flexShrink: 0, overflow: 'hidden', zIndex: 50
        }}
      >
        {sidebarContent}
      </motion.div>

      {/* Mobile Overlay */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            <motion.div
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
              onClick={() => setMobileOpen(false)}
              style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(8px)', zIndex: 70 }}
            />
            <motion.div
              initial={{ x: -300 }} animate={{ x: 0 }} exit={{ x: -300 }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              style={{
                position: 'fixed', top: 0, left: 0, bottom: 0, width: '300px',
                background: 'var(--bg-secondary)', zIndex: 80,
                display: 'flex', flexDirection: 'column',
                borderRight: '1px solid var(--border)'
              }}
            >
              <button
                onClick={() => setMobileOpen(false)}
                style={{ position: 'absolute', top: '24px', right: '24px', color: 'var(--text-muted)', padding: '8px' }}
              >
                <X size={24} />
              </button>
              {sidebarContent}
            </motion.div>
          </>
        )}
      </AnimatePresence>

      {/* Primary Content Plane */}
      <main style={{ flex: 1, overflowY: 'auto', position: 'relative' }} className="custom-scrollbar">
        {children}
      </main>
    </div>
  );
}
