<script>
import { reactive } from 'vue'
import { useVoiceClean } from '../composables/useVoiceClean.js'
import AppTopNav from './layout/AppTopNav.vue'
import AppHeader from './layout/AppHeader.vue'
import WorkspaceOverview from './dashboard/WorkspaceOverview.vue'
import ReferencePanel from './references/ReferencePanel.vue'
import LectureRecorder from './recordings/LectureRecorder.vue'
import RecordingLibrary from './recordings/RecordingLibrary.vue'
import AudioEnhancement from './audio/AudioEnhancement.vue'

export default {
  components: { AppTopNav, AppHeader, WorkspaceOverview, ReferencePanel, LectureRecorder, RecordingLibrary, AudioEnhancement },
  setup() {
    const session = useVoiceClean()
    return { ...session, workspace: reactive(session) }
  }
}
</script>

<template>
  <div class="voiceclean app">
    <a class="skip-link" href="#workspace-title" @click.prevent="workspace.focusWorkspace">
      Skip to workspace
    </a>
    <AppTopNav :active-view="workspace.activeView" @navigate="workspace.navigate" />
    <main id="workspace-panel" class="main">
      <AppHeader :workspace="workspace" />
      <!-- Keep panels mounted: navigation never destroys an active recorder. -->
      <div v-show="workspace.activeView === 'overview'">
        <WorkspaceOverview :workspace="workspace" />
      </div>
      <div v-show="workspace.activeView === 'references'">
        <ReferencePanel :workspace="workspace" />
      </div>
      <div v-show="workspace.activeView === 'recording'">
        <LectureRecorder :workspace="workspace" />
      </div>
      <div v-show="workspace.activeView === 'history'">
        <RecordingLibrary :workspace="workspace" />
      </div>
      <div v-show="workspace.activeView === 'audio'">
        <AudioEnhancement :workspace="workspace" />
      </div>
      <p class="footer">
        VoiceClean
        &middot;
        Record responsibly and obtain permission before recording.
      </p>
    </main>
  </div>
</template>
