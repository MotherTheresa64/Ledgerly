export function localDateISO(value = new Date()) {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function withAsOf(path: string, value = new Date()) {
  const separator = path.includes('?') ? '&' : '?'
  return `${path}${separator}asOf=${encodeURIComponent(localDateISO(value))}`
}
