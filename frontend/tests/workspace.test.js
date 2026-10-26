import test from 'node:test'
import assert from 'node:assert/strict'
import { componentState, renderWorkspace } from './componentHarness.js'
import { formatDuration, formatDate } from '../src/utils/formatters.js'

const lecturer = { id: '11111111-1111-4111-8111-111111111111', name: 'Dr. ' + 'Long lecturer name '.repeat(15), department: 'Computer Engineering' }
const item = { id: '22222222-2222-4222-8222-222222222222', lecturer_id: lecturer.id, lecturer, title: 'Lecture ' + 'VeryLongUnbrokenTitle'.repeat(20), description: '', status: 'ready', created_at: '2026-10-26T08:00:00Z', recorded_at: null, original_audio: { id: 'original', duration_seconds: '90.25', file_size_bytes: 1000 }, audio_url: '/original/audio' }

test('navigation restores known hashes, ignores unknown views, and keeps the same preview session', async () => {
  const location = globalThis.location
  const history = globalThis.history
  globalThis.location = { hash: '#references' }
  let hash
  globalThis.history = { pushState(_state, _title, url) { hash = url } }
  try {
    const page = await componentState()
    assert.equal(page.activeView.value, 'references')
    page.openSavedRecording(item)
    await page.navigate('audio')
    assert.equal(page.activeView.value, 'audio')
    assert.equal(hash, '#audio')
    assert.equal(page.lectureUrl.value, 'http://127.0.0.1:8000/original/audio')
    await page.navigate('nonexistent')
    assert.equal(page.activeView.value, 'audio')
    globalThis.location.hash = '#unknown'
    const fresh = await componentState()
    assert.equal(fresh.activeView.value, 'overview')
  } finally { globalThis.location = location; globalThis.history = history }
})

test('actual Vue panels render long metadata, accessible controls, grouped actions, and valid form labels', async () => {
  const page = await componentState()
  page.selectedLecturer.value = lecturer
  page.selectedLecturerId.value = lecturer.id
  page.lecturers.value = [lecturer]
  page.lecturerTotal.value = 1
  page.history.value = [item]
  page.historyTotal.value = 1
  page.historyLoaded.value = true
  page.processingRecording.value = item
  page.audioVersions.value = [{ id: 'enhanced', file_role: 'processed', available: true, duration_seconds: '90.25', file_size_bytes: 1000, mime_type: 'audio/wav', audio_url: '/enhanced/audio', download_url: '/enhanced/download' }]
  page.activeView.value = 'history'
  const html = await renderWorkspace(page)
  assert.match(html, /aria-current="page"[^>]*>[\s\S]*?Recording History/)
  assert.match(html, /More actions/)
  assert.match(html, /Download original/)
  assert.match(html, /Download enhanced WAV/)
  assert.match(html, /href="http:\/\/127.0.0.1:8000\/enhanced\/download"/)
  assert.match(html, /aria-label="Enhanced audio for/)
  assert.match(html, /role="status"/)
  assert.match(html, /Skip to workspace/)
  assert.ok(html.includes(item.title))
  const ids = [...html.matchAll(/\sid="([^"]+)"/g)].map(match => match[1])
  assert.equal(new Set(ids).size, ids.length, 'ids must remain unique across mounted panels')
  for (const match of html.matchAll(/<label[^>]+for="([^"]+)"/g)) assert.ok(ids.includes(match[1]), 'form labels must point to real controls')
})

test('restored references appear in the reorganized reference panel with their saved preview', async () => {
  const page = await componentState()
  page.selectedLecturer.value = lecturer
  page.selectedLecturerId.value = lecturer.id
  const sample = { id: 'sample', label: 'Saved voice', audio_url: '/sample/audio', audio_file: { duration_seconds: '10.2', original_filename: 'voice.wav' } }
  page.referenceSamples.value = [sample]
  page.referencesLoaded.value = true
  page.openReference(sample)
  page.activeView.value = 'references'
  const html = await renderWorkspace(page)
  assert.match(html, /Saved reference preview/)
  assert.match(html, /Saved voice/)
  assert.match(html, /src="http:\/\/127.0.0.1:8000\/sample\/audio"/)
  assert.match(html, /Delete reference/)
  assert.doesNotMatch(html, /Delete this reference\?/) // confirmation starts closed
  page.sampleDeleteCandidate.value = sample.id
  const confirming = await renderWorkspace(page)
  assert.match(confirming, /Delete this reference\?/)
  assert.equal(page.referenceSamples.value.length, 1, 'opening confirmation must not delete anything')
})

test('navigation preserves active MediaRecorder capture, pause/resume and stop across panels (simulated device)', async () => {
  const nav = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  const originalRecorder = globalThis.MediaRecorder
  let stops = 0
  const track = { stop() { stops++ } }
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { mediaDevices: { async getUserMedia() { return { getTracks: () => [track], getAudioTracks: () => [track] } } } } })
  globalThis.MediaRecorder = class {
    static isTypeSupported() { return true }
    constructor() { this.state = 'inactive'; this.mimeType = 'audio/webm' }
    start() { this.state = 'recording' }
    pause() { this.state = 'paused' }
    resume() { this.state = 'recording' }
    stop() { this.state = 'inactive'; this.ondataavailable?.({ data: new Blob(['simulated']) }); this.onstop?.() }
  }
  try {
    const page = await componentState()
    page.selectedLecturerId.value = lecturer.id
    page.selectedLecturer.value = lecturer
    page.title.value = 'Navigation capture'
    await page.startLecture()
    await page.navigate('references')
    assert.equal(page.recording.value, true)
    assert.equal(page.captureLocked.value, true)
    assert.equal(stops, 0)
    page.pauseLecture()
    await page.navigate('recording')
    assert.equal(page.paused.value, true)
    page.resumeLecture()
    page.stopLecture()
    assert.equal(page.lectureBlobAvailable.value, true)
    page.clearLecturePreview()
  } finally { if (nav) Object.defineProperty(globalThis, 'navigator', nav); globalThis.MediaRecorder = originalRecorder }
})

test('duration and date presentation handles missing values and hour-long lectures', () => {
  assert.equal(formatDuration(null), 'Duration unavailable')
  assert.equal(formatDuration('0.25'), '<1 sec')
  assert.equal(formatDuration('90.25'), '1:30')
  assert.equal(formatDuration(3661), '1:01:01')
  assert.equal(formatDate(null), 'Date unavailable')
  assert.equal(formatDate('invalid'), 'Date unavailable')
})

test('skip-to-workspace focus keeps the current section and hash', async () => {
  const document = globalThis.document
  let focused = false
  globalThis.document = { getElementById(id) { assert.equal(id, 'workspace-title'); return { focus() { focused = true } } } }
  try {
    const page = await componentState()
    page.activeView.value = 'recording'
    await page.focusWorkspace()
    assert.equal(focused, true)
    assert.equal(page.activeView.value, 'recording')
  } finally { globalThis.document = document }
})
