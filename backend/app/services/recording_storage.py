from app.core.config import get_settings
from app.services.reference_storage import ReferenceStorage


class RecordingStorage(ReferenceStorage):
    """Reuse validated byte-preserving storage with separate lecture limits."""

    directory = "recordings"
    allowed_directories = {"recordings", "exports", "processed"}
    kind = "Lecture"
    probe_output_limit = 256 * 1024 * 1024

    @property
    def max_size(self):
        return self.settings.max_recording_size_bytes

    @property
    def max_duration(self):
        return self.settings.max_recording_duration_seconds

    @property
    def probe_timeout(self):
        return self.settings.recording_probe_timeout_seconds


def get_recording_storage() -> RecordingStorage:
    return RecordingStorage(get_settings())
