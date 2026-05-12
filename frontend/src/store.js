import { create } from 'zustand';

// Generate a stable session ID tied to a specific user account + chatbot
export function makeSessionId(userId, chatbotId) {
  return `u${userId}-c${chatbotId || 'global'}`;
}

export const useChatStore = create((set) => ({
  // Default: random fallback until user logs in
  sessionId: localStorage.getItem("tio_session_id") || `session-${Math.random().toString(36).slice(2)}`,
  messages: [],
  isTyping: false,

  // Called on login — binds session to user account
  setSessionFromUser: (userId, chatbotId) => set(() => {
    const id = makeSessionId(userId, chatbotId);
    localStorage.setItem("tio_session_id", id);
    return { sessionId: id, messages: [] };
  }),

  setSessionId: (id) => set({ sessionId: id }),
  setMessages: (updater) => set((state) => ({
    messages: typeof updater === 'function' ? updater(state.messages) : updater
  })),
  setTyping: (status) => set({ isTyping: status }),
  clearSession: () => set((state) => {
    const next = `session-${Math.random().toString(36).slice(2)}`;
    localStorage.setItem("tio_session_id", next);
    return { sessionId: next, messages: [], isTyping: false };
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
