# VoiceClean backend (MVP)

One Django app (`recordings`) + one plain-Python pipeline file (`voiceclean/pipeline.py`).

## Run
    pip install -r requirements.txt      # FFmpeg must also be installed
    python manage.py migrate
    python manage.py runserver
    python manage.py test                # 21 tests

Check FFmpeg: GET http://localhost:8000/api/health/

## API
| Method | URL | What |
|---|---|---|
| POST | /api/recordings/ | multipart: `file`, optional `title`, `subject`, `notes` → processes, returns JSON |
| GET | /api/recordings/ | list |
| GET/PATCH/DELETE | /api/recordings/<id>/ | detail / edit details / delete |
| GET | /api/recordings/<id>/audio/?version=original\|processed[&download=1] | stream (seekable) or download |
| GET | /api/recordings/<id>/export/?format=mp3\|wav\|ogg\|m4a | download |
| POST | /api/recordings/<id>/reprocess/ | retry |

Errors are `{"error": "<friendly message>", "code": "..."}`.

Frontend tip: give the MediaRecorder blob a filename with an extension,
e.g. `new File([blob], "lecture.webm")`, or the upload is rejected.

Tune noise reduction: `VOICECLEAN_DENOISE_STRENGTH=0.6..1.0` (default 0.8).
