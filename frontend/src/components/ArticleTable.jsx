import { formatSeoul } from '../utils/datetime.js'

export default function ArticleTable({ items, page, itemsPerPage }) {
  if (items.length === 0) {
    return <p className="empty">조건에 맞는 기사가 없습니다</p>
  }

  const offset = (page - 1) * itemsPerPage

  return (
    <div className="table-wrap">
      <table className="articles">
        <thead>
          <tr>
            <th className="col-no">번호</th>
            <th>제목</th>
            <th>피드 소스</th>
            <th>키워드</th>
            <th>발행일시</th>
            <th>수집일시</th>
          </tr>
        </thead>
        <tbody>
          {items.map((a, i) => (
            <tr key={a.id}>
              <td className="col-no">{offset + i + 1}</td>
              <td className="col-title">
                <a href={a.link} target="_blank" rel="noopener noreferrer">
                  {a.title}
                </a>
              </td>
              <td>{a.site}</td>
              <td>{a.keyword}</td>
              <td className="col-time">{formatSeoul(a.published_at)}</td>
              <td className="col-time">{formatSeoul(a.collected_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
