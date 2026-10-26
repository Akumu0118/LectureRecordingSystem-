<script setup>
import LecturerSelector from '../shared/LecturerSelector.vue'
import AudioPlayer from '../shared/AudioPlayer.vue'
import ConfirmAction from '../shared/ConfirmAction.vue'
const props = defineProps({ workspace: { type: Object, required: true } })
const w = props.workspace
</script>
<template>
  <div class="recorder-layout studio-layout">
    <section class="card lecture-information" aria-labelledby="lecture-details-heading">
      <p class="eyebrow">
        Before you start
      </p>
      <h2 id="lecture-details-heading">
        Lecture details
      </h2>
      <LecturerSelector
        id="recording-lecturer"
        v-model="w.selectedLecturerId"
        :lecturers="w.lecturers"
        :selected="w.selectedLecturer"
        :disabled="w.captureLocked"
        @select="w.selectLecturer"
        />
      <p class="helper muted">
        Need a lecturer?
        <button class="text-button" @click="w.navigate('references')">
          Register or manage lecturers
        </button>
      </p>
      <div class="field">
        <label for="lecture-title" class="field-label">
          Lecture title
          <span class="required-label">
            (required)
          </span>
        </label>
        <input
          id="lecture-title"
          v-model="w.title"
          maxlength="250"
          placeholder="e.g. Computer Networks - Lecture 3"
          :disabled="w.lectureSaving"
          aria-describedby="recording-requirements"
          />
      </div>
      <p id="recording-requirements" class="muted helper">
        Choose a lecturer and enter a title to start recording.
      </p>
      <details class="optional-details">
        <summary>
          Subject
          &
          notes
          <span class="muted">
            (optional)
          </span>
        </summary>
        <div class="field">
          <label for="lecture-subject" class="field-label">
            Subject
          </label>
          <input
            id="lecture-subject"
            v-model="w.subject"
            maxlength="200"
            placeholder="e.g. Computer Engineering"
            :disabled="w.lectureSaving"
            />
        </div>
        <div class="field">
          <label for="lecture-notes" class="field-label">
            Notes
          </label>
          <textarea
            id="lecture-notes"
            v-model="w.notes"
            maxlength="9000"
            placeholder="Add notes about this lecture"
            rows="4"
            :disabled="w.lectureSaving">
          </textarea>
        </div>
      </details>
      <p v-if="w.referenceBusy" class="feedback notice" role="status">
        Loading lecturer selection...
      </p>
      <p v-if="w.referenceError" class="feedback error" role="alert">
        {{ w.referenceError }}
        <button class="text-button" @click="w.navigate('references')">
          Check lecturers
        </button>
      </p>
    </section>
    <section id="lecture-recorder" class="card recorder-card" :class="{ 'is-recording': w.recording, 'is-paused': w.paused }" aria-labelledby="recorder-heading">
      <div class="section-heading">
        <h2 id="recorder-heading">
          Record lecture
        </h2>
        <span class="badge" :class="w.recording ? 'red' : w.paused ? 'amber' : 'neutral'">
          {{ w.recording ? 'Recording' : w.paused ? 'Paused' : 'Microphone' }}
        </span>
      </div>
      <p class="muted">
        Allow microphone access when your browser requests it.
      </p>
      <div class="studio-stage">
        <p class="eyebrow">Lecture capture / {{ w.selectedLecturer?.name || 'No lecturer selected' }}</p>
        <div class="timer" aria-label="Elapsed recording time">
          {{ w.time }}
        </div>
        <div class="wave" aria-hidden="true">
          <span v-for="n in 36" :key="n" :style="{ '--i': n }" :class="{ moving: w.recording }">
          </span>
        </div>
        <p class="wave-caption">Recording animation &middot; not measured audio levels</p>
        <p class="center muted" role="status">
          {{ w.hint }}
        </p>
        <div class="actions recorder-controls">
          <button
            class="btn primary"
            :disabled="w.captureLocked || !w.selectedLecturerId || !w.title.trim()"
            @click="w.startLecture">
            <span aria-hidden="true">
              &#9679;
            </span>
            {{ w.busy ? 'Connecting...' : 'Start' }}
          </button>
          <button class="btn" :disabled="!w.recording" @click="w.pauseLecture">
            <span aria-hidden="true">
              &#8545;
            </span>
            Pause
          </button>
          <button class="btn" :disabled="!w.paused" @click="w.resumeLecture">
            <span aria-hidden="true">
              &#9654;
            </span>
            Resume
          </button>
          <button class="btn danger" :disabled="!w.recording && !w.paused" @click="w.stopLecture">
            <span aria-hidden="true">
              &#9632;
            </span>
            Stop
          </button>
        </div>
      </div>

      <p v-if="w.error" class="feedback error" role="alert">
        {{ w.error }}
      </p>
    </section>
  </div>
  <section class="card source-alternative" aria-label="Upload an existing lecture">
    <div>
      <p class="eyebrow">Already have a recording?</p>
      <h2>Bring your own audio.</h2>
      <p class="muted">Choose a file to preview and save with these lecture details.</p>
    </div>
    <label class="upload" for="lecture-file">
      <span class="field-label">
        Or choose existing lecture audio
      </span>
      <span class="muted">
        WAV, MP3, or WebM
      </span>
      <input
        id="lecture-file"
        type="file"
        accept=".wav,.mp3,.webm"
        :disabled="w.captureLocked || !w.selectedLecturerId"
        @change="w.loadLecture"
        />
    </label>
  </section>
  <section v-if="w.lectureUrl" class="card recording-output" aria-labelledby="recording-preview-heading">
    <div class="section-heading">
      <div>
        <p class="eyebrow">
          Review your audio
        </p>
        <h2 id="recording-preview-heading">
          Recording preview
        </h2>
      </div>
      <span class="badge" :class="w.savedRecordingId ? 'green' : 'amber'">
        {{ w.savedRecordingId ? 'Saved original' : 'Unsaved preview' }}
      </span>
    </div>
    <h3>
      {{ w.title || w.outputName }}
    </h3>
    <p class="muted">
      {{ w.lectureLecturerName }}
      &middot;
      {{ w.fileSize }}
    </p>
    <AudioPlayer :src="w.lectureUrl" label="Lecture recording preview" />
    <div class="actions">
      <button
        v-if="w.lectureBlobAvailable"
        class="btn primary"
        :disabled="w.lectureSaving || !w.title.trim()"
        @click="w.saveToHistory">
        {{ w.lectureSaving ? 'Uploading lecture...' : 'Save recording' }}
      </button>
      <button
        class="btn"
        :disabled="!w.lectureBlobAvailable && !w.savedRecordingId"
        @click="w.downloadRecording">
        Download {{ w.savedRecordingId ? 'original' : 'preview' }}
      </button>
      <button
        v-if="w.savedRecordingId"
        class="btn"
        :disabled="w.audioJobBusy"
        @click="w.selectProcessing({ id: w.savedRecordingId })">
        Enhancement
        &
        export
      </button>
      <button
        id="delete-preview"
        class="btn text-danger"
        :disabled="w.lectureSaving || w.libraryBusy"
        @click="w.deleteRecording">
        {{ w.savedRecordingId ? 'Delete recording' : 'Discard preview' }}
      </button>
    </div>
    <ConfirmAction
      v-if="w.savedRecordingId && w.deleteCandidate === w.savedRecordingId"
      title="Delete this recording?"
      description="The original and its generated versions will be removed. Other recordings and references are kept."
      :busy="w.libraryBusy"
      return-focus="delete-preview"
      @confirm="w.confirmDeleteRecording({ id: w.savedRecordingId })"
      @cancel="w.deleteCandidate = null"
      />
    <p v-if="w.lectureSaving" class="feedback notice" role="status">
      <span class="spinner" aria-hidden="true">
      </span>
      Uploading and validating your audio. Keep this page open.
    </p>
    <p v-if="w.lectureMessage" class="feedback success" role="status">
      {{ w.lectureMessage }}
    </p>
    <p class="helper muted">
      {{ w.savedRecordingId ? 'Your original is saved. Open Enhancement & export to compare versions or create an MP3.' : 'This preview is local until you select Save recording. Keep it open while saving.' }}
    </p>
  </section>
</template>
