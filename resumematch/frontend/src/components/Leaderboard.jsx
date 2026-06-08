import ScoreCard from './ScoreCard'
import { getExportUrl } from '../api'
import './Leaderboard.css'

const BAND_COUNTS = (results) => ({
  strong: results.filter(r => r.overall_score >= 80).length,
  potential: results.filter(r => r.overall_score >= 60 && r.overall_score < 80).length,
  weak: results.filter(r => r.overall_score < 60).length,
})

export default function Leaderboard({ results, sessionId }) {
  const bands = BAND_COUNTS(results)

  const handleExport = () => {
    window.open(getExportUrl(sessionId), '_blank')
  }

  return (
    <div className="leaderboard">
      {/* Stats row */}
      <div className="leaderboard-stats">
        <div className="stat-pill stat-pill--green">
          <span className="stat-num">{bands.strong}</span>
          <span className="stat-label">Strong Match</span>
        </div>
        <div className="stat-pill stat-pill--yellow">
          <span className="stat-num">{bands.potential}</span>
          <span className="stat-label">Potential Match</span>
        </div>
        <div className="stat-pill stat-pill--red">
          <span className="stat-num">{bands.weak}</span>
          <span className="stat-label">Weak Match</span>
        </div>
        <button className="export-btn" onClick={handleExport} title="Download CSV">
          ↓ Export CSV
        </button>
      </div>

      {/* Candidate cards */}
      <div className="leaderboard-list">
        {results.map((result, i) => (
          <ScoreCard key={`${result.candidate_name}-${i}`} result={result} rank={i + 1} />
        ))}
      </div>

      {results.length === 0 && (
        <div className="leaderboard-empty">No results to display.</div>
      )}
    </div>
  )
}
