import { apiRequest } from './api.js'

export function fetchVersions(id) {
  return apiRequest(`/api/recordings/${id}/versions`)
}

export function generateAudio(id, action) {
  if (!['process', 'exports'].includes(action)) throw Error('Unsupported audio action')
  // Bounded server processing can take longer than a normal metadata request.
  return apiRequest(`/api/recordings/${id}/${action}`, { method: 'POST', timeoutMs: 1200000 })
}
