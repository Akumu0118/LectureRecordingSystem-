<script setup>
import LecturerManager from '../lecturers/LecturerManager.vue'
import AudioPlayer from '../shared/AudioPlayer.vue'
import ListPagination from '../shared/ListPagination.vue'
import ConfirmAction from '../shared/ConfirmAction.vue'
const props = defineProps({ workspace: { type: Object, required: true } })
const w = props.workspace
</script>
<template>
  <div class="reference-workspace">
    <div v-if="w.referenceBusy || w.referenceMessage || w.referenceError" class="workspace-feedback">
      <p v-if="w.referenceBusy" class="feedback notice" role="status">
        Working on your lecturer or reference...
      </p>
      <p v-if="w.referenceMessage" class="feedback success" role="status">
        {{ w.referenceMessage }}
      </p>
      <p v-if="w.referenceError" class="feedback error" role="alert">
        {{ w.referenceError }}
      </p>
    </div>
    <div class="split-layout management-layout">
      <LecturerManager :workspace="w" />
      <div class="panel-stack">
        <section class="card reference-capture" aria-labelledby="reference-heading">
          <div class="section-heading">
            <div>
              <p class="eyebrow">
                Step 2
              </p>
              <h2 id="reference-heading">
                Reference voice
              </h2>
            </div>
            <span v-if="w.sampleRecording" class="badge red" role="status">
              <span class="status-dot" aria-hidden="true">
              </span>
              Recording
            </span>
          </div>
          <p class="muted">
            Record a short sample or upload WAV, MP3, or WebM. Saving a reference does not enable speaker isolation.
          </p>
          <p v-if="!w.selectedLecturerId" class="empty-state">
            Select or register a lecturer to add a reference.
          </p>
          <template v-else>
            <p class="context-label">
              For
              <strong>
                {{ w.selectedLecturer?.name }}
              </strong>
            </p>
            <div class="reference-station" :class="{ 'is-recording': w.sampleRecording }">
              <div class="reference-station-heading"><span class="status-dot" aria-hidden="true"></span><strong>{{ w.sampleRecording ? 'Recording reference' : 'Reference recorder' }}</strong><span class="muted">Microphone capture</span></div>
            <div class="actions">
              <button class="btn primary" :disabled="w.captureLocked" @click="w.startSample">
                <span aria-hidden="true">
                  &#9679;
                </span>
                {{ w.sampleStarting ? 'Requesting microphone...' : 'Record sample' }}
              </button>
              <button class="btn danger" :disabled="!w.sampleRecording" @click="w.stopSample">
                <span aria-hidden="true">
                  &#9632;
                </span>
                Stop sample
              </button>
            </div>
            </div>
            <label class="upload" for="reference-file">
              <span class="field-label">
                Or upload reference audio
              </span>
              <span class="muted">
                WAV, MP3, or WebM
              </span>
              <input
                id="reference-file"
                type="file"
                accept=".wav,.mp3,.webm,audio/wav,audio/mpeg,audio/webm"
                :disabled="w.captureLocked"
                @change="w.loadSample"
                />
            </label>
            <div v-if="w.sampleUrl" class="preview-panel">
              <div class="section-heading">
                <h3>
                  {{ w.samplePending ? 'Unsaved reference preview' : 'Saved reference preview' }}
                </h3>
                <span class="badge" :class="w.samplePending ? 'amber' : 'green'">
                  {{ w.samplePending ? 'Unsaved' : 'Saved' }}
                </span>
              </div>
              <AudioPlayer
                :src="w.sampleUrl"
                label="Reference voice preview"
                :duration="w.selectedSample?.audio_file.duration_seconds"
                />
              <div v-if="w.samplePending" class="field">
                <label class="field-label" for="reference-label">
                  Sample label
                  <span class="muted">
                    (optional)
                  </span>
                </label>
                <input
                  id="reference-label"
                  v-model="w.referenceLabel"
                  maxlength="200"
                  placeholder="e.g. Classroom reference"
                  :disabled="w.referenceBusy"
                  />
              </div>
              <div class="actions">
                <button
                  v-if="w.samplePending"
                  class="btn primary"
                  :disabled="w.captureLocked"
                  @click="w.saveReference">
                  {{ w.referenceBusy ? 'Saving...' : 'Save reference' }}
                </button>
                <button
                  id="remove-reference"
                  class="btn text-danger"
                  :disabled="w.captureLocked"
                  @click="w.selectedSample ? w.sampleDeleteCandidate = w.selectedSample.id : w.clearSample()">
                  {{ w.samplePending ? 'Discard preview' : 'Delete reference' }}
                </button>
              </div>
              <ConfirmAction
                v-if="w.selectedSample && w.sampleDeleteCandidate === w.selectedSample.id"
                title="Delete this reference?"
                description="The saved reference and its audio will be removed. Other samples are kept."
                confirm-label="Delete reference"
                :busy="w.referenceBusy"
                return-focus="remove-reference"
                @confirm="w.clearSample"
                @cancel="w.sampleDeleteCandidate = null"
                />
            </div>
          </template>
        </section>
        <section class="card reference-saved" aria-labelledby="saved-references-heading">
          <div class="section-heading">
            <h2 id="saved-references-heading">
              Saved references
              <span class="count-label">
                {{ w.sampleTotal }}
              </span>
            </h2>
            <button
              class="btn compact"
              :disabled="w.captureLocked || !w.selectedLecturerId"
              @click="w.reloadReferences">
              Refresh
            </button>
          </div>
          <p v-if="w.referenceBusy && !w.referencesLoaded" class="feedback notice" role="status">
            Loading saved references...
          </p>
          <div v-else-if="!w.selectedLecturerId" class="empty-state">
            <h3>
              Choose a lecturer
            </h3>
            <p class="muted">
              Their saved reference samples will appear here.
            </p>
          </div>
          <div
            v-else-if="w.referencesLoaded && !w.referenceError && !w.referenceSamples.length"
            class="empty-state">
            <h3>
              No reference samples yet
            </h3>
            <p class="muted">
              Record or upload a sample, preview it, then select Save reference.
            </p>
          </div>
          <ul v-else class="reference-list">
            <li
              v-for="sample in w.referenceSamples"
              :key="sample.id"
              class="reference-item"
              :class="{ selected: w.selectedSample?.id === sample.id }">
              <div>
                <h3>
                  {{ sample.label || sample.audio_file.original_filename || 'Reference sample' }}
                </h3>
                <p class="muted">
                  {{ sample.audio_file.duration_seconds }} seconds
                  <span v-if="w.selectedSample?.id === sample.id">
                    &middot;
                    In preview
                  </span>
                </p>
              </div>
              <button class="btn compact" :disabled="w.captureLocked" @click="w.openReference(sample)">
                Preview
                <span class="sr-only">
                  {{ sample.label || 'reference sample' }}
                </span>
              </button>
            </li>
          </ul>
          <ListPagination
            v-if="w.selectedLecturerId"
            :offset="w.sampleOffset"
            :total="w.sampleTotal"
            :count="w.referenceSamples.length"
            :busy="w.captureLocked"
            label="samples"
            @change="w.changeSamplePage"
            />
        </section>
      </div>
    </div>
  </div>
</template>
