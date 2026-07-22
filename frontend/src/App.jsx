import React, { useState, useEffect } from 'react';
import { Toaster } from 'react-hot-toast';
import { LogOut, User, Settings, LayoutDashboard } from 'lucide-react';
import JobForm from './JobForm';
import Dashboard from './Dashboard';
import AdminPage from './AdminPage';
import './index.css';

function App() {
  const [userRole, setUserRole] = useState('viewer');
  const [currentPage, setCurrentPage] = useState('dashboard');
  
  useEffect(() => {
    const fetchRole = async () => {
      try {
        const apiUrl = import.meta.env.VITE_API_URL;
        const res = await fetch(`${apiUrl}/me`);
        if (res.ok) {
          const data = await res.json();
          setUserRole(data.role || 'viewer');
        }
      } catch (err) {
        console.error("Failed to fetch user role", err);
      }
    };
    fetchRole();
  }, []);

  return (
    <>
      <header className="app-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
          <img src="/icon-192.png" alt="Highlight Reel Icon" style={{ width: '48px', height: '48px', borderRadius: '12px' }} />
          <div>
            <h1 style={{ margin: 0 }}>Highlight Reel</h1>
            <p style={{ color: 'var(--text-muted)', margin: 0, marginTop: '0.25rem' }}>AI-Powered Automated Sports Highlights</p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255,255,255,0.05)', padding: '0.5rem 1rem', borderRadius: '20px', border: '1px solid rgba(255,255,255,0.1)' }}>
            <User size={16} color="var(--primary-light)" />
            <span style={{ fontSize: '0.9rem', color: 'var(--text-light)', fontWeight: 500, textTransform: 'capitalize' }}>Role: {userRole}</span>
          </div>
          {userRole === 'admin' && (
            <button 
              onClick={() => setCurrentPage(currentPage === 'dashboard' ? 'admin' : 'dashboard')} 
              className="btn-secondary"
              style={{ padding: '0.5rem', cursor: 'pointer' }}
            >
              {currentPage === 'dashboard' ? <Settings size={16} /> : <LayoutDashboard size={16} />}
            </button>
          )}
          <a href="/_gcp_iap/clear_login_cookie" 
             className="btn-secondary" 
             style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', textDecoration: 'none', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', borderColor: 'rgba(239, 68, 68, 0.2)' }}
             onMouseOver={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)' }}
             onMouseOut={(e) => { e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)' }}>
            <LogOut size={16} />
            Logout
          </a>
        </div>
      </header>
      
      <main className="app-container">
        <Toaster position="top-right" toastOptions={{
          style: {
            background: 'var(--panel-bg)',
            color: 'var(--text-light)',
            border: '1px solid var(--border-light)',
            backdropFilter: 'blur(10px)',
          }
        }} />
        {currentPage === 'admin' ? (
          <AdminPage userRole={userRole} />
        ) : (
          <>
            {userRole !== 'viewer' && <JobForm />}
            <Dashboard userRole={userRole} />
          </>
        )}
      </main>
    </>
  );
}

export default App;
