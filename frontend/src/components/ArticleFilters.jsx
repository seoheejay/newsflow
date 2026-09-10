// SR-F-602: 기본 20, 최대 100
const PAGE_SIZE_OPTIONS = [20, 50, 100]

export default function ArticleFilters({
  keywords,
  sites,
  keyword,
  site,
  itemsPerPage,
  onChange,
}) {
  return (
    <form className="filters" onSubmit={(e) => e.preventDefault()}>
      <label>
        키워드
        <select
          value={keyword}
          onChange={(e) => onChange({ keyword: e.target.value })}
        >
          <option value="">전체</option>
          {keywords.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
      </label>

      <label>
        피드 소스
        <select value={site} onChange={(e) => onChange({ site: e.target.value })}>
          <option value="">전체</option>
          {sites.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>

      <label>
        페이지 크기
        <select
          value={itemsPerPage}
          onChange={(e) => onChange({ itemsPerPage: Number(e.target.value) })}
        >
          {PAGE_SIZE_OPTIONS.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
    </form>
  )
}
