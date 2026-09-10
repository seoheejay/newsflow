import { request } from './client.js'

// 목록 응답은 봉투 형태 { total_count, page, items_per_page, items }.
// 피드 소스는 20개 이하(ASM-04)이므로 기본으로 최대 페이지 크기를 쓴다.
export function listFeedSources({ page = 1, itemsPerPage = 100 } = {}, { signal } = {}) {
  return request('/feed-sources', {
    params: { page, items_per_page: itemsPerPage },
    signal,
  })
}

export function createFeedSource(payload, { signal } = {}) {
  return request('/feed-sources', {
    method: 'POST',
    body: JSON.stringify(payload),
    signal,
  })
}

// PUT은 전체 교체. name, url_template, sort_order, is_active 모두 필요
export function updateFeedSource(id, payload, { signal } = {}) {
  return request(`/feed-sources/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
    signal,
  })
}

export function deleteFeedSource(id, { signal } = {}) {
  return request(`/feed-sources/${encodeURIComponent(id)}`, {
    method: 'DELETE',
    signal,
  })
}
