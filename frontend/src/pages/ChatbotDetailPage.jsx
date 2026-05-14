import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { 
  Bot, Globe, Layers, Activity, Cpu, FileText, 
  Search, Shield, Zap, ChevronLeft, Calendar, 
  CheckCircle, Database, Server
} from 'lucide-react';
import { api } from '../api';

export default function ChatbotDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [chatbot, setChatbot] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await api(`/chatbots/${id}`);
        setChatbot(data);
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    load();
  }, [id]);

  if (loading) return <div className="flex-center h-full"><div className="skeleton w-1/2 h-64 rounded-3xl" /></div>;
  if (!chatbot) return <div className="flex-center h-full text-zinc-500">Chatbot not found.</div>;

  const profile = chatbot.site_profile || {};

  return (
    <div style={{ padding: '40px 60px', maxWidth: '1200px', margin: '0 auto' }}>
      <button 
        onClick={() => navigate('/')} 
        className="btn btn-ghost" 
        style={{ marginBottom: '24px', paddingLeft: 0, gap: '8px' }}
      >
        <ChevronLeft size={20} /> Back to Dashboard
      </button>

      <div style={{ display: 'flex', gap: '32px', marginBottom: '60px' }}>
        <div style={{
          width: '80px', height: '80px', borderRadius: '24px',
          background: 'linear-gradient(135deg, #6366f1, #a855f7)',
          display: 'flex', alignItems: 'center', justifyCenter: 'center',
          boxShadow: '0 12px 24px rgba(99,102,241,0.3)'
        }}>
          <Bot size={40} color="#fff" />
        </div>
        <div>
          <div className="flex items-center gap-3 mb-2">
            <h1 style={{ fontSize: '36px', fontWeight: 800 }}>{chatbot.name}</h1>
            <div className={`badge ${chatbot.status === 'ready' ? 'badge-cyan' : 'badge-pulse'}`}>
              {chatbot.status === 'ready' ? 'Operational' : 'Processing'}
            </div>
          </div>
          <div className="flex items-center gap-4 text-zinc-500 text-sm">
            <div className="flex items-center gap-1"><Globe size={14} /> {chatbot.website_url || 'Internal Base'}</div>
            <div className="flex items-center gap-1"><Calendar size={14} /> Created {new Date(chatbot.created_at).toLocaleDateString()}</div>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '32px' }}>
        {/* Main Intel */}
        <div className="space-y-8">
          {/* Site Summary */}
          <section className="glass-panel" style={{ padding: '32px' }}>
            <div className="flex items-center gap-2 mb-4 font-bold text-indigo-500">
              <Zap size={18} />
              <span>Grounded Identity</span>
            </div>
            <h3 className="text-xl font-bold mb-4">Core Summary</h3>
            <p className="text-zinc-600 dark:text-zinc-400 leading-relaxed text-lg">
              {profile.site_summary || "The intelligence engine is still synthesizing the site-wide profile. Re-index to trigger a new understanding pass."}
            </p>
          </section>

          {/* Entities & Services */}
          <div className="grid grid-cols-2 gap-6">
            <section className="glass-panel" style={{ padding: '24px' }}>
              <h3 className="font-bold mb-4 flex items-center gap-2">
                <Layers size={18} className="text-blue-500" /> Top Entities
              </h3>
              <div className="flex flex-wrap gap-2">
                {profile.top_entities?.map((e, i) => (
                  <span key={i} className="px-3 py-1 bg-zinc-100 dark:bg-zinc-900 rounded-full text-sm font-medium border border-zinc-200 dark:border-zinc-800">
                    {e}
                  </span>
                )) || <span className="text-zinc-500 italic">None detected yet.</span>}
              </div>
            </section>
            <section className="glass-panel" style={{ padding: '24px' }}>
              <h3 className="font-bold mb-4 flex items-center gap-2">
                <CheckCircle size={18} className="text-green-500" /> Key Services
              </h3>
              <div className="flex flex-wrap gap-2">
                {profile.key_services?.map((s, i) => (
                  <span key={i} className="px-3 py-1 bg-zinc-100 dark:bg-zinc-900 rounded-full text-sm font-medium border border-zinc-200 dark:border-zinc-800">
                    {s}
                  </span>
                )) || <span className="text-zinc-500 italic">No services mapped.</span>}
              </div>
            </section>
          </div>

          {/* Workflows */}
          <section className="glass-panel" style={{ padding: '32px' }}>
            <h3 className="text-xl font-bold mb-6 flex items-center gap-2">
              <Activity size={20} className="text-purple-500" /> Detected Workflows
            </h3>
            <div className="space-y-4">
              {profile.workflows?.map((w, i) => (
                <div key={i} className="flex gap-4 p-4 bg-zinc-50 dark:bg-zinc-900/50 rounded-2xl border border-zinc-200/50 dark:border-zinc-800/50">
                  <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-white dark:bg-zinc-800 shadow-sm flex items-center justify-center font-bold text-xs">
                    {i + 1}
                  </div>
                  <div>
                    <h4 className="font-semibold text-zinc-900 dark:text-zinc-100">{w}</h4>
                  </div>
                </div>
              )) || <div className="text-zinc-500 p-4 border border-dashed rounded-xl">No specific workflows identified yet.</div>}
            </div>
          </section>
        </div>

        {/* Sidebar Intel */}
        <div className="space-y-6">
          <section className="glass-panel" style={{ padding: '24px' }}>
            <h3 className="font-bold mb-4">Ingestion Stats</h3>
            <div className="space-y-4">
               <StatItem icon={FileText} label="Indexed Pages" value={profile.indexed_pages || '---'} />
               <StatItem icon={Database} label="Vector Count" value={profile.chunk_count || '---'} />
               <StatItem icon={Cpu} label="NER passes" value="Completed" />
            </div>
          </section>

          <section className="glass-panel" style={{ padding: '24px' }}>
            <h3 className="font-bold mb-4">Security Scoping</h3>
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm text-green-500 font-medium">
                <Shield size={16} /> Isolated Retrieval Active
              </div>
              <div className="flex items-center gap-2 text-sm text-blue-500 font-medium">
                <Server size={16} /> Persistence Scoped
              </div>
            </div>
            <div className="mt-6">
              <button 
                onClick={() => navigate(`/files?chatbot_id=${id}`)}
                className="btn btn-ghost w-full justify-between"
              >
                Manage Files <ArrowRight size={16} />
              </button>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function StatItem({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2 text-zinc-500 text-sm">
        <Icon size={14} /> {label}
      </div>
      <div className="font-bold text-sm">{value}</div>
    </div>
  );
}

function ArrowRight({ size }) {
  return <Zap size={size} />;
}
