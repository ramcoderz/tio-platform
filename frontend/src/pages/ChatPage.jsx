import { useEffect, useRef, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Send, Copy, Download, RotateCcw, Trash2,
  ChevronRight, FileText, Zap, Brain, Network,
  ExternalLink, X, Sparkles, Activity, Share2, 
  Archive, FolderPlus, MoreHorizontal, ChevronDown,
  Layout, Plus, Upload
} from 'lucide-react';
import { useChatStore, useDocumentStore } from '../store';
import { api } from '../api';
import { useAppCtx } from '../context/AppContext';

// ── Typing Indicator ────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '16px 20px' }}>
      <div style={{
        width: '32px', height: '32px', borderRadius: '50%',
        background: 'linear-gradient(135deg, var(--accent-violet), var(--accent-blue))',
        display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
      }}>
        <Brain size={14} color="#fff" />
      </div>
      <div className="glass-panel" style={{ padding: '12px 16px', borderRadius: '18px 18px 18px 4px' }}>
        <div className="typing-indicator" style={{ padding: 0 }}>
          <div className="typing-dot" />
          <div className="typing-dot" />
          <div className="typing-dot" />
        </div>
      </div>
    </div>
  );
}

// ── Source Card ──────────────────────────────────────────────────────────────
function SourceCard({ source, index, onClick, isActive }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.06 }}
      onClick={onClick}
      style={{
        padding: '14px',
        borderRadius: '12px',
        border: `1px solid ${isActive ? 'var(--border-blue)' : 'var(--border-glass)'}`,
        background: isActive ? 'rgba(37,99,235,0.08)' : 'rgba(255,255,255,0.02)',
        cursor: 'pointer',
        transition: 'all 0.15s ease',
        marginBottom: '8px',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
        <div style={{
          width: '28px', height: '28px', borderRadius: '8px', flexShrink: 0,
          background: 'var(--accent-blue-dim)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <FileText size={13} color="var(--accent-blue-light)" />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {source.document || source.chunk_id || `Source ${index + 1}`}
          </p>
          <p style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', lineHeight: 1.5 }}>
            {source.text || source.excerpt || ''}
          </p>
          {source.score != null && (
            <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <div style={{ flex: 1, height: '3px', background: 'rgba(255,255,255,0.08)', borderRadius: '2px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: `${Math.round(source.score * 100)}%`, background: 'linear-gradient(90deg, var(--accent-blue), var(--accent-cyan))', borderRadius: '2px' }} />
              </div>
              <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', flexShrink: 0 }}>
                {(source.score * 100).toFixed(0)}%
              </span>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}

// ── Intent Badge ─────────────────────────────────────────────────────────────
function IntentBadge({ intent }) {
  if (!intent || intent === 'simple') return null;
  const labels = {
    'conversational': 'Conversational',
    'document': 'Document Analysis',
    'research': 'Deep Research',
    'ocr': 'Visual Intelligence'
  };
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: 700, color: 'var(--accent-blue-light)', background: 'rgba(37,99,235,0.1)', border: '1px solid rgba(37,99,235,0.2)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
      {labels[intent] || intent}
    </span>
  );
}

// ── Confidence Badge ─────────────────────────────────────────────────────────
function ConfidenceBadge({ score }) {
  const pct = Math.round(score * 100);
  const color = pct >= 80 ? 'var(--accent-green)' : pct >= 60 ? 'var(--accent-yellow)' : 'var(--accent-red)';
  const bg   = pct >= 80 ? 'var(--accent-green-dim)' : pct >= 60 ? 'var(--accent-yellow-dim)' : 'var(--accent-red-dim)';
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '2px 8px', borderRadius: '999px', fontSize: '11px', fontWeight: 600, color, background: bg, border: `1px solid ${color}33`, marginTop: '8px' }}>
      <Activity size={10} /> {pct}% confidence
    </span>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────
export default function ChatPage() {
  const { messages, setMessages } = useChatStore();
  const { addUpload } = useDocumentStore();
  const { sessionId } = useChatStore();
  const [input, setInput]           = useState('');
  const [isTyping, setIsTyping]     = useState(false);
  const [activeSources, setActiveSources] = useState([]);
  const [activeSource, setActiveSource]   = useState(null);
  const [sidebarOpen, setSidebarOpen]     = useState(true);
  const wsRef      = useRef(null);
  const chatEndRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const [isUploading, setIsUploading] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  // ── WebSocket ──────────────────────────────────────────────────────────────
  const connectWS = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host === 'localhost:5173' ? 'localhost:8000' : window.location.host;
    console.log(`[WS] Connecting to: ${protocol}//${host}/ws/chat/${sessionId}`);
    const ws = new WebSocket(`${protocol}//${host}/ws/chat/${sessionId}`);
    wsRef.current = ws;

    ws.onopen = () => console.log("[WS] Connection established.");
    ws.onmessage = (event) => {
      console.log("[WS] Received raw data:", event.data);
      try {
        const data = JSON.parse(event.data);
        console.log("[WS] Parsed data:", data);

        if (data.type === 'metadata') {
          if (data.citations?.length) {
            setActiveSources(data.citations);
            setMessages(prev => {
              const last = prev[prev.length - 1];
              if (last?.role === 'assistant') {
                 return [...prev.slice(0, -1), { ...last, sources: data.citations }];
              }
              return prev;
            });
          }
        }

        if (data.type === 'thinking') {
          setIsTyping(true); // Keep typing indicator active during thinking
          // Optionally show thinking text in UI
        }

        if (data.type === 'token') {
          setIsTyping(false);
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant') {
              return [...prev.slice(0, -1), { ...last, content: last.content + data.content, _streaming: true }];
            }
            return [...prev, { role: 'assistant', content: data.content, _streaming: true }];
          });
        }

        if (data.type === 'final') {
          setIsTyping(false);
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant') {
              const updated = { 
                ...last, 
                content: data.answer || last.content,
                _streaming: false,
                sources: data.citations || last.sources,
                confidence: data.confidence,
                intent: data.intent
              };
              if (data.citations?.length) setActiveSources(data.citations);
              return [...prev.slice(0, -1), updated];
            }
            return prev;
          });
        }

        if (data.error) {
          setIsTyping(false);
          setMessages(prev => [...prev, { role: 'assistant', content: `⚠️ ${data.error}` }]);
        }
      } catch {/* ignore parse errors */}
    };

    ws.onerror = () => setIsTyping(false);
    ws.onclose = (e) => {
      if (e.wasClean) return; 
      setTimeout(() => connectWS(), 3000);
    };
  }, [sessionId, setMessages]);

  useEffect(() => {
    connectWS();
    return () => {
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on unmount
        wsRef.current.close();
      }
    };
  }, [connectWS]);

  // ── Scroll ─────────────────────────────────────────────────────────────────
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // ── Load History ───────────────────────────────────────────────────────────
  useEffect(() => {
    const loadHistory = async () => {
      if (!sessionId) return;
      try {
        const history = await api(`/chat/history/${sessionId}`);
        if (Array.isArray(history)) {
          setMessages(history);
          // Set sources from the last assistant message
          const lastAssistant = [...history].reverse().find(m => m.role === 'assistant');
          if (lastAssistant?.sources) {
            setActiveSources(lastAssistant.sources);
          }
        }
      } catch (err) {
        console.error("Failed to load chat history:", err);
      }
    };
    loadHistory();
  }, [sessionId, setMessages]);

  // ── Send ───────────────────────────────────────────────────────────────────
  const sendMessage = async () => {
    const text = input.trim();
    if (!text || isTyping) return;
    setInput('');
    setIsTyping(true);
    setMessages(prev => [...prev, { role: 'user', content: text }]);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ message: text, session_id: sessionId }));
    } else {
      // HTTP fallback
      try {
        const result = await api('/chat', { method: 'POST', body: JSON.stringify({ session_id: sessionId, message: text }) });
        setIsTyping(false);
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: result.answer,
          confidence: result.confidence,
          sources: result.citations,
        }]);
        if (result.citations?.length) setActiveSources(result.citations);
      } catch {
        setIsTyping(false);
        setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Failed to get a response. Please try again.' }]);
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  const handleFileUpload = async (files) => {
    const file = files[0];
    if (!file) return;
    
    setIsUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    // session_id is passed as query param only

    try {
      const token = localStorage.getItem("token");
      const url = `/api/documents/upload?session_id=${encodeURIComponent(sessionId || '')}`;
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          ...(token ? { "Authorization": `Bearer ${token}` } : {}),
        },
        body: formData
      });
      const result = await response.json();
      
      addUpload({
        id: result.document_id,
        name: file.name,
        type: file.type,
        size: file.size,
        chunks: result.chunks,
        isImage: file.type.startsWith('image/'),
        summary: result.summary,
      });

      setMessages(prev => [...prev, { 
        role: 'system', 
        content: `📎 File "${file.name}" uploaded and indexed successfully.` 
      }]);
    } catch (err) {
      console.error("Upload failed:", err);
      setMessages(prev => [...prev, { role: 'system', content: `❌ Failed to upload "${file.name}".` }]);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files?.length) {
      handleFileUpload(e.dataTransfer.files);
    }
  };

  const copyMessage = (text) => navigator.clipboard.writeText(text).catch(() => {});
  const clearChat   = () => { setMessages([]); setActiveSources([]); setActiveSource(null); };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>

      {/* ── Chat Pane ── */}
      <div 
        onDragOver={e => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0, position: 'relative' }}
      >
        <AnimatePresence>
          {isDragging && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              style={{
                position: 'absolute', inset: 0, zIndex: 100,
                background: 'rgba(5,8,22,0.85)', backdropFilter: 'blur(10px)',
                display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                border: '2px dashed var(--accent-blue)', margin: '12px', borderRadius: '24px',
                pointerEvents: 'none'
              }}
            >
              <div style={{ width: '80px', height: '80px', borderRadius: '24px', background: 'var(--accent-blue-dim)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '20px' }}>
                <Upload size={40} color="var(--accent-blue-light)" />
              </div>
              <h2 style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-primary)' }}>Drop to Ingest Document</h2>
              <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>PDF, DOCX, CSV, Image, TXT, MD</p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Toolbar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 24px', borderBottom: '1px solid var(--border-glass)', background: 'rgba(5,8,22,0.6)', backdropFilter: 'blur(12px)', zIndex: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-green)', boxShadow: '0 0 8px var(--accent-green)', animation: 'pulse-green 2s infinite' }} />
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)' }}>Research Intelligence Session</span>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{sessionId?.slice(0, 16)}</span>
              </div>
            </div>
            <div style={{ height: '24px', width: '1px', background: 'var(--border-glass)' }} />
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={() => {}} className="btn-ghost btn btn-sm" style={{ gap: '6px' }} title="Share Research">
              <Share2 size={13} /> Share
            </button>
            <button onClick={() => {}} className="btn-ghost btn btn-sm" style={{ gap: '6px' }} title="Archive Session">
              <Archive size={13} />
            </button>
            <div style={{ width: '1px', height: '20px', background: 'var(--border-glass)', margin: '0 4px' }} />
            <button onClick={clearChat} title="Clear workspace" className="btn-ghost btn btn-sm" style={{ gap: '6px', color: 'var(--accent-red)' }}>
              <Trash2 size={13} />
            </button>
            <button
              onClick={() => setSidebarOpen(p => !p)}
              className="btn-ghost btn btn-sm"
              style={{ gap: '6px' }}
            >
              <Network size={13} />
            </button>
          </div>
        </div>

        {/* Messages & Input Area */}
        <div 
          className="scroll-area custom-scrollbar" 
          style={{ 
            flex: 1, 
            display: 'flex', 
            flexDirection: 'column',
            justifyContent: messages.length === 0 ? 'center' : 'flex-start',
            transition: 'all 0.5s cubic-bezier(0.4, 0, 0.2, 1)'
          }}
        >
          <div style={{ 
            width: '100%', 
            maxWidth: '900px', 
            margin: '0 auto', 
            padding: messages.length === 0 ? '0 24px 60px' : '24px 24px 100px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            {messages.length === 0 && (
              <motion.div 
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                style={{ textAlign: 'center', marginBottom: '48px' }}
              >
                <div style={{ 
                  width: '64px', height: '64px', borderRadius: '20px', 
                  background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', 
                  margin: '0 auto 24px', boxShadow: '0 0 30px rgba(37,99,235,0.3)'
                }}>
                  <Zap size={32} color="#050816" />
                </div>
                <h1 style={{ fontSize: '32px', fontWeight: 800, letterSpacing: '-0.03em', marginBottom: '12px' }}>
                  What shall we research today?
                </h1>
                <p style={{ fontSize: '15px', color: 'var(--text-secondary)', maxWidth: '500px', margin: '0 auto 40px' }}>
                  Select a research project or start a new intelligence session to explore your knowledge assets.
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', maxWidth: '600px', margin: '0 auto' }}>
                  {[
                    { icon: Sparkles, text: "Summarize recent papers on CRISPR", color: "var(--accent-cyan)" },
                    { icon: Brain, text: "Analyze architecture of the new API", color: "var(--accent-violet)" },
                    { icon: Network, text: "Compare Q2 reports for anomalies", color: "var(--accent-blue)" },
                    { icon: Activity, text: "Monitor intelligence feed for LLM updates", color: "var(--accent-green)" },
                  ].map((s, i) => (
                    <motion.button
                      key={i}
                      whileHover={{ y: -2, background: 'rgba(255,255,255,0.04)', borderColor: s.color }}
                      onClick={() => setInput(s.text)}
                      style={{ 
                        padding: '16px', borderRadius: '16px', background: 'rgba(255,255,255,0.02)', 
                        border: '1px solid var(--border-glass)', textAlign: 'left', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: '12px', transition: 'all 0.2s ease'
                      }}
                    >
                      <s.icon size={16} color={s.color} />
                      <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)' }}>{s.text}</span>
                    </motion.button>
                  ))}
                </div>
              </motion.div>
            )}

            <AnimatePresence initial={false}>
              {messages.map((msg, i) => {
                if (msg.role === 'system') {
                  return (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      style={{ textAlign: 'center', margin: '12px 0', padding: '0 20px' }}
                    >
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600, background: 'rgba(255,255,255,0.03)', padding: '4px 12px', borderRadius: '12px', border: '1px solid var(--border-glass)' }}>
                        {msg.content}
                      </span>
                    </motion.div>
                  );
                }
                return (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.25 }}
                    style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: '16px' }}
                  >
                    {/* Avatar for assistant */}
                    {msg.role === 'assistant' && (
                      <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'linear-gradient(135deg, var(--accent-violet), var(--accent-blue))', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginRight: '10px', marginTop: '4px' }}>
                        <Brain size={14} color="#fff" />
                      </div>
                    )}

                    <div style={{ maxWidth: '85%' }}>
                      {/* Bubble */}
                      <div style={{
                        padding: '14px 18px',
                        borderRadius: msg.role === 'user' ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
                        background: msg.role === 'user'
                          ? 'linear-gradient(135deg, var(--accent-blue), #1d4ed8)'
                          : 'rgba(255,255,255,0.04)',
                        border: msg.role === 'user' ? 'none' : '1px solid var(--border-glass)',
                        color: 'var(--text-primary)',
                        fontSize: '14px',
                        lineHeight: 1.65,
                      }}>
                        {msg.role === 'assistant' ? (
                          <div className="prose">
                            <div style={{ marginBottom: '8px', display: 'flex', justifyContent: 'flex-end' }}>
                              <IntentBadge intent={msg.intent} />
                            </div>
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                          </div>
                        ) : (
                          <p>{msg.content}</p>
                        )}
                      </div>

                      {/* Meta row */}
                      {msg.role === 'assistant' && !msg._streaming && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px', paddingLeft: '4px', flexWrap: 'wrap' }}>
                          {msg.confidence != null && <ConfidenceBadge score={msg.confidence} />}
                          {msg.sources?.length > 0 && (
                            <button
                              onClick={() => { setActiveSources(msg.sources); setSidebarOpen(true); }}
                              style={{ fontSize: '11px', color: 'var(--accent-cyan)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '3px' }}
                            >
                              <ExternalLink size={10} /> {msg.sources.length} sources
                            </button>
                          )}
                          <button onClick={() => copyMessage(msg.content)} style={{ fontSize: '11px', color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '3px' }}>
                            <Copy size={10} /> copy
                          </button>
                        </div>
                      )}
                    </div>
                  </motion.div>
                );
              })}
            </AnimatePresence>

            {isTyping && <TypingIndicator />}
            <div ref={chatEndRef} />
            
            {/* Input Bar (Inside scroll for centered start, or sticky bottom) */}
            <div style={{ 
              marginTop: messages.length === 0 ? '0' : '20px',
              position: messages.length === 0 ? 'relative' : 'sticky',
              bottom: messages.length === 0 ? '0' : '24px',
              zIndex: 5,
              width: '100%',
              background: messages.length === 0 ? 'transparent' : 'rgba(5,8,22,0.8)',
              backdropFilter: messages.length === 0 ? 'none' : 'blur(12px)',
              borderRadius: '20px',
              padding: messages.length === 0 ? '0' : '4px'
            }}>
              <div className="glass-panel" style={{ display: 'flex', alignItems: 'flex-end', gap: '10px', padding: '8px 8px 8px 16px', borderRadius: '16px', boxShadow: '0 10px 40px rgba(0,0,0,0.4)' }}>
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={e => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Ask anything about your documents…"
                  rows={1}
                  style={{
                    flex: 1, background: 'transparent', border: 'none', outline: 'none', resize: 'none',
                    color: 'var(--text-primary)', fontSize: '15px', lineHeight: 1.6, maxHeight: '160px',
                    overflowY: 'auto', paddingTop: '10px', paddingBottom: '10px', fontFamily: 'var(--font-sans)',
                  }}
                  onInput={e => { e.target.style.height = 'auto'; e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px'; }}
                  className="custom-scrollbar"
                />
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingBottom: '4px' }}>
                    <input
                      type="file"
                      ref={fileInputRef}
                      onChange={e => handleFileUpload(e.target.files)}
                      style={{ display: 'none' }}
                    />
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploading}
                    title="Add files & images"
                    style={{
                      width: '40px', height: '40px', borderRadius: '12px',
                      background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-glass)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: isUploading ? 'var(--accent-blue)' : 'var(--text-muted)',
                      cursor: isUploading ? 'not-allowed' : 'pointer',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <Plus size={18} className={isUploading ? "animate-pulse" : ""} />
                  </button>
                  
                  <button
                    onClick={sendMessage}
                    disabled={!input.trim() || isTyping}
                    style={{
                      width: '44px', height: '44px', borderRadius: '12px', flexShrink: 0,
                      background: input.trim() && !isTyping ? 'linear-gradient(135deg, var(--accent-blue), var(--accent-cyan))' : 'rgba(255,255,255,0.06)',
                      border: 'none', cursor: input.trim() && !isTyping ? 'pointer' : 'not-allowed',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: input.trim() && !isTyping ? '#050816' : 'var(--text-muted)',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <Send size={18} />
                  </button>
                </div>
              </div>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '10px', textAlign: 'center', opacity: 0.7 }}>
                Enter to send · Shift+Enter for new line · AI may hallucinate
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ── Intelligence Sidebar ── */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 340, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            style={{ borderLeft: '1px solid var(--border-glass)', background: 'rgba(5,8,22,0.75)', backdropFilter: 'blur(16px)', display: 'flex', flexDirection: 'column', overflow: 'hidden', flexShrink: 0 }}
          >
            <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
              {/* Sidebar Header */}
              <div style={{ padding: '16px 18px', borderBottom: '1px solid var(--border-glass)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Sparkles size={14} color="var(--accent-cyan)" />
                  <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    Source Intelligence
                  </span>
                </div>
                <button onClick={() => setSidebarOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: '4px' }}>
                  <X size={14} />
                </button>
              </div>

              {/* Sources */}
              <div className="scroll-area" style={{ flex: 1, padding: '14px' }}>
                {activeSources.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '40px 16px', color: 'var(--text-muted)' }}>
                    <Network size={32} style={{ margin: '0 auto 12px', opacity: 0.3 }} />
                    <p style={{ fontSize: '12px', lineHeight: 1.6 }}>Sources will appear here after your first query</p>
                  </div>
                ) : (
                  activeSources.map((src, i) => (
                    <SourceCard
                      key={i}
                      source={src}
                      index={i}
                      isActive={activeSource === i}
                      onClick={() => setActiveSource(activeSource === i ? null : i)}
                    />
                  ))
                )}

                {/* Expanded source detail */}
                <AnimatePresence>
                  {activeSource != null && activeSources[activeSource] && (
                    <motion.div
                      initial={{ opacity: 0, height: 0 }}
                      animate={{ opacity: 1, height: 'auto' }}
                      exit={{ opacity: 0, height: 0 }}
                      className="glass-panel"
                      style={{ padding: '14px', marginTop: '8px', borderColor: 'var(--border-blue)' }}
                    >
                      <p style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.7 }}>
                        {activeSources[activeSource].text}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* Agent activity strip */}
              <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border-glass)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Activity size={12} color="var(--accent-blue-light)" />
                <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                  {isTyping ? 'Orchestrating agents…' : 'Ready'}
                </span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
