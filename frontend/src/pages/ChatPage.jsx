import { useEffect, useRef, useState, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { motion, AnimatePresence } from 'framer-motion';
import { useSearchParams } from 'react-router-dom';
import {
  Send, Copy, Trash2,
  FileText, Brain, Bot, 
  ExternalLink, X, Sparkles, Activity,
  Plus, MessageCircle, Globe, Quote
} from 'lucide-react';
import { useChatStore } from '../store';
import { api } from '../api';

export default function ChatPage() {
  const [searchParams] = useSearchParams();
  const chatbotId = searchParams.get('chatbot_id');
  const { messages, setMessages, sessionId } = useChatStore();
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const [chatbot, setChatbot] = useState(null);
  const [activeSources, setActiveSources] = useState([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [suggestions, setSuggestions] = useState([]);
  
  const wsRef = useRef(null);
  const chatEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Load Chatbot Data
  useEffect(() => {
    if (chatbotId) {
      api(`/chatbots/${chatbotId}`).then(data => {
        setChatbot(data);
        if (messages.length === 0) {
           setSuggestions(["What can you help me with?", "Summarize the website for me."]);
        }
      });
    }
  }, [chatbotId]);

  // WebSocket Connection
  const connectWS = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host === 'localhost:5173' ? 'localhost:8000' : window.location.host;
    const ws = new WebSocket(`${protocol}//${host}/ws/chat/${sessionId}`);
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

    ws.onclose = () => {
      setTimeout(connectWS, 3000);
    };
  }, [sessionId, setMessages]);

  useEffect(() => {
    connectWS();
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [connectWS]);

  // Load History
  useEffect(() => {
    if (chatbotId) {
      api(`/chat/history/${chatbotId}`).then(history => {
        if (Array.isArray(history)) setMessages(history);
      });
    }
  }, [chatbotId]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  const sendMessage = async (text = input) => {
    const finalInput = text.trim();
    if (!finalInput || isTyping) return;
    
    setInput('');
    setSuggestions([]);
    setIsTyping(true);
    setMessages(prev => [...prev, { role: 'user', content: finalInput }]);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ 
        message: finalInput, 
        chatbot_id: chatbotId ? parseInt(chatbotId) : null,
        session_id: sessionId 
      }));
    } else {
      // Fallback
      try {
        const result = await api('/chat', { 
          method: 'POST', 
          body: JSON.stringify({ chatbot_id: chatbotId ? parseInt(chatbotId) : null, session_id: sessionId, message: finalInput }) 
        });
        setIsTyping(false);
        setMessages(prev => [...prev, { role: 'assistant', content: result.answer, sources: result.citations }]);
      } catch (err) {
        setIsTyping(false);
        setMessages(prev => [...prev, { role: 'assistant', content: '⚠️ Engine offline.' }]);
      }
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#050816', color: '#fff' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
        <header style={{ padding: '16px 32px', borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(5,8,22,0.8)', backdropFilter: 'blur(20px)', zIndex: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ width: '40px', height: '40px', borderRadius: '12px', background: 'linear-gradient(135deg, #00C6FF, #0072FF)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Bot size={20} color="#050816" />
            </div>
            <div>
              <h2 style={{ fontSize: '16px', fontWeight: 700 }}>{chatbot?.name || "Assistant"}</h2>
              <p style={{ fontSize: '12px', color: '#64748b' }}>{chatbot?.domain || "General"} · {chatbot?.status || "Ready"}</p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button onClick={() => setSidebarOpen(!sidebarOpen)} style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', padding: '8px 12px', color: '#94a3b8', fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <FileText size={14} /> {activeSources.length} Sources
            </button>
          </div>
        </header>

        <div style={{ flex: 1, overflowY: 'auto', padding: '40px 0' }} className="custom-scrollbar">
          <div style={{ maxWidth: '800px', margin: '0 auto', padding: '0 24px' }}>
            {messages.length === 0 && (
              <div style={{ textAlign: 'center', marginTop: '10vh' }}>
                <Sparkles size={48} color="#00C6FF" style={{ margin: '0 auto 24px' }} />
                <h1 style={{ fontSize: '32px', fontWeight: 800 }}>How can I help you today?</h1>
              </div>
            )}
            {messages.map((msg, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} style={{ display: 'flex', gap: '20px', marginBottom: '32px', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                {msg.role === 'assistant' && (
                  <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: 'linear-gradient(135deg, #00C6FF, #0072FF)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Bot size={18} color="#050816" /></div>
                )}
                <div style={{ maxWidth: '85%', padding: msg.role === 'user' ? '12px 20px' : '0', borderRadius: '16px', background: msg.role === 'user' ? 'rgba(0,198,255,0.1)' : 'transparent', border: msg.role === 'user' ? '1px solid rgba(0,198,255,0.2)' : 'none' }}>
                  <div className="prose"><ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown></div>
                </div>
              </motion.div>
            ))}
            {isTyping && <div className="typing-indicator" style={{ marginLeft: '56px' }}><div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" /></div>}
            <div ref={chatEndRef} />
          </div>
        </div>

        <div style={{ padding: '0 32px 40px' }}>
          <div style={{ maxWidth: '800px', margin: '0 auto' }}>
            <div style={{ position: 'relative', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '20px', padding: '8px' }}>
              <textarea ref={textareaRef} rows={1} value={input} onChange={e => setInput(e.target.value)} onKeyDown={handleKeyDown} placeholder="Ask anything..." style={{ width: '100%', background: 'transparent', border: 'none', outline: 'none', color: '#fff', fontSize: '15px', padding: '12px 16px', resize: 'none' }} />
              <button onClick={() => sendMessage()} disabled={!input.trim() || isTyping} style={{ position: 'absolute', right: '12px', bottom: '12px', width: '40px', height: '40px', borderRadius: '12px', background: '#00C6FF', border: 'none', color: '#050816', display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}><Send size={18} /></button>
            </div>
          </div>
        </div>
      </div>

      <AnimatePresence>
        {sidebarOpen && (
          <motion.div initial={{ width: 0 }} animate={{ width: 400 }} exit={{ width: 0 }} style={{ borderLeft: '1px solid rgba(255,255,255,0.08)', background: 'rgba(5,8,22,0.95)', backdropFilter: 'blur(30px)', overflow: 'hidden' }}>
            <div style={{ padding: '24px', borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between' }}>
              <h3 style={{ fontSize: '14px', fontWeight: 800 }}>Sources</h3>
              <button onClick={() => setSidebarOpen(false)} style={{ background: 'transparent', border: 'none', color: '#64748b' }}><X size={20} /></button>
            </div>
            <div style={{ padding: '24px' }}>
              {activeSources.map((src, i) => (
                <div key={i} className="glass-panel" style={{ padding: '16px', marginBottom: '12px' }}>
                  <p style={{ fontSize: '13px', color: '#94a3b8' }}>"{src.text}"</p>
                  <p style={{ fontSize: '11px', color: '#64748b', marginTop: '8px' }}>{src.document}</p>
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
