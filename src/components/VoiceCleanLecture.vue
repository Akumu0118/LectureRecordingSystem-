
<template>
  <div class="app">
    <aside class="sidebar">
      <h2>🎙 VoiceClean</h2>
      <p class="tagline">Clean lectures. Clearer learning.</p>

      <button class="nav active">🎙 Lecture Recording</button>
      <button class="nav" @click="showReference = !showReference">
        👤 Reference Voice
      </button>
      <button class="nav" @click="showProcessing = !showProcessing">
        ⚙ Processing
      </button>
      <button class="nav" @click="showHistory = !showHistory">
        ◷ Recording History
      </button>

      <div class="sidebar-bottom">
        AI-assisted lecture recording
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <h1>Lecture Recording</h1>
          <p>Capture, review, and export your lectures.</p>
        </div>
        <span class="badge" :class="recording ? 'red' : 'green'">
          ● {{ status }}
        </span>
      </header>

      <!-- REFERENCE VOICE -->
      <section v-if="showReference" class="card">
        <h2>Lecturer Reference Voice</h2>
        <p class="muted">
          Upload a voice sample or record one to use as the lecturer reference.
        </p>

        <label class="field-label">Lecturer name</label>
        <input v-model="lecturerName" placeholder="Enter lecturer name" />

        <div class="actions">
          <button class="btn" @click="startSample"
            :disabled="sampleRecording || recording">
            ● Record Sample
          </button>
          <button class="btn danger" @click="stopSample"
            :disabled="!sampleRecording">
            ■ Stop Sample
          </button>
        </div>

        <label class="upload">
          Upload an existing audio sample
          <input type="file" accept="audio/*" @change="loadSample" />
        </label>

        <p v-if="sampleRecording" class="notice">
          Recording reference voice...
        </p>

        <audio v-if="sampleUrl" :src="sampleUrl" controls></audio>

        <div class="actions">
          <button class="btn danger" @click="clearSample" :disabled="!sampleUrl">
            Remove Sample
          </button>
          <span class="muted">
            {{ sampleUrl ? 'Reference loaded' : 'No reference selected' }}
          </span>
        </div>
      </section>

      <!-- LECTURE RECORDER -->
      <section class="card">
        <h2>Record Lecture</h2>
        <p class="muted">
          Allow microphone access when your browser requests permission.
        </p>

        <div class="timer">{{ time }}</div>
        <div class="wave">
          <span v-for="n in 36" :key="n"
            :style="{ '--i': n }"
            :class="{ moving: recording }"></span>
        </div>

        <p class="center muted">{{ hint }}</p>

        <div class="actions center">
          <button class="btn primary" @click="startLecture"
            :disabled="recording || paused || busy">
            ● Start
          </button>
          <button class="btn" @click="pauseLecture"
            :disabled="!recording">
            Ⅱ Pause
          </button>
          <button class="btn" @click="resumeLecture"
            :disabled="!paused">
            ▶ Resume
          </button>
          <button class="btn danger" @click="stopLecture"
            :disabled="!recording && !paused">
            ■ Stop
          </button>
        </div>

        <p v-if="error" class="error">{{ error }}</p>
      </section>

      <!-- DETAILS -->
      <section class="card">
        <h2>Lecture Details</h2>

        <label class="field-label">Lecture title</label>
        <input v-model="title" placeholder="e.g. Computer Networks - Lecture 3" />

        <label class="field-label">Subject</label>
        <input v-model="subject" placeholder="e.g. Computer Engineering" />

        <label class="field-label">Notes</label>
        <textarea v-model="notes" placeholder="Optional notes..." rows="3"></textarea>
      </section>

      <!-- OUTPUT -->
      <section v-if="lectureUrl" class="card">
        <h2>Recording Preview</h2>
        <p class="muted">{{ outputName }} · {{ fileSize }}</p>

        <audio :src="lectureUrl" controls></audio>

        <div class="actions">
          <button class="btn primary" @click="downloadRecording">
            ↓ Download Audio
          </button>
          <button class="btn" @click="saveToHistory">
            Save to History
          </button>
          <button class="btn danger" @click="deleteRecording">
            Delete
          </button>
        </div>

        <p class="muted">
          The browser's supported recording format is used.
          MP3 conversion is not yet connected.
        </p>
      </section>

      <!-- PROCESSING -->
      <section v-if="showProcessing" class="card">
        <h2>Audio Processing Pipeline</h2>
        <div class="pipeline">
          <p>✓ Audio recording and capture</p>
          <p>○ Target-speaker extraction — AI model not connected</p>
          <p>○ DSP noise reduction — not connected</p>
          <p>○ Final processed audio — pending integration</p>
        </div>
        <p class="muted">
          Recording alone does not isolate the lecturer. The AI model
          and noise-reduction pipeline must be integrated separately.
        </p>
      </section>

      <!-- HISTORY -->
      <section v-if="showHistory" class="card">
        <h2>Recording History</h2>
        <p v-if="history.length === 0" class="muted">
          No recordings saved in this session.
        </p>
        <div v-for="item in history" :key="item.id" class="history-item">
          <div>
            <strong>{{ item.title }}</strong>
            <p class="muted">{{ item.date }} · {{ item.duration }}</p>
          </div>
          <button class="btn" @click="restoreHistory(item)">Open</button>
        </div>
      </section>

      <p class="footer">
        VoiceClean · Record responsibly and obtain permission before recording.
      </p>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'

const lecturerName = ref('')
const title = ref('')
const subject = ref('')
const notes = ref('')

const showReference = ref(true)
const showProcessing = ref(false)
const showHistory = ref(false)

const recording = ref(false)
const paused = ref(false)
const busy = ref(false)
const sampleRecording = ref(false)
const error = ref('')
const status = ref('Ready')

const elapsed = ref(0)
const sampleUrl = ref('')
const lectureUrl = ref('')
const outputName = ref('')
const fileSize = ref('')
const history = ref([])

let lectureRecorder = null
let sampleRecorder = null
let stream = null
let sampleStream = null
let lectureChunks = []
let sampleChunks = []
let lectureBlob = null
let sampleBlob = null
let timer = null
let startedAt = 0
let elapsedBeforeStart = 0

const time = computed(() => {
  const s = elapsed.value
  return [
    Math.floor(s / 3600),
    Math.floor((s % 3600) / 60),
    s % 60
  ].map(v => String(v).padStart(2, '0')).join(':')
})

const hint = computed(() => {
  if (recording.value) return 'Recording lecture...'
  if (paused.value) return 'Recording paused'
  if (lectureUrl.value) return 'Recording ready for preview or download'
  return 'Ready to record'
})

function startClock() {
  startedAt = Date.now()
  timer = window.setInterval(() => {
    elapsed.value = elapsedBeforeStart +
      Math.floor((Date.now() - startedAt) / 1000)
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
    'audio/webm'
  ].find(type => MediaRecorder.isTypeSupported(type)) || ''
}

async function getMicrophone() {
  if (!navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === 'undefined') {
    throw new Error('Use an updated browser over HTTPS or localhost.')
  }
  return navigator.mediaDevices.getUserMedia({ audio: true })
}

// Reference sample recording
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
        sampleBlob = new Blob(sampleChunks, {
          type: sampleRecorder.mimeType || 'audio/webm'
        })
        revokeUrl(sampleUrl.value)
        sampleUrl.value = URL.createObjectURL(sampleBlob)
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
  if (sampleRecorder &&
      ['recording', 'paused'].includes(sampleRecorder.state)) {
    sampleRecorder.stop()
  }
}

function loadSample(event) {
  const file = event.target.files?.[0]
  if (!file) return

  if (!file.type.startsWith('audio/')) {
    error.value = 'Please select a valid audio file.'
    event.target.value = ''
    return
  }

  revokeUrl(sampleUrl.value)
  sampleBlob = file
  sampleUrl.value = URL.createObjectURL(file)
  error.value = ''
}

function clearSample() {
  if (sampleRecording.value) stopSample()
  revokeUrl(sampleUrl.value)
  sampleUrl.value = ''
  sampleBlob = null
}

// Lecture recording
async function startLecture() {
  error.value = ''
  busy.value = true

  try {
    stopStream(stream)
    stream = await getMicrophone()
    lectureChunks = []

    revokeUrl(lectureUrl.value)
    lectureUrl.value = ''
    lectureBlob = null

    resetClock()

    const mime = supportedMime()
    lectureRecorder = mime
      ? new MediaRecorder(stream, { mimeType: mime })
      : new MediaRecorder(stream)

    lectureRecorder.ondataavailable = e => {
      if (e.data.size) lectureChunks.push(e.data)
    }

    lectureRecorder.onerror = () => {
      error.value = 'A recording error occurred.'
      stopStream(stream)
      stream = null
      recording.value = false
      paused.value = false
      status.value = 'Error'
      window.clearInterval(timer)
    }

    lectureRecorder.onstop = () => {
      if (lectureChunks.length) {
        lectureBlob = new Blob(lectureChunks, {
          type: lectureRecorder.mimeType || 'audio/webm'
        })

        lectureUrl.value = URL.createObjectURL(lectureBlob)
        fileSize.value = lectureBlob.size < 1048576
          ? `${(lectureBlob.size / 1024).toFixed(1)} KB`
          : `${(lectureBlob.size / 1048576).toFixed(2)} MB`

        outputName.value = `${safeFilename(title.value || 'lecture')}.${extension(lectureBlob.type)}`
      }

      stopStream(stream)
      stream = null
      recording.value = false
      paused.value = false
      busy.value = false
      status.value = lectureBlob ? 'Saved' : 'Ready'
    }

    lectureRecorder.start(1000)
    recording.value = true
    paused.value = false
    status.value = 'Recording'
    startClock()
  } catch (e) {
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
  if (!lectureRecorder ||
      !['recording', 'paused'].includes(lectureRecorder.state)) return

  if (recording.value) pauseClock()

  recording.value = false
  paused.value = false
  busy.value = true
  status.value = 'Saving'
  lectureRecorder.stop()
  stopStream(stream)
  stream = null
}

function safeFilename(value) {
  return value.trim().replace(/[^\w-]+/g, '_').slice(0, 80) || 'lecture'
}

function extension(type) {
  if (type.includes('mp4')) return 'm4a'
  if (type.includes('ogg')) return 'ogg'
  if (type.includes('wav')) return 'wav'
  return 'webm'
}

function downloadRecording() {
  if (!lectureBlob) return
  const url = URL.createObjectURL(lectureBlob)
  const a = document.createElement('a')
  a.href = url
  a.download = outputName.value || 'voiceclean-lecture.webm'
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

function saveToHistory() {
  if (!lectureBlob) return
  history.value.unshift({
    id: Date.now(),
    title: title.value || 'Untitled Lecture',
    subject: subject.value,
    notes: notes.value,
    date: new Date().toLocaleString(),
    duration: time.value,
    blob: lectureBlob
  })
}

function restoreHistory(item) {
  title.value = item.title
  subject.value = item.subject
  notes.value = item.notes
  revokeUrl(lectureUrl.value)
  lectureBlob = item.blob
  lectureUrl.value = URL.createObjectURL(item.blob)
  outputName.value = `${safeFilename(item.title)}.${extension(item.blob.type)}`
  fileSize.value = item.blob.size < 1048576
    ? `${(item.blob.size / 1024).toFixed(1)} KB`
    : `${(item.blob.size / 1048576).toFixed(2)} MB`
  showHistory.value = false
}

function deleteRecording() {
  revokeUrl(lectureUrl.value)
  lectureUrl.value = ''
  lectureBlob = null
  outputName.value = ''
  fileSize.value = ''
  status.value = 'Ready'
}

onBeforeUnmount(() => {
  window.clearInterval(timer)
  if (lectureRecorder &&
      ['recording', 'paused'].includes(lectureRecorder.state)) {
    lectureRecorder.onstop = null
    lectureRecorder.stop()
  }
  if (sampleRecorder &&
      ['recording', 'paused'].includes(sampleRecorder.state)) {
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
* { box-sizing: border-box; }

.app {
  min-height: 100vh;
  display: flex;
  background: #f4f7fc;
  color: #172b4d;
  font-family: Inter, Arial, sans-serif;
}

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
  text-align: left;
  border: 0;
  background: transparent;
  color: #e4eafa;
  padding: 14px 12px;
  border-radius: 9px;
  cursor: pointer;
  margin-bottom: 7px;
}

.nav:hover, .nav.active { background: #2459cb; color: white; }
.sidebar-bottom {
  margin-top: auto;
  padding: 15px 5px;
  color: #bdcce8;
  font-size: 13px;
  line-height: 1.6;
}

.main {
  flex: 1;
  min-width: 0;
  max-width: 1250px;
  padding: 32px;
  margin: 0 auto;
}

.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 15px;
  margin-bottom: 25px;
}

h1 { margin: 0 0 8px; font-size: 30px; }
h2 { margin: 0 0 12px; font-size: 19px; }
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
}


.wave span {
  width: 4px;
  height: calc(8px + var(--i) * 2px);
  max-height: 66px;
  background: #a4c5ff;
  border-radius: 5px;
}


.wave span.moving {
  animation: pulse .7s ease-in-out infinite alternate;
  animation-delay: calc(var(--i) * -.035s);
  background: #2463eb;
}

@keyframes pulse {
  from { transform: scaleY(.3); }
  to { transform: scaleY(1); }
}

.center { text-align: center; }
.actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-top: 18px;
}

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

.btn.primary { background: #205fe5; color: white; border-color: #205fe5; }
.btn.danger { background: #fff0f0; color: #b42332; border-color: #ffd1d1; }
.btn:disabled { opacity: .45; cursor: not-allowed; }

.field-label {
  display: block;
  margin: 16px 0 7px;
  font-size: 13px;
  font-weight: 600;
}

input:not([type="file"]), textarea {
  width: 100%;
  padding: 12px;
  border: 1px solid #d5dfed;
  border-radius: 8px;
  background: white;
  font: inherit;
  color: #172b4d;
}

input:focus, textarea:focus {
  outline: 2px solid #bdd1ff;
  border-color: #2463eb;
}

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
.pipeline p { padding: 9px 0; border-bottom: 1px solid #edf1f8; }
.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid #edf1f8;
  padding: 12px 0;
}
.history-item p { margin-bottom: 0; }
.footer { color: #71809a; font-size: 12px; text-align: center; }

@media (max-width: 760px) {
  .sidebar { width: 65px; padding: 18px 7px; }
  .sidebar h2 { font-size: 0; }
  .sidebar h2:first-letter { font-size: 22px; }
  .tagline, .sidebar-bottom { display: none; }
  .nav { font-size: 0; text-align: center; padding: 14px 2px; }
  .main { padding: 17px 12px; }
  h1 { font-size: 24px; }
  .card { padding: 17px; }
  .timer { font-size: 37px; }
}
</style>
