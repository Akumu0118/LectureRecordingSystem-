// Driven by pytest with a private PostgreSQL schema, temporary storage and two
// actual Uvicorn processes. Not a DOM/browser or microphone automation test.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
import { componentState } from '../componentHarness.js'
import { rememberLecturer } from '../../src/services/referenceContext.js'

const base = process.env.VOICECLEAN_TEST_API_BASE_URL
const mode = process.env.VOICECLEAN_TEST_MODE
const originalFetch = globalThis.fetch
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(base || '')) throw Error('An isolated API URL is required')
globalThis.fetch = (address, options) => originalFetch(String(address).replace('http://127.0.0.1:8000', base), options)
const bytes = await readFile(process.env.VOICECLEAN_TEST_AUDIO_FILE)
const artifact = process.env.VOICECLEAN_TEST_IDS_FILE

test(`real Vue-to-PostgreSQL persistence workflow: ${mode}`, async () => {
  if (mode === 'save') {
    const page = await componentState()
    page.lecturerName.value = 'Isolated frontend integration lecturer'
    await page.saveLecturer()
    assert.equal(page.referenceError.value, '')
    const owner = page.selectedLecturerId.value
    assert.ok(owner)
    page.loadSample({ target: { files: [new File([bytes], 'reference.wav')], value: '' } })
    await page.saveReference()
    assert.equal(page.referenceError.value, '')
    const sample = page.selectedSample.value
    assert.ok(sample?.id)
    const refreshed = await componentState()
    await refreshed.initializeReferences()
    assert.equal(refreshed.selectedLecturerId.value, owner)
    assert.equal(refreshed.referenceSamples.value[0].id, sample.id)
    assert.deepEqual(Buffer.from(await (await fetch(refreshed.sampleUrl.value)).arrayBuffer()), bytes)
    refreshed.title.value = 'Persistent lecture from Vue'
    refreshed.subject.value = 'DSP'
    refreshed.notes.value = 'Integration persistence test'
    refreshed.loadLecture({ target: { files: [new File([bytes], 'lecture.wav')], value: '' } })
    await refreshed.saveToHistory()
    assert.equal(refreshed.error.value, '')
    assert.ok(refreshed.savedRecordingId.value)
    await refreshed.runAudioJob({ id: refreshed.savedRecordingId.value }, 'process')
    assert.equal(refreshed.audioJobError.value, '')
    await refreshed.runAudioJob({ id: refreshed.savedRecordingId.value }, 'exports')
    assert.equal(refreshed.audioJobError.value, '')
    assert.deepEqual(new Set(refreshed.audioVersions.value.map(file => file.file_role)), new Set(['original', 'processed', 'exported']))
    for (const version of refreshed.audioVersions.value) {
      assert.equal((await fetch('http://127.0.0.1:8000' + version.download_url)).status, 200)
    }
    await writeFile(artifact, JSON.stringify({ owner, sample: sample.id, recording: refreshed.savedRecordingId.value }))
  } else {
    const ids = JSON.parse(await readFile(artifact, 'utf8'))
    rememberLecturer(ids.owner)
    const page = await componentState()
    await page.initializeReferences()
    await page.loadHistory()
    assert.equal(page.referenceSamples.value[0].id, ids.sample)
    assert.deepEqual(Buffer.from(await (await fetch(page.sampleUrl.value)).arrayBuffer()), bytes)
    const saved = page.history.value.find(item => item.id === ids.recording)
    assert.ok(saved)
    await page.restoreHistory(saved)
    assert.equal(page.savedRecordingId.value, ids.recording)
    assert.deepEqual(Buffer.from(await (await fetch(page.lectureUrl.value)).arrayBuffer()), bytes)
    await page.selectProcessing(saved)
    assert.equal(page.audioJobError.value, '')
    assert.equal(page.audioVersions.value.length, 3)
    const versionIds = page.audioVersions.value.map(file => file.id)
    for (const version of page.audioVersions.value) {
      const result = await fetch('http://127.0.0.1:8000' + version.download_url)
      assert.equal(result.status, 200)
      assert.equal((await result.arrayBuffer()).byteLength, version.file_size_bytes)
      assert.match(result.headers.get('content-disposition'), /^attachment;/)
    }
    await page.runAudioJob(saved, 'exports')
    assert.equal(page.audioJobError.value, '')
    assert.deepEqual(page.audioVersions.value.map(file => file.id), versionIds)
    page.lecturerDepartment.value = 'Updated through Vue'
    await page.saveLecturer()
    assert.equal(page.referenceError.value, '')
    assert.equal(page.selectedLecturer.value.department, 'Updated through Vue')
    page.lecturerDeleteCandidate.value = ids.owner
    await page.deleteLecturer()
    assert.match(page.referenceError.value, /reference|recording/i)
    assert.equal(page.selectedLecturerId.value, ids.owner)
    // Real HTTP checks for library filters and cancellation state, not DOM clicks.
    page.historySearch.value = 'Persistent lecture from Vue'
    page.historyLecturer.value = ids.owner
    page.historyStatus.value = 'ready'
    await page.searchHistory()
    assert.equal(page.history.value.length, 1)
    assert.equal(page.history.value[0].id, ids.recording)
    page.historySearch.value = 'No matching disposable lecture title'
    await page.searchHistory()
    assert.equal(page.history.value.length, 0)
    page.historySearch.value = ''
    page.historyLecturer.value = ''
    page.historyStatus.value = ''
    await page.searchHistory()
    page.deleteCandidate.value = ids.recording
    page.deleteCandidate.value = null
    assert.equal((await fetch(`${base}/api/recordings/${ids.recording}`)).status, 200)
    page.beginRename(saved)
    page.editTitle.value = 'Renamed through Vue'
    await page.renameRecording(saved)
    assert.equal(page.historyError.value, '')
    assert.equal(page.history.value.find(item => item.id === ids.recording).title, 'Renamed through Vue')
    await page.confirmDeleteRecording(saved)
    assert.equal(page.historyError.value, '')
    assert.equal(page.history.value.some(item => item.id === ids.recording), false)
    assert.equal((await fetch(`${base}/api/recordings/${ids.recording}`)).status, 404)
    assert.equal((await fetch(page.sampleUrl.value)).status, 200)
    assert.equal(page.processingRecording.value, null)
    await page.clearSample()
    assert.equal(page.referenceError.value, '')
    assert.equal((await fetch(`${base}/api/lecturers/${ids.owner}/samples/${ids.sample}`)).status, 404)
    page.lecturerDeleteCandidate.value = ids.owner
    await page.deleteLecturer()
    assert.equal(page.referenceError.value, '')
    assert.equal(page.selectedLecturerId.value, '')
    assert.equal((await fetch(`${base}/api/lecturers/${ids.owner}`)).status, 404)
  }
})
