import { request } from './client.js'

// SRS 부록 A: GET /articles?page&items_per_page&keyword&site&from&to
export function getArticles(
  { page = 1, itemsPerPage = 20, keyword, site, dateFrom, dateTo } = {},
  { signal } = {},
) {
  return request('/articles', {
    // from/to 는 한국 시간 기준 일자 (SRS 부록 A.2)
    params: { page, items_per_page: itemsPerPage, keyword, site, from: dateFrom, to: dateTo },
    signal,
  })
}
