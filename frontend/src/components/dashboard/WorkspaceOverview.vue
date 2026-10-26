<script setup>
import { computed } from 'vue'
import RecentRecordings from './RecentRecordings.vue'
const props = defineProps({ workspace: { type: Object, required: true } })
const filtered = computed(() => Boolean(props.workspace.historySearch || props.workspace.historyLecturer || props.workspace.historyStatus))
</script>

<template>
  <section class="overview-workspace" aria-label="Workspace overview">
    <div class="overview-bento">
      <section class="workspace-welcome" aria-labelledby="welcome-heading">
        <div>
          <p class="eyebrow">VoiceClean / Audio workspace</p>
          <h2 id="welcome-heading">A clearer space<br>for every lecture.</h2>
          <p>Capture your lecture. Keep the original. Review, enhance, and take it with you.</p>
        </div>
        <div class="welcome-footer">
          <button class="btn primary" @click="workspace.navigate('recording')">Start recording <span aria-hidden="true">&rarr;</span></button>
          <span>{{ workspace.selectedLecturer ? 'Working with ' + workspace.selectedLecturer.name : 'Select a lecturer to begin' }}</span>
        </div>
      </section>
      <div class="workspace-numbers" aria-label="Saved workspace counts">
        <button class="metric-cell" @click="workspace.navigate('references')">
          <span class="eyebrow">Registered lecturers</span>
          <strong>{{ workspace.referenceInitialized ? workspace.lecturerTotal : '—' }}</strong>
          <span class="metric-link">Manage profiles <span aria-hidden="true">&nearr;</span></span>
        </button>
        <button class="metric-cell" @click="workspace.navigate('history')">
          <span class="eyebrow">{{ filtered ? 'Library matches' : 'Saved recordings' }}</span>
          <strong>{{ workspace.historyLoaded ? workspace.historyTotal : '—' }}</strong>
          <span class="metric-link">{{ filtered ? 'Current filters applied' : 'Explore your library' }} <span aria-hidden="true">&nearr;</span></span>
        </button>
      </div>
      <article class="lecturer-context" aria-labelledby="context-heading">
        <div class="context-monogram" aria-hidden="true">{{ workspace.selectedLecturer?.name?.trim().charAt(0) || '—' }}</div>
        <div class="context-details"><p class="eyebrow">Current lecturer</p><h2 id="context-heading">{{ workspace.selectedLecturer?.name || 'Your workspace starts here' }}</h2><p class="muted">{{ workspace.selectedLecturer?.department || (workspace.selectedLecturer ? 'No department specified' : 'Register or choose a lecturer to organize your audio.') }}</p></div>
        <div class="context-reference"><strong>{{ workspace.referencesLoaded && workspace.selectedLecturer ? workspace.sampleTotal : '—' }}</strong><span class="muted">saved references</span></div>
        <button class="btn compact" @click="workspace.navigate('references')">{{ workspace.selectedLecturer ? 'View references' : 'Set up lecturer' }}</button>
      </article>
      <RecentRecordings :workspace="workspace" />
      <section class="workflow-rail" aria-labelledby="workflow-heading">
        <p class="eyebrow">Your next step</p><h2 id="workflow-heading">From classroom<br>to your library.</h2>
        <ol>
          <li><span>01</span><div><button class="text-button" @click="workspace.navigate('references')">Set up a lecturer</button><p class="muted">Keep your lectures organized.</p></div></li>
          <li><span>02</span><div><button class="text-button" @click="workspace.navigate('references')">Save a reference</button><p class="muted">Record or upload a short sample.</p></div></li>
          <li><span>03</span><div><button class="text-button" @click="workspace.navigate('recording')">Capture a lecture</button><p class="muted">Record, review, and save.</p></div></li>
          <li><span>04</span><div><button class="text-button" @click="workspace.navigate('audio')">Enhance &amp; export</button><p class="muted">Compare versions. Download MP3.</p></div></li>
        </ol>
        <p class="workflow-footnote muted">Non-AI enhancement. Reference samples do not enable speaker isolation.</p>
      </section>
    </div>
    <p v-if="workspace.referenceBusy || workspace.historyLoading" class="feedback notice" role="status">Loading saved workspace data...</p>
    <div v-if="workspace.referenceError" class="workspace-feedback">
      <p class="feedback error" role="alert">{{ workspace.referenceError }}</p>
      <button class="btn compact" :disabled="workspace.referenceBusy" @click="workspace.initializeReferences">Retry lecturer loading</button>
    </div>
  </section>
</template>
