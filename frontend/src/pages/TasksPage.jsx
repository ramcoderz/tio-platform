import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { CheckSquare, Clock, User, Calendar, Plus, RefreshCw, AlertCircle } from "lucide-react";
import { api } from "../api";

export default function TasksPage() {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const data = await api("/tasks/");
      setTasks(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to fetch tasks", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, []);

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1300px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyItems: 'space-between', marginBottom: '36px', gap: '24px' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-green)', boxShadow: '0 0 8px var(--accent-green)' }} />
            <span style={{ fontSize: '11px', color: 'var(--accent-green)', fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', fontWeight: 600 }}>ACTION ITEMS</span>
          </div>
          <h1 style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)', marginBottom: '6px' }}>Task Orchestration</h1>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Automated task orchestration and tracking from cognitive insights.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
           <button onClick={fetchTasks} className="btn btn-ghost" style={{ padding: '10px', borderRadius: '12px' }}>
              <RefreshCw size={18} className={loading ? 'animate-spin' : ''} />
           </button>
           <button className="btn btn-primary" style={{ padding: '10px 20px', borderRadius: '12px', fontSize: '13px', display: 'flex', gap: '8px' }}>
              <Plus size={16} /> New Task
           </button>
        </div>
      </div>

      {/* Task Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '20px' }}>
        {loading && tasks.length === 0 ? (
           [...Array(6)].map((_, i) => <div key={i} className="skeleton" style={{ height: '200px', borderRadius: '24px' }} />)
        ) : tasks.length === 0 ? (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '80px 20px', background: 'rgba(255,255,255,0.02)', borderRadius: '32px', border: '1px dashed var(--border-glass)' }}>
            <CheckSquare size={48} style={{ margin: '0 auto 16px', color: 'var(--text-muted)', opacity: 0.3 }} />
            <p style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px' }}>No tasks orchestrated yet</p>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Ask TiO to "identify tasks from our discussion" to automatically generate action items.</p>
          </div>
        ) : (
          <AnimatePresence>
            {tasks.map((task, i) => (
              <motion.div
                key={task.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="glass-panel hover-glow"
                style={{ padding: '24px', borderRadius: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <span className={`badge ${task.status === 'completed' ? 'badge-green' : task.status === 'in_progress' ? 'badge-blue' : 'badge-yellow'}`}>
                    {task.status?.replace('_', ' ') || 'pending'}
                  </span>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {new Date(task.created_at).toLocaleDateString()}
                  </span>
                </div>
                
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.5, margin: 0 }}>
                   {task.description}
                </h3>
                
                <div style={{ marginTop: 'auto', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
                       <User size={14} />
                       <span style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Owner</span>
                    </div>
                    <span style={{ fontSize: '13px', color: task.owner ? 'var(--accent-cyan)' : 'var(--text-muted)', fontWeight: 500 }}>
                       {task.owner || "Unassigned"}
                    </span>
                  </div>
                  
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
                       <Calendar size={14} />
                       <span style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Deadline</span>
                    </div>
                    <span style={{ fontSize: '13px', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                       {task.deadline ? new Date(task.deadline).toLocaleDateString() : "TBD"}
                    </span>
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  );
}
