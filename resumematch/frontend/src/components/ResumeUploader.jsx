import { useRef } from 'react'
import './ResumeUploader.css'

export default function ResumeUploader({ resumes, onResumesChange }) {
  const fileRef = useRef(null)

  const addFiles = (newFiles) => {
    // Deduplicate by name
    const existingNames = new Set(resumes.map(f => f.name))
    const unique = Array.from(newFiles).filter(f => !existingNames.has(f.name))
    onResumesChange([...resumes, ...unique])
  }

  const handleFileInput = (e) => {
    if (e.target.files?.length) addFiles(e.target.files)
    e.target.value = ''
  }

  const handleDrop = (e) => {
    e.preventDefault()
    if (e.dataTransfer.files?.length) addFiles(e.dataTransfer.files)
  }

  const removeFile = (name) => {
    onResumesChange(resumes.filter(f => f.name !== name))
  }

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  return (
    <div className="resume-uploader">
      {/* Drop zone */}
      <div
        className={`resume-drop-zone ${resumes.length > 0 ? 'resume-drop-zone--has-files' : ''}`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
      >
        <span className="resume-drop-icon">📋</span>
        <p className="resume-drop-text">
          {resumes.length > 0 ? 'Drop more resumes to add' : 'Drop resumes here'}
        </p>
        <p className="resume-drop-sub">PDF or DOCX · Click to browse · Multiple files supported</p>
      </div>

      {/* File list */}
      {resumes.length > 0 && (
        <ul className="resume-list">
          {resumes.map((file, i) => (
            <li key={file.name} className="resume-item">
              <span className="resume-item-rank">#{i + 1}</span>
              <span className="resume-item-icon">📄</span>
              <div className="resume-item-info">
                <span className="resume-item-name">{file.name}</span>
                <span className="resume-item-size">{formatSize(file.size)}</span>
              </div>
              <button
                className="resume-item-remove"
                onClick={(e) => { e.stopPropagation(); removeFile(file.name) }}
                title="Remove"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      {resumes.length === 0 && (
        <p className="resume-hint">Upload at least one resume to screen</p>
      )}

      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.docx,.txt"
        multiple
        style={{ display: 'none' }}
        onChange={handleFileInput}
      />
    </div>
  )
}
