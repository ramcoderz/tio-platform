import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { 
  Database, Activity, ArrowRight, Shield, Layers, 
  Sparkles, Zap, BookOpen, Clock, Network, 
  FlaskConical, Layout, MessageSquare, TrendingUp,
  Star, ExternalLink
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api";
import { useChatStore } from "../store";
import { AI_NEWS } from "../data/news";

function NewsCard({ item }) {
  return (
    <motion.div
      whileHover={{ y: -4 }}
      className="glass-panel"
      style={{ minWidth: '320px', width: '320px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '12px' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '10px', fontWeight: 800, color: 'var(--accent-blue-light)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>{item.category}</span>
        <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{item.timestamp}</span>
      </div>
      <h4 style={{ fontSize: '15px', fontWeight: 700, lineHeight: 1.4 }}>{item.title}</h4>
      <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{item.summary}</p>
      <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid var(--border-subtle)', paddingTop: '12px' }}>
        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)' }}>{item.source}</span>
        <ExternalLink size={12} color="var(--text-muted)" />
      </div>
    </motion.div>
  );
}

export default function HomePage() {
  const navigate = useNavigate();
  const sessionId = useChatStore(state => state.sessionId);
  const [stats, setStats] = useState(null);
  const [activity, setActivity] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, activityData] = await Promise.all([
          api("/admin/stats"),
          api("/admin/activity")
        ]);
        setStats(statsData);
        setActivity(activityData);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ padding: '40px', maxWidth: '1400px', margin: '0 auto' }}>
      
      {/* Header / Welcome */}
      <div style={{ marginBottom: '48px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ fontSize: '32px', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '8px' }}>
            Intelligence Workspace
          </h1>
          <p style={{ fontSize: '15px', color: 'var(--text-secondary)' }}>Welcome back. Your semantic research environment is ready.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button onClick={() => navigate("/chat")} className="btn-primary" style={{ padding: '12px 24px', borderRadius: '12px' }}>
            Initialize Research
          </button>
        </div>
      </div>

      {/* Main Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '40px' }}>
        
        {/* Left Column: Projects & News */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '48px' }}>
          
          {/* AI News Feed */}
          <section>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Sparkles size={18} color="var(--accent-cyan)" />
                <h3 style={{ fontSize: '14px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>AI Intelligence Feed</h3>
              </div>
              <Link to="/news" style={{ fontSize: '12px', color: 'var(--accent-blue-light)', textDecoration: 'none', fontWeight: 600 }}>View Full Feed</Link>
            </div>
            <div style={{ display: 'flex', gap: '20px', overflowX: 'auto', paddingBottom: '12px' }} className="custom-scrollbar">
              {AI_NEWS.map(item => <NewsCard key={item.id} item={item} />)}
            </div>
          </section>

          {/* Recent Research (Projects) */}
          <section>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Layout size={18} color="var(--accent-violet)" />
                <h3 style={{ fontSize: '14px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>Recent Research</h3>
              </div>
              <Link to="/projects" style={{ fontSize: '12px', color: 'var(--accent-blue-light)', textDecoration: 'none', fontWeight: 600 }}>Manage Projects</Link>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
              <ProjectSummaryCard 
                name="Quantum Computing Research" 
                desc="Analyzing topological qubits..."
                updated="2h ago"
                color="#7C3AED"
              />
              <ProjectSummaryCard 
                name="Semantic Graph Analysis" 
                desc="Exploring relationship data..."
                updated="3d ago"
                color="#06B6D4"
              />
            </div>
          </section>

          {/* Semantic Activity */}
          <section>
             <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
                <Activity size={18} color="var(--accent-green)" />
                <h3 style={{ fontSize: '14px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>Semantic Activity</h3>
              </div>
              <div className="glass-panel" style={{ padding: '0' }}>
                 {[
                   { type: 'query', user: 'Ram', text: 'What are the main risks of topological qubits?', time: '2h ago' },
                   { type: 'upload', user: 'System', text: 'Successfully ingested 12 research papers on CRISPR.', time: '5h ago' },
                   { type: 'insight', user: 'AI', text: 'Detected a recurring theme of "Stability" across 4 projects.', time: '1d ago' },
                 ].map((act, i) => (
                   <div key={i} style={{ padding: '16px 24px', borderBottom: i === 2 ? 'none' : '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: '16px' }}>
                      <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: act.type === 'query' ? 'var(--accent-blue)' : act.type === 'upload' ? 'var(--accent-green)' : 'var(--accent-violet)' }} />
                      <div style={{ flex: 1 }}>
                        <p style={{ fontSize: '13px', color: 'var(--text-primary)', fontWeight: 500 }}>{act.text}</p>
                        <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{act.user} · {act.time}</p>
                      </div>
                   </div>
                 ))}
              </div>
          </section>
        </div>

        {/* Right Column: Suggestions & Quick Stats */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
          
          {/* Suggested Tools */}
          <section>
            <h3 style={{ fontSize: '14px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--text-muted)', marginBottom: '20px' }}>Suggested Tools</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <ToolSuggestCard icon={BookOpen} name="Research Summarizer" color="#7C3AED" />
              <ToolSuggestCard icon={Network} name="Architecture Analyzer" color="#2563EB" />
              <ToolSuggestCard icon={Star} name="Prompt Optimizer" color="#F59E0B" />
            </div>
          </section>

          {/* Activity Feed */}
          <section>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
              <Activity size={16} color="var(--accent-cyan)" />
              <h3 style={{ fontSize: '13px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)' }}>System Activity</h3>
            </div>
            <div className="glass-panel" style={{ padding: '24px', maxHeight: '400px', overflowY: 'auto' }} className="custom-scrollbar glass-panel">
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {activity.length === 0 ? (
                  <p style={{ fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center' }}>Waiting for system events...</p>
                ) : (
                  activity.map((act, i) => (
                    <div key={i} style={{ paddingBottom: '12px', borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                        <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-blue-light)' }}>{act.action.replace('_', ' ')}</span>
                        <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{new Date(act.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>
                      <p style={{ fontSize: '11px', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{act.details || act.resource}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          </section>

          {/* Security Status */}
          <div className="glass-panel" style={{ padding: '20px', background: 'rgba(16,185,129,0.04)', border: '1px solid rgba(16,185,129,0.2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
               <Shield size={16} color="var(--accent-green)" />
               <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--accent-green)' }}>Enterprise Private</span>
            </div>
            <p style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              All research data and model inference is localized to your encrypted workspace.
            </p>
          </div>

        </div>
      </div>
    </div>
  );
}

function ProjectSummaryCard({ name, desc, updated, color }) {
  return (
    <div className="glass-panel" style={{ padding: '20px', position: 'relative', overflow: 'hidden' }}>
       <div style={{ position: 'absolute', top: 0, left: 0, width: '4px', bottom: 0, background: color }} />
       <h4 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '6px' }}>{name}</h4>
       <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '12px' }}>{desc}</p>
       <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)' }}>
          <Clock size={12} />
          <span style={{ fontSize: '11px' }}>{updated}</span>
       </div>
    </div>
  );
}

function ToolSuggestCard({ icon: Icon, name, color }) {
  return (
    <div className="glass-panel" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }}>
       <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: `${color}15`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon size={16} color={color} />
       </div>
       <span style={{ fontSize: '13px', fontWeight: 600 }}>{name}</span>
       <ArrowRight size={14} style={{ marginLeft: 'auto', opacity: 0.3 }} />
    </div>
  );
}
