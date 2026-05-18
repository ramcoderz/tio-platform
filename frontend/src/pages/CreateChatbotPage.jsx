import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Globe, Upload, ArrowRight, Loader2, CheckCircle2,
  FileText, X, Zap, Brain, Database, Search, Layers,
  AlertCircle, ChevronRight, Terminal
} from 'lucide-react';
import { api } from '../api';
import { config } from '../config';

// Full 8-stage deterministic lifecycle
const STAGES = [
  { key: 'crawling',   label: 'Crawling',   icon: Globe,    desc: 'Discovering pages & documents' },
  { key: 'extracting', label: 'Extracting', icon: FileText, desc: 'Parsing text content' },
  { key: 'parsing',    label: 'Parsing',    icon: Brain,    desc: 'Processing documents & resumes' },
  { key: 'chunking',   label: 'Chunking',   icon: Layers,   desc: 'Section-aware text splitting' },
  { key: 'embedding',  label: 'Embedding',  icon: Zap,      desc: 'Generating semantic vectors' },
  { key: 'indexing',   label: 'Indexing',   icon: Database, desc: 'Building retrieval index' },
  { key: 'optimising', label: 'Optimising', icon: Search,   desc: 'Cross-encoder reranking' },
  { key: 'ready',      label: 'Ready',      icon: CheckCircle2, desc: 'Knowledge base complete' },
];

const STAGE_MAP = {
  discovery: 0, crawling: 0,
  extraction: 1, extracting: 1,
  parsing_documents: 2, parsing: 2,
  chunking: 3,
  embedding: 4,
  indexing: 5,
  optimising: 6, finalizing: 6,
  ready: 7, complete: 7,
};

export default function CreateChatbotPage() {
  const navigate = useNavigate();
  const fileRef = useRef(null);

  const [step, setStep] = useState(1);
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [chatbotId, setChatbotId] = useState(null);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState('idle');
  const [stageIdx, setStageIdx] = useState(0);
  const [backendMessage, setBackendMessage] = useState('Initializing...');
  const [progress, setProgress] = useState(0);
  const [counts, setCounts] = useState({ pages: 0, totalPages: 0, current: 0, total: 0 });
  const [error, setError] = useState('');
  const [eta, setEta] = useState('');
  const [terminalLogs, setTerminalLogs] = useState([]);

  const wsRef = useRef(null);
  const isConnecting = useRef(false);
  const redirected = useRef(false);
  const terminalRef = useRef(null);

  // Auto-scroll terminal logs
  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTo({ top: terminalRef.current.scrollHeight, behavior: 'smooth' });
    }
  }, [terminalLogs]);

  // ── WebSocket real-time ingestion tracker ──────────────────────────────
  useEffect(() => {
    if (!chatbotId || status === 'ready' || status === 'error') return;

    let retryCount = 0;
    const MAX_RETRIES = 5;

    const connectWS = () => {
      if (isConnecting.current || wsRef.current?.readyState === WebSocket.OPEN) return;
      isConnecting.current = true;
      const sessionId = `ingest-${chatbotId}-${Math.random().toString(36).slice(2, 7)}`;
      const token = localStorage.getItem('token') || '';
      const wsUrl = `${config.wsBase}/ws/chat/${sessionId}${token ? `?token=${encodeURIComponent(token)}` : ''}`;

      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); }

      console.info(`[WS-Ingestion] Connecting session=${sessionId} for chatbot=${chatbotId}`);
      try {
        const socket = new WebSocket(wsUrl);
        wsRef.current = socket;

      socket.onopen = () => {
        isConnecting.current = false;
        console.log('[WS-Ingestion] Connected. Registering chatbot interest...');
        socket.send(JSON.stringify({ chatbot_id: chatbotId }));
      };

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          console.log("[WS RAW]", msg);
          
          if (msg.type === 'ingestion_event' && String(msg.chatbot_id) === String(chatbotId)) {
            const { event: evType, data } = msg;
            const timestamp = new Date().toLocaleTimeString();
            
            // Console Ingestion Observability Logs
            console.log("%c[INGESTION] Realtime ingestion update received", "color: #3b82f6; font-weight: bold;");
            
            // 1. Granular Telemetry Terminal logs
            if (evType === 'crawler_status') {
               if (data.type === 'document_detected' || data.document) {
                 setTerminalLogs(prev => [...prev, { time: timestamp, text: `[DOCUMENT] ${data.document || 'Document'} detected`, color: 'text-purple-400' }]);
               } else {
                 setTerminalLogs(prev => [...prev, { time: timestamp, text: `[CRAWLER] ${data.stage || 'Crawling...'}`, color: 'text-emerald-400' }]);
               }
            } else if (evType === 'crawl_progress') {
               setTerminalLogs(prev => [...prev, { time: timestamp, text: `[CRAWLER] Fetching: ${data.url || ''} (${data.pages_crawled}/${data.pages_total})`, color: 'text-emerald-400' }]);
            } else if (evType === 'parser_progress') {
               setTerminalLogs(prev => [...prev, { time: timestamp, text: `[PARSER] Extracted: ${data.document || ''}`, color: 'text-purple-400' }]);
            } else if (evType === 'document_detected') {
               setTerminalLogs(prev => [...prev, { time: timestamp, text: `[DOCUMENT] ${data.document} detected`, color: 'text-purple-400' }]);
            } else if (evType === 'embedding_progress') {
               const current = data.current || data.chunk_num || 0;
               const total = data.total || data.total_chunks || 0;
               setTerminalLogs(prev => [...prev, { time: timestamp, text: `[EMBEDDING] Embedded batch: ${current}/${total} chunks`, color: 'text-amber-400' }]);
            } else if (evType === 'vector_progress') {
               setTerminalLogs(prev => [...prev, { time: timestamp, text: `[VECTORSTORE] Inserted ${data.inserted_vectors || 0} vectors into ${data.collection || 'index'}`, color: 'text-pink-400' }]);
            }
            
            // 2. Main System progress logging (STAGES tracker)
            if (evType === 'progress' || evType === 'complete') {
              const stageMsg = data.message || STAGES[STAGE_MAP[data.stage] ?? stageIdx]?.desc || 'Processing...';
              setTerminalLogs(prev => {
                const newLog = { time: timestamp, text: `[SYSTEM] ${stageMsg}`, color: 'text-zinc-300' };
                if (prev.length === 0 || prev[prev.length - 1].text !== newLog.text) {
                  return [...prev, newLog];
                }
                return prev;
              });
              
              const idx = STAGE_MAP[data.stage] ?? stageIdx;
              setStageIdx(idx);
              setBackendMessage(stageMsg);
              setProgress(data.progress || Math.round(((idx + 1) / STAGES.length) * 90));
              setEta(data.eta && data.eta !== 'calculating...' ? data.eta : '');
              setCounts({
                pages: data.pages_crawled || 0,
                totalPages: data.total_pages || 0,
                current: data.embeddings_completed || data.current || 0,
                total: data.total_chunks || data.total || 0,
              });

              if (data.stage === 'ready' || data.stage === 'complete') {
                handleReady();
              }
            } else if (evType === 'failure') {
              setStatus('error');
              setError(`Ingestion Failed: ${data.message}`);
              setTerminalLogs(prev => [...prev, { time: timestamp, text: `[FAILURE] Ingestion failed: ${data.message}`, color: 'text-red-400' }]);
            }
          }
        } catch (err) {
          console.error('[WS-Ingestion] Parse error:', err);
        }
      };
 
       socket.onclose = (e) => {
         isConnecting.current = false;
         console.warn(`[WS-Ingestion] Closed Code=${e.code}`);
         if (status === 'ingesting' && retryCount < MAX_RETRIES) {
           retryCount++;
           setTimeout(connectWS, 3000 * retryCount);
         }
       };
 
       socket.onerror = () => { isConnecting.current = false; };
      } catch (err) {
        isConnecting.current = false;
        console.error('[WS-Ingestion] Failed to initialize WebSocket:', err);
        if (status === 'ingesting' && retryCount < MAX_RETRIES) {
          retryCount++;
          setTimeout(connectWS, 4000 * retryCount);
        }
      }
     };
 
     connectWS();
     return () => {
       if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); wsRef.current = null; }
     };
   // eslint-disable-next-line react-hooks/exhaustive-deps
   }, [chatbotId, status]);
 
   // ── HTTP poll fallback ─────────────────────────────────────────────────
   useEffect(() => {
     if (!chatbotId || status === 'ready' || status === 'error') return;
 
     const startTime = Date.now();
     const TIMEOUT_MS = 12 * 60 * 1000;
 
     const interval = setInterval(async () => {
       // REDUCE FRONTEND POLLING SPAM: Skip HTTP requests if WebSocket is active and connected
       if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
         return;
       }

       if (Date.now() - startTime > TIMEOUT_MS) {
         setStatus('error');
         setError('Ingestion timed out after 12 minutes.');
         clearInterval(interval);
         return;
       }
       try {
         const cb = await api(`/chatbots/${chatbotId}`);
          window._cbPollFailures = 0;
         const job = cb.latest_job || {};
         const currentStatus = job.status || cb.status;
         if (currentStatus === 'ready' || currentStatus === 'complete') {
           clearInterval(interval);
           handleReady();
         } else if (currentStatus === 'error' || currentStatus === 'failed') {
           clearInterval(interval);
           setStatus('error');
           setError(job.error_message || cb.error_message || 'Backend ingestion error.');
         } else {
           const idx = STAGE_MAP[job.current_stage || 'crawling'] ?? stageIdx;
           setStageIdx(idx);
           setBackendMessage(job.status_json?.message || STAGES[idx]?.desc || 'Processing...');
           setProgress(job.progress || Math.round(((idx + 1) / STAGES.length) * 90));
         }
       } catch (err) {
         window._cbPollFailures = (window._cbPollFailures || 0) + 1;
          if (window._cbPollFailures >= 3) {
            console.warn('[POLL] Status check failed persistently:', err);
          }
       }
     }, 5000);
 
     return () => clearInterval(interval);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatbotId, status]);

  const handleReady = () => {
    if (redirected.current) return;
    redirected.current = true;
    setStatus('ready');
    setStageIdx(7);
    setProgress(100);
    setBackendMessage('Knowledge base ready!');
    // ── PART 3: Auto-open chatbot directly ──
    console.info(`[INGESTION] Complete. Auto-routing to /chat?chatbot_id=${chatbotId}`);
    setTimeout(() => navigate(`/chat?chatbot_id=${chatbotId}`), 2200);
  };

  const handleCreate = async () => {
    if (!url.trim()) return;
    setStatus('creating');
    setError('');
    redirected.current = false;
    try {
      const chatbot = await api('/chatbots', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim() || null, website_url: url.trim() }),
      });
      setChatbotId(chatbot.id);
      setStatus('ingesting');
      setStageIdx(0);
      setProgress(0);
      setStep(2);
      console.info(`[INGESTION] Started chatbot_id=${chatbot.id}`);
    } catch (err) {
      setStatus('error');
      setError(err.message || 'Failed to create chatbot.');
    }
  };

  const handleUpload = async (fileList) => {
    if (!chatbotId || !fileList?.length) return;
    setUploading(true);
    for (const file of Array.from(fileList)) {
      const formData = new FormData();
      formData.append('file', file);
      try {
        await fetch(`${config.apiBase}/api/chatbots/${chatbotId}/upload`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
          body: formData,
        });
        setFiles(prev => [...prev, { name: file.name, status: 'done' }]);
      } catch {
        setFiles(prev => [...prev, { name: file.name, status: 'error' }]);
      }
    }
    setUploading(false);
  };

  const currentStage = STAGES[stageIdx] || STAGES[0];
  const StageIcon = currentStage.icon;

  return (
    <div style={{ padding: '40px', maxWidth: '660px', margin: '0 auto' }}>
      <div style={{ marginBottom: '40px' }}>
        <h1 style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '6px' }}>
          Create Chatbot
        </h1>
        <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
          Paste a website URL to generate a context-aware organizational intelligence assistant.
        </p>
      </div>

      {/* ── Step 1: URL + Name ── */}
      {step === 1 && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="glass-panel" style={{ padding: '28px' }}>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px' }}>
            Website URL
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
            <Globe size={18} color="var(--text-muted)" style={{ flexShrink: 0 }} />
            <input
              className="input"
              placeholder="https://example.com"
              value={url}
              onChange={e => setUrl(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && url.trim() && handleCreate()}
              autoFocus
            />
          </div>

          <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px' }}>
            Name (optional)
          </label>
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
            {status === 'creating'
              ? <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} /> Creating...</>
              : <><ArrowRight size={16} /> Create &amp; Start Ingestion</>}
          </button>
        </motion.div>
      )}

      {/* ── Step 2: Full Ingestion Visualizer ── */}
      {step === 2 && (
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>

          {/* Main progress card */}
          <div className="glass-panel" style={{ padding: '28px', marginBottom: '20px' }}>

            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                  {status === 'ready' ? (
                    <CheckCircle2 size={20} color="var(--accent-green)" />
                  ) : status === 'error' ? (
                    <AlertCircle size={20} color="var(--accent-red)" />
                  ) : (
                    <StageIcon size={20} color="var(--accent)" style={{ animation: status === 'ingesting' ? 'pulse 2s ease-in-out infinite' : 'none' }} />
                  )}
                  <p style={{ fontSize: '15px', fontWeight: 700 }}>
                    {status === 'ready' ? '✓ Knowledge Base Ready!' : status === 'error' ? 'Ingestion Failed' : backendMessage}
                  </p>
                </div>
                <p style={{ fontSize: '11px', color: 'var(--text-muted)', paddingLeft: '30px' }}>
                  {counts.totalPages > 0 && `Pages: ${counts.pages}/${counts.totalPages} · `}
                  {counts.total > 0 && `Chunks: ${counts.current}/${counts.total}`}
                  {counts.total === 0 && counts.totalPages === 0 && 'Analyzing site structure...'}
                  {eta && ` · ETA: ${eta}`}
                </p>
              </div>
              <span className={`badge ${status === 'ready' ? 'badge-green' : status === 'error' ? 'badge-red' : 'badge-amber badge-pulse'}`} style={{ flexShrink: 0 }}>
                {status === 'ready' ? 'Complete' : status === 'error' ? 'Error' : currentStage.label}
              </span>
            </div>

            {/* Progress bar */}
            <div className="progress-bar" style={{ marginBottom: '24px', height: '6px' }}>
              <motion.div
                className="progress-fill"
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
                style={{ height: '100%' }}
              />
            </div>

            {/* 8-stage pipeline visual */}
            <div style={{ display: 'flex', gap: '4px', overflowX: 'auto', paddingBottom: '4px' }}>
              {STAGES.map((s, i) => {
                const Icon = s.icon;
                const isDone = i < stageIdx || status === 'ready';
                const isActive = i === stageIdx && status === 'ingesting';
                return (
                  <div
                    key={s.key}
                    title={s.desc}
                    style={{
                      flex: 1, minWidth: '60px',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '5px',
                      padding: '8px 4px', borderRadius: '10px',
                      background: isActive ? 'rgba(0,198,255,0.1)' : isDone ? 'rgba(0,198,255,0.05)' : 'transparent',
                      border: `1px solid ${isActive ? 'rgba(0,198,255,0.4)' : isDone ? 'rgba(0,198,255,0.15)' : 'transparent'}`,
                      transition: 'all 0.3s',
                    }}
                  >
                    <Icon
                      size={14}
                      color={isDone || isActive ? 'var(--accent)' : 'var(--text-dim)'}
                    />
                    <span style={{
                      fontSize: '9px', fontWeight: 600, fontFamily: 'var(--font-mono)',
                      color: isDone || isActive ? 'var(--accent)' : 'var(--text-dim)',
                      textAlign: 'center', lineHeight: 1.2,
                      textTransform: 'uppercase', letterSpacing: '0.04em'
                    }}>
                      {s.label}
                    </span>
                    {i < STAGES.length - 1 && (
                      <ChevronRight size={8} color={isDone ? 'var(--accent)' : 'var(--text-dim)'} style={{ position: 'absolute', right: '-4px', top: '12px' }} />
                    )}
                  </div>
                );
              })}
            </div>

            {error && (
              <div style={{ marginTop: '16px', padding: '12px 16px', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: '10px' }}>
                <p style={{ color: 'var(--accent-red)', fontSize: '13px' }}>{error}</p>
              </div>
            )}

            {/* LIVE INGESTION TERMINAL PANEL */}
            <div 
              style={{
                marginTop: '24px',
                background: '#0a0a0a',
                border: '1px solid #27272a',
                borderRadius: '8px',
                height: '250px',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden'
              }}
            >
              <div style={{ background: '#18181b', padding: '6px 12px', borderBottom: '1px solid #27272a', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Terminal size={14} color="#a1a1aa" />
                <span style={{ fontSize: '12px', color: '#a1a1aa', fontFamily: 'var(--font-mono)' }}>ingestion_telemetry.log</span>
              </div>
              <div 
                ref={terminalRef}
                style={{
                  flex: 1,
                  padding: '12px',
                  overflowY: 'auto',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11.5px',
                  lineHeight: '1.6',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px'
                }}
              >
                {terminalLogs.map((log, i) => {
                  let hexColor = '#d4d4d8';
                  if (log.color === 'text-emerald-400') hexColor = '#10b981';
                  else if (log.color === 'text-amber-400') hexColor = '#fbbf24';
                  else if (log.color === 'text-pink-400') hexColor = '#f472b6';
                  else if (log.color === 'text-purple-400') hexColor = '#c084fc';
                  else if (log.color === 'text-red-400') hexColor = '#f87171';
                  
                  return (
                    <div key={i} style={{ display: 'flex', gap: '8px' }}>
                      <span style={{ color: '#52525b', flexShrink: 0 }}>[{log.time}]</span>
                      <span style={{ color: hexColor }}>{log.text}</span>
                    </div>
                  );
                })}
                {status !== 'ready' && status !== 'error' && (
                  <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                    <span style={{ color: '#52525b' }}>[{new Date().toLocaleTimeString()}]</span>
                    <span style={{ color: '#10b981', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{
                        width: '6px',
                        height: '12px',
                        background: '#10b981',
                        display: 'inline-block',
                        opacity: 0.8,
                        animation: 'pulse 1.5s infinite'
                      }} />
                      {terminalLogs.length === 0 ? "Waiting for telemetry stream..." : "Listening for live backend events..."}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {status === 'ready' && (
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                style={{ marginTop: '16px', padding: '12px 16px', background: 'rgba(0,198,255,0.08)', border: '1px solid rgba(0,198,255,0.25)', borderRadius: '10px', display: 'flex', alignItems: 'center', gap: '10px' }}
              >
                <Loader2 size={14} color="var(--accent)" style={{ animation: 'spin 1s linear infinite' }} />
                <p style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
                  Opening your chatbot...
                </p>
              </motion.div>
            )}
          </div>

          {/* Optional File Upload panel */}
          <AnimatePresence>
            {status !== 'ready' && (
              <motion.div
                initial={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="glass-panel"
                style={{ padding: '24px' }}
              >
                <p style={{ fontSize: '14px', fontWeight: 700, marginBottom: '4px' }}>Upload Additional Files</p>
                <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '16px' }}>
                  Optional — add PDFs, DOCX, or text files for deeper document grounding.
                </p>

                <div
                  onClick={() => fileRef.current?.click()}
                  style={{
                    border: '2px dashed var(--border)', borderRadius: 'var(--radius-md)',
                    padding: '28px', textAlign: 'center', cursor: 'pointer', transition: 'all 0.2s'
                  }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
                  onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
                >
                  <Upload size={22} color="var(--text-muted)" style={{ margin: '0 auto 8px' }} />
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                    Click to browse · PDF, DOCX, TXT, MD
                  </p>
                  <input ref={fileRef} type="file" multiple accept=".pdf,.docx,.txt,.md" onChange={e => handleUpload(e.target.files)} style={{ display: 'none' }} />
                </div>

                {uploading && (
                  <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-muted)' }}>
                    <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> Uploading...
                  </div>
                )}

                {files.length > 0 && (
                  <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {files.map((f, i) => (
                      <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                        <FileText size={14} color={f.status === 'done' ? 'var(--accent-green)' : 'var(--accent-red)'} />
                        <span style={{ color: 'var(--text-secondary)', flex: 1 }}>{f.name}</span>
                        <CheckCircle2 size={14} color={f.status === 'done' ? 'var(--accent-green)' : 'var(--accent-red)'} />
                      </div>
                    ))}
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </div>
  );
}
