import ScoreCard from './ScoreCard'
import './Leaderboard.css'

const BAND_COUNTS = (results) => ({
  strong: results.filter(r => r.overall_score >= 80).length,
  potential: results.filter(r => r.overall_score >= 60 && r.overall_score < 80).length,
  weak: results.filter(r => r.overall_score < 60).length,
})

function toCSV(results) {
  const headers = [
    'Rank', 'Candidate', 'Overall Score', 'Recommendation',
    'Skills Score', 'Matched Skills', 'Missing Skills',
    'Experience Score', 'Experience Notes',
    'Role Alignment Score', 'Role Alignment Notes',
    'Education Score', 'Education Notes',
    'Responsibilities Score', 'Responsibilities Notes',
    'Summary',
  ]
  const escape = (v) => `"${String(v ?? '').replace(/"/g, '""')}"`
  const rows = results.map((r, i) => {
    const dims = r.dimensions ?? {}
    const sm = dims.skills_match ?? {}
    const exp = dims.experience ?? {}
    const ra = dims.role_alignment ?? {}
    const edu = dims.education ?? {}
    const resp = dims.responsibilities ?? {}
    return [
      i + 1,
      r.candidate_name,
      r.overall_score,
      r.recommendation,
      sm.score ?? '',
      (sm.matched_skills ?? []).join(', '),
      (sm.missing_skills ?? []).join(', '),
      exp.score ?? '',
      exp.note ?? '',
      ra.score ?? '',
      ra.note ?? '',
      edu.score ?? '',
      edu.note ?? '',
      resp.score ?? '',
      resp.note ?? '',
      r.summary ?? '',
    ].map(escape).join(',')
  })
  return [headers.map(escape).join(','), ...rows].join('\r\n')
}

export default function Leaderboard({ results, sessionId }) {
  const bands = BAND_COUNTS(results)

  const handleExport = () => {
    const csv = toCSV(results)
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `session_${(sessionId ?? 'export').slice(0, 8)}.csv`
    a.click()
    URL.revokeObjectURL(url)
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
