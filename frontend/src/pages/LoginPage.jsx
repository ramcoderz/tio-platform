import { useState } from 'react';
import { motion } from 'framer-motion';
import { Link, useNavigate } from 'react-router-dom';
import { useAppCtx } from '../context/AppContext';
import { LogIn, Eye, EyeOff, Zap, Shield } from 'lucide-react';
import { api } from '../api';
import { useChatStore } from '../store';

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { setUser } = useAppCtx();
  const { setSessionFromUser } = useChatStore();
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { access_token, user: loggedUser } = await api('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ username, password })
      });

      localStorage.setItem('token', access_token);
      localStorage.setItem('tio_user_id', loggedUser.id);
      setUser(loggedUser);
      setSessionFromUser(loggedUser.id);
      navigate('/');
    } catch (err) {
      setError(err.message || 'Connection error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'var(--bg-primary)',
      padding: '24px',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Decorative blurred backgrounds */}
      <div style={{ position: 'absolute', top: '10%', left: '10%', width: '400px', height: '400px', background: 'radial-gradient(circle, rgba(0, 198, 255, 0.1) 0%, transparent 70%)', filter: 'blur(60px)', zIndex: 1 }} />
      <div style={{ position: 'absolute', bottom: '10%', right: '10%', width: '500px', height: '500px', background: 'radial-gradient(circle, rgba(124, 58, 237, 0.08) 0%, transparent 70%)', filter: 'blur(60px)', zIndex: 1 }} />

      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="glass-panel"
        style={{ 
          width: '100%', 
          maxWidth: '440px', 
          padding: '48px', 
          position: 'relative', 
          zIndex: 10,
          borderRadius: '28px',
          border: '1px solid rgba(255,255,255,0.1)',
          boxShadow: '0 30px 100px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05)'
        }}
      >
        {/* Branding */}
        <div style={{ textAlign: 'center', marginBottom: '40px' }}>
          <div className="flex-center" style={{ marginBottom: '20px' }}>
            <div className="glass-panel" style={{ width: '56px', height: '56px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '16px', boxShadow: '0 10px 30px rgba(0,198,255,0.2)' }}>
              <Zap size={28} color="var(--accent)" />
            </div>
          </div>
          <h1 className="text-premium" style={{ fontSize: '32px', fontWeight: 800, marginBottom: '8px' }}>Access Core</h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '15px' }}>Enter your credentials to synchronize.</p>
        </div>

        <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="form-group">
            <label className="form-label" style={{ marginBottom: '8px' }}>Identity</label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              placeholder="Username"
              required
              className="input"
              style={{ background: 'rgba(255,255,255,0.03)' }}
            />
          </div>

          <div className="form-group">
            <label className="form-label" style={{ marginBottom: '8px' }}>Security Key</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPass ? 'text' : 'password'}
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="input"
                style={{ paddingRight: '48px', background: 'rgba(255,255,255,0.03)' }}
              />
              <button
                type="button"
                onClick={() => setShowPass(p => !p)}
                style={{
                  position: 'absolute', right: '14px', top: '50%', transform: 'translateY(-50%)',
                  color: 'var(--text-muted)', padding: '4px'
                }}
              >
                {showPass ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </div>

          {error && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              style={{
                padding: '12px 16px', borderRadius: '12px',
                background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)',
                color: '#F87171', fontSize: '13px',
              }}
            >
              {error}
            </motion.div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary"
            style={{ 
              marginTop: '12px', 
              height: '52px', 
              fontSize: '15px',
              borderRadius: '14px',
              opacity: loading ? 0.7 : 1
            }}
          >
            {loading ? 'Synchronizing...' : (
              <>
                <Shield size={18} />
                <span>Initialize Session</span>
              </>
            )}
          </button>
        </form>

        <div style={{ marginTop: '32px', textAlign: 'center' }}>
          <p style={{ fontSize: '14px', color: 'var(--text-muted)' }}>
            New to the ecosystem?{' '}
            <Link to="/register" style={{ color: 'var(--accent)', fontWeight: 600, marginLeft: '4px' }}>
              Create Account
            </Link>
          </p>
        </div>
      </motion.div>

      {/* Footer Branding */}
      <div style={{ position: 'absolute', bottom: '32px', opacity: 0.3, letterSpacing: '0.2em', fontSize: '10px', fontWeight: 600 }}>
        TIO INTELLIGENCE PLATFORM v2.0
      </div>
    </div>
  );
}
