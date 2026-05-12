import { AnimatePresence, motion } from "framer-motion";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import AppShell from "./components/AppShell";
import { useAppCtx } from "./context/AppContext";
import HomePage from "./pages/HomePage";
import CreateChatbotPage from "./pages/CreateChatbotPage";
import ChatPage from "./pages/ChatPage";
import FilesPage from "./pages/FilesPage";
import AdminPage from "./pages/AdminPage";
import SettingsPage from "./pages/SettingsPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";

export default function App() {
  const location = useLocation();
  const { user, theme } = useAppCtx();

  return (
    <div className={theme}>
      <AppShell>
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="w-full h-full"
          >
            <Routes location={location}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              
              <Route path="/" element={user ? <HomePage /> : <Navigate to="/login" replace />} />
              <Route path="/create" element={user ? <CreateChatbotPage /> : <Navigate to="/login" replace />} />
              <Route path="/chat" element={user ? <ChatPage /> : <Navigate to="/login" replace />} />
              <Route path="/files" element={user ? <FilesPage /> : <Navigate to="/login" replace />} />
              <Route path="/admin" element={user?.role === 'admin' ? <AdminPage /> : <Navigate to="/" replace />} />
              <Route path="/settings" element={user ? <SettingsPage /> : <Navigate to="/login" replace />} />
              
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </motion.div>
        </AnimatePresence>
      </AppShell>
    </div>
  );
}
