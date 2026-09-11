import { useEffect, useState } from 'react'
import ArticlesPage from './pages/ArticlesPage.jsx'
import FeedSourcesPage from './pages/FeedSourcesPage.jsx'
import ExecutionsPage from './pages/ExecutionsPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'

// 라우터 라이브러리 없이 해시로 화면을 나눈다. 화면 수가 적어 충분하다.
const ROUTES = [
  { hash: '#/articles', label: '기사', Page: ArticlesPage },
  { hash: '#/feed-sources', label: '피드 소스', Page: FeedSourcesPage },
  { hash: '#/executions', label: '실행 이력', Page: ExecutionsPage },
  { hash: '#/settings', label: '설정', Page: SettingsPage },
]

function currentHash() {
  const h = window.location.hash
  return ROUTES.some((r) => r.hash === h) ? h : ROUTES[0].hash
}

function App() {
  const [hash, setHash] = useState(currentHash)

  useEffect(() => {
    const onChange = () => setHash(currentHash())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  const route = ROUTES.find((r) => r.hash === hash) ?? ROUTES[0]
  const { Page } = route

  return (
    <>
      <header className="app-header">
        <span className="app-header__brand">NewsFlow</span>
        <nav className="app-nav" aria-label="주 메뉴">
          {ROUTES.map((r) => (
            <a
              key={r.hash}
              href={r.hash}
              className={r.hash === hash ? 'app-nav__link app-nav__link--active' : 'app-nav__link'}
              aria-current={r.hash === hash ? 'page' : undefined}
            >
              {r.label}
            </a>
          ))}
        </nav>
      </header>
      <main className="app-main">
        <Page />
      </main>
    </>
  )
}

export default App
