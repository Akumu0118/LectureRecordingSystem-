import test from 'node:test'
import assert from 'node:assert/strict'
import { componentState as state } from './componentHarness.js'

const lecturer = { id: '11111111-1111-4111-8111-111111111111', name: 'Test lecturer', department: null }
const sample = { id: 'saved-reference', lecturer_id: lecturer.id, audio_url: '/reference/audio', audio_file: {} }
const recording = { id: 'recording', lecturer_id: lecturer.id, lecturer, title: 'Saved lecture',
  description: 'Subject: DSP\n\nNotes', status: 'ready', recorded_at: null,
  original_audio: { original_filename: 'lecture.webm', file_size_bytes: 2048, duration_seconds: '2.500' },
  audio_url: '/api/recordings/recording/stream' }

test('new component after refresh restores the saved reference and playable backend URL', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async address => new Response(JSON.stringify(address.includes('/samples?')
    ? { items: [sample], total: 1 } : address.endsWith(lecturer.id) ? lecturer : { items: [lecturer], total: 1 }))
  try {
    const initial = await state()
    await initial.initializeReferences()
    const reloaded = await state()
    await reloaded.initializeReferences()
    assert.equal(reloaded.selectedLecturerId.value, lecturer.id)
    assert.equal(reloaded.referenceSamples.value[0].id, sample.id)
    assert.equal(reloaded.sampleUrl.value, 'http://127.0.0.1:8000/reference/audio')
    assert.equal(reloaded.samplePending.value, false)
    assert.equal(reloaded.referencesLoaded.value, true)
  } finally { globalThis.fetch = original }
})

test('saved lecture playback uses remote metadata without requiring a local Blob', async () => {
  const page = await state()
  assert.doesNotThrow(() => page.openSavedRecording(recording))
  assert.equal(page.savedRecordingId.value, recording.id)
  assert.equal(page.lectureBlobAvailable.value, false)
  assert.equal(page.lectureUrl.value, 'http://127.0.0.1:8000' + recording.audio_url)
  assert.equal(page.subject.value, 'DSP')
})

test('reference load error does not claim an empty or successfully saved list', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Offline' }), { status: 503 })
  try {
    const page = await state()
    await page.initializeReferences()
    assert.equal(page.referenceInitialized.value, false)
    assert.equal(page.referencesLoaded.value, false)
    assert.equal(page.referenceError.value, 'Offline')
    assert.equal(page.referenceMessage.value, '')
  } finally { globalThis.fetch = original }
})

test('fresh recording library fetch restores remote recordings and keeps failures distinct from empty lists', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () => new Response(JSON.stringify({ items: [recording], total: 1 }))
  try {
    const page = await state()
    await page.loadHistory()
    assert.equal(page.history.value[0].id, recording.id)
    assert.equal(page.historyLoaded.value, true)
    globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Offline' }), { status: 503 })
    await page.loadHistory()
    assert.equal(page.historyError.value, 'Offline')
    assert.equal(page.history.value[0].id, recording.id)
  } finally { globalThis.fetch = original }
})

test('MediaRecorder controls pause, resume and stop; simultaneous reference capture is blocked (simulated device)', async () => {
  const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  const originalRecorder = globalThis.MediaRecorder
  let microphoneRequests = 0
  const track = { stop() {} }
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: {
    mediaDevices: { async getUserMedia() { microphoneRequests++; return { getTracks: () => [track], getAudioTracks: () => [track] } } }
  } })
  globalThis.MediaRecorder = class {
    static isTypeSupported() { return true }
    constructor() { this.state = 'inactive'; this.mimeType = 'audio/webm' }
    start() { this.state = 'recording' }
    pause() { this.state = 'paused' }
    resume() { this.state = 'recording' }
    stop() { this.state = 'inactive'; this.ondataavailable?.({ data: new Blob(['simulated audio']) }); this.onstop?.() }
  }
  try {
    const page = await state()
    page.selectedLecturerId.value = lecturer.id
    page.selectedLecturer.value = lecturer
    page.title.value = 'Captured lecture'
    await page.startLecture()
    assert.equal(page.recording.value, true)
    await page.startSample()
    assert.equal(microphoneRequests, 1)
    page.pauseLecture()
    assert.equal(page.paused.value, true)
    page.resumeLecture()
    assert.equal(page.recording.value, true)
    page.stopLecture()
    assert.equal(page.lectureBlobAvailable.value, true)
    assert.equal(page.status.value, 'Preview ready')
    page.clearLecturePreview()
  } finally {
    if (originalNavigator) Object.defineProperty(globalThis, 'navigator', originalNavigator)
    globalThis.MediaRecorder = originalRecorder
  }
})

test('microphone denial clears capture state and exposes an error (simulated permission)', async () => {
  const originalNavigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  const originalRecorder = globalThis.MediaRecorder
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: {
    mediaDevices: { async getUserMedia() { throw Error('Microphone permission denied') } }
  } })
  globalThis.MediaRecorder = class { static isTypeSupported() { return true } }
  try {
    const page = await state()
    page.selectedLecturerId.value = lecturer.id
    page.title.value = 'Lecture'
    await page.startLecture()
    assert.equal(page.busy.value, false)
    assert.equal(page.recording.value, false)
    assert.match(page.error.value, /permission denied/)
  } finally {
    if (originalNavigator) Object.defineProperty(globalThis, 'navigator', originalNavigator)
    globalThis.MediaRecorder = originalRecorder
  }
})
