import { useState, useEffect } from "react";
import { 
  FileText, Database, Clock, Search, 
  Filter, MoreVertical, Trash2, ExternalLink, Bot
} from "lucide-react";
import { api } from "../api";

export default function FilesPage() {
  const [chatbots, setChatbots] = useState([]);
  const [selectedChatbot, setSelectedChatbot] = useState(null);
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchChatbots = async () => {
      try {
        const data = await api("/chatbots");
        setChatbots(data || []);
        if (data.length > 0) setSelectedChatbot(data[0]);
      } catch (err) {
        console.error(err);
      }
    };
    fetchChatbots();
  }, []);

  useEffect(() => {
    if (selectedChatbot) {
      const fetchFiles = async () => {
        setLoading(true);
        try {
          const data = await api(`/chatbots/${selectedChatbot.id}/files`);
          setFiles(data || []);
        } catch (err) {
          console.error(err);
        } finally {
          setLoading(false);
        }
      };
      fetchFiles();
    }
  }, [selectedChatbot]);

  return (
    <div style={{ padding: '40px', maxWidth: '1400px', margin: '0 auto' }}>
      <header style={{ marginBottom: '40px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: 800, marginBottom: '8px' }}>Workspace Knowledge Base</h1>
          <p style={{ color: '#64748b' }}>Manage uploaded documents and scraped website content.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '10px', padding: '10px 16px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Bot size={18} color="#00C6FF" />
            <select 
              value={selectedChatbot?.id || ""} 
              onChange={(e) => setSelectedChatbot(chatbots.find(cb => cb.id === parseInt(e.target.value)))}
              style={{ background: 'transparent', border: 'none', color: '#fff', fontSize: '14px', fontWeight: 600, outline: 'none' }}
            >
              {chatbots.map(cb => (
                <option key={cb.id} value={cb.id}>{cb.name}</option>
              ))}
            </select>
          </div>
        </div>
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '24px' }}>
        
        {/* Stats Row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '20px' }}>
          <StatCard icon={FileText} label="Total Documents" value={files.length} color="#00C6FF" />
          <StatCard icon={Database} label="Indexed Chunks" value={files.reduce((acc, f) => acc + (f.chunks || 0), 0)} color="#7C3AED" />
          <StatCard icon={Clock} label="Last Updated" value={files.length > 0 ? "Today" : "N/A"} color="#10B981" />
          <StatCard icon={Bot} label="Chatbot Domain" value={selectedChatbot?.domain || "Unknown"} color="#F59E0B" />
        </div>

        {/* Files Table */}
        <div className="glass-panel" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '20px 24px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div style={{ position: 'relative' }}>
                <Search size={16} style={{ position: 'absolute', left: '12px', top: '10px', color: '#64748b' }} />
                <input 
                  type="text" 
                  placeholder="Search files..." 
                  style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', padding: '8px 12px 8px 36px', fontSize: '13px', color: '#fff', width: '240px' }}
                />
              </div>
              <button style={{ background: 'transparent', border: '1px solid rgba(255,255,255,0.08)', borderRadius: '8px', padding: '8px 12px', fontSize: '13px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Filter size={14} /> Filter
              </button>
            </div>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <th style={{ padding: '16px 24px', fontSize: '12px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>File Name</th>
                <th style={{ padding: '16px 24px', fontSize: '12px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Type</th>
                <th style={{ padding: '16px 24px', fontSize: '12px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Status</th>
                <th style={{ padding: '16px 24px', fontSize: '12px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Chunks</th>
                <th style={{ padding: '16px 24px', fontSize: '12px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Created At</th>
                <th style={{ padding: '16px 24px' }}></th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan="6" style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading documents...</td>
                </tr>
              ) : files.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>No documents found for this chatbot.</td>
                </tr>
              ) : (
                files.map((file) => (
                  <tr key={file.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }} className="hover-row">
                    <td style={{ padding: '16px 24px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <FileText size={16} color="#00C6FF" />
                        </div>
                        <span style={{ fontSize: '14px', fontWeight: 600 }}>{file.filename}</span>
                      </div>
                    </td>
                    <td style={{ padding: '16px 24px' }}>
                      <span style={{ fontSize: '12px', color: '#94a3b8' }}>{file.type}</span>
                    </td>
                    <td style={{ padding: '16px 24px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#10B981' }} />
                        <span style={{ fontSize: '13px', color: '#10B981', fontWeight: 500 }}>Indexed</span>
                      </div>
                    </td>
                    <td style={{ padding: '16px 24px' }}>
                      <span style={{ fontSize: '14px', fontWeight: 600 }}>{file.chunks}</span>
                    </td>
                    <td style={{ padding: '16px 24px' }}>
                      <span style={{ fontSize: '13px', color: '#64748b' }}>{new Date(file.created_at).toLocaleDateString()}</span>
                    </td>
                    <td style={{ padding: '16px 24px', textAlign: 'right' }}>
                      <button style={{ background: 'transparent', border: 'none', color: '#64748b', cursor: 'pointer' }}>
                        <MoreVertical size={16} />
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <div className="glass-panel" style={{ padding: '20px', display: 'flex', alignItems: 'center', gap: '16px' }}>
      <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: `${color}10`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={24} color={color} />
      </div>
      <div>
        <p style={{ fontSize: '12px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: '4px' }}>{label}</p>
        <p style={{ fontSize: '20px', fontWeight: 800 }}>{value}</p>
      </div>
    </div>
  );
}
