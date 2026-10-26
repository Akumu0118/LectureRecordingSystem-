"""Additional real speech integration, using only private schema/temp storage."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from tests.server_process import live_api


def test_synthetic_speech_vue_workflow_across_api_restart(api):
    # Windows provides this synthesizer; no package or microphone is installed/used.
    if os.name != "nt" or not shutil.which("powershell.exe"):
        pytest.skip("Synthetic spoken fixture requires Windows System.Speech")
    asset = api.settings.storage_root / "qa-spoken-fixture.wav"
    assert asset.resolve().is_relative_to(api.settings.storage_root.resolve())
    env = os.environ.copy()
    env["VOICECLEAN_QA_SPEECH_WAV"] = str(asset)
    script = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$qaSpeech = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $qaSpeech.SetOutputToWaveFile($env:VOICECLEAN_QA_SPEECH_WAV)
    $qaSpeech.Speak('This is a disposable VoiceClean test lecture. Signals and systems describe how information changes over time. Save the original, compare the enhanced recording, and export an MP3 for review.')
} finally { $qaSpeech.Dispose() }
'''
    result = subprocess.run([shutil.which("powershell.exe"), "-NoProfile", "-NonInteractive", "-Command", script],
                            env=env, capture_output=True, timeout=45,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert result.returncode == 0, "Windows spoken fixture synthesis failed"
    assert asset.is_file() and asset.stat().st_size > 1000
    duration, _, _ = api.recording_storage.probe(asset, ".wav")
    assert 2 < float(duration) < 120
    node = shutil.which("node")
    assert node, "Node.js is required for the Vue/API integration workflow"
    artifact = api.settings.storage_root / "qa-spoken-ids.json"
    root = Path(__file__).resolve().parents[2]
    for mode in ["save", "restore"]:
        with live_api(api) as client:
            env.update({"VOICECLEAN_TEST_API_BASE_URL": str(client.base_url).rstrip('/'),
                        "VOICECLEAN_TEST_MODE": mode, "VOICECLEAN_TEST_AUDIO_FILE": str(asset),
                        "VOICECLEAN_TEST_IDS_FILE": str(artifact)})
            result = subprocess.run([node, "--test", "tests/integration/liveState.test.js"],
                cwd=root / "frontend", env=env, capture_output=True, text=True, timeout=90,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            assert result.returncode == 0, result.stdout + result.stderr
