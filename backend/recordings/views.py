import logging
import mimetypes
import re
from pathlib import Path

from rest_framework import status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from voiceclean import pipeline

from . import services
from .errors import ApiError
from .models import Recording
from .files import file_response
from .serializers import RecordingCreateSerializer, RecordingSerializer

logger = logging.getLogger(__name__)

EXPORT_MIME = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "ogg": "audio/ogg",
    "m4a": "audio/mp4",
}


def _guess_mime(path: Path) -> str:
    if path.suffix.lower() == ".webm":
        return "audio/webm"
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def _safe_filename(title: str, fallback: str) -> str:
    cleaned = re.sub(r"[^\w\- ]+", "", title, flags=re.UNICODE).strip().replace(" ", "_")
    return cleaned[:80] or fallback


@api_view(["GET"])
def health(request):
    """Quick check that FFmpeg is available (the #1 setup problem)."""
    import shutil

    ffmpeg = shutil.which("ffmpeg") is not None
    ffprobe = shutil.which("ffprobe") is not None
    return Response({"ok": ffmpeg, "ffmpeg": ffmpeg, "ffprobe": ffprobe})


class RecordingViewSet(ModelViewSet):
    """
    POST   /api/recordings/                 upload + process
    GET    /api/recordings/                 list
    GET    /api/recordings/<id>/            detail 
    PATCH  /api/recordings/<id>/            edit title / subject / notes
    DELETE /api/recordings/<id>/            delete recording and its files
    GET    /api/recordings/<id>/audio/      ?version=original|processed[&download=1] (Range-enabled)
    GET    /api/recordings/<id>/export/     ?format=mp3|wav|ogg|m4a&version=processed|original
    POST   /api/recordings/<id>/reprocess/  retry processing
    """

    queryset = Recording.objects.all()
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_serializer_class(self):
        return RecordingCreateSerializer if self.action == "create" else RecordingSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recording = serializer.save()
        recording = services.process_recording(recording)
        data = RecordingSerializer(recording, context={"request": request}).data
        return Response(data, status=status.HTTP_201_CREATED)

    # -- helpers --------------------------------------------------------------
    def _source_path(self, recording: Recording, version: str) -> Path:
        if version == "original":
            return Path(recording.original.path)
        if version == "processed":
            if recording.status == Recording.Status.PROCESSING:
                raise ApiError("Still processing. Try again in a moment.", "not_ready", 409)
            path = services.processed_path(recording)
            if recording.status != Recording.Status.DONE or path is None:
                raise ApiError(
                    "No processed audio available. Retry processing or use the original.",
                    "not_ready",
                    409,
                )
            return path
        raise ApiError("version must be 'original' or 'processed'.", "bad_version")

    # -- actions --------------------------------------------------------------
    @action(detail=True, methods=["get"])
    def audio(self, request, pk=None):
        recording = self.get_object()
        version = request.query_params.get("version", "processed")
        path = self._source_path(recording, version)
        download_name = None
        if request.query_params.get("download"):
            download_name = _safe_filename(recording.title, str(recording.id)) + path.suffix
        return file_response(request, path, _guess_mime(path), download_name=download_name)

    @action(detail=True, methods=["get"])
    def export(self, request, pk=None):
        recording = self.get_object()
        fmt = request.query_params.get("format", "mp3").lower()
        version = request.query_params.get("version", "processed")
        if fmt not in pipeline.EXPORT_FORMATS:
            raise ApiError(
                f"Unsupported export format. Use one of: {', '.join(pipeline.EXPORT_FORMATS)}.",
                "bad_format",
            )
        source = self._source_path(recording, version)

        export_dir = services.recording_dir(recording) / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        ext = pipeline.EXPORT_FORMATS[fmt][0]
        target = export_dir / f"{version}.{ext}"
        if not target.exists():
            try:
                pipeline.export(source, export_dir / version, fmt)
            except pipeline.PipelineError as exc:
                logger.warning("Export failed for %s: %s", recording.id, exc)
                raise ApiError(
                    "Export failed. Try another format, or download the original.",
                    "export_failed",
                    500,
                )

        name = _safe_filename(recording.title, str(recording.id)) + f".{ext}"
        return file_response(request, target, EXPORT_MIME[fmt], download_name=name)

    @action(detail=True, methods=["post"])
    def reprocess(self, request, pk=None):
        recording = self.get_object()
        if recording.status == Recording.Status.PROCESSING:
            raise ApiError("Already processing.", "busy", 409)
        recording = services.process_recording(recording)
        data = RecordingSerializer(recording, context={"request": request}).data
        return Response(data)
