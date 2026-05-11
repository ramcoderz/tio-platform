import { motion } from 'framer-motion';
import { Construction } from 'lucide-react';

export default function PlaceholderPage({ title }) {
  return (
    <div style={{ 
      height: '100%', 
      display: 'flex', 
      flexDirection: 'column', 
      alignItems: 'center', 
      justifyContent: 'center',
      padding: '40px',
      textAlign: 'center'
    }}>
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.5 }}
        style={{
          width: '80px',
          height: '80px',
          borderRadius: '24px',
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid var(--border-glass)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '24px'
        }}
      >
        <Construction size={40} color="var(--text-muted)" />
      </motion.div>
      <h1 style={{ fontSize: '28px', fontWeight: 800, marginBottom: '12px' }}>{title}</h1>
      <p style={{ color: 'var(--text-secondary)', maxWidth: '400px', fontSize: '15px', lineHeight: 1.6 }}>
        This module is currently in development. Core intelligence features are being prioritized first.
      </p>
      
      <div style={{ marginTop: '40px', display: 'flex', gap: '12px' }}>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ width: '100px', height: '4px', background: 'rgba(255,255,255,0.05)', borderRadius: '2px' }} />
        ))}
      </div>
    </div>
  );
}
