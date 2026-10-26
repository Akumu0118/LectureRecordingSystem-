import { ref } from 'vue'

// Presentation guard shared by the overview and library. Capture and API logic
// remain in the workspace controller.
export function useRecordingOpen(workspace) {
  const pendingOpen = ref(null)
  function openRecording(item) {
    if (workspace.captureLocked) return
    if ((workspace.lectureBlobAvailable && !workspace.savedRecordingId) || workspace.samplePending) {
      pendingOpen.value = item
      return
    }
    return workspace.restoreHistory(item)
  }
  function confirmOpen() {
    if (workspace.captureLocked || !pendingOpen.value) return
    const item = pendingOpen.value
    pendingOpen.value = null
    return workspace.restoreHistory(item)
  }
  return { pendingOpen, openRecording, confirmOpen }
}
