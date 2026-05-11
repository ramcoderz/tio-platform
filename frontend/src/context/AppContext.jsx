import { createContext, useContext, useMemo, useState, useEffect } from "react";

const AppContext = createContext(null);

export function AppProvider({ children }) {
  const [theme, setTheme] = useState(() => localStorage.getItem("tio_theme") || "dark");
  const [user, setUser] = useState(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      import("../api").then(({ api }) => {
        api("/auth/me")
          .then(setUser)
          .catch(() => {
            localStorage.removeItem("token");
            setUser(null);
          });
      });
    }

    // --- Inactivity Timeout (30 Minutes) ---
    let timeoutId;
    const INACTIVITY_TIME = 30 * 60 * 1000; // 30 minutes

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

  const toggleTheme = () => {
    const next = theme === "dark" ? "light-neutral" : "dark";
    localStorage.setItem("tio_theme", next);
    setTheme(next);
  };

  const setLightVariant = (variant) => {
    const next = `light-${variant}`;
    localStorage.setItem("tio_theme", next);
    setTheme(next);
  };

  const logout = () => {
    localStorage.removeItem("token");
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
