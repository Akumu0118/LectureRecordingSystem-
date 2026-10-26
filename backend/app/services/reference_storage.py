"""Bounded local reference storage and FFprobe validation. No audio conversion."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import logging
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
from uuid import uuid4

from fastapi import HTTPException, UploadFile

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)
FORMATS = {
    ".wav": ("wav", "audio/wav"),
    ".mp3": ("mp3", "audio/mpeg"),
    ".webm": ("webm", "audio/webm"),
}


@dataclass(frozen=True)
class StoredReference:
    relative_path: str
    original_filename: str
    mime_type: str
    size: int
    duration: Decimal
    sample_rate: int
    channels: int


class ReferenceStorage:
    directory = "references"
    allowed_directories = {"references"}
    kind = "Reference"

    @property
    def max_size(self):
        return self.settings.max_reference_size_bytes

    @property
    def max_duration(self):
        return self.settings.max_reference_duration_seconds

    @property
    def probe_timeout(self):
        return self.settings.ffprobe_timeout_seconds

    probe_output_limit = 32 * 1024 * 1024

    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.storage_root.resolve()
        self.references = (self.root / self.directory).resolve()
        if not self.references.is_relative_to(self.root):
            raise HTTPException(503, "Reference storage is unavailable")

    def path(self, relative_path: str) -> Path:
        relative = PurePosixPath(relative_path)
        if ("\\" in relative_path or relative.is_absolute()
                or len(relative.parts) != 2 or relative.parts[0] not in self.allowed_directories
                or relative.parts[1] in {".", ".."}):
            raise HTTPException(503, "Stored reference path is invalid")
        result = (self.root / relative).resolve()
        directory = (self.root / relative.parts[0]).resolve()
        if (not directory.is_relative_to(self.root) or not result.is_relative_to(directory)
                or result == directory):
            raise HTTPException(503, "Stored reference path is invalid")
        return result

    def cleanup(self, relative_path: str) -> bool:
        """Never hide a committed deletion; report a retryable leftover instead."""
        try:
            self.path(relative_path).unlink(missing_ok=True)
            return True
        except (OSError, HTTPException):
            logger.warning("Reference file cleanup pending for %r", relative_path)
            return False

    def prepare(self, upload: UploadFile) -> StoredReference:
        filename = upload.filename or ""
        if (not filename or len(filename) > 255 or filename != filename.strip()
                or any(char in '<>:"/\\|?*' or ord(char) < 32 or ord(char) == 127 for char in filename)
                or filename.endswith(".")):
            raise HTTPException(422, "Provide a plain audio filename without paths or control characters")
        suffix = Path(filename).suffix.lower()
        if suffix not in FORMATS:
            raise HTTPException(415, "Supported reference formats are WAV, MP3, and WebM")
        relative = f"{self.directory}/{uuid4()}{suffix}"
        final = self.path(relative)
        staged = None
        created = False
        try:
            self.references.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=self.references, prefix=".upload-", suffix=".tmp", delete=False) as output:
                staged = Path(output.name)
                size = 0
                upload.file.seek(0)
                while chunk := upload.file.read(64 * 1024):
                    size += len(chunk)
                    if size > self.max_size:
                        raise HTTPException(413, f"{self.kind} audio exceeds the configured file size limit")
                    output.write(chunk)
            if size == 0:
                raise HTTPException(422, f"{self.kind} audio is empty")
            duration, rate, channels = self.probe(staged, suffix)
            # Exclusive creation prevents collisions from overwriting another file.
            with final.open("xb") as output, staged.open("rb") as source:
                created = True
                shutil.copyfileobj(source, output, length=64 * 1024)
            return StoredReference(relative, filename, FORMATS[suffix][1], size, duration, rate, channels)
        except Exception as exc:
            if created:
                self.cleanup(relative)
            if isinstance(exc, OSError):
                raise HTTPException(503, "Reference storage is unavailable") from None
            raise
        finally:
            if staged is not None:
                try:
                    staged.unlink(missing_ok=True)
                except OSError:
                    logger.warning("Temporary reference cleanup pending for %s", staged.name)

    def probe(self, path: Path, suffix: str) -> tuple[Decimal, int, int]:
        executable = shutil.which(self.settings.ffprobe_path)
        if executable is None:
            raise HTTPException(503, "FFprobe is unavailable; configure FFPROBE_PATH or restart your terminal")
        # Decode audio frames, including browser WebM without a duration header.
        # Restricted demuxers/protocols prevent playlists and network references.
        command = [
            executable, "-v", "error", "-protocol_whitelist", "file",
            "-format_whitelist", "wav,mp3,matroska,webm", "-show_frames",
            "-show_entries", "frame=media_type,best_effort_timestamp_time,nb_samples:"
            "stream=codec_type,codec_name,sample_rate,channels,duration:format=format_name,duration",
            "-of", "compact=p=1:nk=0", str(path),
        ]
        try:
            # Keep potentially large frame output on disk rather than in RAM.
            with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
                result = subprocess.run(command, stdout=output, stderr=errors,
                                        timeout=self.probe_timeout, check=False)
                if result.returncode or errors.tell() or output.tell() > self.probe_output_limit:
                    raise HTTPException(422, "Audio could not be validated")
                output.seek(0)
                streams, formats, durations = [], [], []
                samples = 0
                first_stamp = None
                last_frame = None
                for raw in output:
                    parts = raw.decode("utf-8").strip().split("|")
                    values = dict(part.split("=", 1) for part in parts[1:] if "=" in part)
                    if parts[0] == "stream":
                        streams.append(values)
                    elif parts[0] == "format":
                        formats = values.get("format_name", "").split(",")
                    elif parts[0] == "frame":
                        if values.get("media_type") != "audio":
                            raise HTTPException(415, "Reference uploads must contain audio only")
                        count = int(values.get("nb_samples", "0"))
                        samples += count
                        stamp = values.get("best_effort_timestamp_time", "N/A")
                        if stamp != "N/A":
                            point = Decimal(stamp)
                            if not point.is_finite():
                                raise ValueError
                            first_stamp = point if first_stamp is None else min(first_stamp, point)
                            if last_frame is None or point > last_frame[0]:
                                last_frame = (point, count)
                    duration = values.get("duration", "N/A")
                    if parts[0] in {"stream", "format"} and duration != "N/A":
                        number = Decimal(duration)
                        if not number.is_finite():
                            raise ValueError
                        durations.append(number)
                if (len(streams) != 1 or streams[0].get("codec_type") != "audio"
                        or FORMATS[suffix][0] not in formats or samples <= 0):
                    raise HTTPException(415, "Audio content does not match a supported audio-only format")
                stream = streams[0]
                codec = stream.get("codec_name", "")
                if not ((suffix == ".wav" and codec.startswith("pcm_"))
                        or (suffix == ".mp3" and codec == "mp3")
                        or (suffix == ".webm" and codec in {"opus", "vorbis"})):
                    raise HTTPException(415, "Unsupported audio codec for this format")
                rate, channels = int(stream["sample_rate"]), int(stream["channels"])
                if rate <= 0 or channels <= 0:
                    raise ValueError
                durations.append(Decimal(samples) / rate)
                if first_stamp is not None and last_frame:
                    durations.append(last_frame[0] + Decimal(last_frame[1]) / rate - first_stamp)
                duration = max(durations)
                if duration <= 0:
                    raise HTTPException(422, "Audio must have a positive duration")
                if duration > Decimal(str(self.max_duration)):
                    raise HTTPException(422, f"{self.kind} audio exceeds the configured duration limit")
                return max(duration.quantize(Decimal("0.001")), Decimal("0.001")), rate, channels
        except subprocess.TimeoutExpired:
            raise HTTPException(422, "Audio validation timed out") from None
        except OSError:
            raise HTTPException(503, "FFprobe could not be executed") from None
        except (ValueError, KeyError, InvalidOperation, UnicodeError):
            raise HTTPException(422, "Audio metadata is invalid") from None


def get_reference_storage() -> ReferenceStorage:
    return ReferenceStorage(get_settings())
