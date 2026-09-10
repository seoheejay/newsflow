import { request } from './client.js'

// SR-F-101: { mail_subject, mail_to, max_per_source, keywords }
export function getSettings({ signal } = {}) {
  return request('/settings', { signal })
}

// PUT /settings (부록 A.1). 본문은 GET과 같은 형태
export function updateSettings(payload, { signal } = {}) {
  return request('/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
    signal,
  })
}
