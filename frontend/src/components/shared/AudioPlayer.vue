<script setup>
import { ref, watch } from 'vue'
const props = defineProps({ src: { type: String, required: true }, label: { type: String, default: 'Audio preview' }, duration: { type: [String, Number], default: null } })
const loading = ref(Boolean(props.src))
const error = ref('')
watch(() => props.src, () => { loading.value = true; error.value = '' })
function failed() { loading.value = false; error.value = 'Audio is unavailable. Refresh the saved list and try again.' }
function pauseOthers(event) {
  event.target.closest('.voiceclean')?.querySelectorAll('audio').forEach(player => { if (player !== event.target) player.pause() })
}
</script>
<template>
  <div class="audio-player" :aria-busy="loading">
    <audio
      :src="src"
      :aria-label="label"
      controls
      preload="metadata"
      @loadstart="loading = true; error = ''"
      @loadedmetadata="loading = false"
      @canplay="loading = false"
      @waiting="loading = true"
      @error="failed"
      @play="loading = false; pauseOthers($event)">
    </audio>
    <p v-if="error" class="feedback error" role="alert">
      {{ error }}
    </p>
    <p v-else-if="loading" class="muted audio-status" role="status">
      Loading audio...
    </p>
    <p v-else-if="duration" class="muted audio-status">
      {{ duration }} seconds
    </p>
  </div>
</template>
