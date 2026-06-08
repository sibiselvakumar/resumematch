import { useState, useRef } from 'react'
import './JDUploader.css'

export default function JDUploader({ jdText, onTextChange, jdFile, onFileChange }) {
  const [tab, setTab] = useState('paste') // 'paste' | 'upload'
  const fileRef = useRef(null)

  const handleFile = (e) => {
    const file = e.target.files?.[0]
    if (file) {
      onFileChange(file)
      onTextChange('')
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const file = e.dataTransfer.files?.[0]
    if (file) {
      onFileChange(file)
      onTextChange('')
      setTab('upload')
    }
  }

  const handleTextChange = (e) => {
    onTextChange(e.target.value)
    onFileChange(null)
  }

  const clearFile = () => {
    onFileChange(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  return (
    <div className="jd-uploader">
      {/* Tabs */}
      <div className="jd-tabs">
        <button
          className={`jd-tab ${tab === 'paste' ? 'jd-tab--active' : ''}`}
          onClick={() => setTab('paste')}
        >
          Paste Text
        </button>
        <button
          className={`jd-tab ${tab === 'upload' ? 'jd-tab--active' : ''}`}
          onClick={() => setTab('upload')}
        >
          Upload File
        </button>
      </div>

      {tab === 'paste' && (
        <div className="jd-paste-area">
          <textarea
            className="jd-textarea"
            placeholder="Paste the full job description here...&#10;&#10;Include requirements, responsibilities, skills, and qualifications."
            value={jdText}
            onChange={handleTextChange}
            rows={12}
          />
          {jdText && (
            <div className="jd-char-count">{jdText.length} characters</div>
          )}
        </div>
      )}

      {tab === 'upload' && (
        <div
          className={`jd-drop-zone ${jdFile ? 'jd-drop-zone--has-file' : ''}`}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => !jdFile && fileRef.current?.click()}
        >
          {jdFile ? (
            <div className="jd-file-preview">
              <span className="jd-file-icon">📄</span>
              <div className="jd-file-info">
                <span className="jd-file-name">{jdFile.name}</span>
                <span className="jd-file-size">{(jdFile.size / 1024).toFixed(1)} KB</span>
              </div>
              <button
                className="jd-file-remove"
                onClick={(e) => { e.stopPropagation(); clearFile() }}
                title="Remove file"
              >
                ✕
              </button>
            </div>
          ) : (
            <div className="jd-drop-prompt">
              <span className="jd-drop-icon">📁</span>
              <p className="jd-drop-text">Drop a PDF or DOCX here</p>
              <p className="jd-drop-sub">or click to browse</p>
            </div>
          )}
        </div>
      )}

      <input
        ref={fileRef}
        type="file"
        accept=".pdf,.docx,.txt"
        style={{ display: 'none' }}
        onChange={handleFile}
      />
    </div>
  )
}
