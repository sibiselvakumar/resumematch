import { useState } from 'react'
import DimensionBar from './DimensionBar'
import './ScoreCard.css'

const DIMENSION_ORDER = ['skills_match', 'experience', 'role_alignment', 'education', 'responsibilities']

function scoreColor(score) {
  if (score >= 80) return 'green'
  if (score >= 60) return 'yellow'
  return 'red'
}

const RECOMMENDATION_ICON = {
  'Strong Match': '🟢',
  'Potential Match': '🟡',
  'Weak Match': '🔴',
}

export default function ScoreCard({ result, rank }) {
  const [expanded, setExpanded] = useState(false)
  const color = scoreColor(result.overall_score)
  const icon = RECOMMENDATION_ICON[result.recommendation] || '⚪'

  return (
    <div className={`score-card score-card--${color}`}>
      {/* Header row */}
      <div className="score-card-header" onClick={() => setExpanded(e => !e)}>
        <div className="score-card-left">
          <span className="rank-badge">#{rank}</span>
          <div className="candidate-info">
            <span className="candidate-name">{result.candidate_name}</span>
            <span className="candidate-rec">
              {icon} {result.recommendation}
            </span>
          </div>
        </div>
        <div className="score-card-right">
          <div className={`overall-score overall-score--${color}`}>
            {result.overall_score}
            <span className="overall-score-max">/100</span>
          </div>
          <button className="expand-btn" aria-label={expanded ? 'Collapse' : 'Expand'}>
            {expanded ? '▲' : '▼'}
          </button>
        </div>
      </div>

      {/* Summary (always visible) */}
      {result.summary && (
        <p className="score-card-summary">{result.summary}</p>
      )}

      {/* Error badge */}
      {result.error && (
        <div className="score-card-error">⚠️ {result.error}</div>
      )}

      {/* Expanded dimensions */}
      {expanded && result.dimensions && (
        <div className="score-card-dimensions">
          {DIMENSION_ORDER.map(key =>
            result.dimensions[key] ? (
              <DimensionBar key={key} dimensionKey={key} data={result.dimensions[key]} />
            ) : null
          )}
        </div>
      )}
    </div>
  )
}
