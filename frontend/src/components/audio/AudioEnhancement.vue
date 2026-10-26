<script setup>
import { computed } from 'vue'
import { formatDuration } from '../../utils/formatters.js'
import AudioVersionCard from './AudioVersionCard.vue'
const props = defineProps({ workspace: { type: Object, required: true } })
const w = props.workspace
const availableVersions = computed(() => w.audioVersions.filter(version => version.available))
const comparisonVersions = computed(() => w.audioVersions.filter(version => version.file_role !== 'exported'))
const exportVersions = computed(() => w.audioVersions.filter(version => version.file_role === 'exported'))
function select(event) { if (event.target.value) return w.selectProcessing({ id: event.target.value }) }
</script>
<template>
  <section class="card processing-card audio-lab" aria-labelledby="enhancement-heading">
    <div class="section-heading">
      <div>
        <p class="eyebrow">
          After saving
        </p>
        <h2 id="enhancement-heading">
          Enhance
          &
          export
        </h2>
      </div>
      <button class="btn compact" :disabled="w.audioJobBusy" @click="w.navigate('history')">
        Choose from history
      </button>
    </div>
    <p class="muted">
      Basic speech enhancement reduces rumble and some steady noise, then adjusts loudness. It cannot identify a lecturer or remove overlapping conversations.
    </p>
    <div class="processing-grid" :class="{ 'has-selection': Boolean(w.processingRecording) }">
      <div class="processing-selection">
        <p class="eyebrow">01 / Source recording</p>
        <div class="field">
          <label for="processing-recording" class="field-label">
            Saved recording
          </label>
          <select
            id="processing-recording"
            :value="w.processingRecording?.id || ''"
            :disabled="w.audioJobBusy || w.versionsLoading"
            @change="select">
            <option value="" disabled>
              Select a saved lecture
            </option>
            <option
              v-if="w.processingRecording && !w.history.some(item => item.id === w.processingRecording.id)"
              :value="w.processingRecording.id">
              {{ w.processingRecording.title }}
            </option>
            <option v-for="item in w.history" :key="item.id" :value="item.id">
              {{ item.title }} - {{ item.lecturer.name }}
            </option>
          </select>
          <p class="muted helper">
            This selector uses the current library page. Open history to search or browse all recordings.
          </p>
        </div>
        <div v-if="w.processingRecording" class="lab-source-context"><h3>{{ w.processingRecording.title }}</h3><p>{{ w.processingRecording.lecturer?.name }}</p><div class="source-facts"><span>{{ formatDuration(w.processingRecording.original_audio?.duration_seconds) }}</span><span>{{ w.processingRecording.status }}</span></div><p v-if="w.versionsLoaded" class="source-version-count">{{ availableVersions.length }} available {{ availableVersions.length === 1 ? 'version' : 'versions' }}</p></div>
        <div v-if="!w.processingRecording" class="processing-empty">
          <h3>
            Choose a saved lecture
          </h3>
          <p class="muted">
            Save an original recording, then open it here to compare versions or create an MP3.
          </p>
          <button class="btn" @click="w.navigate('history')">
            Open recording history
          </button>
        </div>
      </div>
      <div v-if="w.processingRecording" class="processing-options">
        <p class="eyebrow">02 / Fixed speech preset</p>
        <div class="preset-description">
          <strong>
            Basic speech enhancement
            <span class="badge neutral">
              Non-AI
            </span>
          </strong>
          <p class="muted">
            Rumble filtering, gentle noise reduction, and loudness adjustment. Saved as a separate WAV; your original stays intact.
          </p>
        </div>
        <div class="actions">
          <button
            class="btn primary"
            :disabled="w.audioJobBusy || w.versionsLoading || w.processingRecording.status !== 'ready'"
            @click="w.runAudioJob(w.processingRecording, 'process')">
            {{ w.audioJobBusy && w.audioJobStatus.includes('Enhancing') ? 'Enhancing...' : 'Enhance audio' }}
          </button>
          <button
            class="btn"
            :disabled="w.audioJobBusy || w.versionsLoading || w.processingRecording.status !== 'ready'"
            @click="w.runAudioJob(w.processingRecording, 'exports')">
            {{ w.audioJobBusy && w.audioJobStatus.includes('Exporting') ? 'Exporting...' : 'Export MP3' }}
          </button>
          <button
            class="btn"
            :disabled="w.audioJobBusy || w.versionsLoading"
            @click="w.selectProcessing(w.processingRecording)">
            Refresh versions
          </button>
        </div>
        <p class="muted helper">
          MP3 exports always use the original audio. Enhanced WAV downloads are available below.
        </p>
      </div>
    </div>
    <p v-if="w.audioJobBusy" class="feedback notice" role="status">
      <span class="spinner" aria-hidden="true">
      </span>
      {{ w.audioJobStatus }} Keep this page open. You may browse other sections.
    </p>
    <p v-if="w.versionsLoading" class="feedback notice" role="status">
      Loading saved audio versions...
    </p>
    <p v-if="w.audioJobError" class="feedback error" role="alert">
      {{ w.audioJobError }}
    </p>
    <p v-if="w.audioJobMessage" class="feedback success" role="status">
      {{ w.audioJobMessage }}
    </p>
  </section>
  <section
    v-if="w.processingRecording"
    class="card audio-comparison"
    aria-labelledby="versions-heading"
    :aria-busy="w.versionsLoading || w.audioJobBusy">
    <div class="section-heading">
      <div>
        <h2 id="versions-heading">
          Compare audio versions
        </h2>
        <p class="muted">
          Play one version at a time, then download the one you need.
        </p>
      </div>
    </div>
    <div
      v-if="w.versionsLoaded && !w.versionsLoading && !w.audioVersions.length && !w.audioJobError"
      class="empty-state">
      <h3>
        No saved audio yet
      </h3>
      <p class="muted">
        Finish uploading the original from Recording History first.
      </p>
      <button class="btn" @click="w.navigate('history')">
        Go to recording history
      </button>
    </div>
    <div class="version-grid">
      <AudioVersionCard
        v-for="version in comparisonVersions"
        :key="version.id"
        :version="version"
        :recording-title="w.processingRecording.title"
        :file-size="w.sizeLabel(version.file_size_bytes)" />
    </div>
    <div v-if="exportVersions.length" class="delivery-versions">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Delivery format</p>
          <h3>MP3 exports</h3>
          <p class="muted">Created from your original. Ready to take with you.</p>
        </div>
      </div>
      <AudioVersionCard
        v-for="version in exportVersions"
        :key="version.id"
        :version="version"
        :recording-title="w.processingRecording.title"
        :file-size="w.sizeLabel(version.file_size_bytes)"
        delivery />
    </div>
    <p class="muted helper">All saved versions reload from the API. Enhancement does not identify or isolate a speaker.</p>
  </section>
</template>
