import './DimensionBar.css'

const DIMENSION_LABELS = {
  skills_match: 'Skills Match',
  experience: 'Experience',
  role_alignment: 'Role Alignment',
  education: 'Education',
  responsibilities: 'Responsibilities',
}

const WEIGHTS = {
  skills_match: 35,
  experience: 30,
  role_alignment: 15,
  education: 10,
  responsibilities: 10,
}

function scoreColor(score) {
  if (score >= 80) return 'green'
  if (score >= 60) return 'yellow'
  return 'red'
}

export default function DimensionBar({ dimensionKey, data }) {
  const label = DIMENSION_LABELS[dimensionKey] || dimensionKey
  const weight = WEIGHTS[dimensionKey] || 0
  const score = data?.score ?? 0
  const color = scoreColor(score)

  return (
    <div className="dim-bar">
      <div className="dim-bar-header">
        <div className="dim-bar-label">
          <span className="dim-bar-name">{label}</span>
          <span className="dim-bar-weight">{weight}%</span>
        </div>
        <span className={`dim-bar-score dim-bar-score--${color}`}>{score}</span>
      </div>

      <div className="dim-bar-track">
        <div
          className={`dim-bar-fill dim-bar-fill--${color}`}
          style={{ width: `${score}%` }}
        />
      </div>

      {data?.note && (
        <p className="dim-bar-note">{data.note}</p>
      )}

      {/* Skills chips for skills_match */}
      {dimensionKey === 'skills_match' && (
        <div className="dim-bar-skills">
          {(data?.matched_skills || []).map(skill => (
            <span key={skill} className="skill-chip skill-chip--matched">✓ {skill}</span>
          ))}
          {(data?.missing_skills || []).map(skill => (
            <span key={skill} className="skill-chip skill-chip--missing">✗ {skill}</span>
          ))}
        </div>
      )}
    </div>
  )
}
