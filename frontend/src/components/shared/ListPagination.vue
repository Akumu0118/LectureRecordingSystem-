<script setup>
defineProps({ offset: { type: Number, default: 0 }, total: { type: Number, default: 0 }, count: { type: Number, default: 0 }, busy: Boolean, label: { type: String, required: true } })
defineEmits(['change'])
</script>
<template>
  <nav class="pagination" :aria-label="label + ' pages'">
    <p class="muted">
      {{ total ? offset + 1 : 0 }}-{{ Math.min(offset + count, total) }} of {{ total }} {{ label }}
    </p>
    <div class="button-group">
      <button
        class="btn compact"
        :aria-label="'Previous ' + label + ' page'"
        :disabled="busy || offset === 0"
        @click="$emit('change', -1)">
        Previous
      </button>
      <button
        class="btn compact"
        :aria-label="'Next ' + label + ' page'"
        :disabled="busy || offset + count >= total"
        @click="$emit('change', 1)">
        Next
      </button>
    </div>
  </nav>
</template>
