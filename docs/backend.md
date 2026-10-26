# Backend and API

The Python backend starts at [`app/main.py`](../backend/app/main.py). FastAPI
registers health, lecturer/reference, and recording/version routers, CORS,
upload body limits, and sanitized database error handlers. Uvicorn runs the ASGI
application. SQLAlchemy connects lazily and yields a session per request;
services explicitly commit mutations. Shutdown disposes the cached engine pool.

## Source map

| Module | Responsibility |
| --- | --- |
| `app/core/config.py` | Environment settings and backend-relative paths |
| `app/core/database.py` | Shared ORM Base, engine, session dependency |
| `app/core/upload_limits.py` | ASGI request byte guard before multipart spooling |
| `app/routers/` | HTTP inputs, status codes, response schemas, file responses |
| `app/schemas/` | Pydantic lecturer, sample, recording, version, health contracts |
| `app/services/lecturers.py` | Lecturer lookup and commit error handling |
| `app/services/voice_samples.py` | Reference sample/audio transaction and cleanup |
| `app/services/recordings.py` | Recording locks, original upload lifecycle, deletion |
| `app/services/reference_storage.py` | Filename/path checks, staging, FFprobe validation |
| `app/services/recording_storage.py` | Shared validation with lecture limits/directories |
| `app/services/audio_jobs.py` | Fixed presets, capacity, conversion, validation, reuse |

## Endpoints

Interactive schemas are at `http://127.0.0.1:8000/docs`, and OpenAPI JSON is
`/openapi.json` while the backend runs. All resource identifiers below are UUIDs.

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/health` | Liveness independent of database connectivity |
| GET | `/health/db` | Runs `SELECT 1`; 503 if unavailable/unconfigured |
| POST | `/api/lecturers` | 201, register lecturer |
| GET | `/api/lecturers` | Paginated lecturers |
| GET | `/api/lecturers/{lecturer_id}` | Lecturer details |
| PATCH | `/api/lecturers/{lecturer_id}` | Edit name/department |
| DELETE | `/api/lecturers/{lecturer_id}` | 204 only when references/recordings do not prevent deletion |
| POST | `/api/lecturers/{lecturer_id}/samples` | 201, validated reference upload |
| GET | `/api/lecturers/{lecturer_id}/samples` | Paginated samples |
| GET | `/api/lecturers/{lecturer_id}/samples/{sample_id}` | Sample details |
| GET | `/api/lecturers/{lecturer_id}/samples/{sample_id}/audio` | Inline reference audio |
| DELETE | `/api/lecturers/{lecturer_id}/samples/{sample_id}` | Delete sample/audio metadata and clean bytes |
| POST | `/api/recordings` | 201 metadata; 200 for identical client UUID retry |
| GET | `/api/recordings` | Paginated/searchable/filterable library |
| GET | `/api/recordings/{recording_id}` | Recording, lecturer, original metadata/URL |
| PATCH | `/api/recordings/{recording_id}` | Edit title/description |
| POST | `/api/recordings/{recording_id}/audio` | Store original; transition to ready |
| GET | `/api/recordings/{recording_id}/stream` | Inline original audio |
| DELETE | `/api/recordings/{recording_id}` | Delete recording and associated audio metadata/files |
| POST | `/api/recordings/{recording_id}/process` | 201 enhanced WAV, or 200 reused valid version |
| POST | `/api/recordings/{recording_id}/exports` | 201 original-to-MP3, or 200 reused valid version |
| GET | `/api/recordings/{recording_id}/exports` | `{items: [...]}` exports |
| GET | `/api/recordings/{recording_id}/versions` | `{items: [...]}` original/processed/exported versions |
| GET | `/api/recordings/{recording_id}/versions/{file_id}/audio` | Inline version bytes |
| GET | `/api/recordings/{recording_id}/versions/{file_id}/download` | Attachment using a safe server-generated filename |

Lecturer/sample/recording lists return `items`, `total`, `limit`, `offset`. Limit
defaults to 20 and accepts 1-100; offset is nonnegative. Lists order by creation
time descending with UUID tie-breaking. Count and items are separate reads and
may differ briefly during concurrent changes. Version lists are not paginated.

Recording filters: `q` (literal case-insensitive title/description search, up to
200 characters), `lecturer_id`, and `status`. File responses support byte ranges
and valid 206 responses; they use verified MIME and scoped lookups.

## Validation and responses

- Lecturer name: trimmed, 1-200 characters. Department: optional, trimmed, at most
  200; blank becomes null. Embedded control characters are rejected.
- Lecturer PATCH requires at least one field. Null name is invalid; null
  department clears it. Unknown JSON fields are rejected.
- Recording creation requires lecturer UUID and a trimmed title of 1-250
  characters. Optional fields are client UUID `id`, description up to 10,000
  characters without NUL, and timezone-aware `recorded_at`.
- Recording PATCH accepts a nonempty subset of title/description; no status
  changes or lecturer reassignment. Null title is invalid; null description clears it.
- Uploads use multipart `file`. References optionally accept trimmed `label`
  up to 200 characters. Browser fetch supplies the multipart boundary itself.
- Audio metadata includes ID, role, original filename, MIME, bytes, duration,
  rate, channels, and creation time. Samples add `audio_url`; recordings include
  lecturer and nullable `original_audio`/`audio_url`. Versions add `preset`,
  `available`, `audio_url`, and `download_url`. No storage paths are exposed.

Audio-backed deletions return:

```json
{"id":"RESOURCE_UUID","deleted":true,"file_cleanup_pending":false}
```

If cleanup is pending, metadata deletion has committed but physical cleanup
needs reconciliation. `available` checks file existence; generation reuse also
checks size and decoded content.

## Error behavior

| Status | Typical meaning |
| --- | --- |
| 404 | Missing resource/file or sample/version under the wrong parent |
| 409 | Relationship conflict, busy recording, existing original, missing ready source, mismatched UUID retry |
| 413 | Request/upload/generated file too large |
| 415 | Unsupported format/codec |
| 422 | Invalid fields/audio, empty file, duration violation, probe timeout, generation validation failure |
| 503 | Database/storage/tool unavailable or generation capacity saturated |
| 504 | FFmpeg job timed out |

Errors use `detail`; DB driver messages/credentials are sanitized. Invalid
Content-Length can return 400. Parent scoping validates relationships, not
account authorization. See [architecture](architecture.md) for current limits.

## PowerShell usage example

Use disposable lecturer/audio data. These commands intentionally create saved
application data. Substitute an actual file path.

```powershell
$base = 'http://127.0.0.1:8000'
$lecturer = Invoke-RestMethod -Method Post "$base/api/lecturers" -ContentType 'application/json' -Body '{"name":"Dr. Example","department":"Computer Engineering"}'
curl.exe -X POST "$base/api/lecturers/$($lecturer.id)/samples" -F 'file=@C:/Audio/reference.wav' -F 'label=Reference sample'
$payload = @{ lecturer_id = $lecturer.id; title = 'DSP Lecture 1' } | ConvertTo-Json
$recording = Invoke-RestMethod -Method Post "$base/api/recordings" -ContentType 'application/json' -Body $payload
curl.exe -X POST "$base/api/recordings/$($recording.id)/audio" -F 'file=@C:/Audio/lecture.webm'
Invoke-RestMethod "$base/api/recordings?q=DSP&limit=20&offset=0"
$enhanced = Invoke-RestMethod -Method Post "$base/api/recordings/$($recording.id)/process"
$export = Invoke-RestMethod -Method Post "$base/api/recordings/$($recording.id)/exports"
Invoke-RestMethod "$base/api/recordings/$($recording.id)/versions"
Invoke-WebRequest "$base$($export.download_url)" -OutFile lecture.mp3
```

See [audio](audio.md) for presets/retries and [database](database/README.md) for
constraints and deletion ordering.
