<script setup>
import { nextTick, onMounted, onBeforeUnmount } from 'vue'
import { audioUrl } from '../../services/api.js'
import { formatDate, formatDuration } from '../../utils/formatters.js'
import ListPagination from '../shared/ListPagination.vue'
import ConfirmAction from '../shared/ConfirmAction.vue'
import { useRecordingOpen } from '../../composables/useRecordingOpen.js'
const props = defineProps({ workspace: { type: Object, required: true } })
const w = props.workspace
const { pendingOpen, openRecording, confirmOpen } = useRecordingOpen(w)
function closeActions(event) {
  const menu = event.currentTarget.closest('details')
  menu.open = false
  menu.querySelector('summary')?.focus()
}
function leaveActions(event) {
  if (event.relatedTarget && !event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false
}
function dismissActions(event) {
  globalThis.document?.querySelectorAll('.audio-library .recording-more[open]').forEach(menu => {
    if (!menu.contains(event.target)) menu.open = false
  })
}
onMounted(() => globalThis.document?.addEventListener('pointerdown', dismissActions))
onBeforeUnmount(() => globalThis.document?.removeEventListener('pointerdown', dismissActions))
async function edit(item) {
  w.beginRename(item)
  await nextTick()
  document.getElementById('edit-title-' + item.id)?.focus()
}
async function finishEdit(item, save = false) {
  if (save) await w.renameRecording(item)
  else w.editingRecordingId = null
  if (!w.editingRecordingId) {
    await nextTick()
    document.getElementById('history-actions-' + item.id)?.focus()
  }
}
</script>
<template>
  <section class="card audio-library" aria-labelledby="library-heading" :aria-busy="w.historyLoading">
    <form class="library-filters" @submit.prevent="w.searchHistory">
      <div class="field search-field">
        <label for="history-search" class="sr-only">
          Search recordings
        </label>
        <input
          id="history-search"
          v-model="w.historySearch"
          maxlength="200"
          placeholder="Search lectures..."
          type="search"
          />
      </div>
      <div class="field">
        <label for="history-lecturer" class="sr-only">
          Lecturer
        </label>
        <select id="history-lecturer" v-model="w.historyLecturer">
          <option value="">
            All lecturers
          </option>
          <option
            v-if="w.selectedLecturer && !w.lecturers.some(item => item.id === w.selectedLecturer.id)"
            :value="w.selectedLecturer.id">
            {{ w.selectedLecturer.name }}
          </option>
          <option v-for="lecturer in w.lecturers" :key="lecturer.id" :value="lecturer.id">
            {{ lecturer.name }}
          </option>
        </select>
      </div>
      <div class="field">
        <label for="history-status" class="sr-only">
          Status
        </label>
        <select id="history-status" v-model="w.historyStatus">
          <option value="">
            All statuses
          </option>
          <option v-for="state in ['pending', 'uploading', 'ready', 'failed']" :key="state" :value="state">
            {{ state }}
          </option>
        </select>
      </div>
      <button class="btn" type="submit" :disabled="w.historyLoading">
        {{ w.historyLoading ? 'Loading...' : 'Search' }}
      </button>
    </form>
    <p v-if="w.historyLoading" class="feedback notice" role="status">
      <span class="spinner" aria-hidden="true">
      </span>
      Loading saved recordings...
    </p>
    <p v-if="w.historyError" class="feedback error" role="alert">
      {{ w.historyError }}
    </p>
    <div
      v-if="w.historyLoaded && !w.historyLoading && !w.historyError && !w.history.length"
      class="empty-state">
      <h3>
        {{ w.historySearch || w.historyLecturer || w.historyStatus ? 'No matching recordings' : 'Your recording library starts here' }}
      </h3>
      <p class="muted">
        {{ w.historySearch || w.historyLecturer || w.historyStatus ? 'Try a different search or filter, then refresh.' : 'Record or upload a lecture, preview it, and save it to see it here.' }}
      </p>
      <button class="btn" @click="w.navigate('recording')">
        Go to recording
      </button>
    </div>
    <ConfirmAction v-if="pendingOpen" title="Replace your unsaved preview?"
      description="Opening this saved lecture replaces the local lecture and reference previews. Save them first if you want to keep them."
      confirm-label="Open saved lecture" busy-label="Please wait..." :busy="w.captureLocked"
      :return-focus="'history-open-' + pendingOpen.id" @confirm="confirmOpen" @cancel="pendingOpen = null" />
    <div class="library-results"><h2 id="library-heading">{{ w.historyLoaded ? w.historyTotal : '-' }} {{ w.historyTotal === 1 ? 'recording' : 'recordings' }}</h2><span class="muted">Newest first</span></div>
    <div v-if="w.history.length" class="library-columns" aria-hidden="true"><span>Lecture</span><span>Recorded</span><span>Duration</span><span>Status</span><span class="column-actions">Actions</span></div>
    <ul class="recording-list">
      <li v-for="item in w.history" :key="item.id" class="recording-item" :class="{ 'is-selected': w.savedRecordingId === item.id }">
        <div class="recording-summary">
          <h3>{{ item.title }}</h3>
          <p class="muted recording-owner">{{ item.lecturer.name }}</p>
          <span v-if="w.savedRecordingId === item.id" class="opened-label">Open in workspace</span>
        </div>
        <time class="library-date" :datetime="item.recorded_at || item.created_at">{{ formatDate(item.recorded_at || item.created_at) }}</time>
        <span class="library-duration">{{ formatDuration(item.original_audio?.duration_seconds) }}</span>
        <span class="badge library-status" :class="item.status === 'ready' ? 'green' : item.status === 'failed' ? 'red' : 'amber'">{{ item.status }}</span>
        <div class="recording-actions">
          <div class="actions">
            <button :id="'history-open-' + item.id" class="btn compact library-play" :disabled="w.captureLocked" @click="openRecording(item)">
              {{ item.status === 'ready' ? 'Play' : 'Complete' }}
              <span class="sr-only">
                : {{ item.title }}
              </span>
            </button>
          </div>
          <details class="recording-more" @keydown.esc.stop.prevent="closeActions" @focusout="leaveActions">
            <summary :id="'history-actions-' + item.id">
              More actions
              <span class="sr-only">
                for {{ item.title }}
              </span>
            </summary>
            <div class="secondary-actions" @click="closeActions">
              <button
                class="btn compact"
                :disabled="w.audioJobBusy || item.status !== 'ready'"
                @click="w.runAudioJob(item, 'process')">
                Enhance
              </button>
              <button
                class="btn compact"
                :disabled="w.audioJobBusy || item.status !== 'ready'"
                @click="w.runAudioJob(item, 'exports')">
                Export MP3
              </button>

              <button class="btn compact" :disabled="w.audioJobBusy" @click="w.selectProcessing(item)">
                Audio versions
              </button>
              <a
                v-if="item.original_audio"
                class="btn compact"
                :href="audioUrl(`/api/recordings/${item.id}/versions/${item.original_audio.id}/download`)"
                download>
                Download original
              </a>
              <button
                :id="'edit-history-' + item.id"
                class="btn compact"
                :disabled="w.libraryBusy"
                @click="edit(item)">
                Rename / edit
              </button>
              <button
                :id="'delete-history-' + item.id"
                class="btn text-danger compact"
                :disabled="w.libraryBusy"
                @click="w.deleteCandidate = item.id">
                Delete recording
              </button>
            </div>
          </details>
        </div>
        <form
          v-if="w.editingRecordingId === item.id"
          class="inset-form"
          @submit.prevent="finishEdit(item, true)">
          <h3>
            Edit recording
          </h3>
          <div class="field">
            <label :for="'edit-title-' + item.id" class="field-label">
              Title
            </label>
            <input
              :id="'edit-title-' + item.id"
              v-model="w.editTitle"
              required
              maxlength="250"
              :disabled="w.libraryBusy"
              />
          </div>
          <div class="field">
            <label :for="'edit-description-' + item.id" class="field-label">
              Description
            </label>
            <textarea
              :id="'edit-description-' + item.id"
              v-model="w.editDescription"
              maxlength="10000"
              rows="3"
              :disabled="w.libraryBusy">
            </textarea>
          </div>
          <div class="actions">
            <button class="btn primary" type="submit" :disabled="w.libraryBusy || !w.editTitle.trim()">
              {{ w.libraryBusy ? 'Saving...' : 'Save changes' }}
            </button>
            <button class="btn" type="button" :disabled="w.libraryBusy" @click="finishEdit(item)">
              Cancel
            </button>
          </div>
        </form>
        <ConfirmAction
          v-if="w.deleteCandidate === item.id"
          title="Delete this recording?"
          :description="`Remove ${item.title}, its original, and generated versions? Other recordings and references are kept.`"
          :busy="w.libraryBusy"
          :return-focus="'history-actions-' + item.id"
          @confirm="w.confirmDeleteRecording(item)"
          @cancel="w.deleteCandidate = null"
          />
      </li>
    </ul>
    <ListPagination
      v-if="w.historyTotal > 20 || w.historyOffset > 0"
      :offset="w.historyOffset"
      :total="w.historyTotal"
      :count="w.history.length"
      :busy="w.historyLoading"
      label="recordings"
      @change="w.changeHistoryPage"
      />
  </section>
</template>
