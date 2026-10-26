<template>
  <label class="field-label" for="lecture-title">Lecture title</label>
  <input id="lecture-title" v-model="title" placeholder="e.g. Computer Networks - Lecture 3" />
  <p class="field-hint">Optional. If you leave it blank, the lecture is named with today's date.</p>

  <label class="field-label" for="lecture-subject">Subject</label>
  <input id="lecture-subject" v-model="subject" placeholder="e.g. Computer Engineering" />

  <label class="field-label" for="lecture-notes">Notes</label>
  <textarea id="lecture-notes" v-model="notes" placeholder="Optional notes..." rows="3"></textarea>
</template>

<script setup>
const title = defineModel('title', { default: '' })
const subject = defineModel('subject', { default: '' })
const notes = defineModel('notes', { default: '' })
</script>
