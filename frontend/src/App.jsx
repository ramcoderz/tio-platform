import { AnimatePresence, motion } from "framer-motion";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import AppShell from "./components/AppShell";
import { useAppCtx } from "./context/AppContext";
import { useSystemStore } from "./store";
import HomePage from "./pages/HomePage";
import UploadPage from "./pages/UploadPage";
import ChatPage from "./pages/ChatPage";
import ProjectsPage from "./pages/ProjectsPage";
import TasksPage from "./pages/TasksPage";
import MemoryPage from "./pages/MemoryPage";
import AdminPage from "./pages/AdminPage";
import AuditPage from "./pages/AuditPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";

export default function App() {
  const location = useLocation();
  const { user } = useAppCtx();
  const theme = useSystemStore(state => state.theme);

  return (
    <div className={theme === "dark" ? "dark" : ""}>
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
            <Route path="/upload" element={user ? <UploadPage /> : <Navigate to="/login" replace />} />
            <Route path="/chat" element={user ? <ChatPage /> : <Navigate to="/login" replace />} />
            <Route path="/projects" element={user ? <ProjectsPage /> : <Navigate to="/login" replace />} />
            <Route path="/tasks" element={user ? <TasksPage /> : <Navigate to="/login" replace />} />
            <Route path="/memory" element={user ? <MemoryPage /> : <Navigate to="/login" replace />} />
            <Route path="/admin" element={user?.role === 'admin' ? <AdminPage /> : <Navigate to="/" replace />} />
            <Route path="/audit" element={user?.role === 'admin' ? <AuditPage /> : <Navigate to="/" replace />} />
            
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </motion.div>
      </AnimatePresence>
    </AppShell>
    </div>
  );
}
