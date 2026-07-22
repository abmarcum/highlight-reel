import React, { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { Trash2, RefreshCw, PlayCircle, Loader2, Copy, Check, Activity, ExternalLink } from 'lucide-react';

const VideoPlayer = ({ jobId, apiUrl, title }) => {
  const [videoUrl, setVideoUrl] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${apiUrl}/${jobId}/video`)
      .then(res => {
        if (!res.ok) throw new Error("Failed to load secure video URL");
        return res.json();
      })
      .then(data => {
        if (data.url) setVideoUrl(data.url);
        else throw new Error("URL not found");
      })
      .catch(err => setError(err.message));
  }, [jobId, apiUrl]);

  const handleDownload = async (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!videoUrl) return;
    try {
      const res = await fetch(videoUrl);
      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = blobUrl;
      a.download = `${title || 'highlight_reel'}.mp4`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (err) {
      window.open(videoUrl, '_blank');
    }
  };

  if (error) return <div style={{ color: 'red' }}>{error}</div>;
  if (!videoUrl) return <div>Loading secure video...</div>;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h4 style={{ margin: '0', color: 'var(--primary)' }}>Final Video</h4>
        <a 
          href={videoUrl} 
          onClick={handleDownload} 
          style={{ 
            textDecoration: 'none', 
            padding: '0.4rem 0.8rem', 
            fontSize: '0.85rem', 
            display: 'inline-flex', 
            alignItems: 'center', 
            gap: '0.3rem',
            background: 'rgba(255, 255, 255, 0.08)',
            color: '#94a3b8',
            border: '1px solid rgba(255, 255, 255, 0.12)',
            borderRadius: '8px',
            cursor: 'pointer'
          }}
        >
          Download
        </a>
      </div>
      <video controls src={videoUrl} style={{ width: '100%', borderRadius: '8px', border: '1px solid var(--border-light)' }}></video>
    </div>
  );
};

const LogsViewer = ({ jobId, apiUrl, reel }) => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const config = reel?.config ? (typeof reel.config === 'string' ? JSON.parse(reel.config) : reel.config) : {};
  const traceUrl = reel?.trace_url || config?.trace_url || (config?.trace_id ? `https://console.cloud.google.com/traces/explorer?tid=${config.trace_id}` : `https://console.cloud.google.com/traces/explorer`);

  const handleCopy = () => {
    const text = logs.map(l => `[${l.severity}] ${new Date(l.timestamp).toLocaleTimeString()} ${l.message}`).join('\n');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const fetchLogs = () => {
    setLoading(true);
    setError(null);
    fetch(`${apiUrl}/${jobId}/logs`)
      .then(res => {
        if (!res.ok) throw new Error("Failed to load logs");
        return res.json();
      })
      .then(data => {
        setLogs(data.logs || []);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchLogs();
  }, [jobId, apiUrl]);

  return (
    <div style={{ marginTop: '1rem' }} onClick={(e) => e.stopPropagation()}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
        <h4 style={{ margin: '0', color: 'var(--primary)' }}>Live Logs</h4>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <a 
            href={traceUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="btn-icon"
            title="View Trace in Google Cloud Console"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: '#8087ff', fontSize: '0.8rem', padding: '0.35rem 0.65rem', border: '1px solid rgba(128, 135, 255, 0.4)', borderRadius: '6px', textDecoration: 'none', background: 'rgba(128, 135, 255, 0.08)' }}
          >
            <Activity size={15} />
            <span style={{ fontWeight: 500 }}>Trace</span>
            <ExternalLink size={12} style={{ opacity: 0.7 }} />
          </a>
          <button onClick={handleCopy} className="btn-icon" title="Copy Logs" disabled={logs.length === 0}>
            {copied ? <Check size={16} color="#4ade80" /> : <Copy size={16} />}
          </button>
          <button onClick={fetchLogs} className="btn-icon" title="Refresh Logs" disabled={loading}>
            <RefreshCw size={16} className={loading ? 'spin-icon' : ''} />
          </button>
        </div>
      </div>
      
      {error && <div style={{ color: 'red', fontSize: '0.9rem', marginBottom: '0.5rem' }}>{error}</div>}
      {!error && logs.length === 0 && !loading && <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>No logs found.</div>}
      
      {!error && (logs.length > 0 || loading) && (
        <div className="logs-container" style={{ background: 'rgba(0,0,0,0.3)', borderRadius: '6px', padding: '0.5rem', maxHeight: '200px', overflowY: 'auto', fontFamily: 'monospace', fontSize: '0.8rem', color: '#ccc' }}>
          {logs.map((log, i) => (
            <div key={i} style={{ marginBottom: '4px', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '4px' }}>
              <span style={{ color: log.severity === 'ERROR' ? '#ff4444' : log.severity === 'WARNING' ? '#ffbb33' : '#33b5e5' }}>[{log.severity}]</span>
              {' '}
              <span style={{ color: '#888' }}>{new Date(log.timestamp).toLocaleTimeString()}</span>
              {' '}
              {log.message}
            </div>
          ))}
          {loading && logs.length > 0 && <div style={{ padding: '0.5rem', color: 'var(--text-muted)' }}>Refreshing...</div>}
          {loading && logs.length === 0 && <div style={{ padding: '0.5rem', color: 'var(--text-muted)' }}>Loading logs...</div>}
        </div>
      )}
    </div>
  );
};

const JobSettingsEditor = ({ reel, apiUrl, onUpdate }) => {
  const config = reel.config ? JSON.parse(reel.config) : {};
  const [settings, setSettings] = useState({
    analysisMode: config.analysisMode || 'audio',
    aspectRatio: config.aspectRatio || '16:9',
    dualVoices: !!config.dualVoices,
    enableSubtitles: !!(config.enableSubtitles || config.enable_subtitles),
    length: config.length || '60',
    musicTrack: config.musicTrack || 'electronic',
    teamPlayerBias: config.teamPlayerBias || ''
  });
  const [saving, setSaving] = useState(false);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setSettings(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSave = async (e) => {
    e.stopPropagation();
    setSaving(true);
    const toastId = toast.loading('Saving job settings...');
    try {
      const res = await fetch(`${apiUrl}/${reel.id}/update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      if (!res.ok) throw new Error(await res.text());
      toast.success('Job settings saved successfully!', { id: toastId });
      if (onUpdate) onUpdate();
    } catch (err) {
      toast.error('Failed to save job settings', { id: toastId });
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.08)' }} onClick={(e) => e.stopPropagation()}>
      <h5 style={{ margin: '0 0 1rem 0', color: 'var(--primary-light)', fontSize: '0.95rem', fontWeight: 600 }}>Edit Job Settings</h5>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem' }}>
        <div className="form-group" style={{ margin: 0 }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Analysis Mode</label>
          <select name="analysisMode" className="form-control" value={settings.analysisMode} onChange={handleChange} style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}>
            <option value="audio">Audio Only (Faster & Cheaper)</option>
            <option value="video">Full Video (Higher Accuracy)</option>
          </select>
        </div>

        <div className="form-group" style={{ margin: 0 }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Aspect Ratio</label>
          <select name="aspectRatio" className="form-control" value={settings.aspectRatio} onChange={handleChange} style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}>
            <option value="16:9">16:9 (YouTube, TV)</option>
            <option value="9:16">9:16 (TikTok, Reels)</option>
            <option value="1:1">1:1 (Instagram Square)</option>
          </select>
        </div>

        <div className="form-group" style={{ margin: 0 }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Clip Length</label>
          <select name="length" className="form-control" value={settings.length} onChange={handleChange} style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}>
            <option value="30">30 Seconds</option>
            <option value="60">1 Minute</option>
            <option value="120">2 Minutes</option>
          </select>
        </div>

        <div className="form-group" style={{ margin: 0 }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Music Track</label>
          <select name="musicTrack" className="form-control" value={settings.musicTrack} onChange={handleChange} style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }}>
            <option value="electronic">High-Tempo Electronic</option>
            <option value="hiphop">Heavy Bass Hip-Hop</option>
            <option value="orchestral">Epic Orchestral</option>
            <option value="none">No Music</option>
          </select>
        </div>

        <div className="form-group" style={{ margin: 0, gridColumn: 'span 2' }}>
          <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Team/Player Bias</label>
          <input type="text" name="teamPlayerBias" className="form-control" placeholder="e.g. Focus on Stephen Curry" value={settings.teamPlayerBias} onChange={handleChange} style={{ padding: '0.4rem 0.6rem', fontSize: '0.85rem' }} />
        </div>
      </div>

      <div className="checkbox-group" style={{ marginTop: '0.75rem', marginBottom: '0.5rem' }}>
        <input type="checkbox" id={`dualVoices_${reel.id}`} name="dualVoices" checked={settings.dualVoices} onChange={handleChange} />
        <label htmlFor={`dualVoices_${reel.id}`} style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-light)' }}>Enable Dual Voices (Play-by-play & Color)</label>
      </div>

      <div className="checkbox-group" style={{ marginTop: '0.5rem', marginBottom: '1rem' }}>
        <input type="checkbox" id={`enableSubtitles_${reel.id}`} name="enableSubtitles" checked={settings.enableSubtitles} onChange={handleChange} />
        <label htmlFor={`enableSubtitles_${reel.id}`} style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-light)' }}>Display Subtitles on Video</label>
      </div>

      <button onClick={handleSave} disabled={saving} className="btn-primary" style={{ padding: '0.4rem 1rem', fontSize: '0.85rem', cursor: 'pointer' }}>
        {saving ? 'Saving...' : 'Save Settings'}
      </button>
    </div>
  );
};

const HighlightTimeline = ({ reel }) => {
  const config = reel.config ? JSON.parse(reel.config) : {};
  let rawSegments = config.final_script || config.finalScript || config.selectedSegments || config.script || config.segments;
  
  if (typeof rawSegments === 'string') {
    try { rawSegments = JSON.parse(rawSegments); } catch { rawSegments = null; }
  }

  const segments = Array.isArray(rawSegments) ? rawSegments : [
    { start: '00:00', end: '00:15', text: 'Game opening commentary & team introduction' },
    { start: '00:15', end: '00:35', text: 'Key highlight play & player feature' },
    { start: '00:35', end: '00:60', text: 'Final score summary & game conclusion' }
  ];

  return (
    <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid rgba(255,255,255,0.08)' }} onClick={(e) => e.stopPropagation()}>
      <h5 style={{ margin: '0 0 0.75rem 0', color: 'var(--primary-light)', fontSize: '0.95rem', fontWeight: 600 }}>Interactive Timeline & Transcript Preview</h5>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {segments.map((seg, i) => (
          <div key={i} style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: '8px', padding: '0.6rem 0.8rem', display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <div style={{ background: 'var(--primary)', color: '#fff', fontSize: '0.75rem', fontWeight: 600, padding: '0.25rem 0.5rem', borderRadius: '4px', whiteSpace: 'nowrap' }}>
              {seg.start} - {seg.end}
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-light)', flexGrow: 1 }}>
              {seg.text}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const Dashboard = ({ userRole }) => {
  const [reels, setReels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expandedJobId, setExpandedJobId] = useState(null);

  const fetchJobs = async () => {
    try {
      const apiUrl = import.meta.env.VITE_API_URL;
      if (!apiUrl) throw new Error("VITE_API_URL is not set.");
      const response = await fetch(apiUrl);
      if (!response.ok) throw new Error('Failed to fetch jobs');
      const data = await response.json();
      setReels(data.jobs || []);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    const hasActiveJobs = reels.some(r => !['COMPLETED', 'FAILED'].includes(r.status));
    const intervalMs = hasActiveJobs ? 3000 : 15000;
    const interval = setInterval(fetchJobs, intervalMs);
    return () => clearInterval(interval);
  }, [reels]);

  const handleDelete = async (e, jobId) => {
    e.stopPropagation();
    if (!window.confirm("Are you sure you want to delete this job?")) return;
    const toastId = toast.loading('Deleting job...');
    try {
      const apiUrl = import.meta.env.VITE_API_URL;
      const res = await fetch(`${apiUrl}/${jobId}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(await res.text());
      toast.success('Job deleted successfully!', { id: toastId });
      fetchJobs();
    } catch (err) {
      toast.error('Failed to delete job', { id: toastId });
      console.error("Delete failed", err);
    }
  };

  const handleRestart = async (e, jobId, mode = 'smart') => {
    e.stopPropagation();
    const isSmart = mode === 'smart';
    const confirmMsg = isSmart
      ? "Resume job from last known good stage?"
      : "Re-run entire pipeline from scratch?";
    if (!window.confirm(confirmMsg)) return;
    
    const toastId = toast.loading(isSmart ? 'Resuming job from last good stage...' : 'Restarting job from scratch...');
    try {
      const apiUrl = import.meta.env.VITE_API_URL;
      const res = await fetch(`${apiUrl}/${jobId}/restart`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      toast.success(data.message || 'Job restarted successfully!', { id: toastId });
      fetchJobs();
    } catch (err) {
      toast.error('Failed to restart job', { id: toastId });
      console.error("Restart failed", err);
    }
  };

  // Skeleton Loader for initial load
  if (loading && reels.length === 0) {
    return (
      <div className="glass-panel">
        <h2>Recent Reels</h2>
        <div className="dashboard-grid" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {[1,2,3].map(i => (
            <div key={i} className="reel-card skeleton-card">
               <div className="skeleton-thumb"></div>
               <div className="skeleton-content">
                  <div className="skeleton-line" style={{ width: '60%' }}></div>
                  <div className="skeleton-line" style={{ width: '40%' }}></div>
                  <div className="skeleton-line status" style={{ width: '20%' }}></div>
               </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="glass-panel">
      <h2>Recent Reels</h2>
      {error && <div style={{color: '#ff4444', marginBottom: '1rem'}}>Error loading jobs: {error}</div>}
      <div className="dashboard-grid" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {reels.length === 0 && !error && <div>No jobs found.</div>}
        {reels.map(reel => {
          const config = reel.config ? JSON.parse(reel.config) : {};
          let fileName = config.originalFileName || config.filename;
          if (!fileName && config.video_gcs_uri) {
            fileName = config.video_gcs_uri.split('/').pop();
          }
          if (fileName) {
            fileName = fileName.replace(/\.[^/.]+$/, "");
          }
          const title = fileName || config.teamPlayerBias || `Job ${reel.id.substring(0,8)}`;
          const isExpanded = expandedJobId === reel.id;
          
          return (
            <div 
              key={reel.id} 
              className={`reel-card animated-card ${(!['COMPLETED', 'FAILED'].includes(reel.status)) ? 'pulse-border' : ''}`}
              style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column' }}
              onClick={() => setExpandedJobId(isExpanded ? null : reel.id)}
            >
              <div style={{ display: 'flex', gap: '1rem', width: '100%', alignItems: 'center' }}>
                <div className="reel-thumbnail">
                  {reel.status === 'COMPLETED' ? (
                    <div className="video-player-thumb">
                       <PlayCircle size={32} color="var(--primary)" />
                    </div>
                  ) : reel.status !== 'FAILED' ? (
                    <div className="processing-thumb">
                       <Loader2 size={24} className="spin-icon" color="var(--accent)" />
                    </div>
                  ) : (
                    <div>Error</div>
                  )}
                </div>
                <div className="reel-info" style={{ flexGrow: 1 }}>
                  <div className="reel-title">{title}</div>
                  <div className="reel-meta">
                    {new Date(reel.created_at).toLocaleDateString()} • {config.tone || 'neutral'} Tone
                  </div>
                  <div className={`status-badge ${['COMPLETED', 'FAILED'].includes(reel.status) ? reel.status.toLowerCase() : 'active'}`}>
                    {reel.status === 'COMPLETED' ? 'Ready to View' : (reel.status ? reel.status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Unknown')}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  {userRole === 'admin' && (
                    <>
                      <button onClick={(e) => handleRestart(e, reel.id)} className="btn-icon" title="Restart Job">
                        <RefreshCw size={18} />
                      </button>
                      <button onClick={(e) => handleDelete(e, reel.id)} className="btn-icon btn-danger" title="Delete Job">
                        <Trash2 size={18} />
                      </button>
                    </>
                  )}
                </div>
              </div>

              {isExpanded && (
                <div className="job-details-pane">
                  <h4 style={{ margin: '0 0 0.5rem 0', color: 'var(--primary)' }}>Job Details</h4>
                  {reel.status === 'COMPLETED' && (
                     <div style={{ marginBottom: '1rem' }}>
                       <VideoPlayer jobId={reel.id} apiUrl={import.meta.env.VITE_API_URL} title={title} />
                     </div>
                  )}
                  <div className="job-config-grid">
                    {Object.entries(config).map(([key, value]) => {
                      if (['jobId', 'selectedSegments', 'final_script', 'finalScript', 'draft_script', 'draftScript', 'script', 'segments', 'audioUris', 'audio_uris', 'original_payload', 'originalPayload', 'srtUri', 'srt_uri'].includes(key)) return null;
                      
                      // Format key (e.g. "musicTrack" -> "Music Track")
                      const formattedKey = key.replace(/([A-Z])/g, ' $1').replace(/^./, str => str.toUpperCase());
                      
                      // Format value
                      let formattedValue = '';
                      if (typeof value === 'boolean') {
                        formattedValue = value ? 'Yes' : 'No';
                      } else if (typeof value === 'object' && value !== null) {
                        formattedValue = JSON.stringify(value);
                      } else if (!value) {
                        formattedValue = 'None';
                      } else if (key === 'youtubeUrl' && value) {
                        formattedValue = <a href={value} target="_blank" rel="noopener noreferrer" style={{color: 'var(--primary)', textDecoration: 'underline'}}>{value}</a>;
                      } else {
                        formattedValue = String(value);
                      }

                      return (
                        <div key={key} className="config-item">
                          <span className="config-key">{formattedKey}</span>
                          <span className="config-value">{formattedValue}</span>
                        </div>
                      );
                    })}
                  </div>

                  <HighlightTimeline reel={reel} />

                  {userRole !== 'viewer' && (
                    <JobSettingsEditor reel={reel} apiUrl={import.meta.env.VITE_API_URL} onUpdate={fetchJobs} />
                  )}

                  {reel.error_message && (
                    <div className="error-banner">
                      <strong>Error:</strong> {reel.error_message}
                    </div>
                  )}
                  <LogsViewer jobId={reel.id} apiUrl={import.meta.env.VITE_API_URL} reel={reel} />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Dashboard;
