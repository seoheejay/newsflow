// 목록 응답 { total_count, page, items_per_page, items } 공통 페이지 이동 UI
export default function Pagination({ page, itemsPerPage, totalCount, onChange, disabled = false }) {
  const totalPages = Math.max(1, Math.ceil(totalCount / itemsPerPage))
  const isFirst = page <= 1
  const isLast = page >= totalPages

  return (
    <nav className="pagination" aria-label="페이지 이동">
      <span className="pagination__count">총 {totalCount.toLocaleString('ko-KR')}건</span>
      <button
        type="button"
        onClick={() => onChange(page - 1)}
        disabled={disabled || isFirst}
      >
        이전
      </button>
      <span className="pagination__page">
        {page} / {totalPages}
      </span>
      <button
        type="button"
        onClick={() => onChange(page + 1)}
        disabled={disabled || isLast}
      >
        다음
      </button>
    </nav>
  )
}
