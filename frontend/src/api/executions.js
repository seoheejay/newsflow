import { request } from './client.js'

// SR-F-701: 202 + { execution_id, status }. 진행 중이면 409 EXECUTION_IN_PROGRESS
export function startCollect({ signal } = {}) {
  return request('/collect', { method: 'POST', signal })
}

// SR-F-706: { id, status, started_at, finished_at, collected_count, new_count, error, node_logs? }
export function getExecution(id, { signal } = {}) {
  return request(`/executions/${encodeURIComponent(id)}`, { signal })
}
