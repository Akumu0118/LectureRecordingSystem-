import { ref, computed, nextTick, onBeforeUnmount, onMounted } from 'vue'
import { apiRequest, audioUrl } from '../services/api.js'
import { loadReferenceContext, rememberLecturer } from '../services/referenceContext.js'
import { recordingDescription, recordingFields, recordingQuery, saveRecordingDraft } from '../services/recordings.js'
import { useAudioVersions } from './useAudioVersions.js'

// Owns one shared session so changing panels cannot interrupt microphone capture.
export function useVoiceClean() {

  const views = {
    overview: { title: 'Overview', description: 'Your lecturers, recordings, and next steps.' },
    references: { title: 'Lecturers & Reference Voice', description: 'Manage lecturers and their saved reference samples.' },
    recording: { title: 'Lecture Recording', description: 'Capture a lecture, review the audio, and save it.' },
    history: { title: 'Recording History', description: 'Find, play, and manage saved lectures.' },
    audio: { title: 'Enhancement & Export', description: 'Compare audio versions and download your files.' }
  }
  function viewFromHash() {
    const name = globalThis.location?.hash?.slice(1)
    return Object.hasOwn(views, name) ? name : 'overview'
  }
  const activeView = ref(viewFromHash())
  const currentView = computed(() => views[activeView.value])
  const captureLocked = computed(() => recording.value || paused.value || busy.value || lectureSaving.value || referenceBusy.value || sampleRecording.value || sampleStarting.value)
  const activity = computed(() => lectureSaving.value ? 'Uploading lecture' : sampleRecording.value ? 'Recording reference' : sampleStarting.value || busy.value ? 'Requesting microphone' : paused.value ? 'Lecture paused' : recording.value ? 'Recording lecture' : audioJobBusy.value ? audioJobStatus.value : status.value)
  async function focusWorkspace() {
    await nextTick()
    globalThis.document?.getElementById?.('workspace-title')?.focus({ preventScroll: false })
  }
  async function navigate(view, { updateHash = true, focus = true } = {}) {
    if (!Object.hasOwn(views, view)) return
    activeView.value = view
    // Pause playback, never microphone capture, when leaving a workspace section.
    globalThis.document?.querySelectorAll?.('.voiceclean audio').forEach(player => player.pause())
    if (updateHash && globalThis.location?.hash !== '#' + view && globalThis.history?.pushState) {
      globalThis.history.pushState(null, '', '#' + view)
    }
    if (focus) await focusWorkspace()
    if (view === 'history') return loadHistory()
  }
  function syncNavigation() {
    const view = viewFromHash()
    // Traversing hash entries can dispatch both popstate and hashchange.
    if (view !== activeView.value) return navigate(view, { updateHash: false })
  }
  onMounted(() => {
    globalThis.window?.addEventListener?.('hashchange', syncNavigation)
    globalThis.window?.addEventListener?.('popstate', syncNavigation)
  })
  onBeforeUnmount(() => {
    globalThis.window?.removeEventListener?.('hashchange', syncNavigation)
    globalThis.window?.removeEventListener?.('popstate', syncNavigation)
  })

  function scrollToRecorder() { return navigate('recording') }

  const lecturerDeleteCandidate = ref(null)
  const sampleDeleteCandidate = ref(null)
  const lecturerName = ref('')
  const lecturerDepartment = ref('')
  const lecturers = ref([])
  const lecturerOffset = ref(0)
  const lecturerTotal = ref(0)
  const selectedLecturerId = ref('')
  const selectedLecturer = ref(null)
  const selectedSample = ref(null)
  const referenceSamples = ref([])
  const referencesLoaded = ref(false)
  const referenceInitialized = ref(false)
  const sampleOffset = ref(0)
  const sampleTotal = ref(0)
  const referenceLabel = ref('')
  const referenceBusy = ref(false)
  const referenceError = ref('')
  const referenceMessage = ref('')
  const samplePending = ref(false)
  const sampleStarting = ref(false)
  let sampleFilename = ''
  let unmounted = false
  const title = ref('')
  const subject = ref('')
  const notes = ref('')

  const audio = useAudioVersions({ isUnmounted: () => unmounted, onSelect: () => navigate('audio') })
  const { processingRecording, audioVersions, versionsLoading, versionsLoaded,
    audioJobBusy, audioJobStatus, audioJobError, audioJobMessage,
    selectProcessing, runAudioJob, clearAudioContext } = audio


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
  const historySearch = ref('')
  const historyLecturer = ref('')
  const historyStatus = ref('')
  const historyOffset = ref(0)
  const historyTotal = ref(0)
  const historyLoading = ref(false)
  const historyLoaded = ref(false)
  const historyError = ref('')
  const libraryBusy = ref(false)
  const editingRecordingId = ref(null)
  const editTitle = ref('')
  const editDescription = ref('')
  const deleteCandidate = ref(null)
  const lectureSaving = ref(false)
  const lectureMessage = ref('')
  const lectureBlobAvailable = ref(false)
  const savedRecordingId = ref(null)
  const savedOriginalId = ref(null)
  const draftRecordingId = ref(null)
  const lectureLecturerName = ref('')
  let lectureLecturerId = ''
  let lectureRecordedAt = null

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
    if (url?.startsWith('blob:')) URL.revokeObjectURL(url)
  }

  function supportedMime() {
    return [
      'audio/webm;codecs=opus',
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
    if (!selectedLecturerId.value || referenceBusy.value || sampleStarting.value || recording.value || paused.value || busy.value || lectureSaving.value) return
    referenceError.value = ''
    referenceMessage.value = ''
    sampleStarting.value = true
    try {
      const mime = typeof MediaRecorder !== 'undefined'
        ? ['audio/webm;codecs=opus', 'audio/webm'].find(type => MediaRecorder.isTypeSupported(type))
        : ''
      if (!mime) throw new Error('This browser cannot record WebM references. Upload a WAV, MP3, or WebM file instead.')
      sampleStream = await getMicrophone()
      if (unmounted) {
        stopStream(sampleStream)
        return
      }
      sampleChunks = []

      sampleRecorder = new MediaRecorder(sampleStream, { mimeType: mime })

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
          sampleFilename = 'reference.webm'
          selectedSample.value = null
          samplePending.value = true
        }
        stopStream(sampleStream)
        sampleStream = null
        sampleRecording.value = false
      }

      sampleRecorder.onerror = () => {
        referenceError.value = 'Could not record the reference. Try again or upload an audio file.'
        stopStream(sampleStream)
        sampleStream = null
        sampleRecording.value = false
      }
      sampleRecorder.start(1000)
      sampleRecording.value = true
    } catch (e) {
      stopStream(sampleStream)
      sampleStream = null
      referenceError.value = e.message || 'Could not access the microphone.'
    } finally {
      sampleStarting.value = false
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

    if (!/\.(wav|mp3|webm)$/i.test(file.name)) {
      referenceError.value = 'Please select a WAV, MP3, or WebM audio file.'
      event.target.value = ''
      return
    }

    revokeUrl(sampleUrl.value)
    sampleBlob = file
    sampleFilename = file.name
    sampleUrl.value = URL.createObjectURL(file)
    selectedSample.value = null
    samplePending.value = true
    referenceError.value = ''
    referenceMessage.value = ''
    event.target.value = ''
  }

  function resetReference() {
    sampleDeleteCandidate.value = null
    revokeUrl(sampleUrl.value)
    sampleUrl.value = ''
    sampleBlob = null
    samplePending.value = false
    selectedSample.value = null
    referenceLabel.value = ''
  }

  async function referenceAction(action) {
    if (referenceBusy.value) return
    referenceBusy.value = true
    referenceError.value = ''
    referenceMessage.value = ''
    try { await action() }
    catch (e) { referenceError.value = e.message || 'Reference operation failed.' }
    finally { referenceBusy.value = false }
  }

  async function fetchLecturers() {
    const page = await apiRequest(`/api/lecturers?limit=20&offset=${lecturerOffset.value}`)
    lecturers.value = page.items
    lecturerTotal.value = page.total
  }

  function refreshLecturers() {
    return referenceInitialized.value ? referenceAction(fetchLecturers) : initializeReferences()
  }
  function changeLecturerPage(direction) {
    return referenceAction(async () => {
      lecturerOffset.value = Math.max(0, lecturerOffset.value + direction * 20)
      await fetchLecturers()
    })
  }

  async function fetchReferences() {
    if (!selectedLecturerId.value) return
    const owner = selectedLecturerId.value
    referencesLoaded.value = false
    const page = await apiRequest(`/api/lecturers/${owner}/samples?limit=20&offset=${sampleOffset.value}`)
    if (selectedLecturerId.value !== owner) return
    referenceSamples.value = page.items
    sampleTotal.value = page.total
    referencesLoaded.value = true
    if (!samplePending.value && !selectedSample.value && page.items[0]) openReference(page.items[0])
  }

  function selectLecturer() {
    sampleDeleteCandidate.value = null
    lecturerDeleteCandidate.value = null
    resetReference()
    referenceSamples.value = []
    referencesLoaded.value = false
    sampleOffset.value = 0
    sampleTotal.value = 0
    selectedLecturer.value = lecturers.value.find(item => item.id === selectedLecturerId.value) ||
      (selectedLecturer.value?.id === selectedLecturerId.value ? selectedLecturer.value : null)
    lecturerName.value = selectedLecturer.value?.name || ''
    lecturerDepartment.value = selectedLecturer.value?.department || ''
    rememberLecturer(selectedLecturerId.value)
    return referenceAction(fetchReferences)
  }

  function saveLecturer() {
    return referenceAction(async () => {
      const path = selectedLecturerId.value ? `/api/lecturers/${selectedLecturerId.value}` : '/api/lecturers'
      const lecturer = await apiRequest(path, {
        method: selectedLecturerId.value ? 'PATCH' : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: lecturerName.value, department: lecturerDepartment.value || null })
      })
      selectedLecturer.value = lecturer
      selectedLecturerId.value = lecturer.id
      rememberLecturer(lecturer.id)
      lecturerName.value = lecturer.name
      lecturerDepartment.value = lecturer.department || ''
      referenceMessage.value = 'Lecturer saved.'
      await fetchLecturers()
      await fetchReferences()
    })
  }

  function deleteLecturer() {
    if (lecturerDeleteCandidate.value !== selectedLecturerId.value || recording.value || paused.value || busy.value || lectureSaving.value || sampleRecording.value || sampleStarting.value) return
    return referenceAction(async () => {
      await apiRequest(`/api/lecturers/${selectedLecturerId.value}`, { method: 'DELETE' })
      resetReference()
      selectedLecturerId.value = ''
      selectedLecturer.value = null
      rememberLecturer('')
      lecturerName.value = ''
      lecturerDepartment.value = ''
      lecturerDeleteCandidate.value = null
      referenceSamples.value = []
      sampleTotal.value = 0
      referencesLoaded.value = false
      lecturerOffset.value = 0
      await fetchLecturers()
      referenceMessage.value = 'Lecturer deleted.'
    })
  }

  function openReference(sample) {
    resetReference()
    selectedSample.value = sample
    sampleUrl.value = audioUrl(sample.audio_url)
  }

  function saveReference() {
    if (!sampleBlob || !selectedLecturerId.value) return
    return referenceAction(async () => {
      const form = new FormData()
      form.append('file', sampleBlob, sampleFilename)
      if (referenceLabel.value.trim()) form.append('label', referenceLabel.value.trim())
      const saved = await apiRequest(`/api/lecturers/${selectedLecturerId.value}/samples`, { method: 'POST', body: form })
      openReference(saved)
      sampleOffset.value = 0
      referenceMessage.value = 'Reference saved.'
      await fetchReferences()
    })
  }

  function clearSample() {
    sampleDeleteCandidate.value = null
    return referenceAction(async () => {
      if (selectedSample.value) {
        const result = await apiRequest(`/api/lecturers/${selectedLecturerId.value}/samples/${selectedSample.value.id}`, { method: 'DELETE' })
        referenceMessage.value = result.file_cleanup_pending
          ? 'Sample removed. Its audio file still needs local cleanup.' : 'Reference removed.'
      }
      resetReference()
      sampleOffset.value = 0
      await fetchReferences()
    })
  }

  function reloadReferences() { return referenceAction(fetchReferences) }
  function changeSamplePage(direction) {
    return referenceAction(async () => {
      sampleOffset.value = Math.max(0, sampleOffset.value + direction * 20)
      await fetchReferences()
    })
  }

  function initializeReferences() {
    return referenceAction(async () => {
      const context = await loadReferenceContext()
      lecturers.value = context.lecturers.items
      lecturerTotal.value = context.lecturers.total
      selectedLecturer.value = context.lecturer
      selectedLecturerId.value = context.lecturer?.id || ''
      lecturerName.value = context.lecturer?.name || ''
      lecturerDepartment.value = context.lecturer?.department || ''
      rememberLecturer(selectedLecturerId.value)
      referenceSamples.value = context.samples?.items || []
      sampleTotal.value = context.samples?.total || 0
      referencesLoaded.value = true
      referenceInitialized.value = true
      if (referenceSamples.value[0]) openReference(referenceSamples.value[0])
    })
  }

  onMounted(initializeReferences)

  // Lecture recording
  async function startLecture() {
    if (!selectedLecturerId.value || !title.value.trim() || referenceBusy.value || sampleRecording.value || sampleStarting.value || lectureSaving.value || busy.value || recording.value || paused.value) return
    error.value = ''
    lectureMessage.value = ''
    busy.value = true

    try {
      if (typeof MediaRecorder === 'undefined' || !supportedMime()) throw new Error('This browser cannot record WebM lectures. Select a WAV, MP3, or WebM file instead.')
      stopStream(stream)
      stream = await getMicrophone()
      if (unmounted) { stopStream(stream); return }
      lectureChunks = []

      if (savedRecordingId.value || lectureLecturerId !== selectedLecturerId.value) draftRecordingId.value = null
      savedRecordingId.value = null
      lectureLecturerId = selectedLecturerId.value
      lectureLecturerName.value = selectedLecturer.value?.name || ''
      lectureRecordedAt = new Date().toISOString()

      revokeUrl(lectureUrl.value)
      lectureUrl.value = ''
      lectureBlob = null
      lectureBlobAvailable.value = false

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
        lectureRecorder.onstop = null
        if (['recording', 'paused'].includes(lectureRecorder.state)) lectureRecorder.stop()
        stopStream(stream)
        stream = null
        recording.value = false
        paused.value = false
        status.value = 'Error'
        busy.value = false
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
          lectureBlobAvailable.value = lectureBlob.size > 0
          if (!lectureBlob.size) error.value = 'The lecture recording is empty. Record again or select an audio file.'
        } else {
          error.value = 'No audio was captured. Record again or select an audio file.'
        }

        stopStream(stream)
        stream = null
        recording.value = false
        paused.value = false
        busy.value = false
        status.value = lectureBlob?.size ? 'Preview ready' : 'Ready'
      }

      lectureRecorder.start(1000)
      stream.getAudioTracks().forEach(track => {
        track.onended = () => {
          if (lectureRecorder && ['recording', 'paused'].includes(lectureRecorder.state)) {
            error.value = 'Microphone capture ended. Review the captured audio before saving.'
            stopLecture()
          }
        }
      })
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
    if (savedRecordingId.value) {
      const item = history.value.find(item => item.id === savedRecordingId.value)
      const fileId = savedOriginalId.value || item?.original_audio?.id
      if (!fileId) { error.value = 'Refresh Recording History before downloading.'; return }
      const a = document.createElement('a')
      a.href = audioUrl(`/api/recordings/${savedRecordingId.value}/versions/${fileId}/download`)
      a.download = ''
      a.click()
      return
    }
    if (!lectureBlob) return
    const url = URL.createObjectURL(lectureBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = outputName.value || 'voiceclean-lecture.webm'
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  async function saveToHistory() {
    if (!lectureBlob?.size || !lectureLecturerId || !title.value.trim() || lectureSaving.value) return
    lectureSaving.value = true
    lectureMessage.value = ''
    error.value = ''
    status.value = 'Uploading'
    draftRecordingId.value ||= crypto.randomUUID()
    try {
      const saved = await saveRecordingDraft({
        id: draftRecordingId.value, lecturerId: lectureLecturerId,
        title: title.value.trim(), description: recordingDescription(subject.value, notes.value),
        recordedAt: lectureRecordedAt, blob: lectureBlob, filename: outputName.value
      })
      openSavedRecording(saved)
      lectureMessage.value = 'Recording saved. It is available in Recording History after refresh.'
    } catch (e) {
      // A network failure can occur after a successful COMMIT. Reconcile by the
      // stable draft UUID before offering a retry of the same original upload.
      let recovered = null
      try { recovered = await apiRequest(`/api/recordings/${draftRecordingId.value}`) } catch { /* Keep local bytes for retry. */ }
      if (recovered?.status === 'ready' && recovered.original_audio) {
        openSavedRecording(recovered)
        lectureMessage.value = 'Recording saved; its confirmation was recovered from the server.'
      } else {
        error.value = e.message || 'Could not save the lecture. Your local preview is kept for retry.'
        status.value = 'Save failed â€” retry available'
      }
    } finally {
      lectureSaving.value = false
      await loadHistory()
    }
  }

  function openSavedRecording(item) {
    savedOriginalId.value = item.original_audio?.id || null
    title.value = item.title
    const fields = recordingFields(item.description)
    subject.value = fields.subject
    notes.value = fields.notes
    revokeUrl(lectureUrl.value)
    lectureBlob = null
    lectureBlobAvailable.value = false
    lectureUrl.value = item.audio_url ? audioUrl(item.audio_url) : ''
    savedRecordingId.value = item.original_audio ? item.id : null
    draftRecordingId.value = item.id
    lectureLecturerId = item.lecturer_id
    lectureLecturerName.value = item.lecturer.name
    lectureRecordedAt = item.recorded_at
    resetClock()
    elapsed.value = Math.round(Number(item.original_audio?.duration_seconds || 0))
    outputName.value = item.original_audio?.original_filename || item.title
    fileSize.value = sizeLabel(item.original_audio?.file_size_bytes || 0)
    status.value = item.status === 'ready' ? 'Saved' : item.status
  }

  async function restoreHistory(item) {
    historyError.value = ''
    try {
      const fresh = await apiRequest(`/api/recordings/${item.id}`)
      openSavedRecording(fresh)
      selectedLecturerId.value = fresh.lecturer_id
      selectedLecturer.value = fresh.lecturer
      lecturerName.value = fresh.lecturer.name
      lecturerDepartment.value = fresh.lecturer.department || ''
      rememberLecturer(fresh.lecturer_id)
      resetReference()
      referenceSamples.value = []
      sampleOffset.value = 0
      await referenceAction(fetchReferences)
      if (!fresh.original_audio) error.value = 'Select a lecture audio file or record again, then save to finish this recording.'
      else error.value = ''
      await navigate('recording')
    } catch (e) { historyError.value = e.message }
  }

  function sizeLabel(bytes) {
    return bytes < 1048576 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1048576).toFixed(2)} MB`
  }

  function loadLecture(event) {
    const file = event.target.files?.[0]
    if (!file) return
    if (!/\.(wav|mp3|webm)$/i.test(file.name) || !file.size) {
      error.value = 'Choose a nonempty WAV, MP3, or WebM lecture file.'
      event.target.value = ''
      return
    }
    if (savedRecordingId.value || lectureLecturerId !== selectedLecturerId.value) {
      draftRecordingId.value = null
      lectureRecordedAt = null
    }
    savedRecordingId.value = null
    lectureLecturerId = selectedLecturerId.value
    lectureLecturerName.value = selectedLecturer.value?.name || ''
    lectureRecordedAt ||= new Date().toISOString()
    revokeUrl(lectureUrl.value)
    lectureBlob = file
    lectureBlobAvailable.value = true
    lectureUrl.value = URL.createObjectURL(file)
    outputName.value = file.name
    fileSize.value = sizeLabel(file.size)
    if (!title.value.trim()) title.value = file.name.replace(/\.[^.]+$/, '')
    status.value = 'Preview ready'
    error.value = ''
    lectureMessage.value = ''
    event.target.value = ''
  }

  let libraryRequest = 0
  async function loadHistory() {
    const sequence = ++libraryRequest
    historyLoading.value = true
    historyError.value = ''
    try {
      const page = await apiRequest(recordingQuery({ q: historySearch.value, lecturer: historyLecturer.value,
        status: historyStatus.value, offset: historyOffset.value }))
      if (sequence !== libraryRequest || unmounted) return
      history.value = page.items
      historyTotal.value = page.total
      historyLoaded.value = true
    } catch (e) {
      if (sequence === libraryRequest) historyError.value = e.message || 'Could not load saved recordings.'
    } finally { if (sequence === libraryRequest) historyLoading.value = false }
  }

  function searchHistory() { historyOffset.value = 0; return loadHistory() }
  function changeHistoryPage(direction) {
    historyOffset.value = Math.max(0, historyOffset.value + direction * 20)
    return loadHistory()
  }

  function beginRename(item) {
    editingRecordingId.value = item.id
    editTitle.value = item.title
    editDescription.value = item.description || ''
  }

  async function renameRecording(item) {
    libraryBusy.value = true
    historyError.value = ''
    try {
      const edited = await apiRequest(`/api/recordings/${item.id}`, { method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editTitle.value, description: editDescription.value || null }) })
      if (savedRecordingId.value === item.id) openSavedRecording(edited)
      editingRecordingId.value = null
      if (processingRecording.value?.id === item.id) processingRecording.value = edited
      await loadHistory()
    } catch (e) { historyError.value = e.message }
    finally { libraryBusy.value = false }
  }

  async function confirmDeleteRecording(item) {
    libraryBusy.value = true
    historyError.value = ''
    try {
      const result = await apiRequest(`/api/recordings/${item.id}`, { method: 'DELETE' })
      if (savedRecordingId.value === item.id || draftRecordingId.value === item.id) clearLecturePreview()
      deleteCandidate.value = null
      if (processingRecording.value?.id === item.id) {
        clearAudioContext()
      }
      await loadHistory()
      if (result.file_cleanup_pending) historyError.value = 'Recording deleted. An unreferenced audio file still needs local cleanup.'
    } catch (e) { historyError.value = e.message; error.value = e.message }
    finally { libraryBusy.value = false }
  }

  function clearLecturePreview() {
    revokeUrl(lectureUrl.value)
    lectureUrl.value = ''
    lectureBlob = null
    lectureBlobAvailable.value = false
    savedRecordingId.value = null
    draftRecordingId.value = null
    lectureRecordedAt = null
    outputName.value = ''
    fileSize.value = ''
    lectureMessage.value = ''
    error.value = ''
    resetClock()
    status.value = 'Ready'
  }

  function deleteRecording() {
    if (savedRecordingId.value) deleteCandidate.value = savedRecordingId.value
    else clearLecturePreview()
  }

  onMounted(loadHistory)


  onBeforeUnmount(() => {
    unmounted = true
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

  return {
    views, activeView, currentView, captureLocked, activity, lecturerDeleteCandidate,
    sampleDeleteCandidate, lecturerName, lecturerDepartment, lecturers, lecturerOffset, lecturerTotal,
    selectedLecturerId, selectedLecturer, selectedSample, referenceSamples, referencesLoaded, referenceInitialized,
    sampleOffset, sampleTotal, referenceLabel, referenceBusy, referenceError,
    referenceMessage, samplePending, sampleStarting, title, subject,
    notes, recording, paused, busy, sampleRecording, error,
    status, elapsed, sampleUrl, lectureUrl, outputName, fileSize,
    history, historySearch, historyLecturer, historyStatus, historyOffset, historyTotal,
    historyLoading, historyLoaded, historyError, libraryBusy, editingRecordingId, editTitle,
    editDescription, deleteCandidate, lectureSaving, lectureMessage, lectureBlobAvailable, savedRecordingId,
    savedOriginalId, draftRecordingId, lectureLecturerName, time, hint, viewFromHash,
    navigate, focusWorkspace, syncNavigation, scrollToRecorder, startClock, pauseClock, resetClock,
    stopStream, revokeUrl, supportedMime, getMicrophone, startSample, stopSample,
    loadSample, resetReference, referenceAction, fetchLecturers, refreshLecturers, changeLecturerPage,
    fetchReferences, selectLecturer, saveLecturer, deleteLecturer, openReference, saveReference,
    clearSample, reloadReferences, changeSamplePage, initializeReferences, startLecture, pauseLecture,
    resumeLecture, stopLecture, safeFilename, extension, downloadRecording, saveToHistory,
    openSavedRecording, restoreHistory, sizeLabel, loadLecture, loadHistory, searchHistory,
    changeHistoryPage, beginRename, renameRecording, confirmDeleteRecording, clearLecturePreview, deleteRecording,
    processingRecording, audioVersions, versionsLoading, versionsLoaded, audioJobBusy, audioJobStatus,
    audioJobError, audioJobMessage, selectProcessing, runAudioJob, clearAudioContext
  }
}
