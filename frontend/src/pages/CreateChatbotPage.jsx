import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Globe, Upload, ArrowRight, Loader2, CheckCircle2, FileText, X } from 'lucide-react';
import { api } from '../api';

const STAGES = ['Crawling', 'Extracting', 'Indexing', 'Ready'];

export default function CreateChatbotPage() {
  const navigate = useNavigate();
  const fileRef = useRef(null);

  const [step, setStep] = useState(1);
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [chatbotId, setChatbotId] = useState(null);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState('idle'); // idle | creating | ingesting | ready | error
  const [stage, setStage] = useState(0);
  const [error, setError] = useState('');

  // Poll chatbot status during ingestion
  useEffect(() => {
    if (!chatbotId || status === 'ready' || status === 'error') return;

    const interval = setInterval(async () => {
      try {
        const cb = await api(`/chatbots/${chatbotId}`);
        if (cb.status === 'ingesting') {
          setStatus('ingesting');
          setStage(prev => Math.min(prev + 1, 2)); // progress through stages
        } else if (cb.status === 'ready') {
          setStatus('ready');
          setStage(3);
          clearInterval(interval);
          // Auto-redirect after 1.5s
          setTimeout(() => navigate(`/chat?chatbot_id=${chatbotId}`), 1500);
        } else if (cb.status === 'error') {
          setStatus('error');
          const exactReason = cb.error_message || 'Unknown backend error';
          setError(`Ingestion Failed: ${exactReason}. Please verify the URL or try uploading files manually.`);
          clearInterval(interval);
        }
      } catch { /* silent */ }
    }, 2000);

    return () => clearInterval(interval);
  }, [chatbotId, status, navigate]);

  const handleCreate = async () => {
    if (!url.trim()) return;
    setStatus('creating');
    setError('');
    try {
      const chatbot = await api('/chatbots', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim() || null, website_url: url.trim() })
      });
      setChatbotId(chatbot.id);
      setStatus('ingesting');
      setStage(0);
      setStep(2);
    } catch (err) {
      setStatus('error');
      setError(err.message || 'Failed to create chatbot.');
    }
  };

  const handleUpload = async (fileList) => {
    if (!chatbotId || !fileList.length) return;
    setUploading(true);
    for (const file of fileList) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        await fetch(`/api/chatbots/${chatbotId}/upload`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
          body: formData
        });
        setFiles(prev => [...prev, { name: file.name, status: 'done' }]);
      } catch {
        setFiles(prev => [...prev, { name: file.name, status: 'error' }]);
      }
    }
    setUploading(false);
  };

  const progressPercent = status === 'ready' ? 100 : status === 'ingesting' ? ((stage + 1) / STAGES.length) * 85 : 0;

  return (
    <div style={{ padding: '40px', maxWidth: '640px', margin: '0 auto' }}>
      <div style={{ marginBottom: '40px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '6px' }}>Create Chatbot</h1>
        <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Paste a website URL to generate a context-aware assistant.</p>
      </div>

      {/* Step 1: URL + Name */}
      {step === 1 && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass-panel" style={{ padding: '28px' }}>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px' }}>Website URL</label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
            <Globe size={18} color="var(--text-muted)" style={{ flexShrink: 0 }} />
            <input
              className="input"
              placeholder="https://example.com"
              value={url}
              onChange={e => setUrl(e.target.value)}
              autoFocus
            />
          </div>

          <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px' }}>Name (optional)</label>
          <input
            className="input"
            placeholder="Auto-generated from URL"
            value={name}
            onChange={e => setName(e.target.value)}
            style={{ marginBottom: '24px' }}
          />

          {error && <p style={{ color: 'var(--accent-red)', fontSize: '13px', marginBottom: '16px' }}>{error}</p>}

          <button
            onClick={handleCreate}
            disabled={!url.trim() || status === 'creating'}
            className="btn btn-primary"
            style={{ width: '100%', justifyContent: 'center', opacity: !url.trim() ? 0.4 : 1 }}
          >
            {status === 'creating' ? <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Creating...</> : <><ArrowRight size={16} /> Create & Start Ingestion</>}
          </button>
        </motion.div>
      )}

      {/* Step 2: Ingestion Progress + Optional Uploads */}
      {step === 2 && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          {/* Progress */}
          <div className="glass-panel" style={{ padding: '28px', marginBottom: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <p style={{ fontSize: '14px', fontWeight: 700 }}>
                {status === 'ready' ? '✓ Chatbot Ready!' : status === 'error' ? '✕ Ingestion Failed' : 'Processing Website...'}
              </p>
              <span className={`badge ${status === 'ready' ? 'badge-green' : status === 'error' ? 'badge-red' : 'badge-amber badge-pulse'}`}>
                {status === 'ready' ? 'Complete' : status === 'error' ? 'Error' : STAGES[stage]}
              </span>
            </div>

            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '16px' }}>
              {STAGES.map((s, i) => (
                <div key={s} style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px',
                  fontSize: '11px', fontWeight: 600, fontFamily: 'var(--font-mono)',
                  color: i <= stage ? 'var(--accent)' : 'var(--text-dim)',
                  flex: 1, textAlign: 'center'
                }}>
                  <span style={{ fontSize: '14px' }}>{i <= stage ? '✓' : '○'}</span>
                  <span>{s}</span>
                </div>
              ))}
            </div>

            {error && <p style={{ color: 'var(--accent-red)', fontSize: '13px', marginTop: '16px' }}>{error}</p>}
            
            {status === 'ready' && (
              <p style={{ color: 'var(--text-secondary)', fontSize: '13px', marginTop: '16px' }}>Redirecting to chat...</p>
            )}
          </div>

          {/* Optional File Upload */}
          <div className="glass-panel" style={{ padding: '28px' }}>
            <p style={{ fontSize: '14px', fontWeight: 700, marginBottom: '4px' }}>Upload Additional Files</p>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>Optional — add PDFs, DOCX, or text files for deeper grounding.</p>

            <div
              onClick={() => fileRef.current?.click()}
              style={{
                border: '2px dashed var(--border)', borderRadius: 'var(--radius-md)',
                padding: '32px', textAlign: 'center', cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
              onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
            >
              <Upload size={24} color="var(--text-muted)" style={{ margin: '0 auto 8px' }} />
              <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Click to browse · PDF, DOCX, TXT, MD</p>
              <input
                ref={fileRef}
                type="file"
                multiple
                accept=".pdf,.docx,.txt,.md"
                onChange={e => handleUpload(e.target.files)}
                style={{ display: 'none' }}
              />
            </div>

            {files.length > 0 && (
              <div style={{ marginTop: '16px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {files.map((f, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', padding: '6px 0' }}>
                    <FileText size={14} color={f.status === 'done' ? 'var(--accent-green)' : 'var(--accent-red)'} />
                    <span style={{ color: 'var(--text-secondary)' }}>{f.name}</span>
                    <CheckCircle2 size={14} color={f.status === 'done' ? 'var(--accent-green)' : 'var(--accent-red)'} style={{ marginLeft: 'auto' }} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </motion.div>
      )}
    </div>
  );
}
