import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, RefreshCw, Eye, Search, Filter } from "lucide-react";
import { api } from "../api";

export default function AuditPage() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const data = await api("/audit/logs");
      setLogs(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("Failed to fetch audit logs", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  const filteredLogs = logs.filter(log => 
    (log.action || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (log.resource || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (log.details || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1300px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: '36px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <Shield size={13} color="var(--accent-red)" />
            <span style={{ fontSize: '11px', color: 'var(--accent-red)', fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', fontWeight: 600 }}>SECURITY & COMPLIANCE</span>
          </div>
          <h1 style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em', color: 'var(--text-primary)', marginBottom: '6px' }}>Enterprise Audit Logs</h1>
          <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Immutable ledger of system activity and resource access.</p>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
           <div className="input-wrapper" style={{ width: '280px' }}>
              <Search className="input-icon" size={16} />
              <input 
                 type="text" 
                 placeholder="Search logs..." 
                 value={searchTerm}
                 onChange={e => setSearchTerm(e.target.value)}
                 className="form-input" 
                 style={{ paddingLeft: '40px', borderRadius: '12px' }}
              />
           </div>
           <button className="btn btn-ghost" style={{ padding: '10px', borderRadius: '12px' }}>
              <Filter size={18} />
           </button>
           <button onClick={fetchLogs} className="btn btn-primary" style={{ padding: '10px 20px', borderRadius: '12px', fontSize: '13px', display: 'flex', gap: '8px' }}>
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
              Refresh
           </button>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: '24px' }}>
        {loading && logs.length === 0 ? (
           <div style={{ padding: '60px', display: 'flex', justifyContent: 'center' }}>
              <div className="loading-spinner" />
           </div>
        ) : logs.length === 0 ? (
           <div style={{ textAlign: 'center', padding: '60px 20px', opacity: 0.4 }}>
              <Eye size={40} color="var(--text-muted)" style={{ margin: '0 auto 12px' }} />
              <p style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>No audit logs recorded yet</p>
           </div>
        ) : (
           <table className="data-table">
              <thead>
                 <tr>
                    <th>Timestamp</th>
                    <th>User ID</th>
                    <th>Action</th>
                    <th>Resource</th>
                    <th>Details</th>
                    <th>IP Address</th>
                 </tr>
              </thead>
              <tbody>
                 <AnimatePresence>
                    {filteredLogs.map((log, i) => (
                       <motion.tr 
                          key={log.id}
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          transition={{ delay: i * 0.02 }}
                          style={{ borderBottom: '1px solid var(--border-subtle)' }}
                       >
                          <td style={{ fontSize: '12px', color: 'var(--text-secondary)', padding: '14px 16px' }}>
                             {new Date(log.timestamp).toLocaleString()}
                          </td>
                          <td style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                             {log.user_id || "System"}
                          </td>
                          <td>
                             <span className="badge badge-blue">
                                {log.action}
                             </span>
                          </td>
                          <td style={{ fontSize: '13px', color: 'var(--text-primary)', fontWeight: 500 }}>
                             {log.resource || "—"}
                          </td>
                          <td style={{ fontSize: '12px', color: 'var(--text-secondary)', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                             {log.details || "—"}
                          </td>
                          <td style={{ fontSize: '12px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                             {log.ip_address || "—"}
                          </td>
                       </motion.tr>
                    ))}
                 </AnimatePresence>
                 {filteredLogs.length === 0 && (
                    <tr>
                       <td colSpan={6} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                          No logs match your search.
                       </td>
                    </tr>
                 )}
              </tbody>
           </table>
        )}
      </div>
    </div>
  );
}
