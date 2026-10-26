import test from 'node:test'
import assert from 'node:assert/strict'
import { componentState, renderWorkspace } from './componentHarness.js'
import { useRecordingOpen } from '../src/composables/useRecordingOpen.js'

const lecturer = { id: 'lecturer', name: 'Dr. Santos', department: 'Computer Engineering' }
const recording = index => ({
  id: `lecture-${index}`, title: `Saved lecture ${index}`, lecturer, lecturer_id: lecturer.id,
  status: 'ready', created_at: '2026-10-26T08:00:00Z',
  original_audio: { id: `original-${index}`, duration_seconds: 90, file_size_bytes: 1024 }
})
const preview = html => html.match(/<section class="recent-recordings"[\s\S]*?<\/section>/)?.[0]

test('opening saved audio requires confirmation for unsaved previews and never interrupts capture', async () => {
  const calls = []
  const workspace = { lectureBlobAvailable: true, savedRecordingId: null,
    samplePending: false, captureLocked: false, restoreHistory(item) { calls.push(item.id) } }
  const control = useRecordingOpen(workspace)
  const item = recording(1)
  control.openRecording(item)
  assert.equal(control.pendingOpen.value.id, item.id)
  assert.deepEqual(calls, [])
  control.pendingOpen.value = null // Cancel leaves previews and API state untouched.
  assert.equal(workspace.lectureBlobAvailable, true)
  control.openRecording(item)
  workspace.captureLocked = true
  control.confirmOpen()
  assert.deepEqual(calls, [])
  workspace.captureLocked = false
  control.confirmOpen()
  assert.deepEqual(calls, [item.id])
  assert.equal(control.pendingOpen.value, null)
  workspace.lectureBlobAvailable = false
  workspace.samplePending = true
  control.openRecording(item)
  assert.equal(calls.length, 1, 'unsaved reference also requires confirmation')
})

test('overview previews at most four real library items with scoped actions and metadata', async () => {
  const page = await componentState()
  page.history.value = Array.from({ length: 6 }, (_, index) => recording(index))
  page.historyLoaded.value = true
  page.historyTotal.value = 6
  page.selectedLecturer.value = lecturer
  page.referencesLoaded.value = true
  page.sampleTotal.value = 2
  const html = await renderWorkspace(page)
  const recent = preview(html)
  assert.match(recent, /Recent recordings/)
  assert.equal((recent.match(/class="recent-title"/g) || []).length, 4)
  assert.match(recent, /Saved lecture 0/)
  assert.doesNotMatch(recent, /Saved lecture 4/)
  assert.match(recent, /Dr\. Santos/)
  assert.match(recent, /1:30/)
  assert.match(recent, /aria-label="Open Saved lecture 0"/)
  assert.match(html, /context-reference[\s\S]*?<strong>2<\/strong>/)
  assert.equal(page.history.value.length, 6, 'preview must not truncate shared library state')
})

test('overview labels a filtered or paginated library preview without claiming global recency', async () => {
  const page = await componentState()
  page.historyLoaded.value = true
  page.history.value = [recording(1)]
  page.historyOffset.value = 20
  let html = preview(await renderWorkspace(page))
  assert.match(html, /Library preview/)
  assert.match(html, /current library page and filters/)
  assert.doesNotMatch(html, /Recent recordings/)
  page.historyOffset.value = 0
  page.historySearch.value = 'DSP'
  html = await renderWorkspace(page)
  assert.match(preview(html), /Library preview/)
  assert.match(html, /Library matches/)
})

test('recent library failures and loading do not show stale items or a false empty success', async () => {
  const page = await componentState()
  page.history.value = [recording(1)]
  page.historyLoaded.value = true
  page.historyError.value = 'Backend unavailable'
  let html = preview(await renderWorkspace(page))
  assert.match(html, /role="alert">Backend unavailable/)
  assert.match(html, /Retry library loading/)
  assert.doesNotMatch(html, /class="recent-title"|first lecture/)
  page.historyError.value = ''
  page.historyLoading.value = true
  html = preview(await renderWorkspace(page))
  assert.match(html, /Loading recordings/)
  assert.doesNotMatch(html, /class="recent-title"|first lecture/)
  page.historyLoading.value = false
  page.historyLoaded.value = false
  page.history.value = []
  html = preview(await renderWorkspace(page))
  assert.match(html, /has not loaded yet/)
  assert.doesNotMatch(html, /first lecture/)
})

test('audio lab retains all version downloads and keeps unavailable files out of native players', async () => {
  const page = await componentState()
  page.processingRecording.value = recording(1)
  page.versionsLoaded.value = true
  page.audioVersions.value = ['original', 'processed', 'exported'].map(role => ({
    id: role, file_role: role, available: role !== 'original', mime_type: role === 'exported' ? 'audio/mpeg' : 'audio/wav',
    duration_seconds: 90, file_size_bytes: 1024, audio_url: `/${role}/audio`, download_url: `/${role}/download`
  }))
  const html = await renderWorkspace(page)
  assert.match(html, /2 available versions/)
  assert.match(html, /class="version-grid"[\s\S]*?Original audio[\s\S]*?Enhanced audio/)
  assert.match(html, /class="delivery-versions"[\s\S]*?Exported MP3/)
  assert.match(html, /href="http:\/\/127.0.0.1:8000\/processed\/download"/)
  assert.match(html, /href="http:\/\/127.0.0.1:8000\/exported\/download"/)
  assert.doesNotMatch(html, /src="http:\/\/127.0.0.1:8000\/original\/audio"/)
  assert.match(html, /File unavailable/)
})

test('lecturer disclosure defaults to registration while saved profiles retain edit and delete controls', async () => {
  const page = await componentState()
  let html = await renderWorkspace(page)
  assert.match(html, /<details class="profile-editor" open>/)
  assert.match(html, /Register a lecturer/)
  page.selectedLecturerId.value = lecturer.id
  page.selectedLecturer.value = lecturer
  page.lecturers.value = [lecturer]
  html = await renderWorkspace(page)
  assert.match(html, /Saved profile/)
  assert.match(html, /<details class="profile-editor"><summary>Edit lecturer details/)
  assert.match(html, /id="lecturer-name"/)
  assert.match(html, /id="delete-lecturer"/)
  assert.match(html, /Recording animation[^<]*not measured audio levels/)
})
