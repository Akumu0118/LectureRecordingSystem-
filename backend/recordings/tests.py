import io
import shutil
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from recordings.models import Recording
from voiceclean import pipeline


def make_lecture_wav(seconds=6, sr=16_000, noise_level=0.03, seed=0, return_clean=False):
    """Speech-like synthetic lecture: wobbling-pitch harmonic voice + white noise.

    Layout: 1s noise only | voiced middle | 1s noise only.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * sr)) / sr
    f0 = 120 + 15 * np.sin(2 * np.pi * 0.7 * t)  # intonation
    phase = 2 * np.pi * np.cumsum(f0) / sr
    voice = sum(np.sin(k * phase) / k for k in range(1, 31))  # broadband harmonics
    voice = voice * 0.12 * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 2.5 * t)))  # syllables
    gate = ((t > 1.0) & (t < seconds - 1.0)).astype(float)
    clean = (voice * gate).astype("float32")
    mix = (clean + rng.normal(0, noise_level, size=t.shape)).astype("float32")
    return (mix, clean) if return_clean else mix


def si_sdr(estimate: np.ndarray, reference: np.ndarray) -> float:
    """Scale-invariant SDR in dB (higher = closer to the clean reference)."""
    ref = reference - reference.mean()
    est = estimate - estimate.mean()
    target = (est @ ref) / (ref @ ref) * ref
    err = est - target
    return float(10 * np.log10((target @ target) / (err @ err + 1e-12)))


def wav_bytes(audio: np.ndarray, sr=16_000, channels=1) -> bytes:
    buf = io.BytesIO()
    data = np.stack([audio] * channels, axis=1) if channels > 1 else audio
    sf.write(buf, data, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def rms(x) -> float:
    return float(np.sqrt(np.mean(np.square(x))))


class PipelineTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def test_denoise_improves_si_sdr_and_cuts_noise(self):
        sr = 16_000
        mix, clean = make_lecture_wav(sr=sr, return_clean=True)
        src, dst = self.tmp / "in.wav", self.tmp / "out.wav"
        sf.write(src, mix, sr, subtype="PCM_16")

        pipeline.denoise(src, dst)
        cleaned, _ = sf.read(dst, dtype="float32")

        voiced = slice(int(2.0 * sr), int(4.0 * sr))
        noise_only = slice(0, sr)
        improvement = si_sdr(cleaned[voiced], clean[voiced]) - si_sdr(mix[voiced], clean[voiced])
        noise_drop_db = 20 * np.log10(rms(mix[noise_only]) / rms(cleaned[noise_only]))

        self.assertGreater(improvement, 1.5, f"SI-SDR gain only {improvement:.1f} dB")
        self.assertGreater(noise_drop_db, 6, f"noise drop only {noise_drop_db:.1f} dB")
        # sanity: the voice must not be wiped out (level is restored later by loudnorm)
        self.assertGreater(rms(cleaned[voiced]) / rms(mix[voiced]), 0.25)

    def test_full_process_outputs_16k_mono_wav(self):
        src = self.tmp / "stereo44k.wav"
        audio = make_lecture_wav(sr=44_100)
        src.write_bytes(wav_bytes(audio, sr=44_100, channels=2))

        final = pipeline.process(src, self.tmp / "work")
        info = sf.info(final)
        self.assertEqual((info.samplerate, info.channels), (16_000, 1))
        self.assertAlmostEqual(pipeline.wav_duration(final), 6.0, delta=0.1)
        # temp stages cleaned up
        self.assertEqual(sorted(p.name for p in (self.tmp / "work").iterdir()), ["processed.wav"])

    def test_export_formats(self):
        src = self.tmp / "a.wav"
        sf.write(src, make_lecture_wav(seconds=2), 16_000, subtype="PCM_16")
        for fmt in pipeline.EXPORT_FORMATS:
            out = pipeline.export(src, self.tmp / "out", fmt)
            self.assertTrue(out.exists() and out.stat().st_size > 0, fmt)

    def test_unsupported_export_format(self):
        with self.assertRaises(pipeline.PipelineError):
            pipeline.export(self.tmp / "x.wav", self.tmp / "out", "flac9000")

    def test_corrupt_input_raises_pipeline_error(self):
        bad = self.tmp / "bad.wav"
        bad.write_bytes(b"this is not audio" * 100)
        with self.assertRaises(pipeline.PipelineError):
            pipeline.process(bad, self.tmp / "work")


class ApiTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media)
        override.enable()
        self.addCleanup(override.disable)
        self.client = APIClient()

    def upload(self, name="lecture.wav", content=None, **extra):
        content = content if content is not None else wav_bytes(make_lecture_wav())
        return self.client.post(
            "/api/recordings/",
            {"file": SimpleUploadedFile(name, content, content_type="audio/wav"), **extra},
            format="multipart",
        )

    def test_health(self):
        res = self.client.get("/api/health/")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["ffmpeg"])

    def test_upload_processes_and_returns_urls(self):
        res = self.upload(title="Signals 101", subject="ECE 301", notes="week 3")
        self.assertEqual(res.status_code, 201, res.content)
        body = res.json()
        self.assertEqual(body["status"], "done")
        self.assertEqual(body["title"], "Signals 101")
        self.assertAlmostEqual(body["duration"], 6.0, delta=0.1)
        self.assertIn("version=processed", body["processed_url"])
        self.assertEqual(body["error"], "")

    def test_default_title_when_missing(self):
        body = self.upload().json()
        self.assertTrue(body["title"].startswith("Lecture "))

    def test_unsupported_file_type(self):
        res = self.upload(name="notes.txt", content=b"hello")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["error"], "That file type isn't supported. Use WAV, MP3, M4A, OGG, or WebM.")
        self.assertEqual(Recording.objects.count(), 0)

    def test_empty_file_rejected(self):
        res = self.upload(content=b"")
        self.assertEqual(res.status_code, 400)

    def test_corrupt_audio_fails_gracefully_and_keeps_original(self):
        res = self.upload(content=b"definitely not a wav" * 200)
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertEqual(body["status"], "failed")
        self.assertEqual(
            body["error"],
            "Processing failed. Your original recording is safe. Retry or download it.",
        )
        self.assertIsNone(body["processed_url"])
        # original is still downloadable
        original = self.client.get(f"/api/recordings/{body['id']}/audio/?version=original")
        self.assertEqual(original.status_code, 200)
        # processed isn't available -> 409 with a clear message
        processed = self.client.get(f"/api/recordings/{body['id']}/audio/?version=processed")
        self.assertEqual(processed.status_code, 409)
        self.assertEqual(processed.json()["code"], "not_ready")

    def test_audio_range_request_for_seeking(self):
        rec = self.upload().json()
        res = self.client.get(
            f"/api/recordings/{rec['id']}/audio/?version=processed", HTTP_RANGE="bytes=0-99"
        )
        self.assertEqual(res.status_code, 206)
        self.assertEqual(len(b"".join(res.streaming_content)), 100)
        self.assertTrue(res["Content-Range"].startswith("bytes 0-99/"))
        self.assertEqual(res["Accept-Ranges"], "bytes")

    def test_range_out_of_bounds(self):
        rec = self.upload().json()
        res = self.client.get(
            f"/api/recordings/{rec['id']}/audio/", HTTP_RANGE="bytes=99999999-"
        )
        self.assertEqual(res.status_code, 416)

    def test_export_mp3_and_wav(self):
        rec = self.upload(title="Intro to DSP!").json()
        mp3 = self.client.get(f"/api/recordings/{rec['id']}/export/?format=mp3")
        self.assertEqual(mp3.status_code, 200)
        self.assertEqual(mp3["Content-Type"], "audio/mpeg")
        self.assertIn('filename="Intro_to_DSP.mp3"', mp3["Content-Disposition"])
        head = next(iter(mp3.streaming_content))[:3]
        self.assertTrue(head == b"ID3" or head[0] == 0xFF, head)

        wav = self.client.get(f"/api/recordings/{rec['id']}/export/?format=wav")
        self.assertEqual(wav.status_code, 200)
        self.assertEqual(next(iter(wav.streaming_content))[:4], b"RIFF")

    def test_download_original_has_attachment_header(self):
        rec = self.upload(title="Raw Lecture").json()
        res = self.client.get(f"/api/recordings/{rec['id']}/audio/?version=original&download=1")
        self.assertEqual(res.status_code, 200)
        self.assertIn('filename="Raw_Lecture.wav"', res["Content-Disposition"])
        inline = self.client.get(f"/api/recordings/{rec['id']}/audio/?version=original")
        self.assertNotIn("Content-Disposition", inline)

    def test_export_failure_message_is_friendly(self):
        rec = self.upload(content=b"not audio at all" * 200).json()
        res = self.client.get(f"/api/recordings/{rec['id']}/export/?format=wav&version=original")
        self.assertEqual(res.status_code, 500)
        self.assertEqual(res.json()["code"], "export_failed")
        self.assertNotIn("ffmpeg", res.json()["error"].lower())

    def test_export_bad_format(self):
        rec = self.upload().json()
        res = self.client.get(f"/api/recordings/{rec['id']}/export/?format=exe")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["code"], "bad_format")

    def test_patch_details_only(self):
        rec = self.upload().json()
        res = self.client.patch(
            f"/api/recordings/{rec['id']}/",
            {"title": "Renamed", "status": "failed"},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["title"], "Renamed")
        self.assertEqual(res.json()["status"], "done")  # read-only field ignored

    def test_reprocess_recovers_failed_recording(self):
        rec = self.upload().json()
        obj = Recording.objects.get(pk=rec["id"])
        # simulate a crash that left the recording failed
        obj.status = Recording.Status.FAILED
        obj.save()
        res = self.client.post(f"/api/recordings/{rec['id']}/reprocess/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "done")

    def test_delete_removes_files(self):
        rec = self.upload().json()
        folder = Path(self.media) / "recordings" / rec["id"]
        self.assertTrue(folder.exists())
        self.assertEqual(self.client.delete(f"/api/recordings/{rec['id']}/").status_code, 204)
        self.assertFalse(folder.exists())

    def test_list_newest_first(self):
        first = self.upload(title="A").json()
        second = self.upload(title="B").json()
        ids = [r["id"] for r in self.client.get("/api/recordings/").json()]
        self.assertEqual(ids, [second["id"], first["id"]])
