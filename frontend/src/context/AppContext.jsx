import { createContext, useContext, useState, useEffect } from "react";
import { useChatStore } from "../store";
import { api } from "../api";

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [theme, setTheme] = useState(() => localStorage.getItem("tio_theme") || "dark");
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    console.log("[BOOT] AppContext Initializing...");
    const token = localStorage.getItem("token");
    
    if (token) {
      console.log("[BOOT] Token found, hydrating auth...");
      api("/auth/me")
          .then((u) => {
            console.log("[BOOT] Auth successful:", u.username);
            setUser(u);
            // Anchor session to this user account
            const sid = useChatStore.getState().syncSession(u.id);
            console.log("[BOOT] Session synchronized:", sid);
          })
          .catch((err) => {
            console.error("[BOOT] Auth hydration failed:", err);
            localStorage.removeItem("token");
            setUser(null);
          })
          .finally(() => {
            console.log("[BOOT] Initialization sequence complete");
            setLoading(false);
          });
    } else {
      console.log("[BOOT] No token, guest mode.");
      setLoading(false);
    }

    // --- Inactivity Timeout (4 Hours) ---
    let timeoutId;
    const INACTIVITY_TIME = 4 * 60 * 60 * 1000; // 4 hours

    const resetTimer = () => {
      if (timeoutId) clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        if (localStorage.getItem("token")) {
           console.log("Inactivity detected. Logging out...");
           logout();
        }
      }, INACTIVITY_TIME);
    };

    const events = ["mousedown", "mousemove", "keypress", "scroll", "touchstart"];
    events.forEach(name => window.addEventListener(name, resetTimer));
    resetTimer();

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
      events.forEach(name => window.removeEventListener(name, resetTimer));
    };
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    localStorage.setItem("tio_theme", next);
    setTheme(next);
    // Sync to backend
    if (user) {
      api("/auth/me", { method: "PUT", body: JSON.stringify({ theme: next }) });
    }
  };

  const setLightVariant = (variant) => {
    const next = `light-${variant}`;
    localStorage.setItem("tio_theme", next);
    setTheme(next);
    // Sync to backend
    if (user) {
      api("/auth/me", { method: "PUT", body: JSON.stringify({ theme: next }) });
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("tio_session_id");
    localStorage.removeItem("tio_user_id");
    useChatStore.getState().clearSession();
    setUser(null);
  };


  return (
    <AppContext.Provider value={{ theme, toggleTheme, setLightVariant, user, setUser, loading, logout }}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppCtx() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("App context missing");
  return ctx;
}
