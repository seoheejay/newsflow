import { useEffect, useState } from 'react'
import {
  createFeedSource,
  deleteFeedSource,
  listFeedSources,
  updateFeedSource,
} from '../api/feedSources.js'
import FormField from '../components/FormField.jsx'
import {
  NAME_MAX_LEN,
  URL_TEMPLATE_MAX_LEN,
  fieldErrorsFromApiError,
  validateFeedSource,
} from '../utils/validation.js'

const EMPTY_FORM = { name: '', url_template: '', sort_order: 0, is_active: true }

function toPayload(form) {
  return {
    name: form.name.trim(),
    url_template: form.url_template.trim(),
    sort_order: Number(form.sort_order),
    is_active: Boolean(form.is_active),
  }
}

// SR-I-102: 피드 소스 등록·수정·삭제·활성 여부 변경. SR-I-106: 항목별 오류 표시.
export default function FeedSourcesPage() {
  const [items, setItems] = useState([])
  const [reloadKey, setReloadKey] = useState(0)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState(null)

  const [editingId, setEditingId] = useState(null) // null이면 신규 등록
  const [form, setForm] = useState(EMPTY_FORM)
  const [fieldErrors, setFieldErrors] = useState({})
  const [saving, setSaving] = useState(false)
  const [busyId, setBusyId] = useState(null) // 행 단위 토글/삭제 진행 중

  useEffect(() => {
    const controller = new AbortController()
    listFeedSources({}, { signal: controller.signal })
      .then((res) => {
        setItems(res?.items ?? [])
        setLoading(false)
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        setMessage({ type: 'error', text: err.message })
        setLoading(false)
      })
    return () => controller.abort()
  }, [reloadKey])

  function reload() {
    setReloadKey((k) => k + 1)
  }

  function setField(name, value) {
    setForm((prev) => ({ ...prev, [name]: value }))
    setFieldErrors((prev) => ({ ...prev, [name]: undefined }))
  }

  function startEdit(item) {
    setEditingId(item.id)
    setForm({
      name: item.name,
      url_template: item.url_template,
      sort_order: item.sort_order,
      is_active: item.is_active,
    })
    setFieldErrors({})
    setMessage(null)
  }

  function cancelEdit() {
    setEditingId(null)
    setForm(EMPTY_FORM)
    setFieldErrors({})
  }

  function handleSubmit(e) {
    e.preventDefault()
    setMessage(null)
    const errors = validateFeedSource(form)
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      setMessage({ type: 'error', text: '입력값을 확인해주세요' })
      return
    }
    setSaving(true)
    const payload = toPayload(form)
    const req = editingId ? updateFeedSource(editingId, payload) : createFeedSource(payload)
    req
      .then(() => {
        setMessage({ type: 'success', text: editingId ? '수정했습니다' : '등록했습니다' })
        cancelEdit()
        reload()
      })
      .catch((err) => {
        // DUPLICATE_NAME(409)은 fields=["name"], FEED_URL_INVALID(400)은 fields 없음
        const fe = fieldErrorsFromApiError(err)
        if (err.code === 'FEED_URL_INVALID') fe.url_template = err.message
        setFieldErrors(fe)
        setMessage({ type: 'error', text: err.message })
      })
      .finally(() => setSaving(false))
  }

  function toggleActive(item) {
    setBusyId(item.id)
    setMessage(null)
    updateFeedSource(item.id, { ...toPayload(item), is_active: !item.is_active })
      .then((updated) => {
        setItems((prev) => prev.map((x) => (x.id === item.id ? updated : x)))
      })
      .catch((err) => setMessage({ type: 'error', text: err.message }))
      .finally(() => setBusyId(null))
  }

  function handleDelete(item) {
    if (!window.confirm(`"${item.name}" 피드 소스를 삭제할까요?\n이미 수집된 기사는 유지됩니다.`)) return
    setBusyId(item.id)
    setMessage(null)
    deleteFeedSource(item.id)
      .then(() => {
        if (editingId === item.id) cancelEdit()
        setItems((prev) => prev.filter((x) => x.id !== item.id))
        setMessage({ type: 'success', text: '삭제했습니다' })
      })
      .catch((err) => setMessage({ type: 'error', text: err.message }))
      .finally(() => setBusyId(null))
  }

  return (
    <section className="feed-sources-page">
      <h1>피드 소스</h1>

      {message && (
        <p className={`alert alert--${message.type}`} role={message.type === 'error' ? 'alert' : 'status'}>
          {message.text}
        </p>
      )}

      <form className="form form--card" onSubmit={handleSubmit} noValidate>
        <h2>{editingId ? '피드 소스 수정' : '피드 소스 등록'}</h2>

        <FormField label="표시명" error={fieldErrors.name} hint={`1~${NAME_MAX_LEN}자, 중복 불가`}>
          <input
            type="text"
            value={form.name}
            maxLength={NAME_MAX_LEN}
            onChange={(e) => setField('name', e.target.value)}
          />
        </FormField>

        <FormField
          label="주소 템플릿"
          error={fieldErrors.url_template}
          hint="http(s)://로 시작. {keyword} 자리에 키워드가 치환됩니다. 없으면 1회만 조회"
        >
          <input
            type="url"
            value={form.url_template}
            maxLength={URL_TEMPLATE_MAX_LEN}
            placeholder="https://news.google.com/rss/search?q={keyword}&hl=ko&gl=KR&ceid=KR:ko"
            onChange={(e) => setField('url_template', e.target.value)}
          />
        </FormField>

        <div className="form__row">
          <FormField label="정렬 순서" error={fieldErrors.sort_order} hint="작을수록 먼저">
            <input
              type="number"
              step={1}
              value={form.sort_order}
              onChange={(e) => setField('sort_order', e.target.value)}
            />
          </FormField>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setField('is_active', e.target.checked)}
            />
            활성
          </label>
        </div>

        <div className="form__actions">
          <button type="submit" className="btn btn--primary" disabled={saving}>
            {saving ? '저장 중…' : editingId ? '수정 저장' : '등록'}
          </button>
          {editingId && (
            <button type="button" className="btn" onClick={cancelEdit} disabled={saving}>
              취소
            </button>
          )}
        </div>
      </form>

      {loading && <p className="status">불러오는 중…</p>}

      {!loading && items.length === 0 ? (
        <p className="empty">등록된 피드 소스가 없습니다</p>
      ) : (
        <div className="table-wrap">
          <table className="feed-sources">
            <thead>
              <tr>
                <th className="col-no">순서</th>
                <th>표시명</th>
                <th>주소 템플릿</th>
                <th>활성</th>
                <th className="col-actions">작업</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const busy = busyId === item.id
                return (
                  <tr key={item.id} className={item.is_active ? '' : 'row--inactive'}>
                    <td className="col-no">{item.sort_order}</td>
                    <td>{item.name}</td>
                    <td className="col-url">
                      <code>{item.url_template}</code>
                    </td>
                    <td>
                      <label className="switch">
                        <input
                          type="checkbox"
                          checked={item.is_active}
                          onChange={() => toggleActive(item)}
                          disabled={busy}
                          aria-label={`${item.name} 활성 여부`}
                        />
                        <span>{item.is_active ? '활성' : '비활성'}</span>
                      </label>
                    </td>
                    <td className="col-actions">
                      <button type="button" className="btn btn--sm" onClick={() => startEdit(item)} disabled={busy}>
                        수정
                      </button>
                      <button
                        type="button"
                        className="btn btn--sm btn--danger"
                        onClick={() => handleDelete(item)}
                        disabled={busy}
                      >
                        삭제
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
