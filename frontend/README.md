# VoiceClean frontend

Vue 3 + Vite. One component (`src/App.vue`), a small API client (`src/api.js`) and pure helpers (`src/utils.js`).

    npm install
    npm run dev          # http://localhost:5173  (proxies /api to Django on 127.0.0.1:8000)

Start the backend first (see ../voiceclean-backend/README.md).
Different backend address: `BACKEND_URL=http://host:8000 npm run dev`.
Serving the frontend from another origin: copy `.env.example` to `.env`, set `VITE_API_URL`,
and add that origin to `CORS_ALLOWED_ORIGINS` in the Django settings.

## Flow
1. Record (start / pause / resume / stop). Mic capture is raw (no browser noise suppression), since the server does the cleaning.
2. **Clean & Save** uploads the recording; the server converts + denoises it and returns it.
3. Flip between **Cleaned / Original** while listening, download as MP3/WAV/M4A/OGG, edit details, delete.
4. **Recording History** lists everything saved; Open reloads a lecture.

The Reference Voice card still works as a local preview, but nothing is sent to the server for it yet (Phase 3).

## Test
With both servers running: `npm run test:integration` (12 checks through the Vite proxy using real WebM/Opus audio).
