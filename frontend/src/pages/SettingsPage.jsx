import { useEffect, useState } from 'react'
import { getSettings, updateSettings } from '../api/settings.js'
import FormField from '../components/FormField.jsx'
import {
  KEYWORD_MAX_COUNT,
  KEYWORD_MAX_LEN,
  MAX_PER_SOURCE_MAX,
  MAX_PER_SOURCE_MIN,
  SUBJECT_MAX_LEN,
  fieldErrorsFromApiError,
  validateKeyword,
  validateSettings,
} from '../utils/validation.js'

const EMPTY_FORM = { mail_subject: '', mail_to: '', max_per_source: 10, keywords: [] }

// SR-I-101: 키워드·메일 제목·수신자·최대 건수 입력. SR-I-106: 항목별 오류 표시.
export default function SettingsPage() {
  const [form, setForm] = useState(EMPTY_FORM)
  const [keywordInput, setKeywordInput] = useState('')
  const [fieldErrors, setFieldErrors] = useState({})
  const [keywordError, setKeywordError] = useState(null)
  const [message, setMessage] = useState(null) // { type: 'error' | 'success', text }
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getSettings({ signal: controller.signal })
      .then((s) => {
        setForm({
          mail_subject: s?.mail_subject ?? '',
          mail_to: s?.mail_to ?? '',
          max_per_source: s?.max_per_source ?? 10,
          keywords: s?.keywords ?? [],
        })
        setLoading(false)
      })
      .catch((err) => {
        if (err.name === 'AbortError') return
        setMessage({ type: 'error', text: err.message })
        setLoading(false)
      })
    return () => controller.abort()
  }, [])

  function setField(name, value) {
    setForm((prev) => ({ ...prev, [name]: value }))
    setFieldErrors((prev) => ({ ...prev, [name]: undefined }))
  }

  function addKeyword() {
    const err = validateKeyword(keywordInput, form.keywords)
    if (err) {
      setKeywordError(err)
      return
    }
    setField('keywords', [...form.keywords, keywordInput.trim()])
    setKeywordInput('')
    setKeywordError(null)
  }

  function removeKeyword(k) {
    setField(
      'keywords',
      form.keywords.filter((x) => x !== k),
    )
  }

  function handleSubmit(e) {
    e.preventDefault()
    setMessage(null)
    const errors = validateSettings(form)
    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors)
      setMessage({ type: 'error', text: '입력값을 확인해주세요' })
      return
    }
    setSaving(true)
    updateSettings({
      mail_subject: form.mail_subject.trim(),
      mail_to: form.mail_to.trim(),
      max_per_source: Number(form.max_per_source),
      keywords: form.keywords,
    })
      .then((saved) => {
        if (saved) {
          setForm({
            mail_subject: saved.mail_subject ?? form.mail_subject,
            mail_to: saved.mail_to ?? form.mail_to,
            max_per_source: saved.max_per_source ?? form.max_per_source,
            keywords: saved.keywords ?? form.keywords,
          })
        }
        setFieldErrors({})
        setMessage({ type: 'success', text: '저장했습니다. 다음 실행부터 반영됩니다' }) // SR-F-107
      })
      .catch((err) => {
        setFieldErrors(fieldErrorsFromApiError(err))
        setMessage({ type: 'error', text: err.message })
      })
      .finally(() => setSaving(false))
  }

  return (
    <section className="settings-page">
      <h1>설정</h1>

      {message && (
        <p className={`alert alert--${message.type}`} role={message.type === 'error' ? 'alert' : 'status'}>
          {message.text}
        </p>
      )}
      {loading && <p className="status">불러오는 중…</p>}

      <form className="form" onSubmit={handleSubmit} noValidate>
        <FormField
          label="메일 제목"
          error={fieldErrors.mail_subject}
          hint={`1~${SUBJECT_MAX_LEN}자`}
        >
          <input
            type="text"
            value={form.mail_subject}
            maxLength={SUBJECT_MAX_LEN}
            onChange={(e) => setField('mail_subject', e.target.value)}
            disabled={loading}
          />
        </FormField>

        <FormField label="수신자 주소" error={fieldErrors.mail_to} hint="이메일 주소 한 개">
          <input
            type="email"
            value={form.mail_to}
            onChange={(e) => setField('mail_to', e.target.value)}
            disabled={loading}
          />
        </FormField>

        <FormField
          label="소스당 최대 수집 건수"
          error={fieldErrors.max_per_source}
          hint={`${MAX_PER_SOURCE_MIN}~${MAX_PER_SOURCE_MAX}`}
        >
          <input
            type="number"
            min={MAX_PER_SOURCE_MIN}
            max={MAX_PER_SOURCE_MAX}
            step={1}
            value={form.max_per_source}
            onChange={(e) => setField('max_per_source', e.target.value)}
            disabled={loading}
          />
        </FormField>

        <FormField
          label={`키워드 (${form.keywords.length}/${KEYWORD_MAX_COUNT})`}
          error={fieldErrors.keywords ?? keywordError}
          hint={`${KEYWORD_MAX_LEN}자 이하, 중복 불가. Enter 또는 추가 버튼`}
        >
          <div className="keyword-input">
            <input
              type="text"
              value={keywordInput}
              maxLength={KEYWORD_MAX_LEN}
              placeholder="예: AI"
              onChange={(e) => {
                setKeywordInput(e.target.value)
                setKeywordError(null)
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault()
                  addKeyword()
                }
              }}
              disabled={loading}
            />
            <button type="button" className="btn" onClick={addKeyword} disabled={loading}>
              추가
            </button>
          </div>
        </FormField>

        <ul className="chips" aria-label="등록된 키워드">
          {form.keywords.map((k) => (
            <li key={k} className="chip">
              <span>{k}</span>
              <button
                type="button"
                className="chip__remove"
                aria-label={`${k} 삭제`}
                onClick={() => removeKeyword(k)}
              >
                ×
              </button>
            </li>
          ))}
          {form.keywords.length === 0 && <li className="chips__empty">등록된 키워드가 없습니다</li>}
        </ul>

        <div className="form__actions">
          <button type="submit" className="btn btn--primary" disabled={loading || saving}>
            {saving ? '저장 중…' : '저장'}
          </button>
        </div>
      </form>
    </section>
  )
}
