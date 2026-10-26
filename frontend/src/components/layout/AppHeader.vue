<script setup>
defineProps({ workspace: { type: Object, required: true } })
</script>

<template>
  <header class="topbar" :class="{ 'history-header': workspace.activeView === 'history' }">
    <div class="heading-group">
      <p v-if="workspace.activeView !== 'history'" class="eyebrow">
        Your workspace
      </p>
      <h1 id="workspace-title" tabindex="-1">
        {{ workspace.currentView.title }}
      </h1>
      <p class="muted">
        {{ workspace.currentView.description }}
      </p>
    </div>
    <div class="header-status">
      <button v-if="workspace.activeView === 'history'" class="btn primary" @click="workspace.navigate('recording')">Record a lecture</button>
      <span
        v-if="workspace.activeView !== 'history' || workspace.captureLocked || workspace.audioJobBusy"
        class="badge"
        :class="workspace.recording || workspace.sampleRecording ? 'red' : workspace.paused ? 'amber' : 'green'"
        role="status">
        <span class="status-dot" aria-hidden="true">
        </span>
        {{ workspace.activity }}
      </span>
      <button
        v-if="workspace.recording || workspace.paused || workspace.sampleRecording || workspace.sampleStarting"
        class="text-button"
        @click="workspace.navigate(workspace.sampleRecording || workspace.sampleStarting ? 'references' : 'recording')">
        Return to capture
      </button>
    </div>
  </header>
</template>
