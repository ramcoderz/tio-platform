import { useState, useEffect } from "react";
import { 
  Brain, Link2, Zap, History, Tag, Search, 
  Trash2, RefreshCw, Cpu, Activity, Network,
  Layers, Database, Sparkles, Clock, Map,
  ChevronRight, X, Info, Filter, Share2
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api";
import { useChatStore } from "../store";

export default function MemoryPage() {
  const sessionId = useChatStore(state => state.sessionId);
  const [entities, setEntities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState("graph"); // "graph" or "list"
  const [selectedEntity, setSelectedEntity] = useState(null);
  const [filter, setFilter] = useState("");

  const fetchMemory = async () => {
    try {
      const data = await api(`/memory/${sessionId}`);
      setEntities(data || []);
    } catch (err) {
      console.error("Failed to fetch memory:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMemory();
  }, [sessionId]);

  const deleteEntry = async (id) => {
    setEntities(entities.filter(e => e.id !== id));
    if (selectedEntity?.id === id) setSelectedEntity(null);
  };

  const filteredEntities = entities.filter(e => {
    const k = (e.key || "").toLowerCase();
    const v = (e.value || "").toLowerCase();
    const f = (filter || "").toLowerCase();
    return k.includes(f) || v.includes(f);
  });

  return (
    <div style={{ height: 'calc(100vh - 8rem)', display: 'flex', flexDirection: 'column', gap: '32px', maxWidth: '1400px', margin: '0 auto', width: '100%', overflow: 'hidden', padding: '32px' }}>
      {/* Header Area */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-violet)' }}>
            <Sparkles size={16} className="animate-pulse" />
            <span style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.3em' }}>Cognitive Persistence</span>
          </div>
          <h1 style={{ fontSize: '36px', fontWeight: 900, color: 'var(--text-primary)', letterSpacing: '-0.05em', display: 'flex', alignItems: 'center', gap: '12px', margin: 0 }}>
             Semantic <span className="text-gradient--violet">Memory Graph</span>
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '14px', maxWidth: '448px', lineHeight: 1.6, margin: 0 }}>Relationship-aware extraction and topic continuity tracking.</p>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
           <div className="input-wrapper">
              <Search className="input-icon" size={16} />
              <input 
                type="text" 
                placeholder="Search memory clusters..." 
                aria-label="Search memory clusters"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="form-input"
                style={{ width: '256px', borderRadius: '16px', paddingLeft: '40px' }}
              />
           </div>

           <div className="glass-panel" style={{ padding: '4px', borderRadius: '16px', display: 'flex', gap: '4px' }}>
              <button 
                onClick={() => setView("graph")}
                aria-label="Switch to graph view"
                style={{
                  padding: '8px 16px', borderRadius: '12px', fontSize: '10px', fontWeight: 700, transition: 'all 0.2s',
                  background: view === "graph" ? 'var(--accent-violet)' : 'transparent',
                  color: view === "graph" ? '#fff' : 'var(--text-secondary)',
                  boxShadow: view === "graph" ? '0 0 20px rgba(124,58,237,0.4)' : 'none'
                }}
              >
                Graph View
              </button>
              <button 
                onClick={() => setView("list")}
                aria-label="Switch to timeline view"
                style={{
                  padding: '8px 16px', borderRadius: '12px', fontSize: '10px', fontWeight: 700, transition: 'all 0.2s',
                  background: view === "list" ? 'var(--accent-violet)' : 'transparent',
                  color: view === "list" ? '#fff' : 'var(--text-secondary)',
                  boxShadow: view === "list" ? '0 0 20px rgba(124,58,237,0.4)' : 'none'
                }}
              >
                Timeline View
              </button>
           </div>
        </div>
      </div>

      <div style={{ flexGrow: 1, position: 'relative', display: 'flex', gap: '32px', minHeight: 0 }}>
        <div className="glass-panel" style={{
          flexGrow: 1, position: 'relative', borderRadius: '48px', overflow: 'hidden', padding: '32px', display: 'flex', gap: '32px', transition: 'all 0.5s',
          marginRight: selectedEntity ? '420px' : '0'
        }}>
          {/* Memory Timeline / List */}
          <div style={{
            transition: 'all 0.7s', display: 'flex', flexDirection: 'column', gap: '24px',
            width: view === "graph" ? '33.333%' : '100%'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
               <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
                  <Clock size={16} />
                  <span style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Temporal Nodes</span>
               </div>
               <button onClick={fetchMemory} style={{ padding: '8px', borderRadius: '8px', color: 'var(--text-secondary)', transition: 'background 0.2s' }} className="hover-glow">
                  <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
               </button>
            </div>

            <div style={{ flexGrow: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px', paddingRight: '16px' }} className="custom-scrollbar">
              {filteredEntities.length > 0 ? filteredEntities.map((e, idx) => (
                <motion.div 
                  key={e.id || idx}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  onClick={() => setSelectedEntity(e)}
                  style={{
                    padding: '20px', borderRadius: '24px', transition: 'all 0.2s', display: 'flex', alignItems: 'flex-start', gap: '16px', cursor: 'pointer', position: 'relative', overflow: 'hidden',
                    background: selectedEntity?.key === e.key ? 'var(--accent-violet-dim)' : 'var(--glass-bg)',
                    border: `1px solid ${selectedEntity?.key === e.key ? 'var(--border-violet)' : 'var(--border-glass)'}`,
                    boxShadow: selectedEntity?.key === e.key ? '0 0 30px rgba(124,58,237,0.1)' : 'none'
                  }}
                  onMouseEnter={(ev) => { if (selectedEntity?.key !== e.key) ev.currentTarget.style.borderColor = 'rgba(124,58,237,0.3)'; }}
                  onMouseLeave={(ev) => { if (selectedEntity?.key !== e.key) ev.currentTarget.style.borderColor = 'var(--border-glass)'; }}
                >
                  <div style={{ width: '40px', height: '40px', borderRadius: '16px', background: 'var(--accent-violet-dim)', border: '1px solid rgba(124,58,237,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#a78bfa', flexShrink: 0, transition: 'transform 0.2s' }}>
                    <Tag size={16} />
                  </div>
                  <div style={{ flexGrow: 1 }}>
                     <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '4px' }}>
                        <h4 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)', margin: 0 }}>{e.key}</h4>
                        <ChevronRight size={14} style={{ transition: 'all 0.2s', color: selectedEntity?.key === e.key ? 'var(--accent-violet)' : 'var(--text-muted)', transform: selectedEntity?.key === e.key ? 'translateX(4px)' : 'none' }} />
                     </div>
                     <p style={{ fontSize: '11px', color: 'var(--text-secondary)', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', lineHeight: 1.6, margin: 0 }}>{e.value}</p>
                  </div>
                  {selectedEntity?.key === e.key && (
                    <motion.div layoutId="active-indicator" style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: '4px', background: 'var(--accent-violet)' }} />
                  )}
                </motion.div>
              )) : (
                <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', gap: '16px' }}>
                  <History size={48} style={{ opacity: 0.1 }} />
                  <p style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.2em', opacity: 0.5, textAlign: 'center', margin: 0 }}>Neural pathways<br/>ready for discovery</p>
                </div>
              )}
            </div>
          </div>

          {/* Semantic Graph Visualization */}
          <AnimatePresence>
            {view === "graph" && (
              <motion.div 
                initial={{ opacity: 0, scale: 0.98 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                style={{ flexGrow: 1, background: 'rgba(5,8,22,0.4)', borderRadius: '40px', border: '1px solid var(--border-glass)', position: 'relative', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
              >
                 <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(circle at center, rgba(37,99,235,0.05) 0%, transparent 70%)' }} />
                 
                 {/* Interactive Neural Connectors */}
                 <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
                    <defs>
                      <linearGradient id="link-grad" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="rgba(124,58,237,0)" />
                        <stop offset="50%" stopColor="rgba(124,58,237,0.27)" />
                        <stop offset="100%" stopColor="rgba(124,58,237,0)" />
                      </linearGradient>
                    </defs>
                    {[...Array(8)].map((_, i) => (
                       <motion.line
                          key={i}
                          x1={`${20 + Math.random() * 60}%`}
                          y1={`${20 + Math.random() * 60}%`}
                          x2="50%"
                          y2="50%"
                          stroke="url(#link-grad)"
                          strokeWidth="1"
                          initial={{ opacity: 0 }}
                          animate={{ 
                             opacity: [0, 1, 0],
                             strokeDashoffset: [0, -50]
                          }}
                          transition={{ 
                             duration: 4 + Math.random() * 4, 
                             repeat: Infinity,
                             delay: Math.random() * 5
                          }}
                          strokeDasharray="10,20"
                       />
                    ))}
                 </svg>

                 <div style={{ position: 'relative', zIndex: 10, textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '32px' }}>
                    <div style={{ position: 'relative', display: 'inline-block', margin: '0 auto' }}>
                       <motion.div 
                          animate={{ scale: [1, 1.2, 1], opacity: [0.1, 0.2, 0.1] }}
                          transition={{ duration: 6, repeat: Infinity }}
                          style={{ position: 'absolute', inset: 0, background: 'var(--accent-violet)', borderRadius: '50%', filter: 'blur(80px)' }}
                       />
                       <div style={{ width: '144px', height: '144px', borderRadius: '50%', background: 'var(--bg-elevated)', border: '1px solid rgba(124,58,237,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative', boxShadow: '0 0 60px rgba(124,58,237,0.15)', transition: 'all 0.7s' }}>
                          <Brain size={56} color="#a78bfa" className="animate-float" />
                          
                          {/* Rotating Rings */}
                          <div style={{ position: 'absolute', inset: 0, border: '1px solid rgba(124,58,237,0.1)', borderRadius: '50%' }} className="animate-spin" />
                          <div style={{ position: 'absolute', inset: '16px', border: '1px solid rgba(37,99,235,0.1)', borderRadius: '50%', animationDuration: '15s', animationDirection: 'reverse' }} className="animate-spin" />
                       </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                       <h3 style={{ fontSize: '24px', fontWeight: 900, color: 'var(--text-primary)', letterSpacing: '-0.02em', margin: 0 }}>Active Neural Context</h3>
                       <p style={{ fontSize: '10px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.4em', fontWeight: 700, margin: 0 }}>Semantic Relationship Orchestration</p>
                    </div>

                    <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '12px', maxWidth: '448px', margin: '0 auto' }}>
                      {filteredEntities.slice(0, 7).map((e, i) => (
                        <motion.div
                          key={i}
                          initial={{ opacity: 0, scale: 0.8 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: i * 0.1 }}
                          onClick={() => setSelectedEntity(e)}
                          style={{
                            padding: '8px 16px', borderRadius: '16px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.1)',
                            fontSize: '10px', fontWeight: 900, color: 'var(--text-primary)', cursor: 'pointer', transition: 'all 0.2s', textTransform: 'uppercase', letterSpacing: '0.1em'
                          }}
                          onMouseEnter={(ev) => { ev.currentTarget.style.background = 'var(--accent-violet)'; ev.currentTarget.style.color = '#fff'; ev.currentTarget.style.borderColor = '#a78bfa'; }}
                          onMouseLeave={(ev) => { ev.currentTarget.style.background = 'rgba(255,255,255,0.03)'; ev.currentTarget.style.color = 'var(--text-primary)'; ev.currentTarget.style.borderColor = 'rgba(255,255,255,0.1)'; }}
                        >
                          {e.key}
                        </motion.div>
                      ))}
                    </div>
                 </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Enhanced Detail Panel */}
        <AnimatePresence>
          {selectedEntity && (
            <motion.div 
              initial={{ x: 450, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 450, opacity: 0 }}
              transition={{ type: "spring", damping: 30, stiffness: 300 }}
              style={{
                position: 'absolute', top: 0, right: 0, width: '400px', height: '100%', background: 'rgba(5,8,22,0.95)',
                backdropFilter: 'blur(24px)', borderLeft: '1px solid var(--border-glass)', padding: '40px',
                display: 'flex', flexDirection: 'column', gap: '40px', boxShadow: '-30px 0 60px rgba(0,0,0,0.8)', zIndex: 30
              }}
            >
               <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div style={{ width: '56px', height: '56px', borderRadius: '16px', background: 'var(--accent-violet-dim)', border: '1px solid rgba(124,58,237,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#a78bfa', boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.2)' }}>
                     <Tag size={28} />
                  </div>
                  <button onClick={() => setSelectedEntity(null)} style={{ padding: '12px', borderRadius: '16px', background: 'rgba(255,255,255,0.05)', color: 'var(--text-secondary)', border: '1px solid var(--border-glass)', transition: 'all 0.2s' }} className="hover-glow">
                     <X size={20} />
                  </button>
               </div>

               <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                  <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '4px 12px', borderRadius: '9999px', background: 'var(--accent-violet-dim)', border: '1px solid rgba(124,58,237,0.2)', fontSize: '9px', fontWeight: 900, color: '#a78bfa', textTransform: 'uppercase', letterSpacing: '0.1em', alignSelf: 'flex-start' }}>
                     <Database size={12} />
                     Verified Concept
                  </div>
                  <h2 style={{ fontSize: '30px', fontWeight: 900, color: 'var(--text-primary)', letterSpacing: '-0.05em', lineHeight: 1, margin: 0 }}>{selectedEntity.key}</h2>
               </div>

               <div style={{ display: 'flex', flexDirection: 'column', gap: '32px', flexGrow: 1, overflowY: 'auto', paddingRight: '8px' }} className="custom-scrollbar">
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                     <label style={{ fontSize: '10px', fontWeight: 900, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.3em' }}>Knowledge Extraction</label>
                     <div style={{ padding: '24px', borderRadius: '24px', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-glass)', fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.6, fontWeight: 500 }}>
                        <span style={{ color: '#a78bfa', fontSize: '24px', fontFamily: 'serif', marginRight: '4px' }}>"</span>
                        {selectedEntity.value}
                        <span style={{ color: '#a78bfa', fontSize: '24px', fontFamily: 'serif', marginLeft: '4px' }}>"</span>
                     </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                     <div style={{ padding: '20px', borderRadius: '24px', background: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-glass)', transition: 'all 0.2s' }} className="hover-glow">
                        <label style={{ fontSize: '9px', fontWeight: 900, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: '8px' }}>Confidence</label>
                        <div style={{ display: 'flex', alignItems: 'flex-end', gap: '4px' }}>
                           <span style={{ fontSize: '24px', fontFamily: 'var(--font-mono)', fontWeight: 900, color: 'var(--text-primary)' }}>0.98</span>
                           <span style={{ fontSize: '10px', color: 'var(--accent-green)', fontWeight: 700, marginBottom: '4px' }}>↑ 2%</span>
                        </div>
                     </div>
                     <div style={{ padding: '20px', borderRadius: '24px', background: 'rgba(255,255,255,0.01)', border: '1px solid var(--border-glass)', transition: 'all 0.2s' }} className="hover-glow">
                        <label style={{ fontSize: '9px', fontWeight: 900, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', display: 'block', marginBottom: '8px' }}>Frequency</label>
                        <div style={{ display: 'flex', alignItems: 'flex-end', gap: '4px' }}>
                           <span style={{ fontSize: '24px', fontFamily: 'var(--font-mono)', fontWeight: 900, color: 'var(--text-primary)' }}>12</span>
                           <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '4px' }}>Passes</span>
                        </div>
                     </div>
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                     <label style={{ fontSize: '10px', fontWeight: 900, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.3em' }}>Neural Connections</label>
                     <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {["Research", "Logic", "Strategy", "Entities"].map(tag => (
                           <span key={tag} style={{ padding: '6px 12px', borderRadius: '12px', background: 'rgba(37,99,235,0.05)', border: '1px solid rgba(37,99,235,0.1)', fontSize: '9px', fontWeight: 700, color: 'rgba(96,165,250,0.7)' }}>
                              #{tag}
                           </span>
                        ))}
                     </div>
                  </div>
               </div>

               <div style={{ display: 'flex', gap: '12px', paddingTop: '24px', borderTop: '1px solid var(--border-glass)' }}>
                  <button className="btn btn-primary" style={{ flexGrow: 1, padding: '16px', borderRadius: '16px', fontSize: '12px', display: 'flex', justifyContent: 'center' }}>
                     <Share2 size={16} />
                     Map Provenance
                  </button>
                  <button onClick={() => deleteEntry(selectedEntity.id)} className="btn btn-danger" style={{ padding: '16px', borderRadius: '16px', display: 'flex', justifyContent: 'center' }}>
                     <Trash2 size={16} />
                  </button>
               </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Footer Stats Area */}
      <div className="glass-panel" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 32px', borderRadius: '40px', flexShrink: 0 }}>
         <div style={{ display: 'flex', alignItems: 'center', gap: '48px' }}>
            <StatItem label="Retention Rate" value="99.4%" sub="Persistent" />
            <StatItem label="Relationships" value={(filteredEntities.length * 2.4).toFixed(1)} sub="Active" />
            <StatItem label="Memory Density" value={filteredEntities.length} sub="Clusters" />
         </div>
         <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '10px 20px', borderRadius: '16px', background: 'var(--accent-violet-dim)', border: '1px solid rgba(124,58,237,0.2)', boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.2)' }}>
            <Activity size={16} color="#a78bfa" className="animate-pulse" />
            <span style={{ fontSize: '10px', fontWeight: 900, color: '#a78bfa', textTransform: 'uppercase', letterSpacing: '0.2em' }}>Neural Sync: Optimal</span>
         </div>
      </div>
    </div>
  );
}

function StatItem({ label, value, sub }) {
   return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
         <span style={{ fontSize: '9px', color: 'var(--text-muted)', fontWeight: 900, textTransform: 'uppercase', letterSpacing: '0.2em' }}>{label}</span>
         <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
            <span style={{ fontSize: '20px', fontFamily: 'var(--font-mono)', fontWeight: 900, color: 'var(--text-primary)' }}>{value}</span>
            <span style={{ fontSize: '9px', color: 'var(--text-secondary)', fontWeight: 700, textTransform: 'uppercase' }}>{sub}</span>
         </div>
      </div>
   );
}
