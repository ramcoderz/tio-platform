import { useState, useEffect } from 'react';
import { User, Shield, Moon, Sun, Key, Zap, Trash2, AlertTriangle, RefreshCw } from 'lucide-react';
import { useAppCtx } from '../context/AppContext';
import { api } from '../api';
import { motion, AnimatePresence } from 'framer-motion';

export default function SettingsPage() {
  const { user, setUser, theme, toggleTheme, logout } = useAppCtx();
  const [isDeleting, setIsDeleting] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const [preferences, setPreferences] = useState({
    private_inference: user?.private_inference || false,
    email: user?.email || '',
    username: user?.username || '',
  });

  useEffect(() => {
    if (user) {
      setPreferences({
        private_inference: !!user.private_inference,
        email: user.email || '',
        username: user.username || '',
      });
    }
  }, [user]);

  const updatePreference = async (key, val) => {
    const next = { ...preferences, [key]: val };
    setPreferences(next);
    setIsSaving(true);
    try {
      const updated = await api('/auth/me', {
        method: 'PUT',
        body: JSON.stringify({ [key]: val })
      });
      setUser(updated);
    } catch (err) {
      console.error('Failed to update preference', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteAccount = async () => {
    setIsDeleting(true);
    try {
      await api('/auth/me', { method: 'DELETE' });
      logout();
    } catch (err) {
      alert('Failed to delete account. Please try again.');
    } finally {
      setIsDeleting(false);
      setShowConfirm(false);
    }
  };

  return (
    <div style={{ padding: '32px 40px', maxWidth: '800px', margin: '0 auto' }}>
      <header style={{ marginBottom: '36px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '6px' }}>Settings</h1>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Manage your profile and platform preferences.</p>
        </div>
        {isSaving && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent)', fontSize: '12px', fontWeight: 600 }}>
             <RefreshCw size={14} className="animate-spin" /> Saving...
          </div>
        )}
      </header>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

        {/* Profile Section */}
        <section className="glass-panel" style={{ padding: '28px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
            <div style={{
              width: '64px', height: '64px', borderRadius: '16px',
              background: 'linear-gradient(135deg, #00C6FF, #0072FF)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '24px', fontWeight: 800, color: '#050816',
              boxShadow: '0 8px 24px rgba(0,198,255,0.2)'
            }}>
              {user?.username?.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <h3 style={{ fontSize: '18px', fontWeight: 700 }}>{user?.username}</h3>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{user?.role === 'admin' ? 'System Administrator' : 'TiO Builder'}</p>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>Username</label>
              <input 
                className="input" 
                value={preferences.username} 
                onChange={(e) => setPreferences({...preferences, username: e.target.value})}
                onBlur={(e) => updatePreference('username', e.target.value)}
                placeholder="Choose a username"
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>Email Address</label>
              <input 
                className="input" 
                value={preferences.email} 
                onChange={(e) => setPreferences({...preferences, email: e.target.value})}
                onBlur={(e) => updatePreference('email', e.target.value)}
                placeholder="Enter your email"
              />
            </div>
          </div>
        </section>

        {/* Builder Preferences */}
        <section className="glass-panel" style={{ padding: '28px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '24px' }}>
            <Zap size={18} color="var(--accent)" />
            <h3 style={{ fontSize: '16px', fontWeight: 700 }}>Preferences</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <Toggle 
              icon={theme === 'dark' ? Moon : Sun} 
              label="Dark Mode" 
              desc="High-contrast theme for focused building." 
              active={theme === 'dark'} 
              onToggle={toggleTheme} 
            />
            <Toggle 
              icon={Shield} 
              label="Private Inference" 
              desc="Use local Ollama models instead of cloud APIs." 
              active={preferences.private_inference} 
              onToggle={() => updatePreference('private_inference', !preferences.private_inference)}
            />
          </div>
        </section>

        {/* Danger Zone */}
        <section className="glass-panel" style={{ padding: '28px', border: '1px solid rgba(239,68,68,0.2)', background: 'rgba(239,68,68,0.02)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
            <AlertTriangle size={18} color="#F87171" />
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: '#F87171' }}>Danger Zone</h3>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>
            Deleting your account will permanently remove all your chatbots, indexed documents, and message history. This action is irreversible.
          </p>
          <button 
            onClick={() => setShowConfirm(true)}
            className="btn btn-danger btn-sm"
            style={{ padding: '10px 16px' }}
          >
            <Trash2 size={14} /> Delete My Account
          </button>
        </section>
      </div>

      {/* Confirmation Modal */}
      <AnimatePresence>
        {showConfirm && (
          <div className="modal-backdrop" onClick={() => setShowConfirm(false)}>
            <motion.div 
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="modal-card" 
              onClick={e => e.stopPropagation()}
              style={{ maxWidth: '440px' }}
            >
              <div style={{ display: 'flex', gap: '16px', marginBottom: '20px' }}>
                <div style={{ 
                  width: '40px', height: '40px', borderRadius: '10px', background: 'rgba(239,68,68,0.1)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  <AlertTriangle size={20} color="#EF4444" />
                </div>
                <div>
                  <h3 className="modal-title" style={{ fontSize: '18px' }}>Permanently Delete Account?</h3>
                  <p className="modal-body" style={{ marginTop: '6px' }}>
                    Are you sure? This will purge all your data from the TiO platform immediately. You cannot undo this.
                  </p>
                </div>
              </div>
              <div className="modal-actions">
                <button 
                  onClick={() => setShowConfirm(false)} 
                  className="btn btn-ghost"
                  disabled={isDeleting}
                >
                  Cancel
                </button>
                <button 
                  onClick={handleDeleteAccount}
                  className="btn btn-danger"
                  style={{ gap: '8px' }}
                  disabled={isDeleting}
                >
                  {isDeleting ? <RefreshCw size={14} className="animate-spin" /> : <Trash2 size={14} />}
                  Delete Permanently
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

function Toggle({ icon: Icon, label, desc, active, onToggle }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div style={{
          width: '40px', height: '40px', borderRadius: '12px',
          background: 'rgba(255,255,255,0.03)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: active ? 'var(--accent)' : 'var(--text-muted)',
          transition: 'all 0.2s'
        }}>
          <Icon size={18} />
        </div>
        <div>
          <p style={{ fontSize: '14px', fontWeight: 600 }}>{label}</p>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>{desc}</p>
        </div>
      </div>
      <div
        onClick={onToggle}
        style={{
          width: '44px', height: '24px', borderRadius: '12px',
          background: active ? 'var(--accent)' : 'rgba(255,255,255,0.08)',
          position: 'relative', cursor: onToggle ? 'pointer' : 'default',
          transition: 'all 0.2s', flexShrink: 0,
          border: active ? 'none' : '1px solid rgba(255,255,255,0.1)'
        }}
      >
        <motion.div 
          animate={{ x: active ? 22 : 3 }}
          style={{
            width: '18px', height: '18px', borderRadius: '50%',
            background: active ? '#050816' : 'rgba(255,255,255,0.4)',
            position: 'absolute', top: '2px',
          }} 
        />
      </div>
    </div>
  );
}
