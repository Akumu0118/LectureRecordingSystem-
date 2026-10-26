<script setup>
import { nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'
const props = defineProps({ activeView: { type: String, required: true } })
const emit = defineEmits(['navigate'])
const mobileOpen = ref(false)
const toolsOpen = ref(false)
const header = ref(null)
const tools = ref(null)
const menuButton = ref(null)
const toolsButton = ref(null)
const toolsLink = ref(null)
const items = [
  { id: 'overview', label: 'Overview' },
  { id: 'references', label: 'Lecturers & References' },
  { id: 'recording', label: 'Record Lecture' },
  { id: 'history', label: 'Recording History' }
]
function closeMenus() { mobileOpen.value = false; toolsOpen.value = false }
function choose(view) { closeMenus(); emit('navigate', view) }
function toggleMobile() { toolsOpen.value = false; mobileOpen.value = !mobileOpen.value }
function toggleTools() { toolsOpen.value = !toolsOpen.value }
async function focusToolsLink() {
  toolsOpen.value = true
  await nextTick()
  toolsLink.value?.focus()
}
async function escape(event) {
  if (!toolsOpen.value && !mobileOpen.value) return
  event.preventDefault()
  event.stopPropagation()
  if (toolsOpen.value) {
    toolsOpen.value = false
    await nextTick()
    toolsButton.value?.focus()
  } else {
    mobileOpen.value = false
    await nextTick()
    menuButton.value?.focus()
  }
}
function outside(event) {
  if (!tools.value?.contains(event.target)) toolsOpen.value = false
  if (!header.value?.contains(event.target)) mobileOpen.value = false
}
function leaveTools(event) {
  if (event.relatedTarget && !tools.value?.contains(event.relatedTarget)) toolsOpen.value = false
}
function leaveHeader(event) {
  if (event.relatedTarget && !header.value?.contains(event.relatedTarget)) closeMenus()
}
watch(() => props.activeView, closeMenus)
onMounted(() => globalThis.document?.addEventListener('pointerdown', outside))
onBeforeUnmount(() => globalThis.document?.removeEventListener('pointerdown', outside))
</script>

<template>
  <header ref="header" class="app-topnav" @keydown.esc="escape" @focusout="leaveHeader">
    <div class="topnav-inner">
      <a class="topnav-brand" href="#overview" @click.prevent="choose('overview')" aria-label="VoiceClean overview">
        <span class="brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
            <rect x="9" y="3" width="6" height="12" rx="3" />
            <path d="M5 10v2a7 7 0 0 0 14 0v-2M12 19v3M8 22h8" />
          </svg>
        </span>
        <span>VoiceClean<span class="brand-caption">Lecture workspace</span></span>
      </a>
      <button ref="menuButton" type="button" class="mobile-menu-button" :aria-expanded="mobileOpen"
        aria-controls="primary-navigation" @click="toggleMobile">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true">
          <path :d="mobileOpen ? 'M6 6l12 12M6 18L18 6' : 'M4 6h16M4 12h16M4 18h16'" />
        </svg>
        {{ mobileOpen ? 'Close' : 'Menu' }}
      </button>
      <nav id="primary-navigation" class="topnav-links" :class="{ 'is-open': mobileOpen }" aria-label="Main navigation">
        <a v-for="item in items" :key="item.id" :href="'#' + item.id" class="topnav-link"
          :class="{ active: activeView === item.id }" :aria-current="activeView === item.id ? 'page' : undefined"
          aria-controls="workspace-panel" @click.prevent="choose(item.id)">{{ item.label }}</a>
        <div ref="tools" class="tools-disclosure" @focusout="leaveTools">
          <button ref="toolsButton" class="topnav-link tools-button" :class="{ active: activeView === 'audio' }"
            type="button" :aria-expanded="toolsOpen" aria-controls="tools-navigation"
            :aria-label="activeView === 'audio' ? 'Tools, Enhancement & Export active' : 'Tools'"
            @click="toggleTools" @keydown.down.prevent="focusToolsLink" @keydown.up.prevent="focusToolsLink">
            Tools
            <svg class="chevron" :class="{ rotated: toolsOpen }" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="m5 8 5 5 5-5" /></svg>
          </button>
          <div v-show="toolsOpen" id="tools-navigation" class="tools-panel">
            <a ref="toolsLink" href="#audio" class="tools-destination" :aria-current="activeView === 'audio' ? 'page' : undefined"
              @click.prevent="choose('audio')" @keydown.up.prevent="toolsButton?.focus()">
              <span class="tool-icon" aria-hidden="true">&#9835;</span>
              <span><strong>Enhancement &amp; Export</strong><small>Compare audio and download versions</small></span>
            </a>
          </div>
        </div>
      </nav>
    </div>
  </header>
</template>
