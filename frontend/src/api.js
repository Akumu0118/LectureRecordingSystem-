import { extensionFor, safeFilename } from './utils.js'

// '' = same origin (Vite proxy in dev). Set VITE_API_URL to call the API directly.
const BASE = (import.meta.env?.VITE_API_URL ?? '').replace(/\/$/, '')

export class ApiError extends Error {
  constructor(message, code = 'error', status = 0) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

const NETWORK_MESSAGE = "Can't reach the VoiceClean server. Make sure the backend is running."

async function toApiError(res) {
  let body = {}
  try { body = await res.json() } catch { /* non-JSON error page */ }
  return new ApiError(
    body.error || `Request failed (${res.status}).`,
    body.code || 'http_error',
    res.status,
  )
}

async function call(url, options) {
  try {
    return await fetch(url, options)
  } catch {
    throw new ApiError(NETWORK_MESSAGE, 'network')
  }
}

async function request(path, options = {}) {
  const res = await call(`${BASE}/api${path}`, options)
  if (!res.ok) throw await toApiError(res)
  return res.status === 204 ? null : res.json()
}

async function fetchFile(url, fallbackName) {
  const res = await call(url)
  if (!res.ok) throw await toApiError(res)
  const match = /filename="([^"]+)"/.exec(res.headers.get('Content-Disposition') || '')
  return { blob: await res.blob(), filename: match?.[1] || fallbackName }
}

const json = (method, data) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(data),
})

export const api = {
  health: () => request('/health/'),

  listRecordings: () => request('/recordings/'),
  getRecording: id => request(`/recordings/${id}/`),

  // Uploads the audio and waits for processing (MVP processes inside this request).
  createRecording(blob, { title = '', subject = '', notes = '' } = {}) {
    const form = new FormData()
    const name = `${safeFilename(title)}.${extensionFor(blob.type)}`
    form.append('file', blob, name)
    if (title) form.append('title', title)
    if (subject) form.append('subject', subject)
    if (notes) form.append('notes', notes)
    return request('/recordings/', { method: 'POST', body: form })
  },

  updateRecording: (id, fields) => request(`/recordings/${id}/`, json('PATCH', fields)),
  deleteRecording: id => request(`/recordings/${id}/`, { method: 'DELETE' }),
  reprocess: id => request(`/recordings/${id}/reprocess/`, { method: 'POST' }),

  exportUrl: (id, format = 'mp3', version = 'processed') =>
    `${BASE}/api/recordings/${id}/export/?format=${format}&version=${version}`,

  // Fetches the encoded file (the server converts on first request, which can take
  // a few seconds) so the UI can show progress and friendly errors.
  downloadExport(id, format = 'mp3', version = 'processed') {
    return fetchFile(this.exportUrl(id, format, version), `lecture.${format}`)
  },

  // The untouched upload exactly as recorded (works even if processing failed).
  downloadOriginal(id) {
    return fetchFile(`${BASE}/api/recordings/${id}/audio/?version=original&download=1`, 'lecture')
  },
}
