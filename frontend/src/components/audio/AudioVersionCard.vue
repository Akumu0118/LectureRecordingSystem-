<script setup>
import { audioUrl } from '../../services/api.js'
import { formatDuration } from '../../utils/formatters.js'
import AudioPlayer from '../shared/AudioPlayer.vue'
defineProps({
  version: { type: Object, required: true },
  recordingTitle: { type: String, required: true },
  fileSize: { type: String, required: true },
  delivery: { type: Boolean, default: false }
})
function versionTitle(role) {
  return role === 'processed' ? 'Enhanced audio' : role === 'exported' ? 'Exported MP3' : 'Original audio'
}
</script>
<template>
  <article class="version-card" :class="{ 'delivery-version': delivery }">
    <div class="section-heading">
      <h3>
        {{ versionTitle(version.file_role) }}
      </h3>
      <span class="badge" :class="version.file_role === 'original' ? 'neutral' : 'green'">
        {{ version.file_role === 'processed' ? 'WAV' : version.file_role === 'exported' ? 'MP3' : 'Original' }}
      </span>
    </div>
    <p class="muted">
      {{ formatDuration(version.duration_seconds) }}
      &middot;
      {{ fileSize }}
      &middot;
      {{ version.mime_type }}
    </p>
    <template v-if="version.available">
      <AudioPlayer
        :src="audioUrl(version.audio_url)"
        :label="versionTitle(version.file_role) + ' for ' + recordingTitle"
        />
      <a
        class="btn download-button"
        :href="audioUrl(version.download_url)"
        :download="version.original_filename || ''">
        Download {{ version.file_role === 'exported' ? 'MP3' : version.file_role === 'processed' ? 'enhanced WAV' : 'original' }}
      </a>
    </template>
    <p v-else class="feedback error">
      File unavailable. Regenerate a generated version; recover missing originals from backup or explicitly recreate the recording.
    </p>
  </article>
</template>
