import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Plus, Folder, MoreVertical, Search, Filter, 
  Calendar, FileText, MessageSquare, ArrowRight,
  Code, FlaskConical, Globe, Zap, Database
} from 'lucide-react';

const PROJECTS = [
  {
    id: 1,
    name: "Quantum Computing Research",
    description: "Analyzing recent breakthroughs in topological qubits and error correction.",
    docs: 12,
    chats: 45,
    updated: "2 hours ago",
    color: "#7C3AED",
    icon: FlaskConical
  },
  {
    id: 2,
    name: "Platform Migration 2024",
    description: "Planning and tracking the transition from legacy systems to TiO Intelligence.",
    docs: 8,
    chats: 12,
    updated: "Yesterday",
    color: "#2563EB",
    icon: Zap
  },
  {
    id: 3,
    name: "Semantic Graph Analysis",
    description: "Exploring relationships between enterprise datasets using GraphRAG.",
    docs: 24,
    chats: 89,
    updated: "3 days ago",
    color: "#06B6D4",
    icon: Database
  },
  {
    id: 4,
    name: "Open-Source LLM Eval",
    description: "Benchmarking Llama 3 vs. Mistral and Phi-3 on internal technical docs.",
    docs: 5,
    chats: 21,
    updated: "1 week ago",
    color: "#10B981",
    icon: Code
  }
];

function ProjectCard({ project, index }) {
  const Icon = project.icon;
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      whileHover={{ y: -4, borderColor: project.color }}
      className="glass-panel"
      style={{ padding: '24px', cursor: 'pointer', position: 'relative', overflow: 'hidden' }}
    >
      <div style={{ 
        position: 'absolute', top: '-20px', right: '-20px', width: '100px', height: '100px', 
        borderRadius: '50%', background: project.color, opacity: 0.05, filter: 'blur(30px)' 
      }} />
      
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
        <div style={{ 
          width: '44px', height: '44px', borderRadius: '12px', background: `${project.color}15`, 
          border: `1px solid ${project.color}30`, display: 'flex', alignItems: 'center', justifyContent: 'center' 
        }}>
          <Icon size={20} color={project.color} />
        </div>
        <button style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
          <MoreVertical size={16} />
        </button>
      </div>

      <h3 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '8px', color: 'var(--text-primary)' }}>{project.name}</h3>
      <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: '24px', minHeight: '42px' }}>
        {project.description}
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <FileText size={14} color="var(--text-muted)" />
          <span style={{ fontSize: '12px', fontWeight: 600 }}>{project.docs} docs</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <MessageSquare size={14} color="var(--text-muted)" />
          <span style={{ fontSize: '12px', fontWeight: 600 }}>{project.chats} chats</span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '4px', color: 'var(--text-muted)' }}>
          <Calendar size={12} />
          <span style={{ fontSize: '11px' }}>{project.updated}</span>
        </div>
      </div>
    </motion.div>
  );
}

export default function ProjectsPage() {
  const [filter, setFilter] = useState('');

  return (
    <div style={{ padding: '40px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: '40px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-blue-light)', boxShadow: '0 0 8px var(--accent-blue)' }} />
            <span style={{ fontSize: '11px', color: 'var(--accent-blue-light)', fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', fontWeight: 600 }}>WORKSPACE PROJECTS</span>
          </div>
          <h1 style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em' }}>Intelligence Projects</h1>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '6px' }}>Organize research, documents, and conversations into semantic workspaces.</p>
        </div>
        <button className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '12px 20px', borderRadius: '12px' }}>
          <Plus size={18} /> Create New Project
        </button>
      </div>

      {/* Toolbar */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '32px' }}>
        <div style={{ flex: 1, position: 'relative' }}>
          <Search size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '14px', top: '50%', transform: 'translateY(-50%)' }} />
          <input 
            type="text" 
            placeholder="Search projects..." 
            value={filter}
            onChange={e => setFilter(e.target.value)}
            style={{ 
              width: '100%', padding: '12px 12px 12px 42px', borderRadius: '12px', 
              background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-glass)',
              color: 'var(--text-primary)', outline: 'none'
            }}
          />
        </div>
        <button className="glass-panel" style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '0 16px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-glass)' }}>
          <Filter size={16} /> Filter
        </button>
      </div>

      {/* Projects Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '24px' }}>
        {PROJECTS.map((p, i) => <ProjectCard key={p.id} project={p} index={i} />)}
        
        {/* Placeholder for "Add New" */}
        <motion.div
          whileHover={{ borderColor: 'var(--accent-blue)' }}
          style={{ 
            padding: '24px', borderRadius: '16px', border: '2px dashed var(--border-glass)',
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', background: 'rgba(255,255,255,0.01)', minHeight: '200px'
          }}
        >
          <div style={{ width: '48px', height: '48px', borderRadius: '50%', border: '2px dashed var(--border-glass)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '16px', color: 'var(--text-muted)' }}>
            <Plus size={20} />
          </div>
          <span style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-muted)' }}>Initialize New Research Project</span>
        </motion.div>
      </div>
    </div>
  );
}
