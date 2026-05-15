import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Globe, Upload, ArrowRight, Loader2, CheckCircle2, FileText, X } from 'lucide-react';
import { api } from '../api';
import { config } from '../config';

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
  const [backendMessage, setBackendMessage] = useState('Initializing...');
  const [progress, setProgress] = useState(0);
  const [counts, setCounts] = useState({ total: 0, current: 0 });
  const [error, setError] = useState('');

  // WebSocket real-time updates
  useEffect(() => {
    if (!chatbotId || status === 'ready' || status === 'error') return;

    let socket = null;
    let retryCount = 0;
    const MAX_RETRIES = 5;

    const connectWS = () => {
      const sessionId = Math.random().toString(36).substring(7);
      const token = localStorage.getItem('token');
      
      const wsUrl = `${config.wsBase}/ws/chat/${sessionId}${token ? `?token=${token}` : ''}`;
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        console.log('[WS] Connected for ingestion tracking');
        socket.send(JSON.stringify({ chatbot_id: chatbotId }));
      };

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'ingestion_event' && msg.chatbot_id === chatbotId) {
            const { event: evType, data } = msg;
            if (evType === 'progress' || evType === 'complete') {
              const stageMap = { 'discovery': 0, 'crawling': 0, 'extraction': 1, 'extracting': 1, 'chunking': 1, 'embedding': 2, 'indexing': 2, 'finalizing': 2, 'ready': 3, 'complete': 3 };
              setStage(stageMap[data.stage] ?? 0);
              
              const displayMessage = data.eta && data.eta !== 'calculating...' 
                ? `${data.message} (${data.eta})` 
                : data.message;
                
              setBackendMessage(displayMessage || 'Processing...');
              setProgress(data.progress || 0);
              setCounts({ 
                total: data.total_chunks || 0, 
                current: data.embeddings_completed || 0,
                pages: data.pages_crawled || 0,
                totalPages: data.total_pages || 0
              });
              
              if (data.stage === 'ready' || data.stage === 'complete') {
                setStatus('ready');
                setTimeout(() => navigate(`/chat/${chatbotId}`), 2500);
              }
            } else if (evType === 'failure') {
              setStatus('error');
              setError(`Ingestion Failed: ${data.message}`);
            }
          }
        } catch (err) {
          console.error('[WS] Message parse error:', err);
        }
      };

      socket.onclose = () => {
        if (status === 'ingesting' && retryCount < MAX_RETRIES) {
          retryCount++;
          setTimeout(connectWS, 2000);
        }
      };
    };

    connectWS();
    return () => socket?.close();
  }, [chatbotId, status, navigate]);

  // Poll chatbot status during ingestion (Fallback)
  useEffect(() => {
    if (!chatbotId || status === 'ready' || status === 'error') return;

    const startTime = Date.now();
    const TIMEOUT_MS = 10 * 60 * 1000; // 10 minutes

    const interval = setInterval(async () => {
      // 0. Safety Timeout
      if (Date.now() - startTime > TIMEOUT_MS) {
        setStatus('error');
        setError('Ingestion timed out after 10 minutes. Please check your network or try again.');
        clearInterval(interval);
        return;
      }

      try {
        const cb = await api(`/chatbots/${chatbotId}`);
        // Support both direct status_json and nested latest_job
        const job = cb.latest_job || {};
        const statusJson = job.status_json || cb.status_json || {};
        const currentStatus = job.status || cb.status;
        
        // Only update if not already set by WebSocket (avoid jumping)
        if (currentStatus === 'ready' || currentStatus === 'complete') {
          if (status !== 'ready') {
            setStatus('ready');
            setStage(3);
            setProgress(100);
            setBackendMessage('Ready');
            clearInterval(interval);
            setTimeout(() => navigate(`/chat/${chatbotId}`), 2500);
          }
        } else if (currentStatus === 'error' || statusJson.error) {
          setStatus('error');
          const exactReason = job.error_message || cb.error_message || statusJson.message || 'Unknown backend error';
          setError(`Ingestion Failed: ${exactReason}. Please verify the URL or try uploading files manually.`);
          clearInterval(interval);
        } else if (currentStatus === 'ingesting' || currentStatus === 'pending') {
          // Polling update (low priority compared to WS)
          const stageMap = { 'discovery': 0, 'crawling': 0, 'extraction': 1, 'extracting': 1, 'chunking': 1, 'indexing': 2, 'finalizing': 2, 'ready': 3, 'complete': 3, 'error': 0, 'failed': 0 };
          const backendStage = job.current_stage || statusJson.stage || 'discovery';
          setStage(stageMap[backendStage] ?? 0);
          setBackendMessage(statusJson.message || job.current_stage || 'Processing...');
          setProgress(job.progress || statusJson.progress || 0);
        }
      } catch (err) {
        console.warn('[POLL] Error polling chatbot status:', err);
      }
    }, 5000); // 5 seconds - even less aggressive fallback

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
        await fetch(`${config.apiBase}/api/chatbots/${chatbotId}/upload`, {
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
              <div>
                <p style={{ fontSize: '14px', fontWeight: 700 }}>
                  {status === 'ready' ? '✓ Chatbot Ready!' : status === 'error' ? '✕ Ingestion Failed' : backendMessage}
                </p>
                <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {counts.totalPages > 0 && `Pages: ${counts.pages}/${counts.totalPages} · `}
                  {counts.total > 0 && `Chunks: ${counts.current}/${counts.total}`}
                  {counts.total === 0 && counts.totalPages === 0 && 'Analyzing site structure...'}
                </p>
              </div>
              <span className={`badge ${status === 'ready' ? 'badge-green' : status === 'error' ? 'badge-red' : 'badge-amber badge-pulse'}`}>
                {status === 'ready' ? 'Complete' : status === 'error' ? 'Error' : STAGES[stage]}
              </span>
            </div>

            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${progress}%` }} />
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
