import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Globe, Upload, CheckCircle2, Loader2, Bot, 
  ArrowRight, ShieldCheck, Sparkles, MessageCircle
} from "lucide-react";
import { api } from "../api";

export default function CreateChatbotPage() {
  const [url, setUrl] = useState("");
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [chatbot, setChatbot] = useState(null);
  const [progress, setProgress] = useState(0);

  const handleCreate = async () => {
    if (!url && files.length === 0) return;
    setLoading(true);
    try {
      const data = await api("/chatbots", "POST", { website_url: url });
      setChatbot(data);
      
      // If there are files, upload them
      for (const file of files) {
        const formData = new FormData();
        formData.append("file", file);
        await fetch(`${window.location.origin}/api/chatbots/${data.id}/upload`, {
          method: "POST",
          body: formData
        });
      }
      
      // Start polling for status
      startPolling(data.id);
    } catch (err) {
      console.error(err);
      setLoading(false);
    }
  };

  const startPolling = (id) => {
    const interval = setInterval(async () => {
      try {
        const data = await api(`/chatbots/${id}`);
        setChatbot(data);
        if (data.status === 'ready' || data.status === 'error') {
          clearInterval(interval);
          setLoading(false);
        }
      } catch (err) {
        clearInterval(interval);
        setLoading(false);
      }
    }, 2000);
  };

  return (
    <div style={{ padding: '40px', maxWidth: '1400px', margin: '0 auto', height: '100%', display: 'flex', flexDirection: 'column' }}>
      <header style={{ marginBottom: '32px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 800, marginBottom: '8px' }}>Create New Chatbot</h1>
        <p style={{ color: '#64748b' }}>Connect your website and documents to build a context-aware assistant.</p>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '32px', flex: 1 }}>
        
        {/* LEFT: Configuration */}
        <section className="glass-panel" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '12px' }}>Website URL</label>
            <div style={{ position: 'relative' }}>
              <Globe size={18} style={{ position: 'absolute', left: '12px', top: '12px', color: '#64748b' }} />
              <input 
                type="text" 
                placeholder="https://example.com" 
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                style={{ width: '100%', padding: '12px 12px 12px 40px', borderRadius: '10px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', color: '#fff' }}
              />
            </div>
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '12px' }}>Upload Documents</label>
            <div 
              style={{ border: '2px dashed rgba(255,255,255,0.08)', borderRadius: '12px', padding: '32px', textAlign: 'center', cursor: 'pointer' }}
              onClick={() => document.getElementById('file-input').click()}
            >
              <Upload size={32} style={{ color: '#00C6FF', marginBottom: '12px' }} />
              <p style={{ fontSize: '14px', color: '#94a3b8' }}>Click to upload PDFs, Docx, or TXT</p>
              <input 
                id="file-input" 
                type="file" 
                multiple 
                hidden 
                onChange={(e) => setFiles(Array.from(e.target.files))}
              />
            </div>
            {files.length > 0 && (
              <div style={{ marginTop: '12px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                {files.map((f, i) => (
                  <div key={i} style={{ padding: '4px 10px', borderRadius: '6px', background: 'rgba(0,198,255,0.1)', color: '#00C6FF', fontSize: '12px' }}>
                    {f.name}
                  </div>
                ))}
              </div>
            )}
          </div>

          <button 
            onClick={handleCreate}
            disabled={loading || (!url && files.length === 0)}
            style={{ 
              marginTop: 'auto', 
              width: '100%', 
              padding: '14px', 
              borderRadius: '12px', 
              background: 'linear-gradient(135deg, #00C6FF, #0072FF)', 
              color: '#050816', 
              fontWeight: 700, 
              border: 'none', 
              cursor: 'pointer',
              opacity: (loading || (!url && files.length === 0)) ? 0.5 : 1
            }}
          >
            {loading ? <Loader2 className="animate-spin" style={{ margin: '0 auto' }} /> : "Generate Chatbot"}
          </button>
        </section>

        {/* CENTER: Status & Domain */}
        <section style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          <div className="glass-panel" style={{ padding: '24px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '20px' }}>Ingestion Progress</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <StatusStep icon={Globe} label="Website Discovery" status={chatbot ? (chatbot.status !== 'pending' ? 'complete' : 'loading') : 'idle'} />
              <StatusStep icon={Bot} label="Domain Detection" status={chatbot?.domain ? 'complete' : (chatbot?.status === 'ingesting' ? 'loading' : 'idle')} />
              <StatusStep icon={Sparkles} label="Behavior Profile Activation" status={chatbot?.behavior_profile ? 'complete' : (chatbot?.status === 'ingesting' ? 'loading' : 'idle')} />
              <StatusStep icon={ShieldCheck} label="Context Grounding" status={chatbot?.status === 'ready' ? 'complete' : (chatbot?.status === 'ingesting' ? 'loading' : 'idle')} />
            </div>
          </div>

          {chatbot?.domain && (
            <motion.div 
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="glass-panel" 
              style={{ padding: '24px', background: 'rgba(0,198,255,0.05)', border: '1px solid rgba(0,198,255,0.2)' }}
            >
              <h3 style={{ fontSize: '12px', fontWeight: 800, color: '#00C6FF', textTransform: 'uppercase', marginBottom: '8px' }}>Detected Domain</h3>
              <p style={{ fontSize: '24px', fontWeight: 800, textTransform: 'capitalize' }}>{chatbot.domain}</p>
              <p style={{ fontSize: '13px', color: '#94a3b8', marginTop: '8px' }}>Behavior profile for <b>{chatbot.domain}</b> has been activated.</p>
            </motion.div>
          )}
        </section>

        {/* RIGHT: Live Preview */}
        <section className="glass-panel" style={{ padding: '0', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '16px 24px', borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: chatbot?.status === 'ready' ? '#10B981' : '#F59E0B' }} />
            <span style={{ fontSize: '14px', fontWeight: 600 }}>Live Chatbot Preview</span>
          </div>
          
          <div style={{ flex: 1, padding: '24px', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center', gap: '16px' }}>
            {chatbot?.status === 'ready' ? (
              <>
                <div style={{ width: '64px', height: '64px', borderRadius: '20px', background: 'linear-gradient(135deg, #00C6FF, #0072FF)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <MessageCircle size={32} color="#050816" />
                </div>
                <div>
                  <h4 style={{ fontSize: '18px', fontWeight: 700 }}>{chatbot.name}</h4>
                  <p style={{ fontSize: '14px', color: '#64748b' }}>Ready to assist your users.</p>
                </div>
                <button 
                  onClick={() => window.location.href = `/chat?chatbot_id=${chatbot.id}`}
                  style={{ padding: '10px 20px', borderRadius: '10px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', fontSize: '14px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}
                >
                  Open Full Chat <ArrowRight size={16} />
                </button>
              </>
            ) : (
              <div style={{ opacity: 0.3 }}>
                <Bot size={48} style={{ marginBottom: '12px' }} />
                <p>Preview will be available once ingestion is complete.</p>
              </div>
            )}
          </div>
        </section>

      </div>
    </div>
  );
}

function StatusStep({ icon: Icon, label, status }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      <div style={{ 
        width: '32px', height: '32px', borderRadius: '8px', 
        background: status === 'complete' ? 'rgba(16,185,129,0.1)' : 'rgba(255,255,255,0.03)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: status === 'complete' ? '#10B981' : '#64748b'
      }}>
        {status === 'loading' ? <Loader2 size={16} className="animate-spin" /> : <Icon size={16} />}
      </div>
      <span style={{ fontSize: '14px', color: status === 'idle' ? '#475569' : '#fff', fontWeight: status === 'complete' ? 600 : 400 }}>{label}</span>
      {status === 'complete' && <CheckCircle2 size={16} color="#10B981" style={{ marginLeft: 'auto' }} />}
    </div>
  );
}
