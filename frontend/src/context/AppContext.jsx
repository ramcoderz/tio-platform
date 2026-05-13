import { createContext, useContext, useMemo, useState, useEffect } from "react";
import { useChatStore } from "../store";

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [theme, setTheme] = useState(() => localStorage.getItem("tio_theme") || "dark");
  const [user, setUser] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      import("../api").then(({ api }) => {
        api("/auth/me")
          .then((u) => {
            setUser(u);
            // Anchor session to this user account
            useChatStore.getState().setSessionFromUser(u.id);
          })
          .catch(() => {
            localStorage.removeItem("token");
            setUser(null);
          });
      });
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
      import("../api").then(({ api }) => api("/auth/me", { method: "PUT", body: JSON.stringify({ theme: next }) }));
    }
  };

  const setLightVariant = (variant) => {
    const next = `light-${variant}`;
    localStorage.setItem("tio_theme", next);
    setTheme(next);
    // Sync to backend
    if (user) {
      import("../api").then(({ api }) => api("/auth/me", { method: "PUT", body: JSON.stringify({ theme: next }) }));
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
    <AppContext.Provider value={{ theme, toggleTheme, setLightVariant, user, setUser, logout }}>
      {children}
    </AppContext.Provider>
  );
}

export function useAppCtx() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("App context missing");
  return ctx;
}
