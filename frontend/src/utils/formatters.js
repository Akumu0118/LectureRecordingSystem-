export function formatDuration(value) {
  if (value === null || value === undefined || value === '') return 'Duration unavailable'
  const seconds = Number(value)
  if (!Number.isFinite(seconds) || seconds < 0) return 'Duration unavailable'
  if (seconds > 0 && seconds < 1) return '<1 sec'
  const whole = Math.round(seconds)
  const hours = Math.floor(whole / 3600)
  const minutes = Math.floor((whole % 3600) / 60)
  const tail = String(whole % 60).padStart(2, '0')
  return hours ? `${hours}:${String(minutes).padStart(2, '0')}:${tail}` : `${minutes}:${tail}`
}

export function formatDate(value) {
  if (!value || !Number.isFinite(new Date(value).getTime())) return 'Date unavailable'
  return new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}
