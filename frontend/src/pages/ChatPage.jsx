import { useEffect, useRef, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import { useSearchParams } from 'react-router-dom';
import {
  Send, Bot, FileText, X, Sparkles, Activity,
  Plus, Mic, Download, ChevronDown, Layers, Copy, Check, Zap
} from 'lucide-react';
import { useChatStore } from '../store';
import { api } from '../api';
import { config } from '../config';
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
  const [activeMetadata, setActiveMetadata] = useState(null);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [copiedIdx, setCopiedIdx] = useState(null);
  const [adminMode, setAdminMode] = useState(false);
  const [sessionMemory, setSessionMemory] = useState({ entities: [], topics: [], documents: [], currentTopic: '', currentDomain: '' });

  const wsRef = useRef(null);
  const chatEndRef = useRef(null);
  const textareaRef = useRef(null);
  const reconnectAttempts = useRef(0);

  const copyToClipboard = (text, idx) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    }).catch(() => {
      // Fallback for older browsers
      const ta = document.createElement('textarea');
      ta.value = text; document.body.appendChild(ta);
      ta.select(); document.execCommand('copy');
      document.body.removeChild(ta);
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    });
    console.info('[CHAT] Copied message to clipboard.');
  };

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
        console.info(`[SESSION] Synchronizing session for chatbot=${chatbotId}`);
          syncSession(storedUserId, chatbotId);
        }
      } catch (err) {
        console.error("[SYSTEM] Initialization failed", err);
      }
    }
    initializeSystem();
  }, [chatbotId, sessionId, syncSession]);

  // 2. PROTECTED WEBSOCKET INITIALIZATION
  const isConnecting = useRef(false);
  const connectWS = useCallback(() => {
    // STRICT GUARDS
    if (!chatbotId || !sessionId) return;
    if (!sessionId.endsWith(`-c${chatbotId}`)) return; // Ensure sync completion
    
    if (isConnecting.current) {
      console.log("[WS] Connection attempt already in progress, blocking duplicate.");
      return;
    }

    const currentStatus = useChatStore.getState().wsStatus;
    if (currentStatus === 'connected') {
      console.log("[WS] Already connected, skipping.");
      return;
    }

    isConnecting.current = true;
    setWsStatus('connecting');
    console.info(`[WS] Initializing connection for session=${sessionId}`);

    const token = localStorage.getItem('token') || '';
    const wsUrl = `${config.wsBase}/ws/chat/${sessionId}?token=${encodeURIComponent(token)}`;

    // Ensure stale socket is fully dead
    if (wsRef.current) {
      console.log("[WS] Disposing stale socket reference...");
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }

    try {
      console.log(`[WS] Opening new instance: ${wsUrl}`);
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        isConnecting.current = false;
        setWsStatus('connected');
        reconnectAttempts.current = 0;
        console.info(`[WS] Socket opened: Protocol established for ${sessionId}`);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Dynamic Update Routing
          if (data.type === 'metadata') {
            if (data.citations) setActiveSources(data.citations);
            setActiveMetadata(data);
            // Hydrate session memory from metadata payload
            if (data.entities?.length || data.session_graph) {
              setSessionMemory(prev => ({
                entities: data.entities?.length ? data.entities : prev.entities,
                topics: data.session_graph?.topics || prev.topics,
                documents: data.session_graph?.documents || prev.documents,
                currentTopic: data.session_graph?.current_topic || prev.currentTopic,
                currentDomain: data.domain || prev.currentDomain,
              }));
            }
          } else if (data.type === 'thought') {
            setIsTyping(false);
            setMessages(prev => {
              const last = prev[prev.length - 1];
              const thoughtText = data.content + '\n';
              if (last?.role === 'assistant' && last._streaming) {
                return [...prev.slice(0, -1), { ...last, thought: (last.thought || '') + thoughtText }];
              }
              return [...prev, { role: 'assistant', content: '', thought: thoughtText, _streaming: true }];
            });
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
                return [...prev.slice(0, -1), { 
                  role: 'assistant', 
                  content: data.answer, 
                  sources: data.citations, 
                  entities: data.entities,
                  workflow: data.workflow,
                  adaptive_expanded: data.adaptive_expanded || false,
                  duration_s: data.duration_s || null,
                  _streaming: false 
                }];
              }
              return prev;
            });
            if (data.citations) setActiveSources(data.citations);
            setActiveMetadata({
              citations: data.citations || [],
              entities: data.entities || [],
              workflow: data.workflow || null,
              adaptive_expanded: data.adaptive_expanded || false,
              tavily_used: data.tavily_used || false
            });
          }
        } catch (err) {
          console.error("[WS] Message parse error:", err);
        }
      };

      ws.onclose = (e) => {
        isConnecting.current = false;
        setWsStatus('disconnected');
        console.warn(`[WS] Socket closed: Code=${e.code} Reason=${e.reason || 'none'}`);
        
        // Controlled Reconnect (Debounced)
        if (e.code !== 1000 && e.code !== 1001) { 
          if (reconnectAttempts.current < 5) {
            const delay = Math.min(10000, 2000 * Math.pow(2, reconnectAttempts.current));
            reconnectAttempts.current++;
            console.info(`[WS] Reconnect scheduled: Attempt ${reconnectAttempts.current} in ${delay}ms`);
            setTimeout(() => {
              if (useChatStore.getState().wsStatus !== 'connected') connectWS();
            }, delay);
          }
        }
      };

      ws.onerror = (err) => {
        isConnecting.current = false;
        console.error("[WS] Socket error encountered:", err);
      };

    } catch (err) {
      isConnecting.current = false;
      setWsStatus('error');
      console.error("[WS] Critical instantiation failure:", err);
    }
  }, [sessionId, chatbotId, setWsStatus, setMessages]);

  useEffect(() => {
    connectWS();
    return () => {
      if (wsRef.current) {
        console.info("[WS] Component unmounting, cleaning up socket...");
        wsRef.current.onclose = null; // Prevent reconnect on unmount
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connectWS]);

  // 3. HISTORY RECOVERY (Only after sync)
  useEffect(() => {
    if (chatbotId && sessionId?.endsWith(`-c${chatbotId}`)) {
      setMessages([]);
      api(`/chat/history/${sessionId}?chatbot_id=${chatbotId}`)
        .then(h => {
          if (Array.isArray(h)) {
            console.info(`[CHAT] Loaded ${h.length} history messages for session=${sessionId}`);
            const normalized = h.map(m => {
              const src = m.sources;
              const isArr = Array.isArray(src);
              return {
                ...m,
                sources: isArr ? src : (src?.chunks || []),
                entities: m.entities || (!isArr ? src?.entities : []) || [],
                workflow: m.workflow || (!isArr ? src?.workflow : null) || null,
                adaptive_expanded: m.adaptive_expanded || (!isArr ? src?.adaptive_expanded : false) || false,
                duration_s: m.duration_s || (!isArr ? src?.duration_s : null) || null,
              };
            });
            setMessages(normalized);
            // Hydrate activeSources and activeMetadata with last assistant message's details
            const lastAssistantMsg = [...normalized].reverse().find(m => m.role === 'assistant');
            if (lastAssistantMsg) {
              setActiveSources(lastAssistantMsg.sources || []);
              setActiveMetadata({
                citations: lastAssistantMsg.sources || [],
                entities: lastAssistantMsg.entities || [],
                workflow: lastAssistantMsg.workflow || null,
                adaptive_expanded: lastAssistantMsg.adaptive_expanded || false
              });
            }
          }
        })
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
    
    // Check socket state before proceeding
    const isSocketOpen = wsRef.current?.readyState === WebSocket.OPEN;
    
    setInput('');
    setIsTyping(true);
    setMessages(prev => [...prev, { role: 'user', content: msg }]);

    if (isSocketOpen) {
      console.info("[WS] Sending message via active socket...");
      wsRef.current.send(JSON.stringify({ 
        message: msg, 
        chatbot_id: chatbotId ? parseInt(chatbotId) : null, 
        session_id: sessionId 
      }));
    } else {
      console.warn("[WS] Socket not open, falling back to HTTP POST.");
      api('/chat', { 
        method: 'POST', 
        body: JSON.stringify({ 
          chatbot_id: chatbotId ? parseInt(chatbotId) : null, 
          session_id: sessionId, 
          message: msg 
        }) 
      })
        .then(r => { 
          setIsTyping(false); 
          setMessages(prev => [...prev, { role: 'assistant', content: r.answer, sources: r.citations }]); 
        })
        .catch(err => { 
          setIsTyping(false); 
          console.error("[WS] Fallback HTTP failed:", err);
          setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Message delivery failed. Please check your connection.' }]); 
        });
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
      const res = await fetch(`${config.apiBase}/api/chat/export/${sessionId}?chatbot_id=${chatbotId}&format=${format}`, {
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

        {/* Chat Area Container */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative', overflow: 'hidden' }}>
          {/* WebSocket Status Warning */}
          {wsStatus !== 'connected' && (
            <div style={{
              position: 'absolute', top: '10px', left: '50%', transform: 'translateX(-50%)',
              zIndex: 100, background: 'rgba(239, 68, 68, 0.9)', color: 'white',
              padding: '6px 16px', borderRadius: '20px', fontSize: '12px', fontWeight: 600,
              display: 'flex', alignItems: 'center', gap: '8px', boxShadow: '0 4px 12px rgba(0,0,0,0.2)'
            }}>
              <Activity size={14} className="animate-pulse" />
              {wsStatus === 'connecting' ? 'Reconnecting to Neural Core...' : 'Disconnected from Intelligence Core'}
            </div>
          )}

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
                <div className={msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'} style={{ maxWidth: '85%', position: 'relative' }}>
                  <div className="prose">
                    {msg.thought && (
                      <details style={{ marginBottom: '16px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', borderRadius: '12px', overflow: 'hidden' }}>
                        <summary style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 600, color: 'var(--accent)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          <Sparkles size={12} /> Neural Reasoning Trace
                        </summary>
                        <div style={{ padding: '0 12px 12px', fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.6, whiteSpace: 'pre-wrap', fontFamily: 'var(--font-mono)' }}>
                          {msg.thought}
                        </div>
                      </details>
                    )}
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>

                  {/* Footer: sources + copy + adaptive badge */}
                  {msg.role === 'assistant' && !msg._streaming && (
                    <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                      {msg.sources?.slice(0, 3).map((s, idx) => (
                        <div key={idx} className="badge" style={{ fontSize: '9px', textTransform: 'none', background: 'rgba(255,255,255,0.03)' }}>
                          <FileText size={10} style={{ marginRight: '4px' }} /> {s.document.split('/').pop()}
                        </div>
                      ))}
                      {msg.adaptive_expanded && (
                        <div className="badge" style={{ fontSize: '9px', background: 'rgba(0,198,255,0.08)', borderColor: 'rgba(0,198,255,0.3)', color: 'var(--accent)' }}>
                          <Zap size={9} style={{ marginRight: '3px' }} /> Adaptive
                        </div>
                      )}
                      {msg.duration_s && (
                        <div className="badge" style={{ fontSize: '9px', background: 'rgba(251,191,36,0.08)', borderColor: 'rgba(251,191,36,0.3)', color: '#FBBF24', display: 'inline-flex', alignItems: 'center', gap: '3px' }} title="Total response generation time">
                          <Activity size={10} /> {msg.duration_s}s
                        </div>
                      )}
                      <button
                        onClick={() => copyToClipboard(msg.content, i)}
                        title="Copy response"
                        style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', padding: '2px', color: copiedIdx === i ? 'var(--accent-green)' : 'var(--text-dim)', transition: 'color 0.2s' }}
                      >
                        {copiedIdx === i ? <Check size={13} /> : <Copy size={13} />}
                      </button>
                    </div>
                  )}

                    {/* Session Memory Intelligence Panel */}
                    {(sessionMemory.entities.length > 0 || sessionMemory.currentTopic || sessionMemory.documents.length > 0) && (
                      <div className="glass-panel" style={{ padding: '20px', marginBottom: '24px', background: 'rgba(124,58,237,0.04)', border: '1px solid rgba(124,58,237,0.2)' }}>
                        <div className="font-heading" style={{ fontSize: '11px', color: '#A78BFA', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '14px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Sparkles size={12} />
                          Session Memory
                        </div>

                        {sessionMemory.currentTopic && (
                          <div style={{ marginBottom: '12px' }}>
                            <div style={{ fontSize: '9px', color: 'rgba(167,139,250,0.6)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '4px' }}>Active Topic</div>
                            <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)' }}>{sessionMemory.currentTopic}</div>
                          </div>
                        )}

                        {sessionMemory.entities.length > 0 && (
                          <div style={{ marginBottom: '12px' }}>
                            <div style={{ fontSize: '9px', color: 'rgba(167,139,250,0.6)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>Tracked Entities</div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                              {sessionMemory.entities.slice(0, 6).map(e => (
                                <span key={e} onClick={() => { setInput(`Tell me more about ${e}`); textareaRef.current?.focus(); }}
                                  style={{ fontSize: '10px', padding: '2px 8px', borderRadius: '20px', background: 'rgba(124,58,237,0.15)', border: '1px solid rgba(124,58,237,0.3)', color: '#C4B5FD', fontWeight: 600, cursor: 'pointer' }}>
                                  {e}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        {sessionMemory.documents.length > 0 && (
                          <div>
                            <div style={{ fontSize: '9px', color: 'rgba(167,139,250,0.6)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '6px' }}>Cached Documents</div>
                            {sessionMemory.documents.slice(0, 3).map((d, i) => (
                              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px', fontSize: '11px', color: 'var(--text-secondary)' }}>
                                <FileText size={10} style={{ color: '#A78BFA', flexShrink: 0 }} />
                                <span style={{ fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>{d.title || d.url}</span>
                                {d.type === 'pdf' && <span style={{ fontSize: '8px', padding: '1px 4px', background: 'rgba(239,68,68,0.15)', border: '1px solid rgba(239,68,68,0.3)', color: '#F87171', borderRadius: '4px', fontWeight: 700 }}>PDF</span>}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                </div>
              </div>
            ))}

            {isTyping && (
              <div style={{ display: 'flex', gap: '16px', marginBottom: '32px' }} className="fade-in">
                <div className="glass-panel" style={{
                  width: '36px', height: '36px', borderRadius: '10px',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0
                }}>
                  <Bot size={18} color="var(--accent)" className="animate-pulse" />
                </div>
                <div className="chat-bubble-assistant" style={{ width: '80%', padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                    <div className="typing-dots"><div className="dot" /><div className="dot" /><div className="dot" /></div>
                    <span style={{ fontSize: '10px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 }}>
                      Synthesizing local vectors...
                    </span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <div className="skeleton" style={{ height: '12px', width: '100%', opacity: 0.8 }} />
                    <div className="skeleton" style={{ height: '12px', width: '85%', opacity: 0.6 }} />
                    <div className="skeleton" style={{ height: '12px', width: '50%', opacity: 0.4 }} />
                  </div>
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
                background: 'rgba(8,11,26,0.92)', backdropFilter: 'blur(30px)',
                borderLeft: '1px solid var(--border)', zIndex: 100,
                display: 'flex', flexDirection: 'column', boxShadow: '-10px 0 30px rgba(0,0,0,0.5)'
              }}
            >
              <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 className="font-heading" style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)' }}>Intelligence Context</h3>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                    <label style={{ fontSize: '10px', color: 'var(--text-dim)', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
                      <input 
                        type="checkbox" 
                        checked={adminMode} 
                        onChange={(e) => setAdminMode(e.target.checked)} 
                        style={{ accentColor: 'var(--accent)' }} 
                      />
                      Admin Debug
                    </label>
                  </div>
                </div>
                <button onClick={() => setSourcesOpen(false)} className="btn btn-ghost" style={{ padding: '8px', borderRadius: '50%' }}><X size={20} /></button>
              </div>

              <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }} className="custom-scrollbar">
                {activeSources.length === 0 && (!activeMetadata || !activeMetadata.entities || activeMetadata.entities.length === 0) ? (
                  <div style={{ textAlign: 'center', marginTop: '60px', opacity: 0.6 }}>
                    <Layers size={40} style={{ margin: '0 auto 16px', color: 'var(--accent)', animation: 'pulse 2s infinite' }} />
                    <p style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '8px' }}>
                      No contextual retrieval available yet.
                    </p>
                    <p style={{ fontSize: '12px', color: 'var(--text-dim)', lineHeight: 1.6, maxWidth: '250px', margin: '0 auto' }}>
                      Ask a question and retrieved knowledge chunks, PDFs, source URLs, and workflow states will dynamically populate here.
                    </p>
                    {chatbot && (
                      <div className="glass-panel" style={{ marginTop: '24px', padding: '16px', textAlign: 'left', background: 'rgba(0,198,255,0.03)', borderColor: 'rgba(0,198,255,0.1)' }}>
                        <div style={{ fontSize: '9px', color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '8px', fontWeight: 800 }}>Target Core Node</div>
                        <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary)' }}>{chatbot.name}</div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '4px', textTransform: 'capitalize' }}>
                          Domain: {chatbot.domain} · Status: {chatbot.status}
                        </div>
                        {chatbot.website_url && (
                          <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginTop: '8px', fontFamily: 'var(--font-mono)', wordBreak: 'break-all' }}>
                            {chatbot.website_url}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ) : (
                  <>
                    {/* Active Workflow & Entities section */}
                    {activeMetadata && (
                      <div className="glass-panel" style={{ padding: '20px', marginBottom: '24px', background: 'rgba(0,198,255,0.04)', border: '1px solid rgba(0,198,255,0.15)' }}>
                         <div className="font-heading" style={{ fontSize: '11px', color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '14px', fontWeight: 800 }}>Cognitive Pipeline State</div>
                         
                         {activeMetadata.workflow && (
                           <div style={{ marginBottom: '14px' }}>
                             <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Active RAG Workflow</div>
                             <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center' }}>
                               <span className="badge badge-cyan" style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase' }}>
                                 {activeMetadata.workflow.replace(/_/g, ' ')}
                               </span>
                               {activeMetadata.workflow_stage && (
                                 <span style={{ fontSize: '11.5px', color: 'var(--text-secondary)', fontWeight: 600 }}>
                                   ➔ {activeMetadata.workflow_stage.replace(/_/g, ' ')}
                                 </span>
                               )}
                             </div>
                           </div>
                         )}

                         {activeMetadata.adaptive_expanded && (
                           <div style={{ marginBottom: '14px' }}>
                             <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Knowledge Discovery</div>
                             <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                               <span className="badge" style={{ fontSize: '11px', background: 'rgba(245,158,11,0.15)', borderColor: 'rgba(245,158,11,0.4)', color: '#FBBF24', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                 <Zap size={11} className="animate-pulse" /> Adaptive Expansion Active
                               </span>
                             </div>
                           </div>
                         )}

                         {activeMetadata.tavily_used && (
                           <div style={{ marginBottom: '14px' }}>
                             <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>External Grounding</div>
                             <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                               <span className="badge" style={{ fontSize: '11px', background: 'rgba(16,185,129,0.15)', borderColor: 'rgba(16,185,129,0.4)', color: '#10B981', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                 <Activity size={11} /> Tavily Web Search Triggered
                               </span>
                             </div>
                           </div>
                         )}

                         {activeMetadata.entities && activeMetadata.entities.length > 0 && (
                           <div>
                             <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Identified Entities (Click to ask)</div>
                             <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                               {activeMetadata.entities.map(e => (
                                 <span 
                                   key={e} 
                                   onClick={() => {
                                     setInput(`Tell me more about ${e}`);
                                     textareaRef.current?.focus();
                                   }}
                                   style={{ 
                                     fontSize: '10px', 
                                     padding: '3px 8px', 
                                     borderRadius: '6px', 
                                     background: 'rgba(255,255,255,0.06)', 
                                     border: '1px solid var(--border)', 
                                     color: 'var(--text-primary)', 
                                     fontWeight: 500,
                                     cursor: 'pointer',
                                     transition: 'all 0.2s ease',
                                   }}
                                   onMouseOver={(event) => {
                                     event.target.style.background = 'rgba(0,198,255,0.15)';
                                     event.target.style.borderColor = 'var(--accent)';
                                   }}
                                   onMouseOut={(event) => {
                                     event.target.style.background = 'rgba(255,255,255,0.06)';
                                     event.target.style.borderColor = 'var(--border)';
                                   }}
                                 >
                                   {e}
                                 </span>
                               ))}
                             </div>
                           </div>
                         )}
                      </div>
                    )}

                    <div className="font-heading" style={{ fontSize: '11px', color: 'var(--text-dim)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '16px', fontWeight: 800 }}>Retrieved Knowledge Chunks</div>
                    
                    {activeSources.length === 0 ? (
                      <div style={{ padding: '16px', background: 'rgba(255,255,255,0.02)', borderRadius: '12px', border: '1px solid var(--border)', textAlign: 'center', fontSize: '12px', color: 'var(--text-dim)' }}>
                        No chunks retrieved for the last response.
                      </div>
                    ) : (
                      activeSources.map((src, i) => {
                        const cleanText = (src.text || '').replace(/^\[Source\s+\d+.*\]\n?/, '');
                        const docName = src.document ? src.document.split('\\').pop().split('/').pop() : 'Unknown Source';
                        const isPdf = docName.toLowerCase().endsWith('.pdf') || 
                                      src.metadata?.source_type === 'application/pdf' || 
                                      src.metadata?.filename?.toLowerCase().endsWith('.pdf');
                        
                        // Parse URL if present in metadata
                        const sourceUrl = src.metadata?.url || src.metadata?.source_url || src.metadata?.source;
                        const isUrl = sourceUrl && (sourceUrl.startsWith('http://') || sourceUrl.startsWith('https://'));

                        return (
                          <div key={i} className="glass-panel" style={{ padding: '20px', marginBottom: '16px', borderLeft: `3px solid ${isPdf ? '#EF4444' : 'var(--accent)'}`, background: 'rgba(255,255,255,0.02)' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                              <span className={`badge ${isPdf ? 'badge-red' : 'badge-cyan'}`} style={{ fontSize: '9px', fontWeight: 800 }}>
                                {isPdf ? 'PDF DOCUMENT' : `SOURCE #${i+1}`}
                              </span>
                              {src.score !== undefined && (
                                <span style={{ fontSize: '10px', color: 'var(--accent-green)', fontWeight: 700, fontFamily: 'var(--font-mono)' }}>
                                  {src.score > 1 ? `RRF: ${src.score.toFixed(4)}` : `Score: ${(src.score * 100).toFixed(0)}%`}
                                </span>
                              )}
                            </div>

                            <div className="custom-scrollbar prose" style={{ fontSize: '13px', color: 'var(--text-primary)', lineHeight: 1.6, marginBottom: '12px', maxHeight: '180px', overflowY: 'auto', overflowX: 'hidden', paddingRight: '8px' }}>
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{cleanText}</ReactMarkdown>
                            </div>

                            {adminMode && (
                              <div style={{ margin: '12px 0', padding: '10px', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', border: '1px dashed var(--border)', fontSize: '10px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                                <div style={{ color: 'var(--accent)', fontWeight: 'bold', marginBottom: '4px' }}>DEBUG METADATA:</div>
                                <div>Chunk ID: {src.chunk_id}</div>
                                <div>Category: {src.semantic_category || 'General'}</div>
                                {src.metadata && (
                                  <div style={{ marginTop: '4px', overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                                    {JSON.stringify(src.metadata, null, 2)}
                                  </div>
                                )}
                              </div>
                            )}

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '10px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--text-muted)', fontSize: '11px' }}>
                                <FileText size={12} style={{ color: isPdf ? '#EF4444' : 'var(--text-dim)' }} />
                                <span style={{ fontFamily: 'var(--font-mono)', wordBreak: 'break-all', fontWeight: 500 }} title={src.document}>
                                  {docName}
                                </span>
                              </div>

                              {isUrl && (
                                <a 
                                  href={sourceUrl} 
                                  target="_blank" 
                                  rel="noopener noreferrer" 
                                  style={{ 
                                    display: 'inline-flex', 
                                    alignItems: 'center', 
                                    gap: '4px', 
                                    color: 'var(--accent)', 
                                    fontSize: '11px', 
                                    textDecoration: 'none',
                                    fontWeight: 600,
                                    width: 'fit-content'
                                  }}
                                  onMouseOver={(e) => e.target.style.textDecoration = 'underline'}
                                  onMouseOut={(e) => e.target.style.textDecoration = 'none'}
                                >
                                  <span>Open Source URL</span>
                                  <span style={{ fontSize: '9px' }}>↗</span>
                                </a>
                              )}
                            </div>
                          </div>
                        );
                      })
                    )}
                  </>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
