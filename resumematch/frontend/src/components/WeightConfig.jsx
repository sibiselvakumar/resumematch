import './WeightConfig.css'

const DIMENSION_LABELS = {
  skills_match: 'Skills Match',
  experience: 'Experience',
  role_alignment: 'Role Alignment',
  education: 'Education',
  responsibilities: 'Responsibilities',
}

export const DEFAULT_WEIGHTS = {
  skills_match: 35,
  experience: 30,
  role_alignment: 15,
  education: 10,
  responsibilities: 10,
}

export default function WeightConfig({ weights, onChange }) {
  const total = Object.values(weights).reduce((a, b) => a + b, 0)
  const isValid = total === 100

  const handleChange = (key, value) => {
    onChange({ ...weights, [key]: Number(value) })
  }

  const handleReset = () => onChange({ ...DEFAULT_WEIGHTS })

  return (
    <div className="weight-config">
      <div className="weight-config-header">
        <div>
          <span className="weight-config-title">Scoring Weights</span>
          <span className="weight-config-hint">Adjust how much each dimension counts toward the final score.</span>
        </div>
        <button className="weight-reset-btn" onClick={handleReset} type="button">
          Reset defaults
        </button>
      </div>

      <div className="weight-sliders">
        {Object.entries(weights).map(([key, val]) => (
          <div key={key} className="weight-row">
            <div className="weight-row-meta">
              <span className="weight-dim-label">{DIMENSION_LABELS[key]}</span>
              <span className="weight-dim-value">{val}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={val}
              onChange={e => handleChange(key, e.target.value)}
              className="weight-slider"
            />
          </div>
        ))}
      </div>

      <div className={`weight-total ${isValid ? 'weight-total--ok' : 'weight-total--error'}`}>
        {isValid
          ? 'Total: 100% ✓'
          : `Total: ${total}% — must equal 100% (${total > 100 ? 'reduce' : 'increase'} by ${Math.abs(100 - total)}%)`
        }
      </div>
    </div>
  )
}
