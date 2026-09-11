import { useEffect, useState } from 'react'
import { getExecutions } from '../api/executions.js'
import Pagination from '../components/Pagination.jsx'
import { formatSeoul } from '../utils/datetime.js'

const EMPTY_PAGE = { total_count: 0, page: 1, items_per_page: 20, items: [] }

const STATUS_LABEL = {
  queued: '대기',
  running: '진행 중',
  success: '성공',
  failed: '실패',
}

const TRIGGER_LABEL = { manual: '수동', scheduled: '자동' }

function elapsed(started, finished) {
  if (!started || !finished) return '-'
  const ms = new Date(finished) - new Date(started)
  if (Number.isNaN(ms) || ms < 0) return '-'
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(1)}초`
}

// UR-EXE-06: 과거 실행 이력 목록. SR-I-105: 실패 사유 표시.
export default function ExecutionsPage() {
  const [page, setPage] = useState(1)
  const [refreshKey, setRefreshKey] = useState(0)
  const [expanded, setExpanded] = useState(null)

  // 조회 조건을 키로 만들어, 마지막으로 도착한 결과가 현재 조건의 것인지 판별한다
  const queryKey = JSON.stringify({ page, refreshKey })
  const [result, setResult] = useState({ key: null, data: EMPTY_PAGE, error: null })
  const loading = result.key !== queryKey
  const { data, error } = result

  useEffect(() => {
    const controller = new AbortController()
    getExecutions({ page }, { signal: controller.signal })
      .then((res) => setResult({ key: queryKey, data: res ?? EMPTY_PAGE, error: null }))
      .catch((err) => {
        if (err.name === 'AbortError') return
        setResult((prev) => ({ key: queryKey, data: prev.data, error: err.message }))
      })
    return () => controller.abort()
  }, [queryKey, page])

  return (
    <section className="executions-page">
      <div className="page-head">
        <h1>실행 이력</h1>
        <button
          type="button"
          className="btn"
          onClick={() => setRefreshKey((k) => k + 1)}
          disabled={loading}
        >
          {loading ? '불러오는 중…' : '새로고침'}
        </button>
      </div>

      {error && (
        <p className="alert alert--error" role="alert">
          {error}
        </p>
      )}

      <div className="table-wrap">
      <table className="articles">
        <thead>
          <tr>
            <th>시작</th>
            <th>구분</th>
            <th>상태</th>
            <th className="num">수집</th>
            <th className="num">신규</th>
            <th className="num">소요</th>
            <th>사유</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((e) => (
            <tr key={e.id} className={e.status === 'failed' ? 'row--failed' : undefined}>
              <td>{formatSeoul(e.started_at)}</td>
              <td>{TRIGGER_LABEL[e.trigger] ?? e.trigger}</td>
              <td>
                <span className={`badge badge--${e.status}`}>
                  {STATUS_LABEL[e.status] ?? e.status}
                </span>
              </td>
              <td className="num">{e.collected_count}</td>
              <td className="num">{e.new_count}</td>
              <td className="num">{elapsed(e.started_at, e.finished_at)}</td>
              <td className="cell--reason">
                {e.error ? (
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                    title={e.error}
                  >
                    {expanded === e.id ? e.error : `${e.error.slice(0, 30)}…`}
                  </button>
                ) : (
                  '-'
                )}
              </td>
            </tr>
          ))}
          {data.items.length === 0 && !loading && (
            <tr>
              <td colSpan={7} className="cell-empty">
                실행 이력이 없습니다
              </td>
            </tr>
          )}
        </tbody>
      </table>
      </div>

      <Pagination
        page={data.page}
        itemsPerPage={data.items_per_page}
        totalCount={data.total_count}
        onChange={setPage}
      />
    </section>
  )
}
