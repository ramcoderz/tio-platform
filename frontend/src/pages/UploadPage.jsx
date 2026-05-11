import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, Image, Table, Trash2, CheckCircle2, AlertCircle, Sparkles, Layers, Plus } from 'lucide-react';
import { useChatStore, useDocumentStore } from '../store';
import { api } from '../api';

function getFileIcon(name = '') {
  const ext = name.split('.').pop().toLowerCase();
  if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) return <Image size={24} color="var(--accent-yellow)" />;
  if (['csv', 'xlsx'].includes(ext)) return <Table size={24} color="var(--accent-green)" />;
  if (['md'].includes(ext)) return <Sparkles size={24} color="var(--accent-violet)" />;
  return <FileText size={24} color="var(--accent-cyan)" />;
}

function formatSize(bytes) {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`;
}

export default function UploadPage() {
  const [dragging, setDragging]   = useState(false);
  const [uploading, setUploading] = useState([]);   // { id, name, progress, done, error }
  const [status, setStatus]       = useState('');
  const fileInputRef = useRef(null);

  const { sessionId } = useChatStore();
  const { uploads, addUpload, setUploads } = useDocumentStore();

  // Fetch existing docs for this session
  useEffect(() => {
    const fetchDocuments = async () => {
      try {
        const data = await api(`/documents/session/${encodeURIComponent(sessionId)}`);
        if (Array.isArray(data)) {
          setUploads(data.map(d => ({
            id: d.document_id,
            name: d.name,
            type: d.type,
            size: d.size,
            chunks: d.chunks,
            summary: d.summary,
            isImage: d.type?.startsWith('image/'),
          })));
        }
      } catch { /* silent */ }
    };
    if (sessionId) fetchDocuments();
  }, [sessionId, setUploads]);

  const uploadFiles = async (files) => {
    const list = Array.from(files);
    if (!list.length) return;
    setStatus(`Ingesting ${list.length} file(s)…`);

    for (const file of list) {
      const uid = `${Date.now()}-${file.name}`;
      setUploading(prev => [...prev, { id: uid, name: file.name, progress: 30, done: false }]);

      const formData = new FormData();
      formData.append('file', file);
      const url = `/api/documents/upload?session_id=${encodeURIComponent(sessionId)}`;

      try {
        const token = localStorage.getItem("token");
        const res = await fetch(url, { 
          method: 'POST', 
          headers: {
            ...(token ? { "Authorization": `Bearer ${token}` } : {}),
          },
          body: formData 
        });
        const data = await res.json();

        setUploading(prev => prev.map(u => u.id === uid ? { ...u, progress: 100, done: true } : u));

        addUpload({
          id: data.document_id || uid,
          name: file.name,
          type: file.type,
          size: file.size,
          chunks: data.chunks,
          isImage: file.type.startsWith('image/'),
          summary: data.summary,
        });

        setTimeout(() => setUploading(prev => prev.filter(u => u.id !== uid)), 2000);
      } catch {
        setUploading(prev => prev.map(u => u.id === uid ? { ...u, error: true, done: true } : u));
      }
    }
    setStatus('');
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    uploadFiles(e.dataTransfer.files);
  };

  const removeUpload = (id) => {
    setUploads(uploads.filter(u => u.id !== id));
  };

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1200px' }}>
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-cyan)', boxShadow: '0 0 8px var(--accent-cyan)' }} />
          <span style={{ fontSize: '11px', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', fontWeight: 600 }}>KNOWLEDGE ACQUISITION</span>
        </div>
        <h1 style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em', marginBottom: '6px' }}>
          Document Intelligence
        </h1>
        <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
          Upload knowledge assets and unlock multimodal semantic insights.
        </p>
      </div>

      {/* Drop Zone */}
      <motion.div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        animate={{ borderColor: dragging ? 'var(--accent-cyan)' : 'rgba(255,255,255,0.12)', background: dragging ? 'rgba(0,229,255,0.04)' : 'rgba(255,255,255,0.02)' }}
        style={{
          border: '2px dashed rgba(255,255,255,0.12)',
          borderRadius: '20px',
          height: '220px',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          gap: '14px', cursor: 'pointer', transition: 'all 0.2s ease', marginBottom: '40px',
          position: 'relative', overflow: 'hidden',
        }}
      >
        <div style={{
          width: '60px', height: '60px', borderRadius: '16px',
          background: dragging ? 'rgba(0,229,255,0.12)' : 'rgba(37,99,235,0.1)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'all 0.2s ease',
        }}>
          <Upload size={26} color={dragging ? 'var(--accent-cyan)' : 'var(--accent-blue-light)'} />
        </div>
        <div style={{ textAlign: 'center' }}>
          <p style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '4px' }}>
            {dragging ? 'Drop to ingest' : 'Drop files here or click to browse'}
          </p>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            PDF · XLSX · CSV · TXT · MD · DOCX · PNG · JPG
          </p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          style={{ display: 'none' }}
          onChange={e => uploadFiles(e.target.files)}
        />
      </motion.div>

      {/* Active Upload Progress */}
      <AnimatePresence>
        {uploading.length > 0 && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            style={{ marginBottom: '32px', display: 'flex', flexDirection: 'column', gap: '8px' }}
          >
            {uploading.map(u => (
              <div key={u.id} className="glass-panel" style={{ padding: '12px 16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                {u.error
                  ? <AlertCircle size={16} color="var(--accent-red)" />
                  : u.done
                  ? <CheckCircle2 size={16} color="var(--accent-green)" />
                  : <div className="loading-spinner" />
                }
                <span style={{ flex: 1, fontSize: '13px', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{u.name}</span>
                {!u.done && (
                  <div style={{ width: '80px', height: '3px', background: 'rgba(255,255,255,0.08)', borderRadius: '2px', overflow: 'hidden' }}>
                    <motion.div
                      animate={{ width: [`${u.progress}%`, '95%'] }}
                      transition={{ duration: 3, ease: 'easeOut' }}
                      style={{ height: '100%', background: 'linear-gradient(90deg, var(--accent-blue), var(--accent-cyan))', borderRadius: '2px' }}
                    />
                  </div>
                )}
              </div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Main Content Area with Folders Sidebar */}
      <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: '40px' }}>
        
        {/* Folders Sidebar */}
        <aside style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
          <section>
            <h3 style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '16px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Layers size={12} /> Workspace
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <FolderItem icon={CheckCircle2} label="All Documents" active count={uploads.length} />
              <FolderItem icon={Image} label="Visual Assets" count={uploads.filter(u => u.isImage).length} />
              <FolderItem icon={FileText} label="Research Papers" count={0} />
              <FolderItem icon={Sparkles} label="AI Generated" count={uploads.filter(u => u.summary).length} />
            </div>
          </section>

          <section>
            <h3 style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '16px' }}>Collections</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <button style={{ padding: '8px 12px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                <Plus size={14} /> New Collection
              </button>
            </div>
          </section>
        </aside>

        {/* Document Grid */}
        <div>
          <div style={{ marginBottom: '16px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Active Knowledge Assets
            </h2>
          </div>

          {uploads.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px 20px', opacity: 0.4 }}>
              <Layers size={40} color="var(--text-muted)" style={{ margin: '0 auto 12px' }} />
              <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>No documents ingested yet</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
              {uploads.map((doc, i) => (
                <motion.div
                  key={doc.id}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className="glass-panel"
                  style={{ padding: '20px', position: 'relative', overflow: 'hidden' }}
                >
                  {/* Top row */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '14px' }}>
                    <div style={{ width: '44px', height: '44px', borderRadius: '12px', background: 'rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                      {getFileIcon(doc.name)}
                    </div>
                    <button
                      onClick={() => removeUpload(doc.id)}
                      style={{ padding: '6px', borderRadius: '8px', background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', opacity: 0, transition: 'all 0.15s ease' }}
                      onMouseEnter={e => { e.currentTarget.style.opacity = 1; e.currentTarget.style.color = 'var(--accent-red)'; e.currentTarget.style.background = 'var(--accent-red-dim)'; }}
                      onMouseLeave={e => { e.currentTarget.style.opacity = 0; }}
                      className="doc-delete-btn"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>

                  {/* Name */}
                  <p style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: '4px' }}>
                    {doc.name}
                  </p>
                  <p style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '12px' }}>
                    {formatSize(doc.size)}{doc.chunks ? ` · ${doc.chunks} chunks` : ''}
                  </p>

                  {/* Summary preview */}
                  {doc.summary && (
                    <p style={{ fontSize: '11px', color: 'var(--text-secondary)', lineHeight: 1.6, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', marginBottom: '12px', borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
                      {doc.summary}
                    </p>
                  )}

                  {/* Tags */}
                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    <span className="badge badge-blue">Session</span>
                    {doc.isImage && <span className="badge badge-yellow" style={{ background: 'var(--accent-yellow-dim)', color: 'var(--accent-yellow)', borderColor: 'rgba(245,158,11,0.3)' }}>Visual</span>}
                    <span className="badge badge-cyan">Indexed</span>
                  </div>

                  {/* Hover glow */}
                  <div style={{ position: 'absolute', inset: 0, borderRadius: 'inherit', background: 'radial-gradient(circle at 80% 20%, rgba(37,99,235,0.06) 0%, transparent 60%)', opacity: 0, transition: 'opacity 0.3s ease', pointerEvents: 'none' }} className="doc-hover-glow" />
                </motion.div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FolderItem({ icon: Icon, label, active, count }) {
  return (
    <button style={{
      display: 'flex', alignItems: 'center', gap: '12px', width: '100%',
      padding: '10px 12px', borderRadius: '10px', border: 'none',
      background: active ? 'rgba(255,255,255,0.06)' : 'transparent',
      color: active ? 'var(--text-primary)' : 'var(--text-secondary)',
      cursor: 'pointer', transition: 'all 0.2s ease',
      textAlign: 'left'
    }}>
      <Icon size={16} color={active ? 'var(--accent-blue)' : 'var(--text-muted)'} />
      <span style={{ flex: 1, fontSize: '13px', fontWeight: active ? 600 : 500 }}>{label}</span>
      {count > 0 && <span style={{ fontSize: '10px', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '6px' }}>{count}</span>}
    </button>
  );
}
