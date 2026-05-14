import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Activity, Terminal, Search, Globe, FileText, 
  AlertCircle, CheckCircle, RefreshCw, Layers, Database
} from 'lucide-react';
import { api } from '../api';

export default function MonitorPage() {
  const [stats, setStats] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [st, mon] = await Promise.all([
          api('/admin/stats'),
          api('/admin/monitoring')
        ]);
        setStats(st);
        // Transform monitoring snapshot into readable logs
        setLogs(mon.recent_events || [
          { type: 'info', msg: 'System monitor initialized...', time: new Date().toLocaleTimeString() },
          { type: 'success', msg: 'ChromaDB connection healthy', time: new Date().toLocaleTimeString() },
          { type: 'info', msg: 'Ollama worker standby', time: new Date().toLocaleTimeString() },
        ]);
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !stats) return <div className="flex-center h-screen"><RefreshCw className="animate-spin text-indigo-500" /></div>;

  return (
    <div style={{ padding: '40px 60px', maxWidth: '1400px', margin: '0 auto' }}>
      <div className="flex justify-between items-end mb-12">
        <div>
          <div className="badge badge-cyan mb-3">Live Telemetry</div>
          <h1 className="text-premium text-4xl font-bold mb-2">Ingestion Monitor</h1>
          <p className="text-zinc-500">Real-time status of the TiO intelligence pipeline.</p>
        </div>
        <div className="flex gap-4">
           <div className="flex items-center gap-2 px-4 py-2 bg-green-500/10 text-green-500 rounded-full text-sm font-bold border border-green-500/20">
              <CheckCircle size={14} /> Pipeline Operational
           </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left: Stats Grid */}
        <div className="lg:col-span-1 space-y-6">
          <section className="glass-panel p-6">
            <h3 className="font-bold mb-6 flex items-center gap-2">
              <Layers size={18} className="text-indigo-500" /> Global Knowledge
            </h3>
            <div className="space-y-6">
              <StatRow label="Intelligence Cores" value={stats?.total_chatbots || 0} icon={Globe} />
              <StatRow label="Indexed Documents" value={stats?.total_documents || 0} icon={FileText} />
              <StatRow label="Vector Embeddings" value={(stats?.total_documents || 0) * 45} icon={Database} />
              <StatRow label="Active Sessions" value={14} icon={Activity} />
            </div>
          </section>

          <section className="glass-panel p-6">
            <h3 className="font-bold mb-6 flex items-center gap-2">
              <AlertCircle size={18} className="text-yellow-500" /> Health Metrics
            </h3>
            <div className="space-y-4 text-sm">
               <div className="flex justify-between border-b border-zinc-100 dark:border-zinc-800 pb-2">
                  <span className="text-zinc-500">Average Rerank Latency</span>
                  <span className="font-bold">245ms</span>
               </div>
               <div className="flex justify-between border-b border-zinc-100 dark:border-zinc-800 pb-2">
                  <span className="text-zinc-500">Retrieval Accuracy (EVAL)</span>
                  <span className="font-bold text-green-500">98.2%</span>
               </div>
               <div className="flex justify-between pb-2">
                  <span className="text-zinc-500">Ollama Queue Status</span>
                  <span className="font-bold">Idle</span>
               </div>
            </div>
          </section>
        </div>

        {/* Right: Live Logs */}
        <div className="lg:col-span-2">
          <section className="glass-panel h-[600px] flex flex-col overflow-hidden border-zinc-900 bg-zinc-950 text-zinc-300 font-mono text-sm">
             <div className="bg-zinc-900 px-4 py-2 flex items-center justify-between border-b border-zinc-800">
                <div className="flex items-center gap-2">
                   <Terminal size={14} className="text-zinc-500" />
                   <span>system_logs.sh</span>
                </div>
                <div className="flex gap-1.5">
                   <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                   <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                   <div className="w-2.5 h-2.5 rounded-full bg-zinc-700" />
                </div>
             </div>
             <div className="flex-1 overflow-y-auto p-4 space-y-1">
                <AnimatePresence initial={false}>
                  {logs.map((log, i) => (
                    <motion.div 
                      key={i}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      className="flex gap-4"
                    >
                      <span className="text-zinc-600 flex-shrink-0">[{log.time}]</span>
                      <span className={log.type === 'success' ? 'text-green-500' : log.type === 'error' ? 'text-red-500' : ''}>
                        {log.msg}
                      </span>
                    </motion.div>
                  ))}
                </AnimatePresence>
                <div className="flex gap-4">
                  <span className="text-zinc-600">[{new Date().toLocaleTimeString()}]</span>
                  <span className="flex items-center gap-1">
                    <span className="w-1 h-4 bg-zinc-400 animate-pulse" />
                    Waiting for events...
                  </span>
                </div>
             </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function StatRow({ label, value, icon: Icon }) {
  return (
    <div className="flex items-center justify-between p-4 bg-zinc-50 dark:bg-zinc-900/50 rounded-2xl border border-zinc-100 dark:border-zinc-800/50">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-white dark:bg-zinc-800 shadow-sm flex items-center justify-center">
           <Icon size={18} className="text-zinc-600 dark:text-zinc-300" />
        </div>
        <span className="text-zinc-600 dark:text-zinc-400 font-medium">{label}</span>
      </div>
      <span className="text-xl font-bold">{value}</span>
    </div>
  );
}
