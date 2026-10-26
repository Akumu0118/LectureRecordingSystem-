# Testing and acceptance

Automated checks validate application logic, schemas, transactions, and files.
Browser/device acceptance validates rendering, native media behavior, and actual
microphone interaction. These are separate kinds of evidence.

## Automated commands

Install frontend dependencies before the full backend suite: live Vue integration
uses Node and the existing frontend compiler/SSR packages. PostgreSQL must be
reachable, the DB role must be allowed to create private schemas, and FFmpeg and
FFprobe must be on the test process PATH. Application `FFPROBE_PATH` alone does
not satisfy fixtures that explicitly locate tools with `shutil.which`.

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic check
```

From `frontend/`:

```powershell
npm.cmd test
npm.cmd run build
npm.cmd ls --depth=0
```

There is no configured frontend lint script. A successful production build
checks compilation/imports; it does not prove visual correctness. Alembic check
compares supported metadata and does not fully validate custom trigger code.

## Coverage map

| Layer | Main tests and evidence |
| --- | --- |
| Health/config/CORS | Liveness, connectivity responses, sanitized failures, missing configuration, allowed origins |
| Database | Columns/relationships, RESTRICT behavior, CHECK/unique/deferred constraints, timestamps, migration reversibility |
| Lecturer/reference API | CRUD, validation, upload formats/limits, metadata, scoped lookup, playback/ranges, rollback and cleanup |
| Recording API | Metadata retry, original upload/status, library search/filter/pagination, concurrency, playback, deletion |
| Audio jobs | Real conversions, reuse, source/output validation, unavailable tools, capacity/timeout, rollback, uncertain commits |
| Frontend component/services | API errors, restored state, hashes/history, unsaved previews, disclosure markup, version availability/download links |
| Simulated capture | Pause/resume/stop, permission denial, empty/unsupported capture, mutual exclusion and navigation preservation |
| Live Vue/API | Actual Vue methods against HTTP/PostgreSQL/files, save/reconstruct, API restart, play/download, enhance/export/reuse, edit/delete |

The existing Node runner loads real Vue templates through Vite/plugin-vue and
SSR. Those tests do not create a browser DOM. The spoken-audio integration
fixture uses Windows System.Speech; synthesized speech is not a physical
microphone recording or a subjective listening test, and that fixture skips
where its Windows facility is unavailable.

## Data isolation

[`conftest.py`](../backend/tests/conftest.py) creates a uniquely generated
`voiceclean_test_<uuid>` PostgreSQL schema. It sets search_path for the private
schema, migrates it, tests downgrade/reapply there, and checks preservation of an
unrelated sentinel table. Cleanup validates the generated schema identifier
before dropping only that schema. Other fixtures use temporary audio storage.

Ordinary database tests roll back; API/deferred-constraint tests can commit
within the private schema. Process-restart tests start separate private APIs.
Tests must never clear public application tables or modify real audio to simulate
failures. When DATABASE_URL is absent, PostgreSQL-dependent checks skip; when
configured but unreachable, they fail. Inspect skips before claiming coverage.

## Recorded verification and current limits

The latest executed implementation checks recorded before this documentation
reorganization were:

- Backend: **171 passed**, with one existing upstream Starlette/HTTPX TestClient
  deprecation warning.
- Frontend: **45 passed**, including persistence, navigation, markup, preview
  protection, and simulated capture checks.
- Production frontend build: passed; the full backend suite and additional live
  Vue/API restart workflows passed during the dashboard work.

These counts are historical execution evidence, not a fresh test run for this
documentation-only change. Re-run commands after functional changes. This docs
reorganization checks source references, internal links, and preservation of
runtime files; it does not need to create/delete application data.

Real app viewport, keyboard, physical microphone, native download/seek, and
subjective audio checks remain unverified. Earlier automation exposed no browser
tabs through the browser bridge; native browser selection failed with unavailable
coordinate geometry and unreliable target screenshots. HTTP 200, SSR, and code
review do not count as rendered browser acceptance.

## Manual acceptance checklist

Use disposable lecturer/audio data and keep existing user references/recordings.
Record browser/version, viewport, result, and relevant console/network errors.

1. Inspect every workspace at 1440, 1280, 1024, 768, 390, and 320px. Check long
   titles, labels, menu/dropdown overflow, action alignment, and native players.
2. Use Tab/Shift+Tab/Enter/Space/Escape: navigation, skip link, Tools/mobile menu,
   lecturer edit, History actions, rename, confirmations, and returned focus.
   Repeat with reduced motion; use a screen reader where available.
3. Register/edit a lecturer; refresh and confirm restoration. Verify a lecturer
   with dependent references/recordings returns an explanatory delete conflict.
4. Allow/deny microphone access manually. Record/stop/preview/save a reference,
   reload/play/seek it, and verify after an API restart. Also try file upload.
5. Capture a lecture; navigate away/return; pause/resume/stop/preview/save. Check
   mutual exclusion, interruption, errors, and unsaved-preview replacement cancel.
6. Search/filter/paginate History. Open, rename/edit, refresh, download original,
   cancel deletion, and verify all saved data after restart.
7. Enhance real spoken audio and listen against the original. Export twice to
   confirm reuse; download/play original, enhanced WAV, and MP3 externally.
8. Test slow/offline/reconnected requests; refresh lists before retrying uncertain
   saves. Do not remove real files or change user data to manufacture errors.
9. Confirm deletion only for disposable recordings/samples, then their empty
   lecturer; verify unrelated user data still works.

Automated success establishes coverage in the named layers. Full demo readiness
requires browser/device acceptance; production security/readiness is not claimed.
