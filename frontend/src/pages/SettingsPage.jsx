import { useState } from "react";
import { 
  User, Shield, Bell, Zap, 
  Moon, Sun, Key, Laptop
} from "lucide-react";
import { useAppCtx } from "../context/AppContext";

export default function SettingsPage() {
  const { user } = useAppCtx();
  const [theme, setTheme] = useState("dark");

  return (
    <div style={{ padding: '40px', maxWidth: '1000px', margin: '0 auto' }}>
      <header style={{ marginBottom: '40px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 800, marginBottom: '8px' }}>Settings</h1>
        <p style={{ color: '#64748b' }}>Manage your account preferences and builder configuration.</p>
      </header>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
        
        {/* Profile */}
        <section className="glass-panel" style={{ padding: '32px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px', marginBottom: '32px' }}>
            <div style={{ width: '64px', height: '64px', borderRadius: '50%', background: 'linear-gradient(135deg, #00C6FF, #0072FF)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '24px', fontWeight: 800, color: '#050816' }}>
              {user?.username?.slice(0, 2).toUpperCase()}
            </div>
            <div>
              <h3 style={{ fontSize: '20px', fontWeight: 700 }}>{user?.username}</h3>
              <p style={{ color: '#64748b' }}>{user?.role || "Builder"} · Active since May 2026</p>
            </div>
          </div>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
            <SettingInput label="Full Name" value={user?.username} />
            <SettingInput label="Email Address" value={`${user?.username}@example.com`} />
          </div>
        </section>

        {/* Builder Settings */}
        <section className="glass-panel" style={{ padding: '32px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
            <Zap size={20} color="#00C6FF" />
            <h3 style={{ fontSize: '18px', fontWeight: 700 }}>Builder Configuration</h3>
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
             <SettingToggle 
                icon={Moon} 
                label="Dark Mode" 
                desc="Use high-contrast dark theme for long building sessions." 
                active={theme === 'dark'}
                onToggle={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
             />
             <SettingToggle 
                icon={Shield} 
                label="Private Inference" 
                desc="Run all RAG operations on local infrastructure." 
                active={true}
             />
             <SettingToggle 
                icon={Key} 
                label="API Access" 
                desc="Enable external API access for your chatbots." 
                active={false}
             />
          </div>
        </section>

        {/* Danger Zone */}
        <section className="glass-panel" style={{ padding: '32px', borderColor: 'rgba(239, 68, 68, 0.2)', background: 'rgba(239, 68, 68, 0.02)' }}>
          <h3 style={{ fontSize: '18px', fontWeight: 700, color: '#ef4444', marginBottom: '8px' }}>Danger Zone</h3>
          <p style={{ color: '#64748b', marginBottom: '24px', fontSize: '14px' }}>Irreversible actions regarding your account and chatbots.</p>
          <button style={{ padding: '10px 20px', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', color: '#ef4444', fontWeight: 600, cursor: 'pointer' }}>
            Delete Account
          </button>
        </section>

      </div>
    </div>
  );
}

function SettingInput({ label, value }) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '8px' }}>{label}</label>
      <input 
        type="text" 
        value={value} 
        readOnly
        style={{ width: '100%', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', padding: '10px 14px', color: '#fff', fontSize: '14px' }}
      />
    </div>
  );
}

function SettingToggle({ icon: Icon, label, desc, active, onToggle }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#64748b' }}>
          <Icon size={18} />
        </div>
        <div>
          <p style={{ fontSize: '15px', fontWeight: 600 }}>{label}</p>
          <p style={{ fontSize: '13px', color: '#64748b' }}>{desc}</p>
        </div>
      </div>
      <div 
        onClick={onToggle}
        style={{ 
          width: '44px', height: '24px', borderRadius: '12px', 
          background: active ? '#00C6FF' : 'rgba(255,255,255,0.1)', 
          position: 'relative', cursor: 'pointer', transition: 'all 0.3s' 
        }}
      >
        <div style={{ 
          width: '18px', height: '18px', borderRadius: '50%', background: active ? '#050816' : '#94a3b8',
          position: 'absolute', top: '3px', left: active ? '23px' : '3px', transition: 'all 0.3s'
        }} />
      </div>
    </div>
  );
}
