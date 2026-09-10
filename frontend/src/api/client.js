const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor({ code, message, fields, status }) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.fields = fields
    this.status = status
  }
}

function buildQuery(params = {}) {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue
    query.set(key, String(value))
  }
  const text = query.toString()
  return text ? `?${text}` : ''
}

export async function request(path, { params, signal, ...options } = {}) {
  const url = `${BASE_URL}${path}${buildQuery(params)}`

  let response
  try {
    response = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
      signal,
      ...options,
    })
  } catch (err) {
    if (err.name === 'AbortError') throw err
    throw new ApiError({
      code: 'NETWORK_ERROR',
      message: '서버에 연결할 수 없습니다',
      status: 0,
    })
  }

  if (response.status === 204) return null

  let body = null
  try {
    body = await response.json()
  } catch {
    body = null
  }

  if (!response.ok) {
    throw new ApiError({
      code: body?.code ?? 'UNKNOWN_ERROR',
      message: body?.message ?? `요청 실패 (${response.status})`,
      fields: body?.fields,
      status: response.status,
    })
  }

  return body
}
