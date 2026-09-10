import { useEffect, useState } from 'react'
import { getArticles, getFeedSources, getSettings } from '../api/articles.js'
import ArticleFilters from '../components/ArticleFilters.jsx'
import ArticleTable from '../components/ArticleTable.jsx'
import Pagination from '../components/Pagination.jsx'

const EMPTY_PAGE = { total_count: 0, page: 1, items_per_page: 20, items: [] }

export default function ArticlesPage() {
  const [filters, setFilters] = useState({ keyword: '', site: '', itemsPerPage: 20 })
  const [page, setPage] = useState(1)

  // 조회 조건을 키로 만들어, 마지막으로 도착한 결과가 현재 조건의 것인지 판별한다
  const queryKey = JSON.stringify({ page, ...filters })
  const [result, setResult] = useState({ key: null, data: EMPTY_PAGE, error: null })
  const loading = result.key !== queryKey
  const error = result.error

  const [keywordOptions, setKeywordOptions] = useState([])
  const [siteOptions, setSiteOptions] = useState([])

  // 필터 선택지: 실패해도 화면을 막지 않는다
  useEffect(() => {
    const controller = new AbortController()
    getSettings({ signal: controller.signal })
      .then((s) => setKeywordOptions(s?.keywords ?? []))
      .catch(() => setKeywordOptions([]))
    // 피드 소스는 20개 이하(ASM-04)이므로 최대 페이지 크기로 한 번에 받는다
    getFeedSources({ itemsPerPage: 100 }, { signal: controller.signal })
      .then((res) => setSiteOptions((res?.items ?? []).map((f) => f.name)))
      .catch(() => setSiteOptions([]))
    return () => controller.abort()
  }, [])

  // 기사 목록: 조회 조건이 바뀔 때마다 재조회. 이전 요청은 취소한다
  useEffect(() => {
    const controller = new AbortController()
    getArticles(
      {
        page,
        itemsPerPage: filters.itemsPerPage,
        keyword: filters.keyword,
        site: filters.site,
      },
      { signal: controller.signal },
    )
      .then((res) => {
        setResult({ key: queryKey, data: res ?? EMPTY_PAGE, error: null })
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        setResult((prev) => ({ key: queryKey, data: prev.data, error: err.message }))
      })
    return () => controller.abort()
  }, [queryKey, page, filters])

  function handleFilterChange(patch) {
    setFilters((prev) => ({ ...prev, ...patch }))
    setPage(1)
  }

  const { data } = result

  return (
    <section className="articles-page">
      <h1>기사 목록</h1>

      <ArticleFilters
        keywords={keywordOptions}
        sites={siteOptions}
        keyword={filters.keyword}
        site={filters.site}
        itemsPerPage={filters.itemsPerPage}
        onChange={handleFilterChange}
      />

      {error && (
        <p className="alert alert--error" role="alert">
          {error}
        </p>
      )}
      {loading && <p className="status">불러오는 중…</p>}

      <ArticleTable items={data.items} page={data.page} itemsPerPage={data.items_per_page} />

      <Pagination
        page={data.page}
        itemsPerPage={data.items_per_page}
        totalCount={data.total_count}
        onChange={setPage}
        disabled={loading}
      />
    </section>
  )
}
