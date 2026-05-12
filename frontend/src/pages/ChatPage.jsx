import { useEffect, useRef, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import { useSearchParams } from 'react-router-dom';
import {
  Send, Bot, FileText, X, Sparkles,
  Plus, Mic, Download, ChevronDown
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

export default function ChatPage() {
  const [searchParams] = useSearchParams();
  const chatbotId = searchParams.get('chatbot_id');
  const { messages, setMessages, sessionId, setSessionFromUser } = useChatStore();
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

  // Load Chatbot + set per-user per-chatbot session
  useEffect(() => {
    if (chatbotId) {
      api(`/chatbots/${chatbotId}`).then(setChatbot).catch(() => {});
      // Scope the session to this specific chatbot so history is isolated
      const stored = localStorage.getItem('tio_user_id');
      if (stored) setSessionFromUser(parseInt(stored), chatbotId);
    }
  }, [chatbotId]);


  // WebSocket
  const connectWS = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (reconnectAttempts.current >= 5) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host === 'localhost:5173' ? 'localhost:8888' : window.location.host;
    const token = localStorage.getItem('token') || '';
    const ws = new WebSocket(`${protocol}//${host}/ws/chat/${sessionId}?token=${encodeURIComponent(token)}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
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
      } else if (data.error) {
        setIsTyping(false);
        setMessages(prev => [...prev, { role: 'assistant', content: `⚠️ ${data.error}` }]);
      }
    };

    ws.onopen = () => { reconnectAttempts.current = 0; };
    ws.onclose = () => {
      reconnectAttempts.current++;
      setTimeout(connectWS, Math.min(1000 * Math.pow(2, reconnectAttempts.current), 10000));
    };
  }, [sessionId, setMessages]);

  useEffect(() => {
    connectWS();
    return () => { if (wsRef.current) wsRef.current.close(); };
  }, [connectWS]);

  // Load History
  useEffect(() => {
    if (chatbotId) {
      api(`/chat/history/${sessionId}`).then(h => { if (Array.isArray(h)) setMessages(h); }).catch(() => {});
    }
  }, [chatbotId]);

  // Auto-scroll
  useEffect(() => {
    if (autoScroll) chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping, autoScroll]);

  const handleScroll = (e) => {
    const { scrollTop, scrollHeight, clientHeight } = e.target;
    setAutoScroll(scrollHeight - scrollTop <= clientHeight + 100);
  };

  // Send message
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

  const handleKeyDown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } };

  // Voice
  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return alert('Voice not supported in this browser.');
    const rec = new SR();
    rec.continuous = false; rec.interimResults = false; rec.lang = 'en-US';
    rec.onstart = () => setIsListening(true);
    rec.onresult = (e) => setInput(prev => prev + (prev ? ' ' : '') + e.results[0][0].transcript);
    rec.onerror = () => setIsListening(false);
    rec.onend = () => setIsListening(false);
    rec.start();
  };

  // Skills
  const executeSkill = async (skillId) => {
    setSkillsOpen(false);
    setIsTyping(true);
    setMessages(prev => [...prev, { role: 'assistant', content: `🚀 Running ${skillId.replace(/_/g, ' ')}...`, _isSkill: true }]);
    try {
      const result = await api('/skills/execute', { method: 'POST', body: JSON.stringify({ skill_id: skillId, chatbot_id: parseInt(chatbotId), session_id: sessionId, args: { query: input || 'general planning' } }) });
      setMessages(prev => { const f = prev.filter(m => !m._isSkill); return [...f, { role: 'assistant', content: result.answer }]; });
    } catch { setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Skill failed.' }]); }
    finally { setIsTyping(false); }
  };

  // Export
  const handleExport = (format) => {
    setExportOpen(false);
    window.open(`/api/chat/export/${sessionId}?format=${format}`, '_blank');
  };

  const domain = chatbot?.domain || 'general';
  const quickActions = DOMAIN_SUGGESTIONS[domain] || DOMAIN_SUGGESTIONS.general;

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--bg-primary)' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Header */}
        <header style={{
          padding: '12px 24px', borderBottom: '1px solid var(--border-light)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          background: 'rgba(5,8,22,0.85)', backdropFilter: 'blur(16px)', zIndex: 10
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              width: '36px', height: '36px', borderRadius: 'var(--radius-sm)',
              background: 'linear-gradient(135deg, #00C6FF, #0072FF)',
              display: 'flex', alignItems: 'center', justifyContent: 'center'
            }}>
              <Bot size={18} color="#050816" />
            </div>
            <div>
              <h2 style={{ fontSize: '15px', fontWeight: 700 }}>{chatbot?.name || 'Assistant'}</h2>
              <p style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                {chatbot?.domain ? chatbot.domain.charAt(0).toUpperCase() + chatbot.domain.slice(1) : 'General'} · Online
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            {/* Export */}
            <div style={{ position: 'relative' }}>
              <button onClick={() => setExportOpen(!exportOpen)} className="btn btn-ghost btn-sm">
                <Download size={14} /> Export
              </button>
              {exportOpen && (
                <div style={{
                  position: 'absolute', top: '100%', right: 0, marginTop: '4px',
                  background: 'var(--bg-card)', border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-sm)', padding: '4px', zIndex: 20, minWidth: '140px'
                }}>
                  {['pdf', 'md', 'docx'].map(f => (
                    <button key={f} onClick={() => handleExport(f)} style={{
                      display: 'block', width: '100%', padding: '8px 12px', textAlign: 'left',
                      fontSize: '13px', color: 'var(--text-secondary)', borderRadius: '4px'
                    }}
                      onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                    >
                      {f.toUpperCase()}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button onClick={() => setSourcesOpen(!sourcesOpen)} className="btn btn-ghost btn-sm">
              <FileText size={14} /> {activeSources.length} Sources
            </button>
          </div>
        </header>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '32px 0' }} className="custom-scrollbar" onScroll={handleScroll}>
          <div style={{ maxWidth: '800px', margin: '0 auto', padding: '0 24px' }}>
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', marginTop: '12vh' }}>
                <Sparkles size={40} color="var(--accent)" style={{ margin: '0 auto 20px' }} />
                <h1 style={{ fontSize: '26px', fontWeight: 800, marginBottom: '8px' }}>How can I help?</h1>
                <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginBottom: '32px' }}>{chatbot?.name || 'Your assistant'} is ready.</p>
                {/* Quick Actions */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', justifyContent: 'center' }}>
                  {quickActions.map(q => (
                    <button key={q} className="chip" onClick={() => sendMessage(q)}>{q}</button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
                style={{
                  display: 'flex', gap: '14px', marginBottom: '24px',
                  justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start'
                }}
              >
                {msg.role === 'assistant' && (
                  <div style={{
                    width: '32px', height: '32px', borderRadius: 'var(--radius-sm)', flexShrink: 0,
                    background: 'linear-gradient(135deg, #00C6FF, #0072FF)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: '2px'
                  }}>
                    <Bot size={16} color="#050816" />
                  </div>
                )}
                <div style={{
                  maxWidth: '80%',
                  padding: msg.role === 'user' ? '10px 18px' : '0',
                  borderRadius: msg.role === 'user' ? 'var(--radius-lg)' : '0',
                  background: msg.role === 'user' ? 'rgba(0,198,255,0.08)' : 'transparent',
                  border: msg.role === 'user' ? '1px solid rgba(0,198,255,0.15)' : 'none'
                }}>
                  <div className="prose">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                </div>
              </motion.div>
            ))}

            {isTyping && (
              <div style={{ display: 'flex', gap: '14px', marginBottom: '24px' }}>
                <div style={{
                  width: '32px', height: '32px', borderRadius: 'var(--radius-sm)',
                  background: 'linear-gradient(135deg, #00C6FF, #0072FF)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}>
                  <Bot size={16} color="#050816" />
                </div>
                <div className="typing-indicator"><div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" /></div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Input Area */}
        <div style={{ padding: '0 24px 28px' }}>
          <div style={{ maxWidth: '800px', margin: '0 auto' }}>
            <div style={{
              display: 'flex', alignItems: 'flex-end', gap: '8px',
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-xl)', padding: '6px 6px 6px 8px'
            }}>
              {/* Plus / Skills */}
              <div style={{ position: 'relative' }}>
                <button
                  onClick={() => setSkillsOpen(!skillsOpen)}
                  style={{
                    width: '36px', height: '36px', borderRadius: 'var(--radius-sm)',
                    background: skillsOpen ? 'var(--accent)' : 'rgba(255,255,255,0.04)',
                    color: skillsOpen ? '#050816' : 'var(--text-muted)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}
                >
                  <Plus size={18} style={{ transform: skillsOpen ? 'rotate(45deg)' : 'none', transition: 'transform 0.2s' }} />
                </button>
                <AnimatePresence>
                  {skillsOpen && <SkillsMenu domain={domain} onSelect={executeSkill} onClose={() => setSkillsOpen(false)} />}
                </AnimatePresence>
              </div>

              <textarea
                ref={textareaRef} rows={1} value={input}
                onChange={e => setInput(e.target.value)} onKeyDown={handleKeyDown}
                placeholder="Ask anything..."
                style={{
                  flex: 1, background: 'transparent', border: 'none', outline: 'none',
                  color: '#fff', fontSize: '14px', padding: '8px 4px', resize: 'none',
                  lineHeight: '1.5', maxHeight: '120px'
                }}
              />

              {/* Mic */}
              <button
                onClick={startListening}
                style={{
                  width: '36px', height: '36px', borderRadius: 'var(--radius-sm)',
                  background: isListening ? 'var(--accent-red)' : 'rgba(255,255,255,0.04)',
                  color: isListening ? '#fff' : 'var(--text-muted)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center'
                }}
              >
                <Mic size={16} />
              </button>

              {/* Send */}
              <button
                onClick={() => sendMessage()}
                disabled={!input.trim() || isTyping}
                style={{
                  width: '36px', height: '36px', borderRadius: 'var(--radius-sm)',
                  background: input.trim() ? 'var(--accent)' : 'rgba(255,255,255,0.04)',
                  color: input.trim() ? '#050816' : 'var(--text-dim)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  transition: 'all 0.15s'
                }}
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Sources Panel */}
      <AnimatePresence>
        {sourcesOpen && (
          <motion.div
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 360, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            style={{
              borderLeft: '1px solid var(--border-light)', background: 'var(--bg-secondary)',
              overflow: 'hidden', flexShrink: 0
            }}
          >
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-light)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '13px', fontWeight: 700 }}>Sources ({activeSources.length})</h3>
              <button onClick={() => setSourcesOpen(false)} style={{ color: 'var(--text-muted)', padding: '4px' }}><X size={16} /></button>
            </div>
            <div style={{ padding: '16px 20px', overflowY: 'auto', height: 'calc(100vh - 60px)' }} className="custom-scrollbar">
              {activeSources.length === 0 ? (
                <p style={{ fontSize: '13px', color: 'var(--text-dim)', textAlign: 'center', marginTop: '40px' }}>Sources appear after your first query.</p>
              ) : (
                activeSources.map((src, i) => (
                  <div key={i} className="glass-panel" style={{ padding: '14px', marginBottom: '10px' }}>
                    <p style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>"{src.text?.slice(0, 200)}..."</p>
                    <p style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '6px', fontFamily: 'var(--font-mono)' }}>{src.document}</p>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
