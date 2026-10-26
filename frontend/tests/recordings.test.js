import test from 'node:test'
import assert from 'node:assert/strict'
import { recordingDescription, recordingFields, recordingQuery, saveRecordingDraft } from '../src/services/recordings.js'

const draft = { id: 'draft', lecturerId: 'lecturer', title: 'DSP', description: null,
  recordedAt: null, blob: new Blob(['audio']), filename: 'lecture.webm' }

test('a lost successful upload response is reconciled without another audio attachment', async () => {
  const calls = []
  const ready = { id: draft.id, lecturer_id: draft.lecturerId, title: draft.title, description: null,
    status: 'ready', original_audio: { id: 'original' } }
  const result = await saveRecordingDraft(draft, async path => { calls.push(path); return ready })
  assert.equal(result, ready)
  assert.deepEqual(calls, ['/api/recordings/draft'])
})

test('first save uses a stable UUID for metadata and original upload', async () => {
  const calls = []
  const result = await saveRecordingDraft(draft, async (path, options) => {
    calls.push({ path, options })
    if (!options) throw Object.assign(new Error('Missing'), { status: 404 })
    if (path === '/api/recordings') return { lecturer_id: 'lecturer', title: 'DSP', description: null, status: 'pending' }
    return { status: 'ready' }
  })
  assert.equal(result.status, 'ready')
  assert.equal(JSON.parse(calls[1].options.body).id, 'draft')
  assert.equal(calls[2].path, '/api/recordings/draft/audio')
  assert.equal(calls[2].options.timeoutMs, 300000)
})

test('failed uploads stay errors and retries reuse pending metadata', async () => {
  const paths = []
  await assert.rejects(saveRecordingDraft(draft, async (path, options) => {
    paths.push(path)
    if (options) throw new Error('Upload failed')
    return { lecturer_id: 'lecturer', title: 'DSP', description: null, status: 'failed' }
  }), /Upload failed/)
  assert.deepEqual(paths, ['/api/recordings/draft', '/api/recordings/draft/audio'])
})

test('an in-progress upload is not duplicated', async () => {
  await assert.rejects(saveRecordingDraft(draft, async () => ({
    lecturer_id: 'lecturer', title: 'DSP', description: null, status: 'uploading'
  })), /in progress/)
})

test('subject and notes persist through the existing description column', () => {
  assert.deepEqual(recordingFields(recordingDescription(' Signals ', ' Notes ')), { subject: 'Signals', notes: 'Notes' })
  assert.deepEqual(recordingFields('plain notes'), { subject: '', notes: 'plain notes' })
})

test('library search and filters are encoded without storing recording metadata locally', () => {
  const query = recordingQuery({ q: '50% & test', lecturer: 'lecturer', status: 'ready', offset: 20 })
  const params = new URL('http://local' + query).searchParams
  assert.equal(params.get('q'), '50% & test')
  assert.equal(params.get('offset'), '20')
  assert.equal(params.get('lecturer_id'), 'lecturer')
})
