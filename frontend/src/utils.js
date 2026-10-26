// Small pure helpers (no Vue, no DOM) so they are easy to test.

export function formatDuration(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds || 0))
  return [Math.floor(s / 3600), Math.floor((s % 3600) / 60), s % 60]
    .map(v => String(v).padStart(2, '0'))
    .join(':')
}

export function formatBytes(bytes) {
  if (!bytes) return '0 KB'
  return bytes < 1048576
    ? `${(bytes / 1024).toFixed(1)} KB`
    : `${(bytes / 1048576).toFixed(2)} MB`
}

// The backend validates uploads by file extension, so the blob needs a real one.
export function extensionFor(mimeType = '') {
  if (mimeType.includes('mp4') || mimeType.includes('aac')) return 'm4a'
  if (mimeType.includes('ogg')) return 'ogg'
  if (mimeType.includes('wav')) return 'wav'
  if (mimeType.includes('mpeg')) return 'mp3'
  return 'webm'
}

export function safeFilename(value, fallback = 'lecture') {
  return (value || '').trim().replace(/[^\w-]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 80) || fallback
}

// Friendly messages for the failures people actually hit.
export function micErrorMessage(err) {
  switch (err?.name) {
    case 'NotAllowedError':
    case 'SecurityError':
      return 'Microphone access was blocked. Click the lock icon in the address bar and allow the microphone.'
    case 'NotFoundError':
    case 'OverconstrainedError':
      return 'No microphone detected. Connect one and try again.'
    case 'NotReadableError':
    case 'AbortError':
      return 'Your microphone is being used by another app.'
    default:
      return err?.message || 'Could not access the microphone.'
  }
}
