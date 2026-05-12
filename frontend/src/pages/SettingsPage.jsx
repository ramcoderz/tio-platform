import { useState } from 'react';
import { User, Shield, Moon, Sun, Key, Zap } from 'lucide-react';
import { useAppCtx } from '../context/AppContext';

export default function SettingsPage() {
  const { user, theme, toggleTheme } = useAppCtx();

  return (
    <div style={{ padding: '32px 40px', maxWidth: '800px', margin: '0 auto' }}>
      <div style={{ marginBottom: '36px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '6px' }}>Settings</h1>
        <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Account and builder preferences.</p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>

        {/* Profile */}
        <section className="glass-panel" style={{ padding: '28px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '24px' }}>
            <div style={{
              width: '52px', height: '52px', borderRadius: '50%',
              background: 'linear-gradient(135deg, #00C6FF, #0072FF)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '20px', fontWeight: 800, color: '#050816'
            }}>
              {user?.username?.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <h3 style={{ fontSize: '18px', fontWeight: 700 }}>{user?.username}</h3>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{user?.role || 'Builder'}</p>
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <SettingField label="Username" value={user?.username} />
            <SettingField label="Email" value={user?.email || `${user?.username}@tio.app`} />
          </div>
        </section>

        {/* Builder Config */}
        <section className="glass-panel" style={{ padding: '28px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
            <Zap size={18} color="var(--accent)" />
            <h3 style={{ fontSize: '16px', fontWeight: 700 }}>Configuration</h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <Toggle icon={theme === 'dark' ? Moon : Sun} label="Dark Mode" desc="High-contrast dark theme." active={theme === 'dark'} onToggle={toggleTheme} />
            <Toggle icon={Shield} label="Private Inference" desc="All inference runs locally via Ollama." active={true} />
            <Toggle icon={Key} label="API Access" desc="Enable external API for chatbots." active={false} />
          </div>
        </section>

        {/* Danger */}
        <section className="glass-panel" style={{ padding: '28px', borderColor: 'rgba(239,68,68,0.15)' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--accent-red)', marginBottom: '6px' }}>Danger Zone</h3>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>Irreversible actions.</p>
          <button className="btn btn-danger btn-sm">Delete Account</button>
        </section>
      </div>
    </div>
  );
}

function SettingField({ label, value }) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>{label}</label>
      <input className="input" value={value || ''} readOnly />
    </div>
  );
}

function Toggle({ icon: Icon, label, desc, active, onToggle }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{
          width: '36px', height: '36px', borderRadius: 'var(--radius-sm)',
          background: 'rgba(255,255,255,0.03)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'var(--text-muted)'
        }}>
          <Icon size={16} />
        </div>
        <div>
          <p style={{ fontSize: '14px', fontWeight: 600 }}>{label}</p>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{desc}</p>
        </div>
      </div>
      <div
        onClick={onToggle}
        style={{
          width: '40px', height: '22px', borderRadius: '11px',
          background: active ? 'var(--accent)' : 'rgba(255,255,255,0.08)',
          position: 'relative', cursor: onToggle ? 'pointer' : 'default',
          transition: 'background 0.2s', flexShrink: 0
        }}
      >
        <div style={{
          width: '16px', height: '16px', borderRadius: '50%',
          background: active ? '#050816' : 'var(--text-muted)',
          position: 'absolute', top: '3px',
          left: active ? '21px' : '3px',
          transition: 'left 0.2s'
        }} />
      </div>
    </div>
  );
}
