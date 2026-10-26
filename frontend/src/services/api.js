export const API_BASE_URL = (import.meta.env?.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '')

export function audioUrl(path) {
  return `${API_BASE_URL}${path}`
}

export async function apiRequest(path, { timeoutMs = 60000, ...options } = {}) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { ...options, signal: controller.signal })
    if (response.status === 204) return null
    const body = await response.json().catch(() => ({}))
    if (!response.ok) {
      const detail = Array.isArray(body.detail)
        ? body.detail.map(item => item.msg).join('; ')
        : body.detail
      const error = new Error(detail || `Request failed (${response.status}).`)
      error.status = response.status
      throw error
    }
    return body
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('The request timed out. Refresh saved items before retrying.')
    if (error instanceof TypeError) throw new Error('Could not reach VoiceClean. Check that the backend is running.')
    throw error
  } finally {
    clearTimeout(timeout)
  }
}
