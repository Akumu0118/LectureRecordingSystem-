import test from 'node:test'
import assert from 'node:assert/strict'
import { loadReferenceContext, rememberedLecturer, rememberLecturer } from '../src/services/referenceContext.js'

const first = { id: '11111111-1111-4111-8111-111111111111', name: 'First' }
const second = { id: '22222222-2222-4222-8222-222222222222', name: 'Second' }
const samples = { items: [{ id: 'saved', lecturer_id: second.id, audio_url: '/saved/audio' }], total: 1 }
const page = { items: [first], total: 1 }

test('selected lecturer survives a new page session and is fetched even outside the first page', async () => {
  const values = new Map()
  const storage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) }
  rememberLecturer(second.id, storage)
  const calls = []
  const result = await loadReferenceContext(async path => {
    calls.push(path)
    if (path.endsWith('/samples?limit=20&offset=0')) return samples
    return path.endsWith(second.id) ? second : page
  }, rememberedLecturer(storage))
  assert.equal(result.lecturer.id, second.id)
  assert.deepEqual(result.samples, samples)
  assert.equal(calls[2], `/api/lecturers/${second.id}/samples?limit=20&offset=0`)
  assert.deepEqual([...values.values()], [second.id]) // No blobs or sample metadata stored locally.
})

test('first visit reloads saved samples for the first lecturer', async () => {
  const result = await loadReferenceContext(async path => path.includes('/samples?') ? samples : page, null)
  assert.equal(result.lecturer.id, first.id)
  assert.equal(result.samples.total, 1)
})

test('deleted remembered lecturer does not load another lecturer samples', async () => {
  const result = await loadReferenceContext(async path => {
    if (path.endsWith(second.id)) throw Object.assign(new Error('Missing'), { status: 404 })
    return page
  }, second.id)
  assert.equal(result.lecturer, null)
  assert.equal(result.samples, null)
})

test('network errors remain errors instead of becoming an empty saved list', async () => {
  await assert.rejects(loadReferenceContext(async path => {
    if (path.includes('/samples?')) throw new Error('Offline')
    return page
  }, null), /Offline/)
})

test('empty backend is an explicit empty context', async () => {
  const result = await loadReferenceContext(async () => ({ items: [], total: 0 }), null)
  assert.equal(result.lecturer, null)
  assert.equal(result.samples, null)
})

test('switching lecturers replaces the sample context and storage failure is harmless', async () => {
  const broken = { getItem() { throw Error('blocked') }, setItem() { throw Error('blocked') } }
  assert.equal(rememberedLecturer(broken), null)
  assert.doesNotThrow(() => rememberLecturer(second.id, broken))
  const result = await loadReferenceContext(async path => path.includes('/samples?')
    ? { items: [], total: 0 } : path.endsWith(second.id) ? second : page, second.id)
  assert.equal(result.lecturer.id, second.id)
  assert.deepEqual(result.samples.items, [])
})
