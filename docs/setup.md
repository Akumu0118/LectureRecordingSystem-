# Local setup and configuration

VoiceClean runs locally with PostgreSQL, FastAPI, and Vite. Preserve existing
`backend/.env` credentials and saved audio. Commands below use Windows PowerShell
and start from the repository root unless stated otherwise.

## Prerequisites

- Python with venv support; the project has been tested with Python 3.13.
- Node.js/npm compatible with the installed Vite version; recorded checks used Node 24.
- A running local PostgreSQL server; the project uses `LectureRecordingSystem`.
- FFmpeg and FFprobe executables, including `libmp3lame`, `pcm_s16le`, and the
  highpass/lowpass/afftdn/loudnorm filters.

## First-time backend setup

Skip environment creation/install steps when the existing environment is ready.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
```

`requirements.txt` declares runtime ranges; `requirements-dev.txt` adds testing
requirements. `requirements-lock.txt` records the installed environment for
reproduction. Activation is optional because commands use the venv Python directly.

Ensure `LectureRecordingSystem` exists in local PostgreSQL. If creating it for
the first time, use pgAdmin and an authorized account; choose an application
login/owner. Reuse existing databases/accounts instead of recreating them.

Edit **`backend/.env`**, not `.env.example`. Its connection format is:

```dotenv
DATABASE_URL=postgresql+psycopg://YOUR_DB_USER:YOUR_URL_ENCODED_PASSWORD@localhost:5432/LectureRecordingSystem
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
```

Replace placeholders with your own credentials. The part before `:` after `//`
is the PostgreSQL username, not the database name. Percent-encode reserved
password characters such as `@`, `:` and `%`. The example template currently uses
`voiceclean` as an illustrative database/user; change it to match your own setup.
Keep `.env` out of Git.

Settings load the `.env` beside the backend regardless of terminal working
directory; process environment values take precedence. Configuration is cached,
so restart the backend after changes. Malformed database URLs fail validation;
an absent URL permits liveness but database operations return 503.

From `backend/`, apply reviewed repository migrations:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
```

The expected repository head is `f1f6a031e255`. See [database](database/README.md).
The API does not create tables at startup.

## Start the application

Terminal 1, from repository root:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000
```

Terminal 2, from repository root:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Run `npm.cmd ci` for first-time installation or restoring lockfile dependencies;
it is not necessary on every launch. Use `npm.cmd` to avoid PowerShell wrapper
issues with Vite flags. Keep both terminals open; Ctrl+C stops their servers.
Use one backend worker because job capacity is process-local.

- App: `http://127.0.0.1:5173`
- API docs: `http://127.0.0.1:8000/docs`
- Liveness: `http://127.0.0.1:8000/health`
- DB check: `http://127.0.0.1:8000/health/db`

The frontend defaults to that API origin. To override it, create `frontend/.env`
from `frontend/.env.example` if needed, set `VITE_API_BASE_URL`, and restart Vite.
The exact frontend origin must be present in backend CORS settings. Preview port
4173 is not allowed by default. CORS supports GET/POST/PATCH/DELETE, Content-Type,
and Range; it does not provide user authentication.

## Configuration reference

Backend source: [`config.py`](../backend/app/core/config.py). Relative
`STORAGE_ROOT` resolves from `backend/`.

| Setting | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | unset | PostgreSQL Psycopg connection URL |
| `CORS_ORIGINS` | localhost and 127.0.0.1 on 5173 | JSON list of allowed frontend origins |
| `STORAGE_ROOT` | `backend/storage` | Metadata-referenced audio root |
| `MAX_REFERENCE_SIZE_BYTES` | 10485760 | 10 MiB reference file limit |
| `MAX_REFERENCE_DURATION_SECONDS` | 120 | Two-minute reference limit |
| `FFPROBE_PATH` | `ffprobe` | Probe executable name or full path |
| `FFPROBE_TIMEOUT_SECONDS` | 30 | Reference validation timeout |
| `MAX_RECORDING_SIZE_BYTES` | 536870912 | 512 MiB lecture file limit |
| `MAX_RECORDING_DURATION_SECONDS` | 14400 | Four-hour lecture limit |
| `RECORDING_PROBE_TIMEOUT_SECONDS` | 180 | Lecture/generated-file probe timeout |
| `FFMPEG_PATH` | `ffmpeg` | Conversion executable name or full path |
| `AUDIO_JOB_TIMEOUT_SECONDS` | 600 | FFmpeg execution timeout |
| `MAX_AUDIO_JOBS` | 2 | Process-local capacity, accepted range 1-8 |
| `MAX_GENERATED_SIZE_BYTES` | 536870912 | Generated output size cap |

## Troubleshooting

| Symptom | Check/action |
| --- | --- |
| FFprobe unavailable while saving | Run `ffprobe -version` in a fresh terminal; verify the backend venv can find it; set full `FFPROBE_PATH` if necessary, then restart the backend |
| FFmpeg unavailable during enhancement/export | Check `ffmpeg -version` and `FFMPEG_PATH`; FFprobe alone cannot generate audio |
| Tools work in a new terminal but not VS Code | Restart VS Code/its terminal to inherit updated PATH, or use full executable paths |
| DB health returns 503 | Verify PostgreSQL is running and the URL's database, user, password, host, port are correct; check migration status |
| Frontend cannot reach API | Start backend; verify API base URL, exact CORS origin, and browser Network errors |
| Port already in use | Check the existing server before starting another; stop only the intended process or choose/configure another port |
| Save/generation timeout or lost response | Refresh library/versions before retrying; the operation may have committed |
| Saved metadata but missing audio | Check configured storage root and backups; do not silently replace the original |
| Lecturer deletion conflict | Remove only intended dependent references/recordings first; the conflict protects their ownership |

From `backend/`, executable lookup can be checked without exposing credentials:

```powershell
ffmpeg -version
ffprobe -version
.\.venv\Scripts\python.exe -c "import shutil; print(shutil.which('ffmpeg')); print(shutil.which('ffprobe'))"
```

A Python package named ffmpeg is not a replacement for the external executables.
See [audio](audio.md) for storage/recovery and [testing](testing.md) for checks.
