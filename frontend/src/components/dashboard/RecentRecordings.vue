<script setup>
import { computed } from 'vue'
import { formatDate, formatDuration } from '../../utils/formatters.js'
import { useRecordingOpen } from '../../composables/useRecordingOpen.js'
import ConfirmAction from '../shared/ConfirmAction.vue'
const props = defineProps({ workspace: { type: Object, required: true } })
const { pendingOpen, openRecording, confirmOpen } = useRecordingOpen(props.workspace)
const recent = computed(() => !props.workspace.historyOffset && !props.workspace.historySearch && !props.workspace.historyLecturer && !props.workspace.historyStatus)
</script>
<template>
  <section class="recent-recordings" aria-labelledby="recent-recordings-heading" :aria-busy="workspace.historyLoading">
    <div class="section-heading"><div><p class="eyebrow">Pick up where you left off</p><h2 id="recent-recordings-heading">{{ recent ? 'Recent recordings' : 'Library preview' }}</h2></div><button class="text-button" @click="workspace.navigate('history')">View library <span aria-hidden="true">&rarr;</span></button></div>
    <p v-if="!recent" class="muted helper">Showing your current library page and filters.</p>
    <p v-if="workspace.historyLoading" class="feedback notice" role="status">Loading recordings...</p>
    <div v-else-if="workspace.historyError"><p class="feedback error" role="alert">{{ workspace.historyError }}</p><button class="btn compact" @click="workspace.loadHistory">Retry library loading</button></div>
    <div v-else-if="!workspace.historyLoaded" class="empty-state"><p class="muted">Your library has not loaded yet.</p><button class="btn" @click="workspace.loadHistory">Load recordings</button></div>
    <div v-else-if="!workspace.history.length" class="empty-state"><h3>{{ recent ? 'Make room for your first lecture.' : 'No recordings match this view.' }}</h3><p class="muted">{{ recent ? 'Record or upload audio, then save it to your library.' : 'Open the library to adjust your filters.' }}</p><button class="btn" @click="workspace.navigate(recent ? 'recording' : 'history')">{{ recent ? 'Record a lecture' : 'Open library' }}</button></div>
    <ul v-else class="recent-list">
      <li v-for="item in workspace.history.slice(0, 4)" :key="item.id">
        <div class="recent-audio-mark" aria-hidden="true">&#9835;</div>
        <div class="recent-title"><h3>{{ item.title }}</h3><p class="muted">{{ item.lecturer.name }}</p><p class="muted recent-date">{{ formatDate(item.recorded_at || item.created_at) }}</p></div>
        <span class="recent-duration">{{ formatDuration(item.original_audio?.duration_seconds) }}</span>
        <button :id="'recent-open-' + item.id" class="btn compact" :aria-label="'Open ' + item.title" :disabled="workspace.captureLocked" @click="openRecording(item)">Open</button>
      </li>
    </ul>
    <ConfirmAction v-if="pendingOpen" title="Replace your unsaved preview?"
      description="Opening this saved lecture replaces the local lecture and reference previews. Save them first if you want to keep them."
      confirm-label="Open saved lecture" busy-label="Please wait..." :busy="workspace.captureLocked"
      :return-focus="'recent-open-' + pendingOpen.id" @confirm="confirmOpen" @cancel="pendingOpen = null" />
  </section>
</template>
