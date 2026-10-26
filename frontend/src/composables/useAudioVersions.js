import { ref } from 'vue'
import { apiRequest } from '../services/api.js'
import { fetchVersions, generateAudio } from '../services/audioVersions.js'

export function useAudioVersions({ isUnmounted = () => false, onSelect = () => {} } = {}) {
  const processingRecording = ref(null)
  const audioVersions = ref([])
  const versionsLoading = ref(false)
  const versionsLoaded = ref(false)
  const audioJobBusy = ref(false)
  const audioJobStatus = ref('')
  const audioJobError = ref('')
  const audioJobMessage = ref('')
  let versionsRequest = 0

  async function selectProcessing(item) {
    if (audioJobBusy.value) return false
    const sequence = ++versionsRequest
    onSelect()
    processingRecording.value = { ...item }
    audioVersions.value = []
    versionsLoaded.value = false
    versionsLoading.value = true
    audioJobError.value = ''
    audioJobMessage.value = ''
    try {
      const [fresh, versions] = await Promise.all([
        apiRequest(`/api/recordings/${item.id}`), fetchVersions(item.id)
      ])
      if (sequence !== versionsRequest || isUnmounted()) return false
      processingRecording.value = fresh
      audioVersions.value = versions.items
      versionsLoaded.value = true
      return true
    } catch (e) {
      if (sequence === versionsRequest) audioJobError.value = e.message
      return false
    } finally { if (sequence === versionsRequest) versionsLoading.value = false }
  }

  async function runAudioJob(item, action) {
    if (audioJobBusy.value) return
    if (!await selectProcessing(item)) return
    // A later selection supersedes an earlier async load.
    if (processingRecording.value?.id !== item.id) return
    audioJobBusy.value = true
    audioJobStatus.value = action === 'exports' ? 'Exporting MP3...' : 'Enhancing audio...'
    audioJobError.value = ''
    audioJobMessage.value = ''
    try {
      await generateAudio(item.id, action)
      audioVersions.value = (await fetchVersions(item.id)).items
      versionsLoaded.value = true
      audioJobMessage.value = action === 'exports' ? 'MP3 ready. Use Download MP3 below.' : 'Enhanced audio ready for preview and download.'
    } catch (e) {
      audioJobError.value = e.message + ' Refresh versions before retrying; a completed output may already be saved.'
    } finally { audioJobBusy.value = false; audioJobStatus.value = '' }
  }

  function clearAudioContext() {
    ++versionsRequest
    processingRecording.value = null
    audioVersions.value = []
    versionsLoaded.value = false
    versionsLoading.value = false
    audioJobMessage.value = ''
    audioJobError.value = ''
  }
  return { processingRecording, audioVersions, versionsLoading, versionsLoaded,
    audioJobBusy, audioJobStatus, audioJobError, audioJobMessage,
    selectProcessing, runAudioJob, clearAudioContext }
}
