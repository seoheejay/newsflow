import { request } from './client.js'

// SR-F-701: 202 + { execution_id, status }. 진행 중이면 409 EXECUTION_IN_PROGRESS
export function startCollect({ signal } = {}) {
  return request('/collect', { method: 'POST', signal })
}

// SR-F-706: { id, status, started_at, finished_at, collected_count, new_count, error, node_logs? }
export function getExecution(id, { signal } = {}) {
  return request(`/executions/${encodeURIComponent(id)}`, { signal })
}

// SR-F-707: 시작 시각 내림차순 봉투 응답. 목록에는 node_logs가 없다
export function getExecutions({ page = 1, itemsPerPage = 20 } = {}, { signal } = {}) {
  return request('/executions', {
    params: { page, items_per_page: itemsPerPage },
    signal,
  })
}
