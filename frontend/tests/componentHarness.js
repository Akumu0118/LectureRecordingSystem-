// Load the real Vue component tree with the project's existing Vite compiler.
// This exercises component logic and SSR markup, not a browser or microphone.
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'
import { createSSRApp, h, reactive } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../', import.meta.url))
const server = await createServer({ root, configFile: false, plugins: [vue()], server: { middlewareMode: true, hmr: false, ws: false, watch: null }, optimizeDeps: { noDiscovery: true, include: [] }, appType: 'custom' })
let component
try { component = (await server.ssrLoadModule('/src/components/VoiceCleanLecture.vue')).default }
finally { await server.close() }
const setup = component.setup
const values = new Map()
globalThis.localStorage = { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value), removeItem: key => values.delete(key) }
globalThis.window = { clearInterval, setInterval }

export async function componentState() {
  let captured
  const instance = { ...component, ssrRender: undefined, render: undefined, setup(props, context) { captured = setup(props, context); return () => h('div') } }
  await renderToString(createSSRApp(instance))
  return captured
}

export async function renderWorkspace(state) {
  return renderToString(createSSRApp({ ...component, setup() { return { ...state, workspace: reactive(state) } } }))
}

// State/handler checks for the real top-nav component. This is not DOM automation.
export async function topNavigationState(activeView = 'overview') {
  const navigation = component.components.AppTopNav
  const props = reactive({ activeView })
  const events = []
  let state
  const instance = { ...navigation, ssrRender: undefined, render: undefined,
    setup(_props, context) {
      state = navigation.setup(props, { ...context, emit(...args) { events.push(args) } })
      return () => h('div')
    }
  }
  await renderToString(createSSRApp(instance, { activeView }))
  return { state, props, events }
}
