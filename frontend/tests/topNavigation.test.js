import test from 'node:test'
import assert from 'node:assert/strict'
import { componentState, renderWorkspace, topNavigationState } from './componentHarness.js'

function escapeEvent() {
  return { prevented: false, stopped: false, preventDefault() { this.prevented = true }, stopPropagation() { this.stopped = true } }
}

test('Tools disclosure opens, focuses its destination, and closes on Escape with focus return', async () => {
  const { state } = await topNavigationState()
  let destinationFocused = false, triggerFocused = false
  state.toolsLink.value = { focus() { destinationFocused = true } }
  state.toolsButton.value = { focus() { triggerFocused = true } }
  await state.focusToolsLink()
  assert.equal(state.toolsOpen.value, true)
  assert.equal(destinationFocused, true)
  const event = escapeEvent()
  await state.escape(event)
  assert.equal(state.toolsOpen.value, false)
  assert.equal(triggerFocused, true)
  assert.equal(event.prevented && event.stopped, true)
})

test('mobile destinations close both disclosures and emit the original section ID', async () => {
  const { state, events } = await topNavigationState()
  state.toggleMobile()
  state.toggleTools()
  assert.equal(state.mobileOpen.value && state.toolsOpen.value, true)
  state.choose('audio')
  assert.equal(state.mobileOpen.value, false)
  assert.equal(state.toolsOpen.value, false)
  assert.deepEqual(events, [['navigate', 'audio']])
  state.toggleMobile()
  let focused = false
  state.menuButton.value = { focus() { focused = true } }
  await state.escape(escapeEvent())
  assert.equal(state.mobileOpen.value, false)
  assert.equal(focused, true)
})

test('pointer and focus leaving the navigation close menus without stealing focus', async () => {
  const { state } = await topNavigationState()
  const insideTools = {}, insideHeader = {}, outside = {}
  state.tools.value = { contains: target => target === insideTools }
  state.header.value = { contains: target => target === insideTools || target === insideHeader }
  state.toolsOpen.value = true
  state.mobileOpen.value = true
  state.outside({ target: insideTools })
  assert.equal(state.toolsOpen.value && state.mobileOpen.value, true)
  state.outside({ target: insideHeader })
  assert.equal(state.toolsOpen.value, false)
  assert.equal(state.mobileOpen.value, true)
  state.toolsOpen.value = true
  state.leaveTools({ relatedTarget: outside })
  assert.equal(state.toolsOpen.value, false)
  state.outside({ target: outside })
  assert.equal(state.mobileOpen.value, false)
  state.mobileOpen.value = true
  state.leaveHeader({ relatedTarget: outside })
  assert.equal(state.mobileOpen.value, false)
})

test('Escape closes the nested Tools disclosure before the mobile navigation', async () => {
  const { state } = await topNavigationState()
  state.mobileOpen.value = true
  state.toolsOpen.value = true
  await state.escape(escapeEvent())
  assert.equal(state.toolsOpen.value, false)
  assert.equal(state.mobileOpen.value, true)
  await state.escape(escapeEvent())
  assert.equal(state.mobileOpen.value, false)
})

test('top navigation renders real hash links, active Tools, labeled mobile toggle, and no sidebar', async () => {
  const page = await componentState()
  page.activeView.value = 'audio'
  const html = await renderWorkspace(page)
  assert.doesNotMatch(html, /<aside/)
  assert.match(html, /class="app-topnav"/)
  for (const id of ['overview', 'references', 'recording', 'history', 'audio']) assert.ok(html.includes(`href="#${id}"`))
  assert.match(html, /aria-label="Tools, Enhancement &amp; Export active"/)
  assert.match(html, /aria-controls="primary-navigation"/)
  assert.match(html, /aria-controls="tools-navigation"/)
  assert.match(html, /id="tools-navigation"[^>]*style="display:none/)
  assert.match(html, /aria-label="Main navigation"/)
  assert.match(html, /Record Lecture/)
})
