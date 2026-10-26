# VoiceClean

VoiceClean is a local lecture recording and audio management system. It helps
users organize lecturers, capture or upload lecture audio, keep a persistent
recording library, apply basic speech enhancement, and download audio versions.

## Features

- Register, select, edit, and safely delete lecturers.
- Record/upload reference voice samples and retrieve them after refresh.
- Record lectures with pause/resume/stop, or upload WAV, MP3, and WebM files.
- Save, search, filter, play, rename, and delete lecture recordings.
- Generate a separate enhanced WAV using a fixed non-AI speech preset.
- Export original lectures as MP3 and download original/generated versions.

Reference samples are stored for management only: they do not identify or isolate
a speaker. AI speaker extraction, transcription, and authentication are not
implemented. This project is intended for local development.

## Technology stack

| Area | Technology |
| --- | --- |
| Frontend | JavaScript, Vue 3, Vite, custom CSS, browser MediaRecorder |
| Backend | Python, FastAPI, Uvicorn, Pydantic |
| Database | PostgreSQL, SQLAlchemy, Psycopg, Alembic migrations |
| Audio tools | FFprobe for validation; FFmpeg for enhancement and MP3 export |
| Testing | Pytest and the Node.js test runner |

PostgreSQL stores metadata; audio files live under `backend/storage/`. The browser
loads saved data through FastAPI. Unsaved previews are temporary and cannot
survive a page refresh.

## 1. Install the required software

For guided automatic installation on Windows, see
[INSTALL_DEPENDENCIES.txt](INSTALL_DEPENDENCIES.txt) and the included
[PowerShell installer](install-dependencies.ps1). From a complete checkout:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install-dependencies.ps1 -InstallTools
```

This installs missing system prerequisites and the backend/frontend packages.
PostgreSQL's installer remains interactive; database credentials and migrations
are configured afterward. Existing `.env` files are preserved. For manual
installation, continue below.

The instructions below target **Windows PowerShell**, the project's tested
development environment. Skip tools already installed at compatible versions.

| Tool | Why it is needed |
| --- | --- |
| Git | Clone the repository |
| Python 3.13 | Run FastAPI and create the backend virtual environment |
| Node.js LTS and npm | Install/build/run Vue; Node 24 was used in development |
| PostgreSQL 18 | Run the local database server |
| FFmpeg and FFprobe | Validate uploads, enhance audio, export MP3 |
| VS Code or another editor | Edit configuration and source; optional |

With WinGet available, install these tools in PowerShell:

```powershell
winget install --id Git.Git --exact --source winget
winget install --id Python.Python.3.13 --exact --source winget
winget install --id OpenJS.NodeJS.LTS --exact --source winget
winget install --id Gyan.FFmpeg --exact --version 9.0.2 --source winget
```

Git's [Windows installation guide](https://git-scm.com/install/windows) documents
the Git WinGet command. The community package manifests identify the
[Python package](https://github.com/microsoft/winget-pkgs/tree/master/manifests/p/Python/Python/3/13),
[Node.js LTS package](https://github.com/microsoft/winget-pkgs/tree/master/manifests/o/OpenJS/NodeJS/LTS),
and [FFmpeg package](https://github.com/microsoft/winget-pkgs/tree/master/manifests/g/Gyan/FFmpeg).
FFmpeg 9.0.2 is the build used in the recorded audio tests.

Install PostgreSQL 18 using the installer linked on the
[PostgreSQL Windows download page](https://www.postgresql.org/download/windows/).
Select the server and command-line tools; pgAdmin is useful for inspecting data.
Remember the `postgres` administrator password, retain port `5432` unless it
conflicts with another installation, and finish starting the database service.

If WinGet is unavailable, use the official
[Python](https://www.python.org/downloads/windows/),
[Node.js](https://nodejs.org/en/download), and Git installers. The
[Node installer provides npm](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm/);
no separate global Vue, Vite, FastAPI, or Uvicorn install is needed.

For manual FFmpeg installation, download the release essentials ZIP from
[Gyan's Windows builds](https://www.gyan.dev/ffmpeg/builds/), extract it to a local
tools folder, and add its actual `bin` directory to your user PATH. That directory
contains both `ffmpeg.exe` and `ffprobe.exe`. Alternatively, configure their full
paths in the backend environment as described below.

**Open a new terminal after installation.** Restart VS Code if its terminal has
an old PATH. Verify the tools:

```powershell
git --version
py -3.13 --version
node --version
npm.cmd --version
ffmpeg -version
ffprobe -version
```

The installed Vite version requires Node `20.19+` in the 20.x line or `22.12+`;
Node 24 satisfies that requirement. FFmpeg/FFprobe are external executables;
installing a Python package named ffmpeg does not replace them.

## 2. Clone the repository

In a folder where you keep projects:

```powershell
git clone https://github.com/Akumu0118/LectureRecordingSystem-.git
cd LectureRecordingSystem-
```

Use a published branch containing the full application. This guide expects:

```text
LectureRecordingSystem-/
  backend/
    app/
    migrations/
    requirements-dev.txt
    .env.example
  frontend/
    src/
    package.json
    package-lock.json
    .env.example
  docs/
  README.md
```

If `backend/` or `frontend/` is missing, check that the full application has been
published and you have checked out the correct branch. A clone does not include
another developer's uncommitted files. A private repository requires access.

## 3. Create your local PostgreSQL database

For a fresh installation, open psql from PowerShell. This is the default
PostgreSQL 18 installation path; adjust it if yours differs:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -h localhost -p 5432 -U postgres -d postgres -W
```

Enter the administrator password you chose during installation. At the psql
prompt, run the following **only if these role/database names do not exist**:

```sql
CREATE ROLE voiceclean WITH LOGIN;
\password voiceclean
CREATE DATABASE "LectureRecordingSystem" OWNER voiceclean;
\q
```

`\password` prompts for the new application user's password. Keep it for the
next step. `voiceclean` is the database login; `LectureRecordingSystem` is the
database name. You may use an existing authorized login/database instead and
adjust the connection URL. Do not recreate or drop an existing database.

## 4. Install backend dependencies and configure it

From the repository root:

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
```

This installs the project's FastAPI, Uvicorn, SQLAlchemy, Psycopg, Alembic, upload,
configuration, and test dependencies inside `backend/.venv`. Using its Python
directly avoids requiring virtual-environment activation or execution-policy changes.

Open **`backend/.env`** in your editor. Set:

```dotenv
DATABASE_URL=postgresql+psycopg://voiceclean:YOUR_URL_ENCODED_PASSWORD@localhost:5432/LectureRecordingSystem
CORS_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
STORAGE_ROOT=storage
FFPROBE_PATH=ffprobe
FFMPEG_PATH=ffmpeg
```

Replace the password placeholder with the application user's password. URL-encode
reserved characters, for example `@` as `%40`, `:` as `%3A`, and `%` as `%25`.
Retain the other limits/settings copied from `.env.example`.

If FFmpeg/FFprobe are not discoverable on PATH, set their full executable paths
in `.env`, for example `FFPROBE_PATH=C:/Tools/ffmpeg/bin/ffprobe.exe`. Use the
actual location on your laptop. Restart the backend after changing configuration.
Keep `.env` private; do not commit passwords.

Still in `backend/`, create/update the tables through Alembic:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m pip check
```

The repository migration head is `f1f6a031e255`. Do not create tables manually;
the API does not create them on startup. Storage folders/files are created as
needed by the application. A fresh setup does not include another user's audio
or database rows.

## 5. Install frontend dependencies

From the backend folder used above:

```powershell
cd ..\frontend
npm.cmd ci
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
```

`npm.cmd ci` installs the Vue/Vite dependencies from the committed lockfile.
Confirm **`frontend/.env`** points to your local backend:

```dotenv
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Restart Vite after changing this value. These dependency installation steps are
for initial setup or dependency changes; they are not needed on every launch.

## 6. Run the backend and frontend

Open two terminals in the **repository root**.

Terminal 1 - backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 8000
```

Terminal 2 - frontend:

```powershell
cd frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Keep PostgreSQL and both terminals running. Ctrl+C stops each development server.
Use one backend worker because audio job limits are process-local.

| Address | Purpose |
| --- | --- |
| http://127.0.0.1:5173 | VoiceClean interface |
| http://127.0.0.1:8000/docs | Interactive API documentation |
| http://127.0.0.1:8000/health | Backend liveness |
| http://127.0.0.1:8000/health/db | PostgreSQL connectivity |

From another terminal, verify backend connectivity:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/health/db
```

The DB check should report `database: connected`. In the interface, register a
lecturer, save a reference, then record/upload and save a lecture. Refresh and
reopen it to check persistence. Enhance/export only after saving the original.

## Common setup problems

| Problem | What to check |
| --- | --- |
| `py`, Git, npm, or FFprobe not found | Install the tool, open a fresh terminal, and check PATH; use full executable paths where needed |
| Backend reports FFprobe unavailable when saving | Verify FFprobe from the backend terminal, correct `FFPROBE_PATH`, and restart the API |
| Database unavailable / connection refused | Start PostgreSQL and check host, port, database name, username, and password in `backend/.env` |
| Tables do not exist | Run `alembic upgrade head` from `backend/` using its venv Python |
| Frontend cannot reach backend | Start port 8000, check `VITE_API_BASE_URL`, and match the exact frontend origin in CORS settings |
| Port 5173/8000 is occupied | Check whether this project is already running before starting another server |
| Test audio tools cannot be found | Tests need FFmpeg and FFprobe on PATH, even if the application uses full paths in `.env` |

## Optional developer checks

From `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic check
```

From `frontend/`:

```powershell
npm.cmd test
npm.cmd run build
```

Database tests use generated private schemas and temporary storage. The full
suite needs PostgreSQL, FFmpeg/FFprobe on PATH, Node, and installed frontend
dependencies. The application role must be able to create schemas. One spoken
fixture requires Windows System.Speech. Browser/microphone acceptance remains
separate from automated tests; see [testing](docs/testing.md).

## Further documentation

Start with [the documentation index](docs/README.md), then read
[architecture](docs/architecture.md), [database design](docs/database/README.md),
[backend/API](docs/backend.md), [frontend](docs/frontend.md),
[audio processing](docs/audio.md), and [configuration/troubleshooting](docs/setup.md).
