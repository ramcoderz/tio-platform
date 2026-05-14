import React from 'react';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Cpu, Globe, Layers, MessageSquare, Shield, Zap } from 'lucide-react';

const LandingPage = () => {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      {/* Navigation */}
      <nav style={{
        position: 'fixed', top: 0, width: '100%', zIndex: 1000,
        background: 'rgba(3, 5, 12, 0.8)', backdropFilter: 'blur(20px)',
        borderBottom: '1px solid var(--border)'
      }}>
        <div className="container" style={{ height: '72px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontWeight: 800, fontSize: '22px', letterSpacing: '-0.03em' }}>
            <div className="glass-panel" style={{ width: '36px', height: '36px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '10px', background: 'var(--accent-gradient)' }}>
              <Cpu size={22} color="#03050c" />
            </div>
            <span>TiO</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <Link to="/login" className="btn btn-ghost btn-sm" style={{ border: 'none' }}>
              Log in
            </Link>
            <Link to="/register" className="btn btn-primary btn-sm" style={{ borderRadius: 'var(--radius-full)', padding: '8px 20px' }}>
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section style={{ pt: '160px', pb: '100px', textAlign: 'center', position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', top: '10%', left: '50%', transform: 'translateX(-50%)', width: '800px', height: '800px', background: 'radial-gradient(circle, rgba(0, 198, 255, 0.05) 0%, transparent 70%)', zIndex: -1 }} />
        
        <div className="container" style={{ paddingTop: '160px' }}>
          <motion.h1 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            style={{ fontSize: 'clamp(40px, 8vw, 84px)', fontWeight: 800, lineHeight: 1.1, marginBottom: '24px', letterSpacing: '-0.04em' }}
          >
            Contextual Intelligence <br />
            <span className="text-premium">for your Website.</span>
          </motion.h1>
          <motion.p 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            style={{ fontSize: 'clamp(16px, 2vw, 20px)', color: 'var(--text-secondary)', maxWidth: '700px', margin: '0 auto 48px', lineHeight: 1.6 }}
          >
            TiO transforms your documentation and websites into grounded, workflow-aware conversational copilots. No hallucinations, just pure context.
          </motion.p>
          <motion.div 
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '20px' }}
          >
            <Link to="/register" className="btn btn-primary" style={{ padding: '16px 32px', fontSize: '16px', borderRadius: 'var(--radius-full)' }}>
              Build your first Chatbot
            </Link>
            <a href="#features" className="btn btn-ghost" style={{ padding: '16px 32px', fontSize: '16px', borderRadius: 'var(--radius-full)' }}>
              See how it works
            </a>
          </motion.div>
        </div>
      </section>

      {/* Features Grid */}
      <section id="features" style={{ py: '100px', background: 'rgba(255,255,255,0.02)', borderY: '1px solid var(--border)' }}>
        <div className="container" style={{ padding: '100px 0' }}>
          <div className="grid-cols-2" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))' }}>
            <FeatureCard 
              icon={<Globe size={24} color="#00C6FF" />}
              title="Smart Ingestion"
              description="Deep crawling with URL scoring and semantic noise filtering. We index only what matters."
            />
            <FeatureCard 
              icon={<Layers size={24} color="#7C3AED" />}
              title="Hybrid Retrieval"
              description="Combining semantic density with keyword precision using RRF fusion and Cross-Encoder reranking."
            />
            <FeatureCard 
              icon={<Shield size={24} color="#3B82F6" />}
              title="Strict Grounding"
              description="Eliminate hallucinations with mandatory context snapshots and high-fidelity entity extraction."
            />
          </div>
        </div>
      </section>

      {/* Architecture Preview */}
      <section style={{ py: '100px' }}>
        <div className="container" style={{ padding: '100px 0' }}>
          <div className="glass-panel-glow" style={{ overflow: 'hidden' }}>
            <div style={{ padding: 'clamp(32px, 8vw, 64px)' }}>
              <h2 style={{ fontSize: '36px', fontWeight: 800, marginBottom: '48px', display: 'flex', alignItems: 'center', gap: '16px' }}>
                <Zap size={32} color="#FBBF24" />
                Workflow-Aware Intelligence
              </h2>
              <div style={{ display: 'grid', gap: '40px' }}>
                <div style={{ display: 'flex', gap: '24px' }}>
                  <div className="flex-center" style={{ width: '48px', height: '48px', background: 'rgba(255,255,255,0.05)', borderRadius: '14px', flexShrink: 0, fontWeight: 800, color: 'var(--text-muted)' }}>1</div>
                  <div>
                    <h3 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '8px' }}>Site Understanding</h3>
                    <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>TiO builds a persistent organizational memory, mapping services and workflows before the first chat.</p>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '24px' }}>
                  <div className="flex-center" style={{ width: '48px', height: '48px', background: 'rgba(255,255,255,0.05)', borderRadius: '14px', flexShrink: 0, fontWeight: 800, color: 'var(--text-muted)' }}>2</div>
                  <div>
                    <h3 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '8px' }}>Response Planning</h3>
                    <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>Every response starts with a logical goal-based plan, ensuring proactive assistance instead of passive chat.</p>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '24px' }}>
                  <div className="flex-center" style={{ width: '48px', height: '48px', background: 'rgba(255,255,255,0.05)', borderRadius: '14px', flexShrink: 0, fontWeight: 800, color: 'var(--text-muted)' }}>3</div>
                  <div>
                    <h3 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '8px' }}>External Grounding</h3>
                    <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>Autonomous research fallback via Tavily ensures grounded answers even when local context is insufficient.</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer style={{ py: '64px', borderTop: '1px solid var(--border)', background: 'var(--bg-secondary)' }}>
        <div className="container" style={{ padding: '64px 0', display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '32px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontWeight: 800, fontSize: '20px' }}>
             <Cpu color="var(--accent)" />
             <span>TiO Platform</span>
          </div>
          <div style={{ display: 'flex', gap: '32px', fontSize: '14px', color: 'var(--text-muted)' }}>
            <a href="#" className="nav-link" style={{ textDecoration: 'none', color: 'inherit' }}>Documentation</a>
            <a href="#" className="nav-link" style={{ textDecoration: 'none', color: 'inherit' }}>Privacy</a>
            <a href="#" className="nav-link" style={{ textDecoration: 'none', color: 'inherit' }}>API</a>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-dim)' }}>© 2026 TiO Intelligence. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

const FeatureCard = ({ icon, title, description }) => (
  <div className="glass-panel" style={{ padding: '40px', borderRadius: '32px' }}>
    <div className="flex-center" style={{ width: '56px', height: '56px', borderRadius: '16px', background: 'rgba(255,255,255,0.03)', marginBottom: '24px' }}>
      {icon}
    </div>
    <h3 style={{ fontSize: '22px', fontWeight: 700, marginBottom: '16px' }}>{title}</h3>
    <p style={{ color: 'var(--text-secondary)', lineHeight: 1.7 }}>
      {description}
    </p>
  </div>
);

export default LandingPage;
