import { useState, useRef, useEffect, useCallback } from "react";
import { MessageSquare, X, Send, Bot, Sparkles, Zap, ChevronDown, Plus } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import SkillsMenu from "./SkillsMenu";

// Domain-specific quick actions surfaced in the widget
const DOMAIN_QUICK_ACTIONS = {
  tourism:   ["Plan my trip", "Top attractions", "Best time to visit"],
  education: ["Find courses", "Admission requirements", "Scholarship info"],
  medical:   ["Find a department", "Book appointment", "Emergency contacts"],
  developer: ["API authentication", "Code example", "List endpoints"],
  ecommerce: ["Top products", "Return policy", "Shipping info"],
  general:   ["What can you help with?", "Summarise this site"],
};

// Typing indicator dots component
function TypingDots() {
  return (
    <div style={{ display: "flex", gap: "4px", padding: "6px 2px", alignItems: "center" }}>
      {[0, 1, 2].map(i => (
        <div
          key={i}
          style={{
            width: "7px", height: "7px", borderRadius: "50%",
            background: "var(--widget-accent, #00C6FF)",
            animation: `widgetBounce 1.2s ${i * 0.15}s infinite ease-in-out`,
          }}
        />
      ))}
    </div>
  );
}

// Single chat message bubble
function MessageBubble({ msg }) {
  const isUser = msg.role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      style={{
        display: "flex",
        justifyContent: isUser ? "flex-end" : "flex-start",
        marginBottom: "12px",
      }}
    >
      {!isUser && (
        <div style={{
          width: "26px", height: "26px", borderRadius: "8px", flexShrink: 0,
          background: "linear-gradient(135deg, #00C6FF, #0072FF)",
          display: "flex", alignItems: "center", justifyContent: "center",
          marginRight: "8px", marginTop: "2px",
        }}>
          <Bot size={13} color="#050816" />
        </div>
      )}
      <div
        style={{
          maxWidth: "82%",
          padding: "10px 14px",
          borderRadius: isUser ? "16px 16px 4px 16px" : "4px 16px 16px 16px",
          background: isUser
            ? "linear-gradient(135deg, #0072FF, #00C6FF)"
            : "rgba(255,255,255,0.07)",
          color: "#fff",
          fontSize: "13px",
          lineHeight: 1.55,
          border: isUser ? "none" : "1px solid rgba(255,255,255,0.1)",
          backdropFilter: "blur(8px)",
          wordBreak: "break-word",
          whiteSpace: "pre-wrap",
        }}
      >
        {msg.content}
      </div>
    </motion.div>
  );
}

/**
 * ChatWidget — floating embeddable chatbot widget.
 *
 * Props:
 *   chatbotId  {number}  — ID of the TiO chatbot to connect to
 *   domain     {string}  — detected domain for quick actions ("tourism" | "education" | ...)
 *   title      {string}  — widget header title (default: "TiO Assistant")
 *   apiBase    {string}  — base URL for the TiO API (default: window.location.origin)
 *   accentColor {string} — primary accent hex (default: "#00C6FF")
 */
export default function ChatWidget({
  chatbotId,
  domain = "general",
  title = "TiO Assistant",
  apiBase,
  accentColor = "#00C6FF",
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [unread, setUnread] = useState(0);
  const [showActions, setShowActions] = useState(true);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [wsStatus, setWsStatus] = useState('disconnected');

  const wsRef = useRef(null);
  const chatEndRef = useRef(null);
  const inputRef = useRef(null);
  const sessionId = useRef(null);
  const reconnectRef = useRef(0);

  const base = apiBase || (typeof window !== "undefined" ? window.location.origin : "http://localhost:8000");
  const quickActions = DOMAIN_QUICK_ACTIONS[domain] || DOMAIN_QUICK_ACTIONS.general;

  // 1. SERIALIZED INITIALIZATION
  useEffect(() => {
    if (!chatbotId) return;
    
    // Create/Restore session ID with chatbot affinity
    const storedSession = localStorage.getItem(`tio_widget_session_${chatbotId}`);
    if (storedSession) {
      sessionId.current = storedSession;
    } else {
      const newId = `guest_${Math.random().toString(36).slice(2, 7)}-c${chatbotId}`;
      sessionId.current = newId;
      localStorage.setItem(`tio_widget_session_${chatbotId}`, newId);
    }
  }, [chatbotId]);

  // 2. PROTECTED WEBSOCKET CONNECTION
  const connectWS = useCallback(() => {
    // GUARDS
    if (!chatbotId || !sessionId.current) return;
    if (!sessionId.current.endsWith(`-c${chatbotId}`)) return;
    if (wsStatus === 'connected' || wsStatus === 'connecting') return;

    setWsStatus('connecting');
    const wsBase = base.replace(/^http/, "ws");
    const token = typeof localStorage !== "undefined" ? (localStorage.getItem("token") || "") : "";

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    try {
      const ws = new WebSocket(`${wsBase}/ws/chat/${sessionId.current}?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsStatus('connected');
        reconnectRef.current = 0;
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === "token") {
            setIsStreaming(false);
            setMessages(prev => {
              const last = prev[prev.length - 1];
              if (last?.role === "assistant" && last._streaming) {
                return [...prev.slice(0, -1), { ...last, content: last.content + data.content }];
              }
              return [...prev, { role: "assistant", content: data.content, _streaming: true }];
            });
            if (!isOpen) setUnread(u => u + 1);
          } else if (data.type === "final") {
            setIsStreaming(false);
            setMessages(prev => {
              const last = prev[prev.length - 1];
              if (last?.role === "assistant") {
                return [...prev.slice(0, -1), { role: "assistant", content: data.answer, _streaming: false }];
              }
              return prev;
            });
          }
        } catch { /* ignore */ }
      };

      ws.onclose = () => {
        setWsStatus('disconnected');
        reconnectRef.current++;
        if (reconnectRef.current < 5) {
          setTimeout(connectWS, 2000 * reconnectRef.current);
        }
      };

      ws.onerror = () => setWsStatus('error');

    } catch (err) {
      setWsStatus('error');
    }
  }, [base, isOpen, chatbotId, wsStatus]);

  useEffect(() => {
    connectWS();
    return () => wsRef.current?.close();
  }, [connectWS]);

  // ── Auto-scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isStreaming]);

  // ── Focus input when opening ──────────────────────────────────────────────
  useEffect(() => {
    if (isOpen) {
      setUnread(0);
      setTimeout(() => inputRef.current?.focus(), 120);
    }
  }, [isOpen]);

  // ── Send via WS, fallback to HTTP POST ───────────────────────────────────
  const sendMessage = useCallback((text) => {
    const msg = (text || input).trim();
    if (!msg || isStreaming) return;
    setInput("");
    setShowActions(false);
    setIsStreaming(true);
    setMessages(prev => [...prev, { role: "user", content: msg }]);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        message: msg,
        chatbot_id: chatbotId ? parseInt(chatbotId) : null,
        session_id: sessionId.current,
      }));
    } else {
      // HTTP fallback
      fetch(`${base}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chatbot_id: chatbotId ? parseInt(chatbotId) : null,
          session_id: sessionId.current,
          message: msg,
        }),
      })
        .then(r => r.json())
        .then(data => {
          setIsStreaming(false);
          setMessages(prev => [...prev, { role: "assistant", content: data.answer || "No response." }]);
        })
        .catch(() => {
          setIsStreaming(false);
          setMessages(prev => [...prev, { role: "assistant", content: "Connection lost. Please try again." }]);
        });
    }
  }, [input, isStreaming, chatbotId, base]);

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    if (e.key === "Escape") setSkillsOpen(false);
  };

  const handleInputChange = (e) => {
    const val = e.target.value;
    setInput(val);
    if (val.startsWith("/")) setSkillsOpen(true);
    else setSkillsOpen(false);
  };

  const executeSkill = async (skillId) => {
    setSkillsOpen(false);
    setIsStreaming(true);
    setInput("");
    setMessages(prev => [...prev, { role: "assistant", content: `🚀 Running ${skillId.replace(/_/g, ' ')}...`, _isSkill: true }]);
    
    try {
      const response = await fetch(`${base}/api/skills/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          skill_id: skillId,
          chatbot_id: chatbotId ? parseInt(chatbotId) : null,
          session_id: sessionId.current,
          args: { query: "general information" }
        })
      });
      const result = await response.json();
      setMessages(prev => {
        const f = prev.filter(m => !m._isSkill);
        return [...f, { role: "assistant", content: result.answer }];
      });
    } catch {
      setMessages(prev => [...prev, { role: "assistant", content: "⚠️ Skill failed." }]);
    } finally {
      setIsStreaming(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      {/* Keyframe animations injected once */}
      <style>{`
        @keyframes widgetBounce {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
          40% { transform: translateY(-5px); opacity: 1; }
        }
        @keyframes widgetPulse {
          0%, 100% { box-shadow: 0 0 0 0 ${accentColor}55; }
          50% { box-shadow: 0 0 0 8px ${accentColor}00; }
        }
        .tio-input:focus { outline: none; }
        .tio-input::placeholder { color: rgba(255,255,255,0.3); }
        .tio-action-chip:hover {
          background: rgba(0,198,255,0.12) !important;
          border-color: rgba(0,198,255,0.3) !important;
          color: #00C6FF !important;
        }
        .tio-send-btn:hover:not(:disabled) {
          transform: scale(1.05);
          box-shadow: 0 4px 16px ${accentColor}55;
        }
        .tio-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }
        .tio-launcher:hover { transform: scale(1.07); }
        .tio-launcher:active { transform: scale(0.97); }
      `}</style>

      <div style={{ position: "fixed", bottom: "24px", right: "24px", zIndex: 99999, fontFamily: "Inter, -apple-system, sans-serif" }}>

        {/* Chat Panel */}
        <AnimatePresence>
          {isOpen && (
            <motion.div
              initial={{ opacity: 0, y: 24, scale: 0.93 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 24, scale: 0.93 }}
              transition={{ type: "spring", stiffness: 320, damping: 28 }}
              style={{
                width: "380px",
                height: "560px",
                marginBottom: "16px",
                display: "flex",
                flexDirection: "column",
                borderRadius: "20px",
                overflow: "hidden",
                background: "rgba(9, 14, 30, 0.92)",
                backdropFilter: "blur(24px)",
                border: "1px solid rgba(255,255,255,0.1)",
                boxShadow: "0 24px 60px rgba(0,0,0,0.6), 0 0 0 1px rgba(0,198,255,0.06)",
              }}
            >
              {/* Header */}
              <div style={{
                padding: "16px 18px",
                background: "linear-gradient(135deg, rgba(0,114,255,0.5), rgba(0,198,255,0.3))",
                borderBottom: "1px solid rgba(255,255,255,0.08)",
                display: "flex", alignItems: "center", justifyContent: "space-between",
                backdropFilter: "blur(12px)",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <div style={{
                    width: "34px", height: "34px", borderRadius: "10px",
                    background: "linear-gradient(135deg, #00C6FF, #0072FF)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    boxShadow: "0 4px 12px rgba(0,198,255,0.4)",
                  }}>
                    <Bot size={17} color="#050816" />
                  </div>
                  <div>
                    <div style={{ fontSize: "14px", fontWeight: 700, color: "#fff", lineHeight: 1.2 }}>{title}</div>
                    <div style={{ display: "flex", alignItems: "center", gap: "5px", marginTop: "2px" }}>
                      <div style={{ width: "6px", height: "6px", borderRadius: "50%", background: "#10B981", animation: "widgetPulse 2s infinite" }} />
                      <span style={{ fontSize: "11px", color: "rgba(255,255,255,0.6)" }}>Online · {domain}</span>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => setIsOpen(false)}
                  style={{ color: "rgba(255,255,255,0.5)", padding: "6px", borderRadius: "8px", transition: "color 0.15s", cursor: "pointer" }}
                  onMouseEnter={e => e.currentTarget.style.color = "#fff"}
                  onMouseLeave={e => e.currentTarget.style.color = "rgba(255,255,255,0.5)"}
                >
                  <X size={17} />
                </button>
              </div>

              {/* Messages */}
              <div
                className="custom-scrollbar"
                style={{ flex: 1, overflowY: "auto", padding: "20px 16px 8px" }}
              >
                {/* Empty state */}
                {messages.length === 0 && (
                  <div style={{ textAlign: "center", paddingTop: "32px" }}>
                    <div style={{
                      width: "52px", height: "52px", borderRadius: "16px",
                      background: "linear-gradient(135deg, rgba(0,114,255,0.2), rgba(0,198,255,0.1))",
                      border: "1px solid rgba(0,198,255,0.2)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      margin: "0 auto 14px",
                    }}>
                      <Sparkles size={22} color="#00C6FF" />
                    </div>
                    <p style={{ fontSize: "14px", fontWeight: 600, color: "#fff", marginBottom: "4px" }}>
                      {title}
                    </p>
                    <p style={{ fontSize: "12px", color: "rgba(255,255,255,0.4)", marginBottom: "20px" }}>
                      Ask anything — I'll give you a direct answer.
                    </p>
                  </div>
                )}

                {/* Quick action chips (shown until first message) */}
                {showActions && messages.length === 0 && (
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", justifyContent: "center", marginBottom: "16px" }}>
                    {quickActions.map(action => (
                      <button
                        key={action}
                        className="tio-action-chip"
                        onClick={() => sendMessage(action)}
                        style={{
                          padding: "7px 14px", borderRadius: "20px",
                          background: "rgba(255,255,255,0.05)",
                          border: "1px solid rgba(255,255,255,0.1)",
                          color: "rgba(255,255,255,0.7)", fontSize: "12px",
                          cursor: "pointer", transition: "all 0.2s",
                        }}
                      >
                        {action}
                      </button>
                    ))}
                  </div>
                )}

                {/* Message list */}
                {messages.map((msg, i) => (
                  <MessageBubble key={i} msg={msg} />
                ))}

                {/* Typing indicator */}
                {isStreaming && (
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                    <div style={{
                      width: "26px", height: "26px", borderRadius: "8px", flexShrink: 0,
                      background: "linear-gradient(135deg, #00C6FF, #0072FF)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      <Bot size={13} color="#050816" />
                    </div>
                    <TypingDots />
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>

              {/* Input */}
              <div style={{
                padding: "12px 14px 16px",
                borderTop: "1px solid rgba(255,255,255,0.07)",
                background: "rgba(0,0,0,0.2)",
              }}>
                <div style={{
                  display: "flex", alignItems: "flex-end", gap: "8px",
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "14px", padding: "8px 8px 8px 14px",
                  transition: "border-color 0.2s",
                }}>
                  <textarea
                    ref={inputRef}
                    className="tio-input"
                    rows={1}
                    value={input}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask anything or / for skills..."
                    style={{
                      flex: 1, background: "transparent", border: "none",
                      color: "#fff", fontSize: "13px", resize: "none",
                      lineHeight: 1.5, maxHeight: "80px",
                    }}
                  />
                  <AnimatePresence>
                    {skillsOpen && (
                      <div style={{ position: "absolute", bottom: "100%", left: 0, marginBottom: "12px", width: "100%" }}>
                        <SkillsMenu 
                          domain={domain} 
                          onSelect={executeSkill} 
                          onClose={() => setSkillsOpen(false)} 
                        />
                      </div>
                    )}
                  </AnimatePresence>
                  <button
                    className="tio-send-btn"
                    onClick={() => sendMessage()}
                    disabled={!input.trim() || isStreaming}
                    style={{
                      width: "34px", height: "34px", borderRadius: "10px", flexShrink: 0,
                      background: input.trim() && !isStreaming
                        ? "linear-gradient(135deg, #0072FF, #00C6FF)"
                        : "rgba(255,255,255,0.08)",
                      color: input.trim() && !isStreaming ? "#fff" : "rgba(255,255,255,0.3)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      cursor: "pointer", transition: "all 0.2s",
                      border: "none",
                    }}
                  >
                    <Send size={15} />
                  </button>
                </div>
                <div style={{ textAlign: "center", marginTop: "8px" }}>
                  <span style={{ fontSize: "10px", color: "rgba(255,255,255,0.2)" }}>Powered by TiO · Local AI</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Launcher Button */}
        <motion.button
          className="tio-launcher"
          onClick={() => setIsOpen(o => !o)}
          style={{
            width: "58px", height: "58px", borderRadius: "50%",
            background: "linear-gradient(135deg, #0072FF, #00C6FF)",
            color: "#fff", border: "none", cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "0 8px 28px rgba(0,198,255,0.4)",
            position: "relative", transition: "transform 0.2s, box-shadow 0.2s",
          }}
        >
          <AnimatePresence mode="wait">
            {isOpen ? (
              <motion.div key="close" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.18 }}>
                <X size={24} />
              </motion.div>
            ) : (
              <motion.div key="open" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }} transition={{ duration: 0.18 }}>
                <MessageSquare size={24} />
              </motion.div>
            )}
          </AnimatePresence>

          {/* Unread badge */}
          {unread > 0 && !isOpen && (
            <div style={{
              position: "absolute", top: "-2px", right: "-2px",
              width: "18px", height: "18px", borderRadius: "50%",
              background: "#EF4444", fontSize: "10px", fontWeight: 700, color: "#fff",
              display: "flex", alignItems: "center", justifyContent: "center",
              border: "2px solid #050816",
            }}>
              {unread > 9 ? "9+" : unread}
            </div>
          )}
        </motion.button>
      </div>
    </>
  );
}
