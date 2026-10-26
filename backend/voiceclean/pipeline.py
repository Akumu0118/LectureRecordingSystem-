"""
VoiceClean audio pipeline.

Deliberately has NO web-framework imports so it can be run from a script,
benchmarked, or reused when you swap in speaker extraction (Phase 3/4).

Stages (MVP):
    normalize()    any browser/upload format -> 16 kHz mono WAV
    denoise()      DSP noise reduction (noisereduce)
    post_process() 80 Hz high-pass + loudness normalization
    export()       WAV -> mp3 / wav / ogg / m4a

Phase 3/4 will add an `extract_speaker()` stage between denoise and post_process.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import noisereduce as nr
import numpy as np
import soundfile as sf

SAMPLE_RATE = 16_000
# 0-1. Higher = quieter background but more risk of artifacts on the voice.
DENOISE_STRENGTH = float(os.environ.get("VOICECLEAN_DENOISE_STRENGTH", "0.8"))

# format -> (file extension, ffmpeg codec args)
EXPORT_FORMATS: dict[str, tuple[str, list[str]]] = {
    "mp3": ("mp3", ["-c:a", "libmp3lame", "-b:a", "192k"]),
    "wav": ("wav", ["-c:a", "pcm_s16le"]),
    "ogg": ("ogg", ["-c:a", "libvorbis", "-q:a", "5"]),
    "m4a": ("m4a", ["-c:a", "aac", "-b:a", "192k"]),
}


class PipelineError(Exception):
    """Raised when any pipeline stage fails."""


def _run_ffmpeg(args: list[str]) -> None:
    if shutil.which("ffmpeg") is None:
        raise PipelineError("FFmpeg is not installed or not on PATH.")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise PipelineError(f"FFmpeg failed: {result.stderr.strip()[-500:]}")


def wav_duration(path: str | Path) -> float:
    """Exact duration of a WAV file in seconds (reliable, no ffprobe needed)."""
    try:
        info = sf.info(str(path))
    except Exception as exc:  # soundfile raises RuntimeError / LibsndfileError
        raise PipelineError(f"Could not read audio file: {exc}")
    return info.frames / info.samplerate


def normalize(src: str | Path, dst: str | Path) -> Path:
    """Convert any input to 16 kHz mono 16-bit PCM WAV."""
    dst = Path(dst)
    _run_ffmpeg([
        "-i", str(src), "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE),
        "-c:a", "pcm_s16le", str(dst),
    ])
    if not dst.exists() or dst.stat().st_size == 0:
        raise PipelineError("Normalization produced an empty file.")
    return dst


def _estimate_noise_clip(audio: np.ndarray, sr: int) -> np.ndarray:
    """
    Build a noise sample from the quietest ~10% of the recording.

    Lectures rarely have a clean "silence only" intro, so instead of assuming one
    we collect the lowest-energy 32 ms frames (pauses between sentences, room
    tone) from anywhere in the file and concatenate them.
    """
    frame = int(0.032 * sr)
    n_frames = len(audio) // frame
    min_samples = int(0.5 * sr)
    if n_frames < 4 or len(audio) < 2 * min_samples:
        return audio  # too short to be selective; use everything
    frames = audio[: n_frames * frame].reshape(n_frames, frame)
    energy = np.sqrt((frames ** 2).mean(axis=1))
    keep = max(int(n_frames * 0.10), -(-min_samples // frame))  # >= 0.5 s of frames
    quietest = np.argsort(energy)[:keep]
    return frames[np.sort(quietest)].reshape(-1)


def denoise(src: str | Path, dst: str | Path, strength: float | None = None) -> Path:
    """
    Spectral-gating noise reduction with an automatically estimated noise profile.

    `strength` is prop_decrease (0-1): higher removes more noise but risks
    "underwater" artifacts on the voice. Tune on real lecture recordings.

    Note: stationary=True (fixed noise profile) is used on purpose. The
    non-stationary mode adapts to a ~2 s moving average, which treats sustained
    speech as background and suppresses the lecturer.
    """
    strength = DENOISE_STRENGTH if strength is None else strength
    audio, sr = sf.read(str(src), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if audio.size == 0:
        raise PipelineError("Audio file is empty.")

    cleaned = nr.reduce_noise(
        y=audio,
        sr=sr,
        y_noise=_estimate_noise_clip(audio, sr),
        stationary=True,
        prop_decrease=strength,
    )
    cleaned = np.clip(cleaned, -1.0, 1.0).astype("float32")
    sf.write(str(dst), cleaned, sr, subtype="PCM_16")
    return Path(dst)


def post_process(src: str | Path, dst: str | Path) -> Path:
    """80 Hz high-pass (rumble/handling noise) + EBU R128 loudness normalization."""
    dst = Path(dst)
    _run_ffmpeg([
        "-i", str(src),
        "-af", "highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(dst),
    ])
    return dst


def export(src: str | Path, dst_stem: str | Path, fmt: str) -> Path:
    """Encode a WAV into the requested format. Returns the output path."""
    fmt = fmt.lower()
    if fmt not in EXPORT_FORMATS:
        raise PipelineError(
            f"Unsupported export format '{fmt}'. Use one of: {', '.join(EXPORT_FORMATS)}."
        )
    ext, codec_args = EXPORT_FORMATS[fmt]
    dst = Path(f"{dst_stem}.{ext}")
    _run_ffmpeg(["-i", str(src), "-vn", *codec_args, str(dst)])
    return dst


def process(src: str | Path, workdir: str | Path, out_name: str = "processed") -> Path:
    """
    Run the full MVP pipeline and return the path of the processed 16 kHz WAV.
    Intermediate files are cleaned up; only the final WAV remains in `workdir`.
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    normalized = workdir / f"{out_name}.normalized.wav"
    denoised = workdir / f"{out_name}.denoised.wav"
    final = workdir / f"{out_name}.wav"

    try:
        normalize(src, normalized)
        denoise(normalized, denoised)
        post_process(denoised, final)
    finally:
        normalized.unlink(missing_ok=True)
        denoised.unlink(missing_ok=True)
    return final
