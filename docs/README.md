# VoiceClean system documentation

VoiceClean is a local lecture recording and audio management application built
with Vue 3, FastAPI, SQLAlchemy, PostgreSQL, and FFmpeg/FFprobe. It stores lecturer
profiles, reference samples, original lectures, and generated audio versions.
Enhancement is a fixed non-AI speech preset; reference samples do not identify
or isolate a speaker.

These guides explain the current implementation, organized by system concern.

| Guide | What it explains |
| --- | --- |
| [Local setup and configuration](setup.md) | Prerequisites, database connection, environment settings, migrations, launch commands, troubleshooting |
| [System architecture](architecture.md) | Technology roles, layers, request flows, recording lifecycle, transactions, storage, limitations |
| [Database design](database/README.md) | ER diagram, every table/column, relationships, constraints, indexes, migration workflow |
| [Backend and API](backend.md) | Python modules, validation, endpoints, responses, examples, error handling |
| [Frontend architecture and workflows](frontend.md) | Vue components, shared state, navigation, capture, persistence, dashboard behavior |
| [Audio validation and processing](audio.md) | Supported formats, validation limits, storage, DSP chain, MP3 export, concurrency and recovery |
| [Testing and acceptance](testing.md) | Automated suites, isolated PostgreSQL data, executed evidence, manual browser/device checks |

For a first read, follow architecture -> database -> backend -> frontend -> audio.
For running the project, start with setup. API schemas can also be explored at
`http://127.0.0.1:8000/docs` while the backend is running.

The source code is the implementation authority. This documentation was reviewed
against the repository on October 26, 2026. Historical test results are labeled
in the testing guide; they are not a promise about the state of a running process
or a substitute for testing a changed application.
