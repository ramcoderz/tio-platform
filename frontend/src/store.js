import { create } from 'zustand';

// Generate a stable session ID tied to a specific user account + chatbot
export function makeSessionId(userId, chatbotId) {
  return `u${userId}-c${chatbotId || 'global'}`;
}

export const useChatStore = create((set) => ({
  // Default: random fallback until user logs in
  sessionId: localStorage.getItem("tio_session_id") || null,
  messages: [],
  isTyping: false,
  wsStatus: 'disconnected', // 'disconnected' | 'connecting' | 'connected' | 'error'

  // Serialized session update
  syncSession: (userId, chatbotId) => {
    const id = makeSessionId(userId, chatbotId);
    localStorage.setItem("tio_session_id", id);
    set({ sessionId: id, messages: [], wsStatus: 'disconnected' });
    return id;
  },

  setSessionId: (id) => set({ sessionId: id }),
  setWsStatus: (status) => set({ wsStatus: status }),
  setMessages: (updater) => set((state) => ({
    messages: typeof updater === 'function' ? updater(state.messages) : updater
  })),
  setTyping: (status) => set({ isTyping: status }),
  clearSession: () => set((state) => {
    localStorage.removeItem("tio_session_id");
    return { sessionId: null, messages: [], isTyping: false, wsStatus: 'disconnected' };
  })
}));


export const useDocumentStore = create((set) => ({
  uploads: JSON.parse(localStorage.getItem("tio_uploads") || "[]"),
  addUpload: (upload) => set((state) => {
    const next = [upload, ...state.uploads].slice(0, 50);
    localStorage.setItem("tio_uploads", JSON.stringify(next));
    return { uploads: next };
  }),
  setUploads: (uploads) => set(() => {
    localStorage.setItem("tio_uploads", JSON.stringify(uploads));
    return { uploads };
  }),
  clearUploads: () => set(() => {
    localStorage.removeItem("tio_uploads");
    return { uploads: [] };
  })
}));

export const useSystemStore = create((set) => ({
  theme: localStorage.getItem("tio_theme") || "dark",
  toggleTheme: () => set((state) => {
    const next = state.theme === "dark" ? "light" : "dark";
    localStorage.setItem("tio_theme", next);
    if (next === "dark") document.documentElement.classList.add("dark");
    else document.documentElement.classList.remove("dark");
    return { theme: next };
  })
}));
