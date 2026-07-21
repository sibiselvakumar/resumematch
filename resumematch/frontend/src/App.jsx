import { useState } from 'react'
import JDUploader from './components/JDUploader'
import ResumeUploader from './components/ResumeUploader'
import WeightConfig, { DEFAULT_WEIGHTS } from './components/WeightConfig'
import Leaderboard from './components/Leaderboard'
import { analyzeResumes } from './api'
import './App.css'

const LOADING_MESSAGES = [
  'Reading the job description...',
  'Extracting required skills and experience...',
  'Scoring candidates against the role...',
  'Ranking your candidates...',
]

function formatElapsed(totalSec) {
  const m = Math.floor(totalSec / 60)
  const s = totalSec % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

export default function App() {
  const [stage, setStage] = useState('upload') // 'upload' | 'loading' | 'results'
  const [jdText, setJdText] = useState('')
  const [jdFile, setJdFile] = useState(null)
  const [resumes, setResumes] = useState([])
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)
  const [loadingMsg, setLoadingMsg] = useState(LOADING_MESSAGES[0])
  const [elapsedSec, setElapsedSec] = useState(0)
  const [weights, setWeights] = useState({ ...DEFAULT_WEIGHTS })

  const weightsTotal = Object.values(weights).reduce((a, b) => a + b, 0)
  const weightsValid = weightsTotal === 100

  const handleScreening = async () => {
    const hasJD = jdText.trim().length > 0 || jdFile
    if (!hasJD) { setError('Please provide a job description.'); return }
    if (resumes.length === 0) { setError('Please upload at least one resume.'); return }
    if (!weightsValid) { setError('Scoring weights must add up to 100%.'); return }

    setError(null)
    setStage('loading')

    // Cycle through loading messages every 4 seconds
    let msgIdx = 0
    setLoadingMsg(LOADING_MESSAGES[0])
    const msgInterval = setInterval(() => {
      msgIdx = Math.min(msgIdx + 1, LOADING_MESSAGES.length - 1)
      setLoadingMsg(LOADING_MESSAGES[msgIdx])
    }, 4000)

    // Real elapsed time, ticking every second — actual runs range from
    // ~30s to several minutes depending on model/API load, so a fixed
    // estimate is misleading.
    setElapsedSec(0)
    const timerStart = Date.now()
    const timerInterval = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - timerStart) / 1000))
    }, 1000)

    try {
      const data = await analyzeResumes(jdText, jdFile, resumes, weights)
      setResults(data)
      setStage('results')
    } catch (err) {
      setError(err.message || 'Something went wrong. Make sure the backend is running.')
      setStage('upload')
    } finally {
      clearInterval(msgInterval)
      clearInterval(timerInterval)
    }
  }

  const handleReset = () => {
    setStage('upload')
    setJdText('')
    setJdFile(null)
    setResumes([])
    setResults(null)
    setError(null)
    setWeights({ ...DEFAULT_WEIGHTS })
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">🎯</span>
            <span className="logo-text">ResumeMatch</span>
          </div>
          <p className="header-tagline">AI-powered resume screening · Internal HR Tool</p>
        </div>
      </header>

      <main className="main">
        {/* ── Upload Stage ───────────────────────────── */}
        {stage === 'upload' && (
          <div className="upload-container">
            {error && <div className="error-banner">⚠️ {error}</div>}

            <div className="upload-grid">
              <div className="upload-section">
                <h2 className="section-title">
                  <span className="step-badge">1</span>
                  Job Description
                </h2>
                <JDUploader
                  jdText={jdText}
                  onTextChange={setJdText}
                  jdFile={jdFile}
                  onFileChange={setJdFile}
                />
              </div>

              <div className="upload-section">
                <h2 className="section-title">
                  <span className="step-badge">2</span>
                  Resumes
                  {resumes.length > 0 && (
                    <span style={{ marginLeft: 'auto', fontSize: 13, fontWeight: 400, color: 'var(--muted)' }}>
                      {resumes.length} file{resumes.length !== 1 ? 's' : ''}
                    </span>
                  )}
                </h2>
                <ResumeUploader resumes={resumes} onResumesChange={setResumes} />
              </div>
            </div>

            <div className="upload-section upload-section--full">
              <h2 className="section-title">
                <span className="step-badge">3</span>
                Scoring Weights
              </h2>
              <WeightConfig weights={weights} onChange={setWeights} />
            </div>

            <div className="screen-action">
              <button
                className="screen-btn"
                onClick={handleScreening}
                disabled={(!jdText.trim() && !jdFile) || resumes.length === 0 || !weightsValid}
              >
                🔍 Screen Resumes
                {resumes.length > 0 && (
                  <span className="screen-btn-count">{resumes.length}</span>
                )}
              </button>
              {(!jdText.trim() && !jdFile) && (
                <p className="screen-hint">Add a JD and at least one resume to get started</p>
              )}
            </div>
          </div>
        )}

        {/* ── Loading Stage ──────────────────────────── */}
        {stage === 'loading' && (
          <div className="loading-container">
            <div className="loading-spinner" />
            <p className="loading-text">{loadingMsg}</p>
            <p className="loading-sub">
              Elapsed: {formatElapsed(elapsedSec)} (up to 5 min max) · Scoring {resumes.length} resume{resumes.length !== 1 ? 's' : ''} in parallel
            </p>
          </div>
        )}

        {/* ── Results Stage ──────────────────────────── */}
        {stage === 'results' && results && (
          <div className="results-container">
            <div className="results-header">
              <div>
                <h2 className="results-title">Screening Results</h2>
                <p className="results-meta">
                  {results.results?.length ?? 0} candidate{results.results?.length !== 1 ? 's' : ''} screened
                  {results.jd_requirements?.role_title
                    ? ` · ${results.jd_requirements.role_title}`
                    : ''}
                  {results.jd_requirements?.seniority_level
                    ? ` (${results.jd_requirements.seniority_level})`
                    : ''}
                </p>
              </div>
              <button className="new-screening-btn" onClick={handleReset}>
                + New Screening
              </button>
            </div>

            {/* JD quick-summary bar */}
            {results.jd_requirements && (
              <div className="jd-summary">
                {results.jd_requirements.min_experience_years > 0 && (
                  <><strong>Min exp:</strong> {results.jd_requirements.min_experience_years}+ yrs &nbsp;·&nbsp;</>
                )}
                {results.jd_requirements.education_requirement && (
                  <><strong>Education:</strong> {results.jd_requirements.education_requirement} &nbsp;·&nbsp;</>
                )}
                {results.jd_requirements.required_skills?.length > 0 && (
                  <><strong>Key skills:</strong> {results.jd_requirements.required_skills.slice(0, 6).join(', ')}</>
                )}
              </div>
            )}

            <Leaderboard results={results.results ?? []} sessionId={results.session_id} weights={weights} />
          </div>
        )}
      </main>

      <footer className="footer">
        ResumeMatch · Internal HR Tool · Powered by NVIDIA API + Llama 3.1 70B
      </footer>
    </div>
  )
}
