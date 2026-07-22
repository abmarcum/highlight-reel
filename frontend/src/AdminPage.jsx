import React, { useState, useEffect } from 'react';
import { Trash2, UserPlus, Shield, User, Eye, Settings, Save, HardDrive, Globe } from 'lucide-react';
import toast from 'react-hot-toast';

export default function AdminPage({ userRole }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState('viewer');

  const [settings, setSettings] = useState({
    ai_model: 'gemini-3.5-flash',
    analyzer_persona: '',
    producer_persona: '',
    proxy_enabled: 'false',
    proxy_host: '',
    proxy_user: '',
    proxy_pass: ''
  });
  const [storageStats, setStorageStats] = useState([]);

  const apiUrl = import.meta.env.VITE_API_URL;

  const fetchUsers = async () => {
    try {
      const res = await fetch(`${apiUrl}/users`);
      if (res.ok) {
        const data = await res.json();
        setUsers(data.users || []);
      }
    } catch (err) {
      toast.error("Error connecting to API");
    }
  };

  const fetchSettings = async () => {
    try {
      const res = await fetch(`${apiUrl}/settings`);
      if (res.ok) {
        const data = await res.json();
        setSettings({
          ai_model: 'gemini-3.6-flash',
          analyzer_persona: '',
          producer_persona: '',
          proxy_enabled: 'false',
          proxy_host: '',
          proxy_user: '',
          proxy_pass: '',
          ...data.settings
        });
      }
    } catch (err) {
      toast.error("Error connecting to API");
    }
  };

  const fetchStorage = async () => {
    try {
      const res = await fetch(`${apiUrl}/storage`);
      if (res.ok) {
        const data = await res.json();
        setStorageStats(data.storage || []);
      }
    } catch (err) {
      toast.error("Error fetching storage stats");
    }
  };

  useEffect(() => {
    if (userRole === 'admin') {
      Promise.all([fetchUsers(), fetchSettings(), fetchStorage()]).finally(() => setLoading(false));
    }
  }, [userRole]);

  const handleAddUpdateUser = async (e) => {
    e.preventDefault();
    if (!newEmail) return;

    try {
      const res = await fetch(`${apiUrl}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: newEmail, role: newRole })
      });
      if (res.ok) {
        toast.success("User role updated successfully");
        setNewEmail('');
        fetchUsers();
      } else {
        const data = await res.json();
        toast.error(`Error: ${data.error}`);
      }
    } catch (err) {
      toast.error("Error updating user");
    }
  };

  const handleDeleteUser = async (email) => {
    if (!window.confirm(`Are you sure you want to remove ${email}?`)) return;
    
    try {
      const res = await fetch(`${apiUrl}/users/${encodeURIComponent(email)}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        toast.success("User removed");
        fetchUsers();
      } else {
        const data = await res.json();
        toast.error(`Error: ${data.error}`);
      }
    } catch (err) {
      toast.error("Error deleting user");
    }
  };

  const handleSaveSettings = async (e) => {
    if (e) e.preventDefault();
    const toastId = toast.loading('Saving settings...');
    try {
      const res = await fetch(`${apiUrl}/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      if (res.ok) {
        toast.success("Settings saved successfully", { id: toastId });
      } else {
        const data = await res.json();
        toast.error(`Error: ${data.error}`, { id: toastId });
      }
    } catch (err) {
      toast.error("Error saving settings", { id: toastId });
    }
  };

  const handleClearProxy = () => {
    setSettings(prev => ({
      ...prev,
      proxy_enabled: 'false',
      proxy_host: '',
      proxy_user: '',
      proxy_pass: ''
    }));
  };

  const handlePurgeStorage = async (bucket) => {
    const bucketNameShort = bucket.split('-').pop();
    if (!window.confirm(`Are you sure you want to purge all files in ${bucketNameShort} (${bucket})? This action cannot be undone.`)) return;
    const toastId = toast.loading(`Purging ${bucketNameShort} bucket...`);
    try {
      const res = await fetch(`${apiUrl}/storage/purge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bucket })
      });
      if (res.ok) {
        const data = await res.json();
        toast.success(data.message || `Bucket purged successfully`, { id: toastId });
        fetchStorage();
      } else {
        const errData = await res.json().catch(() => ({}));
        toast.error(errData.error || 'Failed to purge bucket', { id: toastId });
      }
    } catch (err) {
      toast.error("Error purging bucket", { id: toastId });
    }
  };

  if (userRole !== 'admin') return <div className="glass-panel" style={{ marginTop: '2rem' }}><h2>Access Denied</h2><p>You must be an admin to view this page.</p></div>;

  const RoleIcon = ({ role }) => {
    if (role === 'admin') return <Shield size={14} className="role-icon admin" />;
    if (role === 'user') return <User size={14} className="role-icon user" />;
    return <Eye size={14} className="role-icon viewer" />;
  };

  if (loading) {
    return <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>Loading Admin Page...</div>;
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', marginTop: '1.5rem' }}>
      
      {/* ROW 1: User Management & AI Settings */}
      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', width: '100%' }}>
        
        {/* User Management Panel (Left) */}
        <div className="glass-panel" style={{ flex: '1 1 450px', minWidth: '320px' }}>
          <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Shield size={20} color="var(--primary)" />
            User Management
          </h2>

          <form onSubmit={handleAddUpdateUser} style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 200px' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>Email Address</label>
              <input 
                type="email" 
                value={newEmail} 
                onChange={(e) => setNewEmail(e.target.value)} 
                placeholder="user@example.com" 
                className="input-field"
                required
                style={{ width: '100%', boxSizing: 'border-box' }}
              />
            </div>
            <div style={{ flex: '1 1 120px' }}>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>Role</label>
              <select 
                value={newRole} 
                onChange={(e) => setNewRole(e.target.value)}
                className="input-field"
                style={{ width: '100%', boxSizing: 'border-box' }}
              >
                <option value="admin">Admin</option>
                <option value="user">User</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
            <button type="submit" className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: '0 0 auto' }}>
              <UserPlus size={16} />
              Add
            </button>
          </form>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-light)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '0.75rem 1rem', fontWeight: 500 }}>Email</th>
                  <th style={{ padding: '0.75rem 1rem', fontWeight: 500 }}>Role</th>
                  <th style={{ padding: '0.75rem 1rem', fontWeight: 500, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.email} style={{ borderBottom: '1px solid rgba(255,255,255,0.02)' }}>
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-light)' }}>{user.email}</td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                        <RoleIcon role={user.role} />
                        {user.role}
                      </div>
                    </td>
                    <td style={{ padding: '0.75rem 1rem', textAlign: 'right' }}>
                      <button 
                        onClick={() => handleDeleteUser(user.email)}
                        className="btn-icon btn-danger" 
                        title="Remove User"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={3} style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
                      No users found.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* AI Settings Panel (Right) */}
        <div className="glass-panel" style={{ flex: '1 1 450px', minWidth: '320px' }}>
          <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Settings size={20} color="var(--primary)" />
            AI Settings
          </h2>
          <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>AI Model</label>
              <select 
                value={settings.ai_model} 
                onChange={(e) => setSettings({ ...settings, ai_model: e.target.value })} 
                className="input-field"
                style={{ width: '100%' }}
              >
                <option value="gemini-3.6-flash">gemini-3.6-flash</option>
                <option value="gemini-3.1-pro-preview">gemini-3.1-pro-preview</option>
                <option value="gemini-3.5-flash">gemini-3.5-flash</option>
                <option value="gemini-2.5-pro">gemini-2.5-pro</option>
                <option value="gemini-2.5-flash">gemini-2.5-flash</option>
                <option value="gemini-2.0-pro-exp-02-05">gemini-2.0-pro-exp</option>
                <option value="gemini-2.0-flash">gemini-2.0-flash</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>Analyst Agent Persona</label>
              <textarea 
                value={settings.analyzer_persona} 
                onChange={(e) => setSettings({ ...settings, analyzer_persona: e.target.value })} 
                className="input-field"
                rows={3}
                style={{ width: '100%', resize: 'vertical' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-muted)', fontSize: '0.9rem' }}>Producer Agent Persona</label>
              <textarea 
                value={settings.producer_persona} 
                onChange={(e) => setSettings({ ...settings, producer_persona: e.target.value })} 
                className="input-field"
                rows={3}
                style={{ width: '100%', resize: 'vertical' }}
              />
            </div>
            <div>
              <button type="submit" className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Save size={16} />
                Save AI Settings
              </button>
            </div>
          </form>
        </div>

      </div>

      {/* ROW 2: Storage Overview & Proxy Configuration */}
      <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', width: '100%' }}>
        
        {/* Storage Overview Panel (Left) */}
        <div className="glass-panel" style={{ flex: '1 1 450px', minWidth: '320px' }}>
          <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <HardDrive size={20} color="var(--primary)" />
            Storage Overview
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {storageStats.map((stat) => (
              <div key={stat.bucket} style={{ background: 'rgba(255,255,255,0.02)', padding: '1.25rem', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h3 style={{ color: 'var(--text-light)', marginBottom: '0.5rem', fontSize: '1rem' }}>{stat.bucket.split('-').pop()}</h3>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    Files: <strong style={{ color: 'var(--text-light)' }}>{stat.file_count}</strong> • Size: <strong style={{ color: 'var(--text-light)' }}>{(stat.total_size_bytes / (1024 * 1024)).toFixed(2)} MB</strong>
                  </div>
                </div>
                <button 
                  onClick={() => handlePurgeStorage(stat.bucket)}
                  className="btn-danger"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', padding: '0.4rem 0.75rem', borderRadius: '6px' }}
                  title={`Purge all files in ${stat.bucket}`}
                >
                  <Trash2 size={14} />
                  <span>Purge</span>
                </button>
              </div>
            ))}
            {storageStats.length === 0 && <div style={{ color: 'var(--text-muted)' }}>No storage data available.</div>}
          </div>
        </div>

        {/* Proxy Configuration Panel (Right) */}
        <div className="glass-panel" style={{ flex: '1 1 450px', minWidth: '320px' }}>
          <h2 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Globe size={20} color="var(--primary)" />
            Proxy Configuration
          </h2>
          <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <input 
                type="checkbox" 
                id="proxy_enabled"
                checked={settings.proxy_enabled === 'true'} 
                onChange={(e) => setSettings({ ...settings, proxy_enabled: e.target.checked ? 'true' : 'false' })} 
                style={{ width: '16px', height: '16px', accentColor: 'var(--primary)' }}
              />
              <label htmlFor="proxy_enabled" style={{ color: 'var(--text-light)', fontWeight: 500 }}>Enable Proxy</label>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', opacity: settings.proxy_enabled === 'true' ? 1 : 0.5, pointerEvents: settings.proxy_enabled === 'true' ? 'auto' : 'none' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '0.4rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>Proxy Host (e.g. proxy.com:8080)</label>
                <input 
                  type="text" 
                  value={settings.proxy_host} 
                  onChange={(e) => setSettings({ ...settings, proxy_host: e.target.value })} 
                  className="input-field"
                  style={{ width: '100%' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.4rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>Username (optional)</label>
                <input 
                  type="text" 
                  value={settings.proxy_user} 
                  onChange={(e) => setSettings({ ...settings, proxy_user: e.target.value })} 
                  className="input-field"
                  style={{ width: '100%' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '0.4rem', color: 'var(--text-muted)', fontSize: '0.85rem' }}>Password (optional)</label>
                <input 
                  type="password" 
                  value={settings.proxy_pass} 
                  onChange={(e) => setSettings({ ...settings, proxy_pass: e.target.value })} 
                  className="input-field"
                  style={{ width: '100%' }}
                />
              </div>
            </div>
            
            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', marginTop: '0.5rem' }}>
              <button type="submit" className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Save size={16} />
                Save Proxy Settings
              </button>
              <button type="button" onClick={handleClearProxy} className="btn-secondary" style={{ fontSize: '0.85rem' }}>
                Clear Proxy
              </button>
            </div>
          </form>
        </div>

      </div>

    </div>
  );
}
