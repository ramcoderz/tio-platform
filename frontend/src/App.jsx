import { AnimatePresence, motion } from "framer-motion";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import AppShell from "./components/AppShell";
import { useAppCtx } from "./context/AppContext";

import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import LandingPage from "./pages/LandingPage";
import DashboardPage from "./pages/DashboardPage";
import ChatbotDetailPage from "./pages/ChatbotDetailPage";
import MonitorPage from "./pages/MonitorPage";
import CreateChatbotPage from "./pages/CreateChatbotPage";
import ChatPage from "./pages/ChatPage";
import FilesPage from "./pages/FilesPage";
import AdminPage from "./pages/AdminPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  const location = useLocation();
  const { user, loading } = useAppCtx();

  if (loading) {
    return (
      <div className="flex-center h-screen bg-[#03050c]">
        <div className="loader-premium"></div>
      </div>
    );
  }

  return (
    <AppShell>
      <AnimatePresence mode="wait">
        <motion.div
          key={location.pathname}
          initial={{ opacity: 0, y: 5 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -5 }}
          transition={{ duration: 0.2 }}
          style={{ height: '100%' }}
        >
          <Routes location={location}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            
            <Route path="/" element={user ? <DashboardPage /> : <LandingPage />} />
            <Route path="/create" element={user ? <CreateChatbotPage /> : <Navigate to="/login" replace />} />
            <Route path="/chat" element={user ? <ChatPage /> : <Navigate to="/login" replace />} />
            <Route path="/chatbot/:id" element={user ? <ChatbotDetailPage /> : <Navigate to="/login" replace />} />
            <Route path="/files" element={user ? <FilesPage /> : <Navigate to="/login" replace />} />
            <Route path="/monitor" element={user ? <MonitorPage /> : <Navigate to="/login" replace />} />
            <Route path="/admin" element={user?.role === 'admin' ? <AdminPage /> : <Navigate to="/" replace />} />
            <Route path="/settings" element={user ? <SettingsPage /> : <Navigate to="/login" replace />} />
            
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </motion.div>
      </AnimatePresence>
    </AppShell>
  );
}
