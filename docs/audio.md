# Audio validation, processing, and storage

Audio bytes are stored locally; PostgreSQL stores their ownership and technical
metadata. Originals and reference samples are preserved. Enhancement and MP3
export create separate derivative versions from the original lecture.

## Upload validation

[`reference_storage.py`](../backend/app/services/reference_storage.py) stages and
validates uploads; `RecordingStorage` reuses it with lecture-specific limits.

| Extension | Verified container/codec | Stored MIME |
| --- | --- | --- |
| `.wav` | WAV with PCM codec | `audio/wav` |
| `.mp3` | MP3 container and codec | `audio/mpeg` |
| `.webm` | WebM/Matroska demuxer with Opus or Vorbis | `audio/webm` |

FFprobe decodes/inspects frames with restricted demuxers and the local-file
protocol. Exactly one audio stream is accepted; video/mixed or multiple streams
are rejected. The WebM demuxer is shared with Matroska; no independent EBML
DocType restriction is imposed. Extension must match validated content. Client
MIME alone never establishes validity. MP4/M4A is not supported.

Empty/corrupt files, unsupported codecs, invalid filenames, excessive size, and
nonpositive/excessive duration are rejected. Names must be plain filenames,
without paths, separators, invalid filename characters, control characters,
leading/trailing whitespace, or more than 255 characters.

Browser WebM may lack duration headers. Validation uses decoded sample counts,
frame timestamps, and available stream/container duration, taking the maximum.
Duration is stored to millisecond precision. Upload bytes are not converted.

File bytes are counted in 64 KiB chunks. ASGI middleware also counts request
bytes before unrestricted multipart spooling, allowing 64 KiB of multipart
overhead beyond the file limit. Accepted multipart input may still spool to
framework temporary storage before the synchronous handler runs.

| Default | Reference | Lecture |
| --- | --- | --- |
| Maximum upload | 10 MiB | 512 MiB |
| Maximum duration | 120 seconds | 14,400 seconds (4 hours) |
| FFprobe timeout | 30 seconds | 180 seconds |
| Probe output cap | 32 MiB | 256 MiB |

Probe output uses temporary disk files, not accumulated memory. Output caps are
checked after bounded execution; these are not OS-level resource quotas. See
[settings](setup.md#configuration-reference) for overrides.

## Fixed enhancement preset

[`audio_jobs.py`](../backend/app/services/audio_jobs.py) applies this exact chain:

```text
highpass=f=80,lowpass=f=7000,afftdn=nr=6:nf=-35,loudnorm=I=-18:TP=-1.5:LRA=11
```

| Stage | Purpose and configured value |
| --- | --- |
| High-pass | 80 Hz cutoff to reduce low rumble |
| Low-pass | 7 kHz cutoff to limit high-frequency content |
| FFT denoising | 6 dB noise reduction with fixed -35 dB noise floor |
| Loudness normalization | Single-pass targets: -18 LUFS, -1.5 dBTP, 11 LU loudness range |
| Output encoding | Mono, 16 kHz signed 16-bit PCM WAV (`pcm_s16le`) |

These are processing targets, not measured guarantees for every recording. The
output is explicitly resampled after loudness processing. This optional non-AI
preset may help steady noise/rumble, but can change timbre or raise remaining
noise. It cannot identify a lecturer or reliably separate overlapping speech.
Reference samples are not supplied to enhancement. Subjective improvement must
be assessed by listening to real original/enhanced lectures.

## MP3 export and version reuse

MP3 export uses the original, `libmp3lame`, constant 64 kbit/s, mono, 32 kHz,
audio-only output. It is a lossy speech delivery version, not an enhanced MP3.

Preset identity is stored in server-generated filename metadata:
`speech-enhance-v1.wav` and `speech-mp3-v1.mp3`. Physical filenames are UUIDs.
Repeated generation requests reuse a matching valid version after checking
existence, size, and FFprobe decoding. Future preset changes must update the
identity marker. Missing/corrupt derivatives can be replaced transactionally;
older/unrecognized outputs remain distinct. A cached valid output can be reused
if the original later disappears; new generation requires a valid original.

Input is validated before FFmpeg. Output is decoded again, checked for size,
duration, and agreement with source duration before registration. Commands use
fixed argument lists, no shell interpolation, restricted demuxers/protocols,
audio-only mapping, metadata stripping, and `-nostdin`/`-xerror`.

Generation holds a recording `FOR UPDATE NOWAIT` lock through validation and
commit. A process-local semaphore defaults to two jobs (configurable 1-8), one
codec/filter thread per job, a 600-second FFmpeg timeout, and a 512 MiB generated
output limit. Use one Uvicorn worker. There is no durable queue or percentage
progress; the UI reports a truthful busy state. Total request time also includes
probing and database/file work; the frontend waits up to 20 minutes.

## Storage layout

```text
backend/storage/
  references/    references/<uuid>.wav|mp3|webm
  recordings/    recordings/<uuid>.wav|mp3|webm
  processed/     processed/<uuid>.wav
  exports/       exports/<uuid>.mp3
```

The root is configurable. PostgreSQL stores only relative paths. Staging files
stay inside the destination directory; final UUID files are created exclusively,
not overwritten. Persisted paths are resolved/checked for traversal and outside
root targets before playback/deletion. Storage is never publicly mounted;
recording/lecturer-scoped file endpoints serve audio and attachment downloads.
The local app owner must control storage directories; this is not protection
against malicious concurrent local filesystem tampering.

## Cleanup and recovery

Database/file writes are coordinated as described in
[architecture](architecture.md#transactions-and-concurrency). Newly written files
are cleaned after confirmed non-commit. A lost COMMIT response is reconciled by
audio ID; uncertain files are retained instead of risking live references.
Deletion commits metadata removal before unlinking physical audio. A failed
unlink returns `file_cleanup_pending` or logs a recoverable leftover.

Crashes can leave `.upload-*`, `.job-*`, or unreferenced UUID files. There is no
automatic cleanup worker. Before manual cleanup, stop uploads/jobs, back up DB
and storage, resolve uncertain commits, and compare candidates with **all**
`audio_files.storage_path` rows. Remove only confirmed unreferenced files. Never
remove a referenced original or sample. A missing original must be recovered
from backup or explicitly recreated by the user; it is not silently replaced.
Playback and deletion can race; refresh/retry when a selected file disappears.
