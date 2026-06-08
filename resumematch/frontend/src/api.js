const API_BASE = (import.meta.env.VITE_API_URL || '') + '/api'

/**
 * Send JD + resumes to the backend for screening.
 * @param {string|null} jdText - Job description as plain text
 * @param {File|null} jdFile - Job description as a file
 * @param {File[]} resumeFiles - Array of resume files
 */
export async function analyzeResumes(jdText, jdFile, resumeFiles) {
  const formData = new FormData()

  if (jdFile) {
    formData.append('jd_file', jdFile)
  } else {
    formData.append('jd_text', jdText)
  }

  for (const file of resumeFiles) {
    formData.append('resumes', file)
  }

  const response = await fetch(`${API_BASE}/analyze`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    let detail = 'Analysis failed. Check that the backend is running.'
    try {
      const err = await response.json()
      detail = err.detail || detail
    } catch (_) {}
    throw new Error(detail)
  }

  return response.json()
}

/**
 * Returns the CSV export URL for a session (open in new tab to download).
 */
export function getExportUrl(sessionId) {
  return `${API_BASE}/sessions/${sessionId}/export`
}

/**
 * Fetch list of past sessions.
 */
export async function fetchSessions() {
  const response = await fetch(`${API_BASE}/sessions`)
  if (!response.ok) throw new Error('Failed to fetch sessions')
  return response.json()
}
