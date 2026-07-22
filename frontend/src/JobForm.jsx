import React, { useState, useRef } from 'react';
import toast from 'react-hot-toast';
import { UploadCloud, Info, AlertTriangle } from 'lucide-react';
import { getTracer, logEvent } from './tracing';

const JobForm = () => {
  const [formData, setFormData] = useState({
    sourceType: 'upload',
    youtubeUrl: '',
    file: null,
    language: 'en',
    tone: 'hype',
    dualVoices: false,
    enableSubtitles: false,
    musicTrack: 'electronic',
    aspectRatio: '16:9',
    bias: '',
    length: '60',
    voice: 'en-US-Journey-D',
    voice2: 'en-US-Journey-F',
    analysisMode: 'audio'
  });
  
  const voiceOptions = [
    { value: "en-US-Journey-D", label: "Journey Male (US) - Energetic" },
    { value: "en-US-Journey-F", label: "Journey Female (US) - Energetic" },
    { value: "en-US-Studio-M", label: "Studio Male (US) - Professional" },
    { value: "en-US-Studio-O", label: "Studio Female (US) - Professional" },
    { value: "en-US-Studio-Q", label: "Studio Male (US) - Conversational" },
    { value: "en-GB-Journey-D", label: "Journey Male (UK) - Energetic" },
    { value: "en-GB-Journey-F", label: "Journey Female (UK) - Energetic" },
    { value: "en-AU-Journey-D", label: "Journey Male (AU) - Energetic" },
    { value: "en-AU-Journey-F", label: "Journey Female (AU) - Energetic" }
  ];
  
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const fileInputRef = useRef(null);

  const checkDuplicateFile = async (selectedFile) => {
    if (!selectedFile) return;
    const fileNameNoExt = selectedFile.name.replace(/\.[^/.]+$/, "");
    try {
      const apiUrl = import.meta.env.VITE_API_URL;
      if (!apiUrl) return;
      const res = await fetch(apiUrl);
      if (res.ok) {
        const data = await res.json();
        const existingJob = (data.jobs || []).find(j => {
          try {
            const c = JSON.parse(j.config || "{}");
            return c.originalFileName && c.originalFileName.toLowerCase() === fileNameNoExt.toLowerCase();
          } catch(e) { return false; }
        });
        if (existingJob) {
          toast(`Notice: A file named "${fileNameNoExt}" has already been uploaded previously.`, { icon: '⚠️', duration: 6000 });
        }
      }
    } catch(e) { console.error("Duplicate check error", e); }
  };

  const handleChange = (e) => {
    const { name, value, type, checked, files } = e.target;
    if (name === 'sourceType' && value === 'youtube') {
      toast('YouTube downloads are currently blocked for GCP IP addresses.', { icon: '⚠️', duration: 6000 });
    }
    const newValue = type === 'checkbox' ? checked : (type === 'file' ? files[0] : value);
    setFormData(prev => ({
      ...prev,
      [name]: newValue
    }));
    if (type === 'file' && files && files[0]) {
      checkDuplicateFile(files[0]);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const droppedFile = e.dataTransfer.files[0];
      setFormData(prev => ({ ...prev, file: droppedFile }));
      checkDuplicateFile(droppedFile);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (formData.sourceType === 'upload' && !formData.file) {
      toast.error('Please select a video file to upload.');
      return;
    }
    
    const toastId = toast.loading('Submitting job...');
    const tracer = getTracer();
    const span = tracer.startSpan('handleSubmit');
    
    try {
      span.setAttribute('job.sourceType', formData.sourceType);
      span.setAttribute('job.language', formData.language);
      span.setAttribute('job.tone', formData.tone);
      
      logEvent('info', 'Job submission started', { formData });
      
      const apiUrl = import.meta.env.VITE_API_URL;
      if (!apiUrl) {
        throw new Error("VITE_API_URL is not set.");
      }

      const payload = { ...formData };
      if (formData.sourceType === 'upload' && formData.file) {
        payload.originalFileName = formData.file.name.replace(/\.[^/.]+$/, "");
      }
      
      if (formData.sourceType === 'upload' && formData.file) {
        // Check for duplicates to save time
        try {
          const jobsRes = await fetch(apiUrl);
          if (jobsRes.ok) {
             const data = await jobsRes.json();
             const existingJob = (data.jobs || []).find(j => {
               try {
                 const c = JSON.parse(j.config || "{}");
                 return c.originalFileName && c.originalFileName.toLowerCase() === payload.originalFileName.toLowerCase() && c.video_gcs_uri;
               } catch(e) { return false; }
             });
             if (existingJob) {
               const oldConfig = JSON.parse(existingJob.config);
               if (window.confirm(`This file ("${payload.originalFileName}") has already been uploaded previously. Do you want to reuse the existing video to skip the upload?`)) {
                  payload.video_gcs_uri = oldConfig.video_gcs_uri;
                  delete payload.file;
               }
             }
          }
        } catch(e) { console.error("Duplicate check failed", e); }
        
        if (payload.file) {
          toast.loading('Preparing upload...', { id: toastId });
          
          // Request signed URL
          const uploadUrlResponse = await fetch(`${apiUrl}/upload-url`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ 
              filename: formData.file.name,
              contentType: formData.file.type || "video/mp4"
            })
          });
          
          if (!uploadUrlResponse.ok) {
            const errData = await uploadUrlResponse.json().catch(() => ({}));
            throw new Error(errData.error || 'Failed to get upload URL');
          }
          
          const { url: signedUrl, video_gcs_uri } = await uploadUrlResponse.json();
          
          toast.loading('Uploading video...', { id: toastId });
          // Upload directly to GCS via PUT with XHR for progress tracking
          setUploadProgress(1); // initialize progress
          
          await new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open("PUT", signedUrl);
            xhr.setRequestHeader("Content-Type", formData.file.type || "video/mp4");
            
            xhr.upload.onprogress = (event) => {
              if (event.lengthComputable) {
                const percentComplete = Math.round((event.loaded / event.total) * 100);
                setUploadProgress(percentComplete);
              }
            };
            
            xhr.onload = () => {
              if (xhr.status >= 200 && xhr.status < 300) {
                resolve(xhr);
              } else {
                reject(new Error(`Upload failed with status ${xhr.status}`));
              }
            };
            
            xhr.onerror = () => reject(new Error('Network error during upload'));
            xhr.send(formData.file);
          });
          
          payload.video_gcs_uri = video_gcs_uri;
          delete payload.file; // Don't send file object in JSON
        }
      }

      toast.loading('Submitting job configuration...', { id: toastId });
      const response = await fetch(apiUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.error || response.statusText);
      }

      const result = await response.json();
      span.addEvent('Job Submitted');
      
      toast.success(`Job submitted successfully!`, { id: toastId });
      
      // Reset file input and progress
      setFormData(prev => ({ ...prev, file: null, youtubeUrl: '' }));
      setUploadProgress(0);
      if (fileInputRef.current) fileInputRef.current.value = '';
      
    } catch (error) {
      span.recordException(error);
      logEvent('error', 'Job submission failed', { error: error.message });
      toast.error(`Error: ${error.message}`, { id: toastId });
      setUploadProgress(0);
    } finally {
      span.end();
    }
  };

  const PRESETS = [
    {
      name: "TikTok Hype Reel (9:16, 30s)",
      config: { aspectRatio: "9:16", length: "30", tone: "hype", musicTrack: "electronic", analysisMode: "audio", dualVoices: false, enableSubtitles: false }
    },
    {
      name: "Tactical Breakdown (16:9, 2m)",
      config: { aspectRatio: "16:9", length: "120", tone: "analytic", musicTrack: "orchestral", analysisMode: "video", dualVoices: true, enableSubtitles: false }
    },
    {
      name: "Instagram Square (1:1, 1m)",
      config: { aspectRatio: "1:1", length: "60", tone: "funny", musicTrack: "hiphop", analysisMode: "audio", dualVoices: false, enableSubtitles: false }
    }
  ];

  const handleApplyPreset = (e) => {
    const presetName = e.target.value;
    if (!presetName) return;
    const selected = PRESETS.find(p => p.name === presetName);
    if (selected) {
      setFormData(prev => ({
        ...prev,
        ...selected.config
      }));
      toast.success(`Preset "${selected.name}" applied!`);
    }
  };

  return (
    <div className="glass-panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0 }}>Create Highlight Reel</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <label style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>Preset Template:</label>
          <select 
            onChange={handleApplyPreset} 
            defaultValue="" 
            className="form-control" 
            style={{ width: 'auto', padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}
          >
            <option value="" disabled>Select a Preset...</option>
            {PRESETS.map(p => (
              <option key={p.name} value={p.name}>{p.name}</option>
            ))}
          </select>
        </div>
      </div>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Video Source</label>
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', color: '#fff' }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', margin: 0, cursor: 'pointer' }}>
              <input type="radio" name="sourceType" value="upload" checked={formData.sourceType === 'upload'} onChange={handleChange} /> File Upload
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', margin: 0, cursor: 'pointer' }}>
              <input type="radio" name="sourceType" value="youtube" checked={formData.sourceType === 'youtube'} onChange={handleChange} /> YouTube Link
            </label>
          </div>
          
          {formData.sourceType === 'upload' ? (
            <div 
              className={`drag-drop-zone ${isDragging ? 'dragging' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <UploadCloud size={48} className="upload-icon" />
              {formData.file ? (
                <p className="file-name">{formData.file.name}</p>
              ) : (
                <p>Drag and drop your .mp4 file here<br/>or click to browse</p>
              )}
              <input 
                type="file" 
                name="file" 
                ref={fileInputRef}
                style={{ display: 'none' }}
                onChange={handleChange} 
                accept="video/*" 
              />
            </div>
          ) : (
            <div>
              <input type="url" name="youtubeUrl" className="form-control" placeholder="https://youtube.com/watch?v=..." value={formData.youtubeUrl} onChange={handleChange} />
              <div style={{ background: 'rgba(234, 179, 8, 0.15)', border: '1px solid rgba(234, 179, 8, 0.4)', color: '#fde047', padding: '0.75rem 1rem', borderRadius: '8px', marginTop: '0.75rem', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <AlertTriangle size={18} color="#fde047" style={{ flexShrink: 0 }} />
                <span><strong>Warning:</strong> YouTube downloads are currently blocked for GCP IP addresses.</span>
              </div>
            </div>
          )}

          {uploadProgress > 0 && uploadProgress < 100 && (
            <div style={{ marginTop: '1rem' }}>
              <div style={{ background: 'rgba(255,255,255,0.1)', borderRadius: '8px', overflow: 'hidden', height: '8px' }}>
                <div style={{ 
                  width: `${uploadProgress}%`, 
                  background: 'var(--primary, #8b5cf6)', 
                  height: '100%', 
                  transition: 'width 0.3s ease' 
                }}></div>
              </div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-light)', textAlign: 'center', marginTop: '0.5rem', fontWeight: 500 }}>
                Uploading: {uploadProgress}% (This may take a while for large files)
              </div>
            </div>
          )}
          {uploadProgress === 100 && (
            <div style={{ marginTop: '0.5rem', fontSize: '0.85rem', color: '#4caf50', textAlign: 'center', fontWeight: 500 }}>
              Upload Complete! Processing...
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
          <div className="form-group">
            <label htmlFor="analysisMode" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              Analysis Mode
              <span title="Full video analysis processes the visual stream, which costs more and takes significantly longer. Audio-only is highly recommended for speed and lower cost.">
                <Info size={14} style={{ opacity: 0.7, cursor: 'help' }} />
              </span>
            </label>
            <select id="analysisMode" name="analysisMode" className="form-control" value={formData.analysisMode} onChange={handleChange}>
              <option value="audio">Audio Only (Faster & Cheaper)</option>
              <option value="video">Full Video (Higher Accuracy)</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="language">Language</label>
            <select id="language" name="language" className="form-control" value={formData.language} onChange={handleChange}>
              <option value="en">English</option>
              <option value="fr">French</option>
              <option value="ru">Russian</option>
              <option value="es">Spanish</option>
              <option value="zh">Chinese</option>
              <option value="ja">Japanese</option>
              <option value="el">Greek</option>
              <option value="ar">Arabic</option>
              <option value="vi">Vietnamese</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="tone">Tone</label>
            <select id="tone" name="tone" className="form-control" value={formData.tone} onChange={handleChange}>
              <option value="hype">Hype / Energetic</option>
              <option value="analytic">Analytic / Tactical</option>
              <option value="funny">Funny / Entertaining</option>
              <option value="emotional">Emotional / Dramatic</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="aspectRatio">Aspect Ratio</label>
            <select id="aspectRatio" name="aspectRatio" className="form-control" value={formData.aspectRatio} onChange={handleChange}>
              <option value="16:9">16:9 (YouTube, TV)</option>
              <option value="9:16">9:16 (TikTok, Reels)</option>
              <option value="1:1">1:1 (Instagram Square)</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="musicTrack">Music Track</label>
            <select id="musicTrack" name="musicTrack" className="form-control" value={formData.musicTrack} onChange={handleChange}>
              <option value="electronic">High-Tempo Electronic</option>
              <option value="hiphop">Heavy Bass Hip-Hop</option>
              <option value="orchestral">Epic Orchestral</option>
              <option value="none">No Music</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="length">Clip Length</label>
            <select id="length" name="length" className="form-control" value={formData.length} onChange={handleChange}>
              <option value="30">30 Seconds</option>
              <option value="60">1 Minute</option>
              <option value="120">2 Minutes</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="voice">{formData.dualVoices ? "Play-by-play Voice" : "Voice Persona"}</label>
            <select id="voice" name="voice" className="form-control" value={formData.voice} onChange={handleChange}>
              {voiceOptions.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
            </select>
          </div>

          {formData.dualVoices && (
            <div className="form-group">
              <label htmlFor="voice2">Color Commentator Voice</label>
              <select id="voice2" name="voice2" className="form-control" value={formData.voice2} onChange={handleChange}>
                {voiceOptions.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
              </select>
            </div>
          )}
        </div>

        <div className="form-group">
          <label htmlFor="bias">Team/Player Bias</label>
          <input type="text" id="bias" name="bias" className="form-control" placeholder="e.g. Focus on Stephen Curry" value={formData.bias} onChange={handleChange}/>
        </div>

        <div className="checkbox-group" style={{ marginBottom: '0.75rem' }}>
          <input type="checkbox" id="dualVoices" name="dualVoices" checked={formData.dualVoices} onChange={handleChange}/>
          <label htmlFor="dualVoices" style={{ margin: 0 }}>Enable Dual Voices (Play-by-play & Color)</label>
        </div>

        <div className="checkbox-group" style={{ marginBottom: '1.5rem' }}>
          <input type="checkbox" id="enableSubtitles" name="enableSubtitles" checked={formData.enableSubtitles} onChange={handleChange}/>
          <label htmlFor="enableSubtitles" style={{ margin: 0 }}>Display Subtitles on Video</label>
        </div>

        <button type="submit" className="btn" style={{ width: '100%' }}>Generate Highlight Reel</button>
      </form>
    </div>
  );
};

export default JobForm;
