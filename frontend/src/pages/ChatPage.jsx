import { useEffect, useRef, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import { useSearchParams } from 'react-router-dom';
import {
  Send, Bot, FileText, X, Sparkles,
  Plus, Mic, Download, ChevronDown, Layers
} from 'lucide-react';
import { useChatStore } from '../store';
import { api } from '../api';
import SkillsMenu from '../components/SkillsMenu';

const DOMAIN_SUGGESTIONS = {
  tourism: ['Plan my trip', 'Top attractions', 'Food & dining', 'Travel tips'],
  education: ['Find courses', 'Admissions info', 'Scholarships', 'Campus life'],
  medical: ['Book appointment', 'Find a doctor', 'Insurance info', 'Departments'],
  developer: ['API reference', 'Authentication', 'Code examples', 'SDK setup'],
  ecommerce: ['Product search', 'Compare items', 'Return policy', 'Track order'],
  general: ['What can you help with?', 'Summarize the website', 'Tell me more'],
};

const DOMAIN_COLORS = {
  tourism: { bg: 'rgba(52,211,153,0.12)', color: '#34D399' },
  medical: { bg: 'rgba(239,68,68,0.12)', color: '#F87171' },
  education: { bg: 'rgba(124,58,237,0.12)', color: '#A78BFA' },
  developer: { bg: 'rgba(59,130,246,0.12)', color: '#60A5FA' },
  ecommerce: { bg: 'rgba(245,158,11,0.12)', color: '#FBBF24' },
  general: { bg: 'rgba(0,198,255,0.12)', color: '#00C6FF' },
};

const STATUS_MAP = {
  ready: { label: 'Operational', cls: 'badge-cyan' },
  ingesting: { label: 'Processing', cls: 'badge-pulse' },
  error: { label: 'Fault', cls: 'badge-red' },
  pending: { label: 'Standby', cls: 'badge-gray' },
};

export default function ChatPage() {
  const [searchParams] = useSearchParams();
  const chatbotId = searchParams.get('chatbot_id');
  const { 
    messages, setMessages, sessionId, syncSession, wsStatus, setWsStatus 
  } = useChatStore();
  
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [chatbot, setChatbot] = useState(null);
  const [activeSources, setActiveSources] = useState([]);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);

  const wsRef = useRef(null);
  const chatEndRef = useRef(null);
  const textareaRef = useRef(null);
  const reconnectAttempts = useRef(0);

  // 1. SERIALIZED INITIALIZATION FLOW
  useEffect(() => {
    async function initializeSystem() {
      if (!chatbotId) return;

      // Step A: Reset and Load Chatbot Metadata
      setChatbot(null);
      setActiveSources([]);
      setIsTyping(false);
      
      try {
        const botData = await api(`/chatbots/${chatbotId}`);
        setChatbot(botData);
        
        // Step B: Authenticate & Sync Session
        const storedUserId = localStorage.getItem('tio_user_id') || 'guest';
        const expectedSuffix = `-c${chatbotId}`;
        
        // Only sync if strictly necessary to avoid loops
        if (!sessionId || !sessionId.endsWith(expectedSuffix)) {
          console.info(`[SYSTEM] Synchronizing session for chatbot=${chatbotId}`);
          syncSession(storedUserId, chatbotId);
        }
      } catch (err) {
        console.error("[SYSTEM] Initialization failed", err);
      }
    }
    initializeSystem();
  }, [chatbotId, sessionId, syncSession]);

  // 2. PROTECTED WEBSOCKET INITIALIZATION
  const connectWS = useCallback(() => {
    // STRICT GUARDS
    if (!chatbotId || !sessionId) return;
    if (!sessionId.endsWith(`-c${chatbotId}`)) return; // Ensure sync completion
    if (wsStatus === 'connected' || wsStatus === 'connecting') return;

    setWsStatus('connecting');
    console.info(`[WS] Initializing connection for session=${sessionId}`);

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host === 'localhost:5173' ? 'localhost:8000' : window.location.host;
    const token = localStorage.getItem('token') || '';

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    try {
      const ws = new WebSocket(`${protocol}//${host}/ws/chat/${sessionId}?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus('connected');
        reconnectAttempts.current = 0;
        console.info(`[WS] Protocol established for ${sessionId}`);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        // Dynamic Update Routing
        if (data.type === 'metadata') {
          if (data.citations) setActiveSources(data.citations);
        } else if (data.type === 'token') {
          setIsTyping(false);
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant' && last._streaming) {
              return [...prev.slice(0, -1), { ...last, content: last.content + data.content }];
            }
            return [...prev, { role: 'assistant', content: data.content, _streaming: true }];
          });
        } else if (data.type === 'final') {
          setIsTyping(false);
          setMessages(prev => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant') {
              return [...prev.slice(0, -1), { role: 'assistant', content: data.answer, sources: data.citations, _streaming: false }];
            }
            return prev;
          });
        }
      };

      ws.onclose = (e) => {
        setWsStatus('disconnected');
        if (e.code !== 1000) { // Not normal closure
          reconnectAttempts.current++;
          if (reconnectAttempts.current < 5) {
            console.warn(`[WS] Connection lost. Retry ${reconnectAttempts.current}/5...`);
            setTimeout(connectWS, 2000 * reconnectAttempts.current);
          }
        }
      };

      ws.onerror = () => setWsStatus('error');

    } catch (err) {
      setWsStatus('error');
      console.error("[WS] Critical failure", err);
    }
  }, [sessionId, chatbotId, wsStatus, setWsStatus, setMessages]);

  useEffect(() => {
    connectWS();
    return () => { if (wsRef.current) wsRef.current.close(); };
  }, [connectWS]);

  // 3. HISTORY RECOVERY (Only after sync)
  useEffect(() => {
    if (chatbotId && sessionId?.endsWith(`-c${chatbotId}`)) {
      setMessages([]);
      api(`/chat/history/${sessionId}?chatbot_id=${chatbotId}`)
        .then(h => { if (Array.isArray(h)) setMessages(h); })
        .catch(() => setMessages([]));
    }
  }, [chatbotId, sessionId, setMessages]);

  useEffect(() => {
    if (autoScroll) chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping, autoScroll]);

  const handleScroll = (e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.target;
    setAutoScroll(scrollHeight - scrollTop <= clientHeight + 100);
  };

  const sendMessage = (text = input) => {
    const msg = text.trim();
    if (!msg || isTyping) return;
    setInput('');
    setIsTyping(true);
    setMessages(prev => [...prev, { role: 'user', content: msg }]);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ message: msg, chatbot_id: chatbotId ? parseInt(chatbotId) : null, session_id: sessionId }));
    } else {
      api('/chat', { method: 'POST', body: JSON.stringify({ chatbot_id: chatbotId ? parseInt(chatbotId) : null, session_id: sessionId, message: msg }) })
        .then(r => { setIsTyping(false); setMessages(prev => [...prev, { role: 'assistant', content: r.answer, sources: r.citations }]); })
        .catch(() => { setIsTyping(false); setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Connection failed.' }]); });
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
    if (e.key === 'Escape') setSkillsOpen(false);
  };

  const handleInputChange = (e) => {
    const val = e.target.value;
    setInput(val);
    setSkillsOpen(val.startsWith('/'));
  };

  const triggerUpload = () => {
    const input = document.createElement('input');
    input.type = 'file'; input.multiple = true;
    input.onchange = async (e) => {
      const files = Array.from(e.target.files);
      for (const file of files) {
        const formData = new FormData(); formData.append('file', file);
        setMessages(prev => [...prev, { role: 'assistant', content: `📤 Uploading ${file.name}...`, _uploading: true }]);
        try {
          await api(`/chatbots/${chatbotId}/upload`, { method: 'POST', body: formData, isFormData: true });
          setMessages(prev => {
            const f = prev.filter(m => m.content !== `📤 Uploading ${file.name}...`);
            return [...f, { role: 'assistant', content: `✅ Successfully ingested ${file.name}.` }];
          });
        } catch {
          setMessages(prev => [...prev, { role: 'assistant', content: `❌ Failed to upload ${file.name}.` }]);
        }
      }
    };
    input.click();
  };

  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return alert('Voice not supported.');
    const rec = new SR();
    rec.onstart = () => setIsListening(true);
    rec.onresult = (e) => setInput(prev => prev + (prev ? ' ' : '') + e.results[0][0].transcript);
    rec.onerror = () => setIsListening(false);
    rec.onend = () => setIsListening(false);
    rec.start();
  };

  const executeSkill = async (skillId) => {
    setSkillsOpen(false); setIsTyping(true);
    setMessages(prev => [...prev, { role: 'assistant', content: `🚀 Running ${skillId.replace(/_/g, ' ')}...`, _isSkill: true }]);
    try {
      const result = await api('/skills/execute', { method: 'POST', body: JSON.stringify({ skill_id: skillId, chatbot_id: parseInt(chatbotId), session_id: sessionId, args: { query: input || 'general' } }) });
      setMessages(prev => { const f = prev.filter(m => !m._isSkill); return [...f, { role: 'assistant', content: result.answer }]; });
    } catch { setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Skill failed.' }]); }
    finally { setIsTyping(false); }
  };

  const handleExport = async (format) => {
    setExportOpen(false);
    try {
      const token = localStorage.getItem('token') || '';
      const res = await fetch(`/api/chat/export/${sessionId}?format=${format}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tio-chat-${sessionId.slice(0, 8)}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Export error:', err);
    }
  };

  const domain = chatbot?.domain || 'general';
  const quickActions = DOMAIN_SUGGESTIONS[domain] || DOMAIN_SUGGESTIONS.general;

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg-primary)', overflow: 'hidden' }}>
      

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
        {/* Top Navigation */}
        <header style={{
          padding: '16px 32px', borderBottom: '1px solid var(--border)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: 'rgba(3,5,12,0.7)', backdropFilter: 'blur(20px)', zIndex: 10
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
              <h2 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-primary)' }}>{chatbot?.name || 'Neural Core'}</h2>
              {chatbotId && (
                <div className="badge badge-cyan" style={{ fontSize: '9px', padding: '2px 6px', opacity: 0.8 }}>
                  CORE ID: {chatbotId}
                </div>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {chatbot && (
                <>
                  <div className={`badge ${STATUS_MAP[chatbot.status]?.cls || 'badge-gray'}`} style={{ fontSize: '9px', padding: '2px 8px' }}>
                    {STATUS_MAP[chatbot.status]?.label || 'Pending'}
                  </div>
                  <div className="badge" style={{ 
                    fontSize: '9px', 
                    padding: '2px 8px',
                    borderColor: DOMAIN_COLORS[chatbot.domain]?.color || '#fff', 
                    color: DOMAIN_COLORS[chatbot.domain]?.color || '#fff', 
                    background: `${DOMAIN_COLORS[chatbot.domain]?.color || '#fff'}08`, 
                    textTransform: 'capitalize' 
                  }}>
                    {chatbot.domain}
                  </div>
                </>
              )}
              <p style={{ fontSize: '10px', color: 'var(--text-dim)', letterSpacing: '0.02em', marginLeft: '4px' }}>
                SID: {sessionId.split('-')[0]}
              </p>
            </div>
          </div>
          
          <div style={{ display: 'flex', gap: '12px' }}>
            <div style={{ position: 'relative' }}>
              <button onClick={() => setExportOpen(!exportOpen)} className="btn btn-ghost btn-sm" style={{ borderRadius: 'var(--radius-full)' }}>
                <Download size={14} /> <span className="hide-mobile">Export</span>
              </button>
              <AnimatePresence>
                {exportOpen && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="glass-panel" 
                    style={{ position: 'absolute', top: '110%', right: 0, padding: '8px', zIndex: 100, minWidth: '150px' }}
                  >
                    {['pdf', 'md', 'docx'].map(f => (
                      <button key={f} onClick={() => handleExport(f)} className="btn btn-ghost btn-sm" style={{ width: '100%', justifyContent: 'flex-start' }}>
                        {f.toUpperCase()} Document
                      </button>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
            <button onClick={() => setSourcesOpen(!sourcesOpen)} className="btn btn-ghost btn-sm" style={{ borderRadius: 'var(--radius-full)' }}>
              <Layers size={14} /> <span className="hide-mobile">Context ({activeSources.length})</span>
            </button>
          </div>
        </header>

        {/* Chat Area */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '40px 0' }} className="custom-scrollbar" onScroll={handleScroll}>
          <div style={{ maxWidth: '850px', margin: '0 auto', padding: '0 32px' }}>
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', marginTop: '15vh' }} className="fade-in">
                <div className="flex-center" style={{ marginBottom: '24px' }}>
                  <div className="glass-panel" style={{ width: '80px', height: '80px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '24px', boxShadow: '0 0 40px rgba(0,198,255,0.15)' }}>
                    <Bot size={40} color="var(--accent)" />
                  </div>
                </div>
                <h1 className="text-premium" style={{ fontSize: '32px', fontWeight: 800, marginBottom: '12px' }}>Universal Intelligence</h1>
                <p style={{ color: 'var(--text-secondary)', fontSize: '16px', marginBottom: '40px', maxWidth: '500px', margin: '0 auto 40px' }}>
                  I'm your TiO agent, capable of web search, document retrieval, and specialized skill execution. How can I assist you today?
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', justifyContent: 'center' }}>
                  {quickActions.map(q => (
                    <button key={q} className="chip" onClick={() => sendMessage(q)}>{q}</button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  display: 'flex', gap: '16px', marginBottom: '32px',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
                }}
              >
                {msg.role === 'assistant' && (
                  <div className="glass-panel" style={{
                    width: '36px', height: '36px', borderRadius: '10px', flexShrink: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: '4px'
                  }}>
                    <Bot size={18} color="var(--accent)" />
                  </div>
                )}
                <div className={msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'} style={{ maxWidth: '85%' }}>
                  <div className="prose">
                    {msg.thought && (
                      <details style={{ 
                        marginBottom: '16px', 
                        background: 'rgba(255,255,255,0.03)', 
                        border: '1px solid var(--border)',
                        borderRadius: '12px',
                        overflow: 'hidden'
                      }}>
                        <summary style={{ 
                          padding: '8px 12px', 
                          fontSize: '11px', 
                          fontWeight: 600, 
                          color: 'var(--accent)', 
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                          textTransform: 'uppercase',
                          letterSpacing: '0.05em'
                        }}>
                          <Sparkles size={12} /> Neural Reasoning Trace
                        </summary>
                        <div style={{ 
                          padding: '0 12px 12px', 
                          fontSize: '12px', 
                          color: 'var(--text-secondary)',
                          lineHeight: 1.6,
                          whiteSpace: 'pre-wrap',
                          fontFamily: 'var(--font-mono)'
                        }}>
                          {msg.thought}
                        </div>
                      </details>
                    )}
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                  {msg.sources && msg.sources.length > 0 && !msg._streaming && (
                    <div style={{ marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--border)', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                      {msg.sources.slice(0, 3).map((s, idx) => (
                        <div key={idx} className="badge" style={{ fontSize: '9px', textTransform: 'none', background: 'rgba(255,255,255,0.03)' }}>
                          <FileText size={10} style={{ marginRight: '4px' }} /> {s.document.split('/').pop()}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isTyping && (
              <div style={{ display: 'flex', gap: '16px', marginBottom: '32px' }}>
                <div className="glass-panel" style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <Bot size={18} color="var(--accent)" />
                </div>
                <div className="chat-bubble-assistant">
                  <div className="typing-dots"><div className="dot" /><div className="dot" /><div className="dot" /></div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Input Control Center */}
        <div style={{ padding: '0 32px 32px' }}>
          <div style={{ maxWidth: '850px', margin: '0 auto' }}>
            <motion.div 
              layout
              className="glass-panel" 
              style={{ 
                display: 'flex', 
                alignItems: 'flex-end', 
                gap: '12px',
                padding: '12px 16px',
                borderRadius: '24px',
                borderWidth: '1px',
                boxShadow: '0 20px 50px rgba(0,0,0,0.3)'
              }}
            >
              <button onClick={triggerUpload} className="btn btn-ghost" style={{ padding: '10px', borderRadius: '14px', flexShrink: 0 }}>
                <Plus size={20} />
              </button>

              <div style={{ flex: 1, position: 'relative' }}>
                <textarea
                  ref={textareaRef} rows={1} value={input}
                  onChange={handleInputChange} onKeyDown={handleKeyDown}
                  placeholder="Message TiO or / to browse skills..."
                  style={{
                    width: '100%', background: 'transparent', border: 'none', outline: 'none',
                    color: 'var(--text-primary)', fontSize: '15px', padding: '8px 0', resize: 'none',
                    lineHeight: '1.5', maxHeight: '200px', fontWeight: 400
                  }}
                />
                <AnimatePresence>
                  {skillsOpen && (
                    <motion.div 
                      initial={{ opacity: 0, scale: 0.95, y: -10 }}
                      animate={{ opacity: 1, scale: 1, y: -20 }}
                      exit={{ opacity: 0, scale: 0.95, y: -10 }}
                      style={{ position: 'absolute', bottom: '100%', left: 0, zIndex: 1000 }}
                    >
                      <SkillsMenu domain={domain} onSelect={(id) => { executeSkill(id); setInput(''); }} onClose={() => setSkillsOpen(false)} />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
                <button onClick={startListening} className={`btn ${isListening ? 'btn-premium' : 'btn-ghost'}`} style={{ padding: '10px', borderRadius: '14px' }}>
                  <Mic size={18} />
                </button>
                <button onClick={() => sendMessage()} disabled={!input.trim() || isTyping} className="btn btn-primary" style={{ padding: '10px 18px', borderRadius: '14px', color: '#03050c' }}>
                  <Send size={18} strokeWidth={2.5} />
                </button>
              </div>
            </motion.div>
            <p style={{ textAlign: 'center', marginTop: '12px', fontSize: '10px', color: 'var(--text-dim)', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Advanced Neural Architecture · TiO v2.0
            </p>
          </div>
        </div>

        {/* Sources Overlay */}
        <AnimatePresence>
          {sourcesOpen && (
            <motion.div
              initial={{ x: '100%' }}
              animate={{ x: 0 }}
              exit={{ x: '100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              style={{
                position: 'absolute', top: 0, right: 0, height: '100%', width: '400px',
                background: 'rgba(8,11,26,0.8)', backdropFilter: 'blur(30px)',
                borderLeft: '1px solid var(--border)', zIndex: 100,
                display: 'flex', flexDirection: 'column'
              }}
            >
              <div style={{ padding: '24px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 className="font-heading" style={{ fontSize: '18px' }}>Intelligence Context</h3>
                <button onClick={() => setSourcesOpen(false)} className="btn btn-ghost" style={{ padding: '8px' }}><X size={20} /></button>
              </div>
              <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }} className="custom-scrollbar">
                {activeSources.length === 0 ? (
                  <div style={{ textAlign: 'center', marginTop: '100px', opacity: 0.4 }}>
                    <FileText size={48} style={{ margin: '0 auto 16px' }} />
                    <p>No knowledge sources retrieved for the current session.</p>
                  </div>
                ) : (
                  activeSources.map((src, i) => (
                    <div key={i} className="glass-panel" style={{ padding: '20px', marginBottom: '16px', borderLeft: '3px solid var(--accent)' }}>
                      <div className="badge badge-cyan" style={{ marginBottom: '12px' }}>Source #{i+1}</div>
                      <p style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: '12px' }}>"{src.text}"</p>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-muted)', fontSize: '11px' }}>
                        <FileText size={12} />
                        <span style={{ fontFamily: 'var(--font-mono)' }}>{src.document.split('\\').pop().split('/').pop()}</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
