import test from 'node:test'
import assert from 'node:assert/strict'
import { componentState } from './componentHarness.js'

test('section changes create history entries; back and forward restore the matching view', async () => {
  const location = globalThis.location
  const history = globalThis.history
  const entries = ['#overview']
  let position = 0
  globalThis.location = { hash: '#overview' }
  globalThis.history = {
    replaceState(_state, _title, hash) { entries[position] = hash; globalThis.location.hash = hash },
    pushState(_state, _title, hash) { entries.splice(position + 1); entries.push(hash); position++; globalThis.location.hash = hash }
  }
  try {
    const page = await componentState()
    await page.navigate('references')
    await page.navigate('recording')
    assert.deepEqual(entries, ['#overview', '#references', '#recording'])
    await page.navigate('recording')
    assert.equal(entries.length, 3, 'same-view navigation must not create duplicate entries')
    globalThis.location.hash = entries[--position]
    await page.syncNavigation()
    assert.equal(page.activeView.value, 'references')
    globalThis.location.hash = entries[++position]
    await page.syncNavigation()
    assert.equal(page.activeView.value, 'recording')
  } finally { globalThis.location = location; globalThis.history = history }
})

test('duplicate popstate/hashchange notifications refresh the library once without adding history', async () => {
  const location = globalThis.location
  const history = globalThis.history
  const fetch = globalThis.fetch
  let reads = 0, writes = 0
  globalThis.location = { hash: '#history' }
  globalThis.history = { pushState() { writes++ } }
  globalThis.fetch = async () => { reads++; return new Response(JSON.stringify({ items: [], total: 0 })) }
  try {
    const page = await componentState()
    page.activeView.value = 'recording'
    await page.syncNavigation()
    await page.syncNavigation()
    assert.equal(page.activeView.value, 'history')
    assert.equal(reads, 1)
    assert.equal(writes, 0)
  } finally { globalThis.location = location; globalThis.history = history; globalThis.fetch = fetch }
})

test('empty capture and unsupported WebM show errors without a saved preview (simulated device)', async () => {
  const navigator = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  const recorder = globalThis.MediaRecorder
  let microphoneRequests = 0
  const track = { stop() {} }
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { mediaDevices: { async getUserMedia() { microphoneRequests++; return { getTracks: () => [track], getAudioTracks: () => [track] } } } } })
  globalThis.MediaRecorder = class {
    static isTypeSupported() { return true }
    constructor() { this.state = 'inactive'; this.mimeType = 'audio/webm' }
    start() { this.state = 'recording' }
    stop() { this.state = 'inactive'; this.onstop?.() }
  }
  try {
    const page = await componentState()
    page.selectedLecturerId.value = '11111111-1111-4111-8111-111111111111'
    page.title.value = 'Disposable capture'
    await page.startLecture()
    await page.startSample()
    assert.equal(microphoneRequests, 1, 'simultaneous reference capture must be blocked')
    page.stopLecture()
    assert.equal(page.lectureBlobAvailable.value, false)
    assert.match(page.error.value, /No audio was captured/)
    assert.equal(page.savedRecordingId.value, null)
    assert.equal(page.lectureMessage.value, '')
    globalThis.MediaRecorder.isTypeSupported = () => false
    await page.startLecture()
    assert.equal(microphoneRequests, 1)
    assert.match(page.error.value, /cannot record WebM/)
    assert.equal(page.recording.value, false)
  } finally { if (navigator) Object.defineProperty(globalThis, 'navigator', navigator); globalThis.MediaRecorder = recorder }
})
