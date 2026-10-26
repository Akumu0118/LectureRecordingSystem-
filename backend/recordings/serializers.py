from pathlib import Path

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers

from .models import Recording
from .services import FRIENDLY_PROCESSING_ERROR

ALLOWED_EXTENSIONS = {
    ".wav", ".mp3", ".m4a", ".mp4", ".aac", ".ogg", ".oga", ".opus", ".webm", ".flac",
}
UNSUPPORTED_MESSAGE = "That file type isn't supported. Use WAV, MP3, M4A, OGG, or WebM."


class RecordingCreateSerializer(serializers.ModelSerializer):
    """Upload: a file plus optional lecture details."""

    file = serializers.FileField(write_only=True)

    class Meta:
        model = Recording
        fields = ["file", "title", "subject", "notes"]

    def validate_file(self, value):
        ext = Path(value.name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(UNSUPPORTED_MESSAGE)
        if value.size == 0:
            raise serializers.ValidationError("The recording is empty. Try recording again.")
        max_mb = settings.VOICECLEAN_MAX_UPLOAD_MB
        if value.size > max_mb * 1024 * 1024:
            raise serializers.ValidationError(f"File is too large (max {max_mb} MB).")
        return value

    def create(self, validated_data):
        upload = validated_data.pop("file")
        if not validated_data.get("title"):
            stamp = timezone.localtime().strftime("%Y-%m-%d %H:%M")
            validated_data["title"] = f"Lecture {stamp}"
        return Recording.objects.create(original=upload, **validated_data)


class RecordingSerializer(serializers.ModelSerializer):
    """Read everything; only lecture details are editable."""

    original_url = serializers.SerializerMethodField()
    processed_url = serializers.SerializerMethodField()
    error = serializers.SerializerMethodField()
    error_detail = serializers.SerializerMethodField()

    class Meta:
        model = Recording
        fields = [
            "id", "title", "subject", "notes", "status", "duration",
            "error", "error_detail", "original_url", "processed_url",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "status", "duration", "created_at", "updated_at"]

    def _audio_url(self, obj, version):
        request = self.context.get("request")
        url = reverse("recording-audio", args=[obj.id]) + f"?version={version}"
        return request.build_absolute_uri(url) if request else url

    def get_original_url(self, obj):
        return self._audio_url(obj, "original")

    def get_processed_url(self, obj):
        if obj.status != Recording.Status.DONE:
            return None
        return self._audio_url(obj, "processed")

    def get_error(self, obj):
        return FRIENDLY_PROCESSING_ERROR if obj.status == Recording.Status.FAILED else ""

    def get_error_detail(self, obj):
        # Technical detail is only exposed while developing.
        return obj.error if settings.DEBUG and obj.error else ""
