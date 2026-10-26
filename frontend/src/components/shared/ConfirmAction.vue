<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue'
const props = defineProps({ title: { type: String, required: true }, description: { type: String, required: true }, confirmLabel: { type: String, default: 'Confirm delete' }, busyLabel: { type: String, default: 'Deleting...' }, busy: Boolean, returnFocus: { type: String, default: '' } })
defineEmits(['confirm', 'cancel'])
const cancel = ref(null)
onMounted(() => cancel.value?.focus({ preventScroll: true }))
onBeforeUnmount(() => { queueMicrotask(() => {
  const target = globalThis.document?.getElementById(props.returnFocus) || globalThis.document?.getElementById('workspace-title')
  if (!globalThis.document?.activeElement || globalThis.document.activeElement === globalThis.document.body) target?.focus({ preventScroll: true })
}) })
</script>
<template>
  <div class="confirmation" role="group" :aria-label="title">
    <strong>
      {{ title }}
    </strong>
    <p class="muted">
      {{ description }}
    </p>
    <div class="actions">
      <button ref="cancel" class="btn" :disabled="busy" @click="$emit('cancel')">
        Cancel
      </button>
      <button class="btn danger" :disabled="busy" @click="$emit('confirm')">
        {{ busy ? busyLabel : confirmLabel }}
      </button>
    </div>
  </div>
</template>
