import test from 'node:test'
import assert from 'node:assert/strict'
import { componentState } from './componentHarness.js'

const recording = { id: '11111111-1111-4111-8111-111111111111', title: 'Speech', status: 'ready' }
const original = { id: 'original', file_role: 'original', available: true }
const enhanced = { id: 'enhanced', file_role: 'processed', available: true }
const mp3 = { id: 'mp3', file_role: 'exported', available: true }
function json(data, status = 200) { return new Response(JSON.stringify(data), { status }) }

test('audio jobs show truthful pending state and reload versions only after server completion', async () => {
  const fetch = globalThis.fetch
  let complete, started
  const waiting = new Promise(resolve => { started = resolve })
  let files = [original]
  globalThis.fetch = async (url, options) => {
    if (options?.method === 'POST') {
      started()
      await new Promise(resolve => { complete = resolve })
      files = [original, enhanced]
      return json(enhanced, 201)
    }
    return json(url.endsWith('/versions') ? { items: files } : recording)
  }
  try {
    const page = await componentState()
    const job = page.runAudioJob(recording, 'process')
    await waiting
    assert.equal(page.audioJobBusy.value, true)
    assert.match(page.audioJobStatus.value, /Enhancing/)
    assert.equal(page.audioJobMessage.value, '')
    assert.deepEqual(page.audioVersions.value, [original])
    complete()
    await job
    assert.equal(page.audioJobBusy.value, false)
    assert.equal(page.audioJobError.value, '')
    assert.deepEqual(page.audioVersions.value, [original, enhanced])
    const refreshed = await componentState()
    await refreshed.selectProcessing(recording)
    assert.deepEqual(refreshed.audioVersions.value, [original, enhanced])
  } finally { globalThis.fetch = fetch }
})

test('failed export keeps original versions and never shows success', async () => {
  const fetch = globalThis.fetch
  globalThis.fetch = async (url, options) => options?.method === 'POST'
    ? json({ detail: 'FFmpeg unavailable' }, 503)
    : json(url.endsWith('/versions') ? { items: [original] } : recording)
  try {
    const page = await componentState()
    await page.runAudioJob(recording, 'exports')
    assert.match(page.audioJobError.value, /FFmpeg unavailable/)
    assert.equal(page.audioJobMessage.value, '')
    assert.equal(page.audioJobBusy.value, false)
    assert.deepEqual(page.audioVersions.value, [original])
  } finally { globalThis.fetch = fetch }
})

test('MP3 success offers the actual persisted download metadata and selection errors remain errors', async () => {
  const fetch = globalThis.fetch
  let exported = false
  globalThis.fetch = async (url, options) => {
    if (options?.method === 'POST') { exported = true; return json(mp3) }
    return json(url.endsWith('/versions') ? { items: exported ? [original, mp3] : [original] } : recording)
  }
  try {
    const page = await componentState()
    await page.runAudioJob(recording, 'exports')
    assert.match(page.audioJobMessage.value, /Download MP3/)
    assert.deepEqual(page.audioVersions.value, [original, mp3])
    globalThis.fetch = async () => json({ detail: 'Offline' }, 503)
    await page.selectProcessing(recording)
    assert.equal(page.versionsLoaded.value, false)
    assert.equal(page.audioJobError.value, 'Offline')
    assert.equal(page.audioJobMessage.value, '')
  } finally { globalThis.fetch = fetch }
})

test('lecturer deletion conflicts retain selection and success clears remembered context', async () => {
  const fetch = globalThis.fetch
  let conflict = true
  globalThis.fetch = async (url, options) => options?.method === 'DELETE'
    ? (conflict ? json({ detail: 'Lecturer has reference samples' }, 409) : new Response(null, { status: 204 }))
    : json({ items: [], total: 0 })
  try {
    const page = await componentState()
    page.selectedLecturerId.value = recording.id
    page.lecturerDeleteCandidate.value = recording.id
    await page.deleteLecturer()
    assert.equal(page.selectedLecturerId.value, recording.id)
    assert.match(page.referenceError.value, /reference samples/)
    conflict = false
    await page.deleteLecturer()
    assert.equal(page.selectedLecturerId.value, '')
    assert.equal(page.referenceMessage.value, 'Lecturer deleted.')
  } finally { globalThis.fetch = fetch }
})

test('saved original download uses its scoped server URL without requiring a local Blob', async () => {
  const document = globalThis.document
  let anchor
  globalThis.document = { createElement() { anchor = { click() { this.clicked = true } }; return anchor } }
  try {
    const page = await componentState()
    page.savedRecordingId.value = recording.id
    page.savedOriginalId.value = 'saved-original-id'
    page.downloadRecording()
    assert.equal(anchor.clicked, true)
    assert.equal(anchor.href, `http://127.0.0.1:8000/api/recordings/${recording.id}/versions/saved-original-id/download`)
  } finally { globalThis.document = document }
})
