import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { FileText, Upload, Trash2, ChevronDown, Search, Plus } from 'lucide-react';
import { api } from '../api';

export default function FilesPage() {
  const [searchParams] = useSearchParams();
  const chatbotId = searchParams.get('chatbot_id');
  const [chatbots, setChatbots] = useState([]);
  const [selectedBot, setSelectedBot] = useState(chatbotId || '');
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  useEffect(() => {
    api('/chatbots').then(setChatbots).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedBot) { setFiles([]); return; }
    setLoading(true);
    api(`/chatbots/${selectedBot}/files`)
      .then(setFiles)
      .catch(() => setFiles([]))
      .finally(() => setLoading(false));
  }, [selectedBot]);

  const handleUpload = async (fileList) => {
    if (!selectedBot || !fileList.length) return;
    setUploading(true);
    for (const file of fileList) {
      const fd = new FormData();
      fd.append('file', file);
      try {
        await fetch(`/api/chatbots/${selectedBot}/upload`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
          body: fd
        });
      } catch { /* silent */ }
    }
    // Refresh
    const updated = await api(`/chatbots/${selectedBot}/files`);
    setFiles(updated);
    setUploading(false);
  };

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1000px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '32px' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '6px' }}>Files</h1>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Manage knowledge base documents for your chatbots.</p>
        </div>
      </div>

      {/* Chatbot Selector */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', alignItems: 'center' }}>
        <select
          value={selectedBot}
          onChange={e => setSelectedBot(e.target.value)}
          className="input"
          style={{ maxWidth: '300px' }}
        >
          <option value="">Select a chatbot...</option>
          {chatbots.map(cb => <option key={cb.id} value={cb.id}>{cb.name}</option>)}
        </select>

        {selectedBot && (
          <button onClick={() => fileRef.current?.click()} className="btn btn-primary btn-sm" disabled={uploading}>
            <Upload size={14} /> {uploading ? 'Uploading...' : 'Upload File'}
          </button>
        )}
        <input ref={fileRef} type="file" multiple accept=".pdf,.docx,.txt,.md" onChange={e => handleUpload(e.target.files)} style={{ display: 'none' }} />
      </div>

      {/* Files Table */}
      {!selectedBot ? (
        <div className="glass-panel" style={{ padding: '48px', textAlign: 'center' }}>
          <FileText size={36} style={{ margin: '0 auto 12px', opacity: 0.15, color: 'var(--text-muted)' }} />
          <p style={{ color: 'var(--text-muted)' }}>Select a chatbot to view its files.</p>
        </div>
      ) : loading ? (
        <div className="skeleton" style={{ height: '200px' }} />
      ) : files.length === 0 ? (
        <div className="glass-panel" style={{ padding: '48px', textAlign: 'center' }}>
          <FileText size={36} style={{ margin: '0 auto 12px', opacity: 0.15, color: 'var(--text-muted)' }} />
          <p style={{ color: 'var(--text-muted)', marginBottom: '16px' }}>No documents in this chatbot's knowledge base.</p>
          <button onClick={() => fileRef.current?.click()} className="btn btn-ghost btn-sm"><Plus size={14} /> Upload Files</button>
        </div>
      ) : (
        <div className="glass-panel" style={{ padding: '0', overflow: 'hidden' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Filename</th>
                <th>Type</th>
                <th>Chunks</th>
                <th>Added</th>
              </tr>
            </thead>
            <tbody>
              {files.map((f, i) => (
                <motion.tr key={f.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.03 }}>
                  <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <FileText size={14} color="var(--accent)" />
                    <span style={{ fontWeight: 500, color: 'var(--text-primary)', maxWidth: '280px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.filename}</span>
                  </td>
                  <td><span className="badge badge-cyan" style={{ fontFamily: 'var(--font-mono)' }}>{f.type?.split('/').pop() || '—'}</span></td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontSize: '12px' }}>{f.chunks ?? '—'}</td>
                  <td style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{f.created_at ? new Date(f.created_at).toLocaleDateString() : '—'}</td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
