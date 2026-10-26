<template>
  <div class="app">
    <aside class="sidebar">
      <h2>🎙 VoiceClean</h2>
      <p class="tagline">Clean lectures. Clearer learning.</p>

      <button class="nav" :class="{ active: view === 'record' }" @click="view = 'record'">
        🎙 Record
        <span v-if="navDot" class="dot" :class="navDot" :title="navDotTitle"></span>
      </button>
      <button class="nav" :class="{ active: view === 'history' }" @click="view = 'history'">
        ◷ History
      </button>
      <button class="nav" :class="{ active: view === 'reference' }" @click="view = 'reference'">
        👤 Reference Voice <span class="soon">Soon</span>
      </button>

      <div class="sidebar-bottom">
        AI-assisted lecture recording
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <h1>{{ pageTitle }}</h1>
          <p>{{ pageSubtitle }}</p>
        </div>
        <span class="badge" :class="badgeClass">● {{ status }}</span>
      </header>

      <div v-for="message in banners" :key="message" class="banner">{{ message }}</div>

      <!-- ============================ RECORD ============================ -->
      <template v-if="view === 'record'">
        <ol class="steps" aria-label="Progress">
          <li v-for="s in steps" :key="s.n"
            :class="{ current: step === s.n, done: step > s.n }">
            <span class="num">{{ step > s.n ? '✓' : s.n }}</span>
            {{ s.label }}
          </li>
        </ol>

        <!-- STEP 1: record -->
        <section v-if="step === 1" class="card">
          <h2>Record your lecture</h2>

          <div class="timer">{{ time }}</div>
          <div class="wave" :class="{ live: recording }" :style="{ '--level': level }">
            <span v-for="n in 36" :key="n" :style="{ '--i': n }"></span>
          </div>

          <p class="center muted">{{ hint }}</p>

          <div class="actions center">
            <button v-if="!recording && !paused && !busy" class="btn primary big" @click="startLecture">
              ● Start recording
            </button>
            <button v-if="recording" class="btn" @click="pauseLecture">Ⅱ Pause</button>
            <button v-if="paused" class="btn primary" @click="resumeLecture">▶ Resume</button>
            <button v-if="recording || paused" class="btn danger" @click="stopLecture">
              ■ Stop &amp; review
            </button>
            <span v-if="busy" class="notice"><span class="spinner"></span> Finishing up…</span>
          </div>

          <p v-if="error" class="error center">{{ error }}</p>
          <p v-if="!recording && !paused && !busy" class="center muted tip">
            Tip: keep the microphone close to the lecturer for the cleanest result.
          </p>
        </section>

        <!-- STEP 2: review + clean -->
        <section v-else-if="step === 2" class="card">
          <h2>Review your recording</h2>
          <p class="muted">Length {{ time }} · {{ localSize }}</p>

          <audio :src="lectureUrl" controls></audio>

          <h3>Name this lecture <span class="optional">(optional)</span></h3>
          <DetailsForm v-model:title="title" v-model:subject="subject" v-model:notes="notes" />

          <div class="actions">
            <button class="btn primary big" @click="cleanAndSave" :disabled="uploading">
              {{ uploading ? 'Cleaning…' : '✨ Clean & Save' }}
            </button>
            <button class="btn" @click="downloadOriginal" :disabled="uploading">
              ↓ Download original
            </button>
            <button class="btn danger" @click="discardLocal" :disabled="uploading">
              Discard &amp; record again
            </button>
          </div>

          <p v-if="uploading" class="notice">
            <span class="spinner"></span>
            Cleaning your recording. Long lectures can take a few minutes, so keep this tab open.
          </p>
          <p v-if="actionError" class="error">{{ actionError }}</p>

          <details class="how">
            <summary>What does “Clean &amp; Save” do?</summary>
            <ol>
              <li>Converts your recording to a standard format.</li>
              <li>Reduces steady background noise (fans, hum, room tone).</li>
              <li>Evens out the volume.</li>
              <li>Saves it to History so you can download it any time.</li>
            </ol>
            <p class="muted">
              It doesn't isolate the lecturer from other voices yet. That comes in a later phase.
            </p>
          </details>
        </section>

        <!-- STEP 3: result -->
        <template v-else>
          <section class="card">
            <template v-if="current.status === 'done'">
              <h2>Your cleaned lecture is ready</h2>
              <p class="muted">
                {{ current.title }} · {{ formatDuration(current.duration) }} · {{ formatDate(current.created_at) }}
              </p>

              <div class="compare">
                <span class="muted">Listen to:</span>
                <div class="toggle" role="group" aria-label="Which version to play">
                  <button :class="{ on: version === 'processed' }" @click="switchVersion('processed')">Cleaned</button>
                  <button :class="{ on: version === 'original' }" @click="switchVersion('original')">Original</button>
                </div>
              </div>

              <audio ref="player" :src="playerSrc" controls preload="metadata"></audio>

              <div class="actions">
                <label class="muted" for="export-format">Download as</label>
                <select id="export-format" v-model="exportFormat" class="select">
                  <option value="mp3">MP3 (best for sharing)</option>
                  <option value="wav">WAV (highest quality)</option>
                  <option value="m4a">M4A</option>
                  <option value="ogg">OGG</option>
                </select>
                <button class="btn primary" @click="downloadExport" :disabled="exporting">
                  {{ exporting ? 'Preparing…' : '↓ Download' }}
                </button>
              </div>
            </template>

            <template v-else>
              <h2>Cleaning didn't finish</h2>
              <p class="error">{{ current.error || 'Processing did not finish.' }}</p>
              <p v-if="current.error_detail" class="muted">Detail: {{ current.error_detail }}</p>
              <audio :src="current.original_url" controls preload="metadata"></audio>
              <div class="actions">
                <button class="btn primary" @click="retryProcessing" :disabled="uploading">
                  {{ uploading ? 'Retrying…' : '↻ Try again' }}
                </button>
                <button class="btn" @click="downloadOriginalFromServer" :disabled="exporting">
                  ↓ Download original
                </button>
              </div>
            </template>

            <p v-if="uploading" class="notice"><span class="spinner"></span> Working…</p>
            <p v-if="actionError" class="error">{{ actionError }}</p>

            <div class="actions footer-actions">
              <button class="btn" @click="newRecording">+ Record another lecture</button>
              <button class="btn danger" @click="deleteCurrent">Delete this lecture</button>
            </div>
          </section>

          <section class="card">
            <h2>Lecture details</h2>
            <DetailsForm v-model:title="title" v-model:subject="subject" v-model:notes="notes" />
            <div class="actions">
              <button class="btn" @click="saveDetails" :disabled="!detailsDirty || savingDetails">
                {{ savingDetails ? 'Saving…' : 'Save changes' }}
              </button>
            </div>
          </section>
        </template>
      </template>

      <!-- ============================ HISTORY ============================ -->
      <section v-else-if="view === 'history'" class="card">
        <p v-if="historyLoading" class="muted">Loading…</p>
        <div v-else-if="history.length === 0" class="empty">
          <p>No saved lectures yet.</p>
          <button class="btn primary" @click="view = 'record'">🎙 Record your first lecture</button>
        </div>

        <div v-for="item in history" :key="item.id" class="history-item">
          <div>
            <strong>{{ item.title }}</strong>
            <span v-if="item.status === 'failed'" class="pill fail">needs retry</span>
            <p class="muted">
              {{ formatDate(item.created_at) }} · {{ formatDuration(item.duration) }}
              <template v-if="item.subject"> · {{ item.subject }}</template>
            </p>
          </div>
          <div class="actions tight">
            <button class="btn" @click="openRecording(item)">Open</button>
            <button class="btn danger" @click="deleteFromHistory(item)">Delete</button>
          </div>
        </div>
        <p v-if="actionError" class="error">{{ actionError }}</p>
      </section>

      <!-- ========================= REFERENCE VOICE ========================= -->
      <section v-else class="card">
        <div class="banner soft">
          <strong>Coming soon.</strong> In a later phase you'll register a lecturer's voice here so
          VoiceClean can pick it out from the room. Nothing on this page is used yet; you can try
          recording a sample, but it stays in this browser tab.
        </div>

        <label class="field-label" for="lecturer-name">Lecturer name</label>
        <input id="lecturer-name" v-model="lecturerName" placeholder="Enter lecturer name" />

        <div class="actions">
          <button class="btn" @click="startSample" :disabled="sampleRecording || recording">
            ● Record sample
          </button>
          <button class="btn danger" @click="stopSample" :disabled="!sampleRecording">
            ■ Stop sample
          </button>
        </div>

        <label class="upload">
          Or upload an existing audio sample
          <input type="file" accept="audio/*" @change="loadSample" />
        </label>

        <p v-if="sampleRecording" class="notice">Recording reference voice...</p>
        <p v-if="error" class="error">{{ error }}</p>

        <audio v-if="sampleUrl" :src="sampleUrl" controls></audio>

        <div class="actions">
          <button class="btn danger" @click="clearSample" :disabled="!sampleUrl">Remove sample</button>
          <span class="muted">{{ sampleUrl ? 'Sample loaded' : 'No sample selected' }}</span>
        </div>
      </section>

      <p class="footer">
        VoiceClean · Record responsibly and obtain permission before recording.
      </p>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from './api.js'
import DetailsForm from './components/DetailsForm.vue'
import {
  formatDuration, formatBytes, extensionFor, safeFilename, micErrorMessage,
} from './utils.js'

// ------------------------------------------------------------------- navigation
const view = ref('record') // 'record' | 'history' | 'reference'

const steps = [
  { n: 1, label: 'Record' },
  { n: 2, label: 'Review & clean' },
  { n: 3, label: 'Download' },
]

// ---------------------------------------------------------------- form state
const lecturerName = ref('')
const title = ref('')
const subject = ref('')
const notes = ref('')

// ------------------------------------------------------------ recorder state
const recording = ref(false)
const paused = ref(false)
const busy = ref(false) // finalising a recording after Stop
const sampleRecording = ref(false)
const error = ref('') // microphone / recorder problems
const status = ref('Ready')
const elapsed = ref(0)
const level = ref(0) // 0..1 live microphone level

const sampleUrl = ref('')
const lectureUrl = ref('') // local preview of the raw recording
const localExt = ref('webm')
const localSize = ref('')

// ------------------------------------------------------------- server state
const current = ref(null) // the saved Recording returned by the API
const uploading = ref(false)
const exporting = ref(false)
const savingDetails = ref(false)
const actionError = ref('')
const history = ref([])
const historyLoading = ref(false)
const banners = ref([])

const version = ref('processed') // which version the player plays
const exportFormat = ref('mp3')
const player = ref(null)

// Raw capture: the server does the noise reduction, so browser-side processing
// (which can distort the voice before we ever see it) is switched off.
const AUDIO_CONSTRAINTS = {
  audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
}

// Non-reactive handles
let lectureRecorder = null
let sampleRecorder = null
let stream = null
let sampleStream = null
let lectureChunks = []
let sampleChunks = []
let lectureBlob = null
let timer = null
let startedAt = 0
let elapsedBeforeStart = 0
let audioCtx = null
let analyser = null
let rafId = 0

// ------------------------------------------------------------------ computed
// Where you are in the record -> review -> download flow.
const step = computed(() => (current.value ? 3 : lectureUrl.value ? 2 : 1))

const PAGE_TITLES = {
  record: ['Record a lecture', {
    1: 'Record it, then clean it up in two more steps.',
    2: 'Listen back, name your lecture, then clean it.',
    3: 'Compare, then download your cleaned lecture.',
  }],
  history: ['History', { all: "Lectures you've cleaned and saved." }],
  reference: ['Reference voice', { all: "Teach VoiceClean the lecturer's voice (coming soon)." }],
}

const pageTitle = computed(() => PAGE_TITLES[view.value][0])
const pageSubtitle = computed(() => {
  const subtitles = PAGE_TITLES[view.value][1]
  return subtitles.all ?? subtitles[step.value]
})

const time = computed(() => formatDuration(elapsed.value))

const hint = computed(() => {
  if (recording.value) return 'Recording… press Pause for a break, or Stop when the lecture ends.'
  if (paused.value) return 'Paused. Press Resume when the lecture continues.'
  if (busy.value) return 'Finishing up…'
  return 'Press Start. Your browser asks for microphone access the first time.'
})

const badgeClass = computed(() => {
  if (recording.value || status.value === 'Error') return 'red'
  if (['Cleaning', 'Saving'].includes(status.value) || paused.value) return 'amber'
  return 'green'
})

// A dot on the Record tab so you notice a recording or unsaved audio while on another page.
const navDot = computed(() => {
  if (recording.value) return 'red'
  if (paused.value || (view.value !== 'record' && step.value === 2)) return 'amber'
  return ''
})
const navDotTitle = computed(() =>
  recording.value ? 'Recording in progress' : paused.value ? 'Recording paused' : 'Unsaved recording',
)

const localName = computed(() => `${safeFilename(title.value)}.${localExt.value}`)

const detailsDirty = computed(() =>
  !!current.value && (
    title.value !== current.value.title ||
    subject.value !== current.value.subject ||
    notes.value !== current.value.notes
  ),
)

const playerSrc = computed(() => {
  if (!current.value) return ''
  return version.value === 'processed' && current.value.processed_url
    ? current.value.processed_url
    : current.value.original_url
})

function formatDate(iso) {
  return iso ? new Date(iso).toLocaleString() : ''
}

// --------------------------------------------------------------------- clock
function startClock() {
  startedAt = Date.now()
  timer = window.setInterval(() => {
    elapsed.value = elapsedBeforeStart + Math.floor((Date.now() - startedAt) / 1000)
  }, 250)
}

function pauseClock() {
  elapsedBeforeStart += Math.floor((Date.now() - startedAt) / 1000)
  window.clearInterval(timer)
  timer = null
  elapsed.value = elapsedBeforeStart
}

function resetClock() {
  window.clearInterval(timer)
  timer = null
  elapsed.value = 0
  elapsedBeforeStart = 0
}

// ------------------------------------------------------------- level meter
function startMeter(micStream) {
  stopMeter()
  const Ctx = window.AudioContext || window.webkitAudioContext
  if (!Ctx) return
  try {
    audioCtx = new Ctx()
    audioCtx.resume?.()
    analyser = audioCtx.createAnalyser()
    analyser.fftSize = 1024
    audioCtx.createMediaStreamSource(micStream).connect(analyser)
  } catch {
    stopMeter() // the meter is cosmetic; never let it break recording
    return
  }
  const data = new Uint8Array(analyser.fftSize)
  const tick = () => {
    analyser.getByteTimeDomainData(data)
    let sum = 0
    for (let i = 0; i < data.length; i++) {
      const v = (data[i] - 128) / 128
      sum += v * v
    }
    const target = recording.value ? Math.min(1, Math.sqrt(sum / data.length) * 6) : 0
    level.value = target > level.value ? target : level.value * 0.85 // fast attack, slow decay
    rafId = requestAnimationFrame(tick)
  }
  tick()
}

function stopMeter() {
  cancelAnimationFrame(rafId)
  rafId = 0
  level.value = 0
  analyser = null
  audioCtx?.close().catch(() => {})
  audioCtx = null
}

// ------------------------------------------------------------------- helpers
function stopStream(s) {
  s?.getTracks().forEach(track => track.stop())
}

function revokeUrl(url) {
  if (url) URL.revokeObjectURL(url)
}

function supportedMime() {
  return [
    'audio/webm;codecs=opus',
    'audio/mp4',
    'audio/webm',
  ].find(type => MediaRecorder.isTypeSupported(type)) || ''
}

async function getMicrophone() {
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    throw new Error("This browser can't record audio here. Use Chrome or Edge over HTTPS or localhost.")
  }
  try {
    return await navigator.mediaDevices.getUserMedia(AUDIO_CONSTRAINTS)
  } catch (e) {
    throw new Error(micErrorMessage(e))
  }
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

// Unsaved audio only exists in this tab, so ask before throwing it away.
function confirmDiscardUnsaved() {
  if (lectureUrl.value && !current.value) {
    return window.confirm('You have a recording that has not been saved. Discard it?')
  }
  return true
}

function clearLocalAudio() {
  revokeUrl(lectureUrl.value)
  lectureUrl.value = ''
  lectureBlob = null
  localSize.value = ''
}

function syncDetails(rec) {
  title.value = rec.title
  subject.value = rec.subject
  notes.value = rec.notes
}

// ----------------------------------------------------- reference sample (local)
async function startSample() {
  error.value = ''
  try {
    sampleStream = await getMicrophone()
    sampleChunks = []

    const mime = supportedMime()
    sampleRecorder = mime
      ? new MediaRecorder(sampleStream, { mimeType: mime })
      : new MediaRecorder(sampleStream)

    sampleRecorder.ondataavailable = e => {
      if (e.data.size) sampleChunks.push(e.data)
    }

    sampleRecorder.onstop = () => {
      if (sampleChunks.length) {
        revokeUrl(sampleUrl.value)
        sampleUrl.value = URL.createObjectURL(
          new Blob(sampleChunks, { type: sampleRecorder.mimeType || 'audio/webm' }),
        )
      }
      stopStream(sampleStream)
      sampleStream = null
      sampleRecording.value = false
    }

    sampleRecorder.start()
    sampleRecording.value = true
  } catch (e) {
    stopStream(sampleStream)
    sampleStream = null
    error.value = e.message || 'Could not access the microphone.'
  }
}

function stopSample() {
  if (sampleRecorder && ['recording', 'paused'].includes(sampleRecorder.state)) {
    sampleRecorder.stop()
  }
}

function loadSample(event) {
  const file = event.target.files?.[0]
  if (!file) return

  if (!file.type.startsWith('audio/')) {
    error.value = "That file type isn't supported. Use WAV, MP3, M4A, OGG, or WebM."
    event.target.value = ''
    return
  }

  revokeUrl(sampleUrl.value)
  sampleUrl.value = URL.createObjectURL(file)
  error.value = ''
}

function clearSample() {
  if (sampleRecording.value) stopSample()
  revokeUrl(sampleUrl.value)
  sampleUrl.value = ''
}

// ---------------------------------------------------------- lecture recording
async function startLecture() {
  if (!confirmDiscardUnsaved()) return
  error.value = ''
  actionError.value = ''
  busy.value = true

  try {
    stopStream(stream)
    stream = await getMicrophone()
    lectureChunks = []

    current.value = null
    clearLocalAudio()
    resetClock()

    const mime = supportedMime()
    lectureRecorder = mime
      ? new MediaRecorder(stream, { mimeType: mime })
      : new MediaRecorder(stream)

    lectureRecorder.ondataavailable = e => {
      if (e.data.size) lectureChunks.push(e.data)
    }

    lectureRecorder.onerror = () => {
      error.value = 'A recording error occurred. Please try again.'
      stopMeter()
      stopStream(stream)
      stream = null
      recording.value = false
      paused.value = false
      busy.value = false
      status.value = 'Error'
      window.clearInterval(timer)
    }

    lectureRecorder.onstop = () => {
      if (lectureChunks.length) {
        lectureBlob = new Blob(lectureChunks, {
          type: lectureRecorder.mimeType || 'audio/webm',
        })
        lectureUrl.value = URL.createObjectURL(lectureBlob)
        localSize.value = formatBytes(lectureBlob.size)
        localExt.value = extensionFor(lectureBlob.type)
      } else {
        error.value = 'Nothing was recorded. Please try again.'
      }

      stopMeter()
      stopStream(stream)
      stream = null
      recording.value = false
      paused.value = false
      busy.value = false
      status.value = lectureBlob ? 'Recorded' : 'Ready'
    }

    lectureRecorder.start(1000) // emit a chunk every second
    busy.value = false
    recording.value = true
    paused.value = false
    status.value = 'Recording'
    startMeter(stream)
    startClock()
  } catch (e) {
    stopMeter()
    stopStream(stream)
    stream = null
    recording.value = false
    paused.value = false
    busy.value = false
    status.value = 'Ready'
    error.value = e.message || 'Could not start recording.'
  }
}

function pauseLecture() {
  if (lectureRecorder?.state !== 'recording') return
  lectureRecorder.pause()
  pauseClock()
  recording.value = false
  paused.value = true
  status.value = 'Paused'
}

function resumeLecture() {
  if (lectureRecorder?.state !== 'paused') return
  lectureRecorder.resume()
  paused.value = false
  recording.value = true
  status.value = 'Recording'
  startClock()
}

function stopLecture() {
  if (!lectureRecorder || !['recording', 'paused'].includes(lectureRecorder.state)) return

  if (recording.value) pauseClock()

  recording.value = false
  paused.value = false
  busy.value = true
  status.value = 'Saving'
  lectureRecorder.stop() // onstop releases the microphone once the last chunk is flushed
}

function downloadOriginal() {
  if (lectureBlob) saveBlob(lectureBlob, localName.value)
}

function discardLocal() {
  if (!window.confirm('Discard this recording and start over?')) return
  clearLocalAudio()
  resetClock()
  actionError.value = ''
  status.value = 'Ready'
}

// ------------------------------------------------------------ server actions
function applyResult(rec) {
  current.value = rec
  syncDetails(rec)
  version.value = rec.status === 'done' ? 'processed' : 'original'
  status.value = rec.status === 'done' ? 'Done' : 'Error'
}

async function cleanAndSave() {
  if (!lectureBlob || uploading.value) return
  actionError.value = ''
  uploading.value = true
  status.value = 'Cleaning'
  try {
    applyResult(await api.createRecording(lectureBlob, {
      title: title.value.trim(),
      subject: subject.value.trim(),
      notes: notes.value.trim(),
    }))
  } catch (e) {
    actionError.value = e.message
    status.value = 'Error'
  } finally {
    uploading.value = false
  }
}

async function retryProcessing() {
  if (!current.value || uploading.value) return
  actionError.value = ''
  uploading.value = true
  status.value = 'Cleaning'
  try {
    applyResult(await api.reprocess(current.value.id))
  } catch (e) {
    actionError.value = e.message
    status.value = 'Error'
  } finally {
    uploading.value = false
  }
}

async function saveDetails() {
  if (!current.value || !detailsDirty.value) return
  actionError.value = ''
  savingDetails.value = true
  try {
    const rec = await api.updateRecording(current.value.id, {
      title: title.value.trim() || current.value.title,
      subject: subject.value.trim(),
      notes: notes.value.trim(),
    })
    current.value = rec
    syncDetails(rec)
  } catch (e) {
    actionError.value = e.message
  } finally {
    savingDetails.value = false
  }
}

async function runDownload(fn) {
  actionError.value = ''
  exporting.value = true
  try {
    const { blob, filename } = await fn()
    saveBlob(blob, filename)
  } catch (e) {
    actionError.value = e.message
  } finally {
    exporting.value = false
  }
}

const downloadExport = () =>
  runDownload(() => api.downloadExport(current.value.id, exportFormat.value, 'processed'))

const downloadOriginalFromServer = () =>
  runDownload(() => api.downloadOriginal(current.value.id))

async function deleteRecordingById(id) {
  await api.deleteRecording(id)
  history.value = history.value.filter(item => item.id !== id)
  if (current.value?.id === id) {
    current.value = null
    clearLocalAudio()
    resetClock()
    status.value = 'Ready'
  }
}

async function deleteCurrent() {
  if (!current.value) return
  if (!window.confirm('Delete this lecture and its audio files? This cannot be undone.')) return
  actionError.value = ''
  try {
    await deleteRecordingById(current.value.id)
  } catch (e) {
    actionError.value = e.message
  }
}

function newRecording() {
  current.value = null
  clearLocalAudio()
  resetClock()
  title.value = ''
  notes.value = ''
  actionError.value = ''
  status.value = 'Ready'
}

// --------------------------------------------------------------- A/B player
function switchVersion(next) {
  if (next === version.value) return
  const el = player.value
  const resumeAt = el?.currentTime || 0
  const wasPlaying = !!el && !el.paused

  if (el) {
    // Keep the listening position so you can flip between versions mid-sentence.
    el.addEventListener('loadedmetadata', () => {
      el.currentTime = resumeAt
      if (wasPlaying) el.play().catch(() => {})
    }, { once: true })
  }
  version.value = next
}

// ------------------------------------------------------------------- history
async function loadHistory() {
  historyLoading.value = true
  actionError.value = ''
  try {
    history.value = await api.listRecordings()
  } catch (e) {
    actionError.value = e.message
  } finally {
    historyLoading.value = false
  }
}

watch(view, next => {
  actionError.value = ''
  if (next === 'history') loadHistory()
})

function openRecording(item) {
  if (recording.value || paused.value || busy.value) {
    actionError.value = 'Finish or stop the current recording before opening another lecture.'
    return
  }
  if (!confirmDiscardUnsaved()) return
  clearLocalAudio()
  actionError.value = ''
  applyResult(item)
  status.value = 'Ready'
  view.value = 'record'
}

async function deleteFromHistory(item) {
  if (!window.confirm(`Delete "${item.title}" and its audio files? This cannot be undone.`)) return
  actionError.value = ''
  try {
    await deleteRecordingById(item.id)
  } catch (e) {
    actionError.value = e.message
  }
}

// ----------------------------------------------------------------- lifecycle
function onBeforeUnload(event) {
  const unsaved = !!lectureUrl.value && !current.value
  if (recording.value || paused.value || uploading.value || unsaved) {
    event.preventDefault()
    event.returnValue = ''
  }
}

onMounted(async () => {
  window.addEventListener('beforeunload', onBeforeUnload)

  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
    banners.value.push("This browser can't record audio here. Use Chrome or Edge over HTTPS or localhost.")
  }
  try {
    const health = await api.health()
    if (!health.ffmpeg) {
      banners.value.push('The server is running but FFmpeg is not installed, so recordings cannot be processed yet.')
    }
  } catch (e) {
    banners.value.push(e.message)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('beforeunload', onBeforeUnload)
  window.clearInterval(timer)
  stopMeter()
  if (lectureRecorder && ['recording', 'paused'].includes(lectureRecorder.state)) {
    lectureRecorder.onstop = null
    lectureRecorder.stop()
  }
  if (sampleRecorder && ['recording', 'paused'].includes(sampleRecorder.state)) {
    sampleRecorder.onstop = null
    sampleRecorder.stop()
  }
  stopStream(stream)
  stopStream(sampleStream)
  revokeUrl(lectureUrl.value)
  revokeUrl(sampleUrl.value)
})
</script>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  background: #f4f7fc;
  color: #172b4d;
  font-family: Inter, Arial, sans-serif;
}

/* ------------------------------------------------------------------ sidebar */
.sidebar {
  width: 235px;
  flex-shrink: 0;
  background: #101e3b;
  color: white;
  padding: 25px 15px;
  display: flex;
  flex-direction: column;
}

.sidebar h2 { margin: 0; font-size: 23px; }
.tagline { color: #b9c8e5; font-size: 12px; margin: 8px 0 30px; }

.nav {
  display: flex;
  align-items: center;
  gap: 8px;
  text-align: left;
  border: 0;
  background: transparent;
  color: #e4eafa;
  padding: 14px 12px;
  border-radius: 9px;
  cursor: pointer;
  margin-bottom: 7px;
  font: inherit;
}
.nav:hover, .nav.active { background: #2459cb; color: white; }

.soon {
  margin-left: auto;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 10px;
  background: #ffffff22;
  color: #cfdcf5;
}

.dot { width: 9px; height: 9px; border-radius: 50%; margin-left: auto; }
.dot.red { background: #ff5b6b; animation: blink 1.2s ease-in-out infinite; }
.dot.amber { background: #ffc43d; }
@keyframes blink { 50% { opacity: .35; } }

.sidebar-bottom {
  margin-top: auto;
  padding: 15px 5px;
  color: #bdcce8;
  font-size: 13px;
  line-height: 1.6;
}

/* --------------------------------------------------------------------- main */
.main {
  flex: 1;
  min-width: 0;
  max-width: 900px;
  padding: 32px;
  margin: 0 auto;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
  margin-bottom: 22px;
}

h1 { margin: 0 0 8px; font-size: 30px; }
h2 { margin: 0 0 12px; font-size: 19px; }
h3 { margin: 26px 0 0; font-size: 15px; }
.optional { color: #6b7d99; font-weight: 400; font-size: 13px; }
p { line-height: 1.5; }
.muted { color: #6b7d99; font-size: 13px; }

.card {
  background: white;
  border: 1px solid #dce6f5;
  border-radius: 13px;
  padding: 23px;
  margin-bottom: 20px;
  box-shadow: 0 3px 12px #172b4d08;
}

.badge {
  border-radius: 20px;
  padding: 8px 12px;
  font-size: 12px;
  white-space: nowrap;
}
.red { color: #b42332; background: #ffebed; }
.green { color: #18794e; background: #e4f8ed; }
.amber { color: #8a5a00; background: #fff4d6; }
.dot.red, .dot.amber { background-clip: padding-box; }

.banner {
  background: #fff4d6;
  border: 1px solid #f3dd9b;
  color: #6b4a00;
  border-radius: 10px;
  padding: 12px 15px;
  font-size: 13px;
  margin-bottom: 16px;
}
.banner.soft {
  background: #eef4ff;
  border-color: #cfe0ff;
  color: #24407a;
  line-height: 1.5;
}

/* -------------------------------------------------------------------- steps */
.steps {
  display: flex;
  gap: 8px;
  list-style: none;
  padding: 0;
  margin: 0 0 20px;
}
.steps li {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 11px 13px;
  border-radius: 10px;
  background: #e9eff9;
  color: #6b7d99;
  font-size: 13px;
  font-weight: 600;
}
.steps .num {
  width: 24px;
  height: 24px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: #cfd9ea;
  color: white;
  font-size: 12px;
}
.steps li.current { background: #dfe9ff; color: #1b4fc4; }
.steps li.current .num { background: #205fe5; }
.steps li.done { background: #e4f8ed; color: #18794e; }
.steps li.done .num { background: #2fa36b; }

/* ----------------------------------------------------------------- recorder */
.timer {
  font-size: 48px;
  font-weight: 700;
  text-align: center;
  font-variant-numeric: tabular-nums;
  margin: 24px 0;
}

.wave {
  height: 70px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  overflow: hidden;
  margin: 15px 0;
  --level: 0;
}
.wave span {
  width: 4px;
  height: calc(8px + var(--i) * 2px);
  max-height: 66px;
  background: #a4c5ff;
  border-radius: 5px;
}
/* While recording, bars follow the real microphone level. */
.wave.live span {
  background: #2463eb;
  transform: scaleY(calc(0.15 + var(--level) * 0.85));
}

.center { text-align: center; }
.tip { margin-top: 18px; }

.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 18px;
}
.actions.center { justify-content: center; }
.actions.tight { margin-top: 0; }
.footer-actions { margin-top: 26px; padding-top: 18px; border-top: 1px solid #edf1f8; }

.btn {
  border: 1px solid #d4dfef;
  background: #f8faff;
  color: #213b65;
  border-radius: 8px;
  padding: 11px 15px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn.big { padding: 14px 22px; font-size: 15px; }
.btn.primary { background: #205fe5; color: white; border-color: #205fe5; }
.btn.danger { background: #fff0f0; color: #b42332; border-color: #ffd1d1; }
.btn:disabled { opacity: .45; cursor: not-allowed; }

.select {
  border: 1px solid #d4dfef;
  background: white;
  color: #213b65;
  border-radius: 8px;
  padding: 10px 12px;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
}

.compare { display: flex; align-items: center; gap: 12px; margin-top: 6px; }
.toggle {
  display: inline-flex;
  border: 1px solid #d4dfef;
  border-radius: 9px;
  overflow: hidden;
}
.toggle button {
  border: 0;
  background: #f8faff;
  color: #213b65;
  padding: 9px 18px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.toggle button.on { background: #205fe5; color: white; }

.upload {
  display: block;
  border: 1px dashed #8ca9d8;
  border-radius: 9px;
  background: #f5f8ff;
  padding: 18px;
  margin-top: 18px;
  font-size: 13px;
  cursor: pointer;
}
.upload input { display: block; margin-top: 10px; max-width: 100%; }

audio { width: 100%; margin: 14px 0; }
.error { color: #b42332; font-size: 13px; }
.notice { color: #2459cb; font-size: 13px; }

.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  margin-right: 6px;
  border: 2px solid #bdd1ff;
  border-top-color: #2463eb;
  border-radius: 50%;
  vertical-align: -1px;
  animation: spin .8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.how { margin-top: 22px; font-size: 13px; color: #35507d; }
.how summary { cursor: pointer; font-weight: 600; }
.how ol { padding-left: 20px; line-height: 1.7; }

/* ------------------------------------------------------------------ history */
.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid #edf1f8;
  padding: 12px 0;
}
.history-item:last-of-type { border-bottom: 0; }
.history-item p { margin-bottom: 0; }
.pill {
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
}
.pill.fail { background: #ffebed; color: #b42332; }
.empty { text-align: center; padding: 26px 0; color: #6b7d99; }

.footer { color: #71809a; font-size: 12px; text-align: center; }

@media (max-width: 760px) {
  .sidebar { width: 65px; padding: 18px 7px; }
  .sidebar h2 { font-size: 0; }
  .sidebar h2:first-letter { font-size: 22px; }
  .tagline, .sidebar-bottom, .soon { display: none; }
  .nav { font-size: 0; justify-content: center; padding: 14px 2px; }
  .nav::first-letter { font-size: 16px; }
  .dot { margin-left: 0; }
  .main { padding: 17px 12px; }
  h1 { font-size: 24px; }
  .card { padding: 17px; }
  .timer { font-size: 37px; }
  .steps li { font-size: 0; justify-content: center; padding: 10px 4px; }
  .steps .num { font-size: 12px; }
  .history-item { flex-direction: column; align-items: flex-start; }
}
</style>
