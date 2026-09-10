import { request } from './client.js'

// SRS 부록 A: GET /articles?page&items_per_page&keyword&site (from/to는 UR-STO-05에서 추가)
export function getArticles({ page = 1, itemsPerPage = 20, keyword, site } = {}, { signal } = {}) {
  return request('/articles', {
    params: { page, items_per_page: itemsPerPage, keyword, site },
    signal,
  })
}
