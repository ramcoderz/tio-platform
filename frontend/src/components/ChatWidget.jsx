import { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Send, Bot, User, Sparkles, Loader2 } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api";

export default function ChatWidget({ chatbotId, title = "TiO Assistant", theme = "dark" }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => `widget_${Math.random().toString(36).substring(7)}`);
  const chatEndRef = useRef(null);

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = { role: "user", content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const response = await api("/chat", {
        method: "POST",
        body: JSON.stringify({
          chatbot_id: chatbotId,
          session_id: sessionId,
          message: input
        })
      });
      setMessages(prev => [...prev, { role: "assistant", content: response.answer }]);
    } catch (err) {
      setMessages(prev => [...prev, { role: "assistant", content: "Sorry, I encountered an error. Please try again." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={theme} style={{ position: 'fixed', bottom: '24px', right: '24px', zIndex: 9999, fontFamily: 'var(--font-sans)' }}>
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="glass-panel"
            style={{
              width: '380px',
              height: '520px',
              display: 'flex',
              flexDirection: 'column',
              overflow: 'hidden',
              marginBottom: '16px',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-glass)',
              boxShadow: 'var(--shadow-xl)'
            }}
          >
            {/* Header */}
            <div style={{ padding: '16px 20px', background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-blue-light))', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Bot size={20} />
                <div>
                  <h4 style={{ fontSize: '14px', fontWeight: 700, margin: 0 }}>{title}</h4>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10B981' }} />
                    <span style={{ fontSize: '10px', opacity: 0.8 }}>Online</span>
                  </div>
                </div>
              </div>
              <button onClick={() => setIsOpen(false)} style={{ color: '#fff', opacity: 0.8 }}><X size={18} /></button>
            </div>

            {/* Messages */}
            <div className="custom-scrollbar" style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {messages.length === 0 && (
                <div style={{ textAlign: 'center', marginTop: '40px', opacity: 0.6 }}>
                  <Sparkles size={32} style={{ margin: '0 auto 12px', color: 'var(--accent-blue)' }} />
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Hi! How can I help you today?</p>
                </div>
              )}
              {messages.map((msg, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start' }}>
                  <div style={{
                    maxWidth: '85%',
                    padding: '10px 14px',
                    borderRadius: '12px',
                    fontSize: '13px',
                    lineHeight: 1.5,
                    background: msg.role === 'user' ? 'var(--accent-blue)' : 'var(--bg-tertiary)',
                    color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
                    border: msg.role === 'user' ? 'none' : '1px solid var(--border-subtle)',
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start'
                  }}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {loading && (
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                  <Loader2 size={14} className="animate-spin" /> Assistant is thinking...
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Footer */}
            <form onSubmit={handleSend} style={{ padding: '16px', borderTop: '1px solid var(--border-glass)', display: 'flex', gap: '10px' }}>
              <input
                type="text"
                placeholder="Type a message..."
                value={input}
                onChange={e => setInput(e.target.value)}
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  borderRadius: '10px',
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border-glass)',
                  color: 'var(--text-primary)',
                  fontSize: '13px'
                }}
              />
              <button 
                type="submit" 
                style={{ 
                  width: '40px', height: '40px', borderRadius: '10px', 
                  background: 'var(--accent-blue)', color: '#fff', 
                  display: 'flex', alignItems: 'center', justifyContent: 'center' 
                }}
              >
                <Send size={18} />
              </button>
            </form>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setIsOpen(!isOpen)}
        style={{
          width: '60px',
          height: '60px',
          borderRadius: '50%',
          background: 'linear-gradient(135deg, var(--accent-blue), var(--accent-blue-light))',
          color: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: 'var(--shadow-lg)',
          cursor: 'pointer'
        }}
      >
        {isOpen ? <X size={28} /> : <MessageSquare size={28} />}
      </motion.button>
    </div>
  );
}
