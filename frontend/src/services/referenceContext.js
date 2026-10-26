import { API_BASE_URL, apiRequest } from './api.js'

const key = `voiceclean:lecturer:${API_BASE_URL}`
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function rememberedLecturer(storage) {
  try {
    storage ??= globalThis.localStorage
    const value = storage?.getItem(key)
    return uuid.test(value || '') ? value : null
  } catch { return null }
}

export function rememberLecturer(id, storage) {
  try {
    storage ??= globalThis.localStorage
    if (uuid.test(id || '')) storage?.setItem(key, id)
    else storage?.removeItem(key)
  } catch { /* Local storage can be unavailable; backend persistence still works. */ }
}

export async function loadReferenceContext(request = apiRequest, rememberedId = rememberedLecturer()) {
  const lecturers = await request('/api/lecturers?limit=20&offset=0')
  let lecturer = null
  if (rememberedId && uuid.test(rememberedId)) {
    try { lecturer = await request(`/api/lecturers/${rememberedId}`) }
    catch (error) {
      if (error.status !== 404) throw error
      // A deleted lecturer must not cause another lecturer's samples to appear.
      return { lecturers, lecturer: null, samples: null }
    }
  } else lecturer = lecturers.items[0] || null
  const samples = lecturer
    ? await request(`/api/lecturers/${lecturer.id}/samples?limit=20&offset=0`)
    : null
  return { lecturers, lecturer, samples }
}
