# Frontend architecture and workflows

The frontend uses JavaScript, Vue 3, Vite, native browser media controls, and
custom CSS. It has no router, state-management framework, CSS framework, or
animation dependency beyond the existing Vue/Vite stack.

## Component organization

```text
frontend/src/
  main.js / App.vue
  components/
    VoiceCleanLecture.vue           Workspace shell; keeps feature panels mounted
    layout/AppTopNav.vue            Sticky links, Tools disclosure, mobile menu
    layout/AppHeader.vue            Current section and shared operation status
    dashboard/WorkspaceOverview.vue Bento overview and real workspace context
    dashboard/RecentRecordings.vue  Current library preview, truthful loading/errors
    lecturers/LecturerManager.vue   Lecturer selection, profile, registration/edit/delete
    references/ReferencePanel.vue   Reference recording, upload, preview, saved list
    recordings/LectureRecorder.vue Details, microphone studio, upload, preview/save
    recordings/RecordingLibrary.vue Search/filter, playback, actions, edit/delete
    audio/AudioEnhancement.vue      Source/preset selection, comparison, exports
    audio/AudioVersionCard.vue      Shared native player/download/missing-file UI
    shared/                        LecturerSelector, AudioPlayer, ConfirmAction, ListPagination
  composables/
    useVoiceClean.js                Shared lecturer/reference/capture/library session
    useAudioVersions.js             Selected source, versions, bounded request states
    useRecordingOpen.js             Unsaved-preview replacement confirmation guard
  services/
    api.js                         Base URL, fetch wrapper, timeout/error mapping
    referenceContext.js            Remembered lecturer and API reconstruction
    recordings.js                  Metadata/audio save and retry helpers
    audioVersions.js               Version loading and generation requests
  styles/                          Tokens, shared components, navigation, workspaces
  utils/formatters.js               Date and duration presentation
```

## State and request flow

The shell creates one `useVoiceClean()` session and passes a shared reactive
workspace to each feature. Feature components render state and call its commands.
`useAudioVersions()` separates version/generation state, and `useRecordingOpen()`
protects unsaved previews when opening library audio.

Example: a reference Save click calls the workspace command, builds FormData,
sends it through `api.js`, receives a saved sample, reloads the sample list, and
uses its backend playback URL. See the [backend contract](backend.md).

`api.js` defaults to `http://127.0.0.1:8000`; `VITE_API_BASE_URL` can override it.
Normal requests time out after 60 seconds unless overridden. Audio generation
allows 20 minutes. Errors remain failures; a timeout prompts refreshing saved
items before retrying because the server may have committed the operation.

## Navigation and presentation

Top navigation keeps the existing section hashes: `#overview`, `#references`,
`#recording`, `#history`, and `#audio`. Tools contains Enhancement & Export.
Navigation pushes distinct history entries; hash/popstate listeners restore
Back/Forward state without duplicate History loads. Unknown hashes use Overview.
The current heading receives focus after navigation and through the skip link.

Panels use `v-show`, preserving an active MediaRecorder and unsaved audio when
switching sections. Navigation pauses playback, not capture. The mobile menu and
Tools disclosure support labeled controls, focus intent, outside dismissal, and
Escape. Native audio players pause other VoiceClean players when playback starts.

Tokens define navy/blue actions, light surfaces, typography, radii, spacing, and
shadows. `components.css` supplies reusable controls, `navigation.css` owns top
navigation, and `workspaces.css` composes feature layouts. Reduced-motion rules
disable animation/transitions without removing text status. History uses a
compact toolbar/list, secondary actions disclosure, and pagination only when
needed. Keyboard focus remains visible.

## User workflows

| Workspace | Workflow |
| --- | --- |
| Overview | View actual lecturer/recording/reference counts, current lecturer, up to four library entries, next-step links |
| Lecturers & References | Select/register lecturer; edit saved profile through disclosure; record/upload/preview/save reference; reload/play/delete samples; confirmed lecturer deletion when empty |
| Record Lecture | Choose lecturer/title; capture/pause/resume/stop or select file; preview/save/download; open persisted output |
| Recording History | Search/filter, open/play or complete pending recordings, inspect versions, enhance/export, download, rename, confirmed delete |
| Enhancement & Export | Select saved source; run fixed non-AI enhancement/export; compare original/enhanced; play/download persistent versions |

Overview's library preview reuses the current History page. It says Recent
recordings only for the first unfiltered page; otherwise it says Library preview.
The audio-lab selector also uses the current library page; History handles wider
browsing/search. No fabricated analytics or signal-derived audio levels are shown.

## Microphone and unsaved audio

MediaRecorder requests WebM/Opus where supported. Unsupported capture browsers
can upload WAV/MP3/WebM instead. Reference and lecture capture are mutually
exclusive. Permission denial, empty capture, unsupported formats, and failures
have visible errors. The waveform is existing decorative recording animation.

Captured Blobs and object URLs are temporary browser state. Opening a saved
recording asks for confirmation if unsaved lecture/reference previews would be
replaced. Cancel leaves them intact. Navigation preserves them, but refresh does
not. Saved audio downloads use server attachment URLs rather than buffering large
files into a JavaScript Blob; unsaved preview downloads retain browser format.

## Persistence

PostgreSQL and backend storage are the source of saved metadata/bytes. localStorage
contains only the last lecturer UUID, namespaced by backend origin. Startup loads
lecturers, retrieves the remembered lecturer even outside the first page, and
loads that lecturer's references. A deleted remembered lecturer clears selection
without showing another lecturer's samples. Storage access failures are tolerated.

The frontend keeps a draft recording UUID across save retries in memory. It
reconciles saved metadata/original state before attaching again. Refresh discards
the local draft and unsaved audio, but committed pending/failed metadata remains
in History. Subject and notes are encoded in the existing description field;
there is no separate subject table/column.

Implementation/state/SSR tests do not prove native browser focus, layout,
microphone, seeking, or download behavior. See [testing and acceptance](testing.md).
