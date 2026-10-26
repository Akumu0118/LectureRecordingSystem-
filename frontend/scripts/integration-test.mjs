// Exercises the real src/api.js + src/utils.js against a running stack.
//   node scripts/integration-test.mjs [http://127.0.0.1:5173] [path/to/audio.webm]
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const ORIGIN = process.argv[2] || 'http://127.0.0.1:5173'
const AUDIO = process.argv[3] || '/tmp/lecture.webm'

// api.js uses relative URLs (browser same-origin); point them at the dev server.
const realFetch = globalThis.fetch
globalThis.fetch = (url, opts) =>
  realFetch(typeof url === 'string' && url.startsWith('/') ? ORIGIN + url : url, opts)

const { api, ApiError } = await import('../src/api.js')
const { formatDuration, micErrorMessage, extensionFor, safeFilename } = await import('../src/utils.js')

let passed = 0
const test = async (name, fn) => {
  try { await fn(); passed++; console.log('  ok  ', name) }
  catch (e) { console.log('  FAIL', name, '\n      ', e.message); process.exitCode = 1 }
}

// ---- pure helpers
await test('utils: formatDuration / extensionFor / safeFilename / micErrorMessage', () => {
  assert.equal(formatDuration(3725), '01:02:05')
  assert.equal(formatDuration(null), '00:00:00')
  assert.equal(extensionFor('audio/webm;codecs=opus'), 'webm')
  assert.equal(extensionFor('audio/mp4'), 'm4a')
  assert.equal(safeFilename('  CpE 301: Lecture #3! '), 'CpE_301_Lecture_3')
  assert.equal(safeFilename(''), 'lecture')
  assert.match(micErrorMessage({ name: 'NotAllowedError' }), /blocked/)
  assert.match(micErrorMessage({ name: 'NotFoundError' }), /No microphone/)
  assert.match(micErrorMessage({ name: 'NotReadableError' }), /another app/)
})

const webm = new Blob([readFileSync(AUDIO)], { type: 'audio/webm;codecs=opus' })
let rec

await test('health reports ffmpeg', async () => {
  const h = await api.health()
  assert.equal(h.ffmpeg, true)
})

await test('createRecording uploads WebM/Opus, cleans it, returns done', async () => {
  rec = await api.createRecording(webm, { title: 'Net Lecture 3', subject: 'CpE', notes: 'week 3' })
  assert.equal(rec.status, 'done')
  assert.equal(rec.title, 'Net Lecture 3')
  assert.equal(rec.subject, 'CpE')
  assert.ok(Math.abs(rec.duration - 8) < 0.3, `duration ${rec.duration}`)
  assert.ok(rec.processed_url && rec.original_url)
})

await test('blank title gets a server default', async () => {
  const r = await api.createRecording(webm, {})
  assert.match(r.title, /^Lecture /)
  await api.deleteRecording(r.id)
})

await test('processed + original audio stream, with Range support (seeking)', async () => {
  for (const url of [rec.processed_url, rec.original_url]) {
    const path = new URL(url).pathname + new URL(url).search
    const full = await fetch(path)
    assert.equal(full.status, 200)
    assert.match(full.headers.get('content-type'), /audio\//)
    const part = await fetch(path, { headers: { Range: 'bytes=0-99' } })
    assert.equal(part.status, 206)
    assert.equal((await part.arrayBuffer()).byteLength, 100)
  }
})

await test('downloadExport mp3 / wav / m4a / ogg return real audio with a good filename', async () => {
  const mp3 = await api.downloadExport(rec.id, 'mp3')
  assert.equal(mp3.filename, 'Net_Lecture_3.mp3')
  const head = new Uint8Array(await mp3.blob.slice(0, 3).arrayBuffer())
  assert.ok((head[0] === 0x49 && head[1] === 0x44) || head[0] === 0xff, 'mp3 magic')
  const wav = await api.downloadExport(rec.id, 'wav')
  assert.equal(Buffer.from(await wav.blob.slice(0, 4).arrayBuffer()).toString(), 'RIFF')
  for (const fmt of ['m4a', 'ogg']) {
    const f = await api.downloadExport(rec.id, fmt)
    assert.ok(f.blob.size > 1000 && f.filename.endsWith('.' + fmt), fmt)
  }
})

await test('downloadOriginal returns the untouched upload', async () => {
  const f = await api.downloadOriginal(rec.id)
  assert.equal(f.filename, 'Net_Lecture_3.webm')
  assert.equal(f.blob.size, webm.size)
})

await test('updateRecording + listRecordings + getRecording', async () => {
  const upd = await api.updateRecording(rec.id, { title: 'Renamed', notes: 'edited' })
  assert.equal(upd.title, 'Renamed')
  assert.equal(upd.status, 'done')
  const list = await api.listRecordings()
  assert.ok(Array.isArray(list) && list.some(r => r.id === rec.id))
  assert.equal((await api.getRecording(rec.id)).notes, 'edited')
})

await test('undecodable audio -> status failed, friendly error, original still downloadable', async () => {
  const bad = new Blob([Buffer.from('this is not audio '.repeat(300))], { type: 'audio/webm' })
  const r = await api.createRecording(bad, { title: 'Broken' })
  assert.equal(r.status, 'failed')
  assert.equal(r.error, 'Processing failed. Your original recording is safe. Retry or download it.')
  assert.equal(r.processed_url, null)
  const orig = await api.downloadOriginal(r.id)
  assert.equal(orig.blob.size, bad.size)
  const retry = await api.reprocess(r.id)
  assert.equal(retry.status, 'failed')
  await assert.rejects(api.downloadExport(r.id, 'mp3'), e =>
    e instanceof ApiError && e.code === 'not_ready')
  await api.deleteRecording(r.id)
})

await test('server validation errors surface as ApiError with the friendly message', async () => {
  await assert.rejects(
    api.createRecording(new Blob([''], { type: 'audio/webm' }), { title: 'Empty' }),
    e => e instanceof ApiError && e.status === 400 && /empty/i.test(e.message),
  )
  await assert.rejects(api.downloadExport(rec.id, 'exe'), e => e.code === 'bad_format')
})

await test('deleteRecording removes it (404 afterwards)', async () => {
  assert.equal(await api.deleteRecording(rec.id), null)
  await assert.rejects(api.getRecording(rec.id), e => e instanceof ApiError && e.status === 404)
  assert.ok(!(await api.listRecordings()).some(r => r.id === rec.id))
})

await test('backend down -> friendly network error', async () => {
  const saved = globalThis.fetch
  globalThis.fetch = () => Promise.reject(new TypeError('fetch failed'))
  await assert.rejects(api.health(), e => e instanceof ApiError && e.code === 'network' && /backend is running/.test(e.message))
  globalThis.fetch = saved
})

console.log(`\n${passed} checks passed${process.exitCode ? ' (with failures)' : ''}`)
