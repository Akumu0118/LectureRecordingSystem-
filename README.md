# VoiceClean (MVP)

    backend/    Django + DRF, FFmpeg + noisereduce pipeline
    frontend/   Vue 3 + Vite

Run (two terminals; FFmpeg must be installed):

    cd backend  && pip install -r requirements.txt && python manage.py migrate && python manage.py runserver
    cd frontend && npm install && npm run dev

Open http://localhost:5173 (microphone access needs localhost or HTTPS).
