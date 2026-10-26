import { apiRequest } from './api.js'

export function recordingDescription(subject, notes) {
  return [subject.trim() ? `Subject: ${subject.trim()}` : '', notes.trim()].filter(Boolean).join('\n\n') || null
}

export function recordingFields(description) {
  if (description?.startsWith('Subject: ')) {
    const [first, ...rest] = description.split('\n')
    return { subject: first.slice(9), notes: rest.join('\n').trimStart() }
  }
  return { subject: '', notes: description || '' }
}

export function recordingQuery({ q = '', lecturer = '', status = '', offset = 0 } = {}) {
  const values = new URLSearchParams({ limit: '20', offset: String(offset) })
  if (q.trim()) values.set('q', q.trim())
  if (lecturer) values.set('lecturer_id', lecturer)
  if (status) values.set('status', status)
  return `/api/recordings?${values}`
}

export async function saveRecordingDraft({ id, lecturerId, title, description, recordedAt, blob, filename }, request = apiRequest) {
  let value
  try { value = await request(`/api/recordings/${id}`) }
  catch (error) {
    if (error.status !== 404) throw error
    value = await request('/api/recordings', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, lecturer_id: lecturerId, title, description, recorded_at: recordedAt })
    })
  }
  if (value.lecturer_id !== lecturerId) throw new Error('This draft belongs to a different lecturer.')
  if (value.title !== title || value.description !== description) {
    value = await request(`/api/recordings/${id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, description })
    })
  }
  // A previous request may have committed even when its response was lost.
  if (value.status === 'ready' && value.original_audio) return value
  if (value.status === 'uploading') throw new Error('Upload is in progress. Refresh the library before retrying.')
  const form = new FormData()
  form.append('file', blob, filename)
  return request(`/api/recordings/${id}/audio`, { method: 'POST', body: form, timeoutMs: 300000 })
}
