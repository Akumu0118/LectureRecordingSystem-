import test from 'node:test'
import assert from 'node:assert/strict'
import { apiRequest } from '../src/services/api.js'

test('failed upload rejects instead of returning a successful saved response', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Audio is invalid' }), { status: 422 })
  try { await assert.rejects(apiRequest('/samples', { method: 'POST' }), error => error.status === 422 && error.message === 'Audio is invalid') }
  finally { globalThis.fetch = original }
})

test('network outage is a visible error', async () => {
  const original = globalThis.fetch
  globalThis.fetch = async () => { throw new TypeError('network') }
  try { await assert.rejects(apiRequest('/samples'), /Could not reach VoiceClean/) }
  finally { globalThis.fetch = original }
})
