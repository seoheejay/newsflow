// 클라이언트 측 입력값 검증. 서버 검증(SR-F-1xx, 2xx)과 같은 규칙을 미리 적용해
// 항목별 사유를 화면에 보여준다 (SR-I-106). 최종 판정은 서버가 한다.

// RFC 5322를 완전히 구현하지 않고 실무 수준으로 근사한다 (SR-F-104)
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export const KEYWORD_MAX_LEN = 64 // SR-F-102
export const KEYWORD_MAX_COUNT = 20 // SR-F-102
export const SUBJECT_MAX_LEN = 200 // SR-F-106
export const MAX_PER_SOURCE_MIN = 1 // SR-F-105
export const MAX_PER_SOURCE_MAX = 100 // SR-F-105
export const SCHEDULE_HOUR_MAX = 23 // SR-F-805
export const SCHEDULE_MINUTE_MAX = 59 // SR-F-805
export const NAME_MAX_LEN = 64
export const URL_TEMPLATE_MAX_LEN = 1000

export function validateKeyword(value, existing = []) {
  const v = value.trim()
  if (v.length === 0) return '키워드를 입력하세요'
  if (v.length > KEYWORD_MAX_LEN) return `키워드는 ${KEYWORD_MAX_LEN}자 이하여야 합니다`
  if (existing.includes(v)) return '이미 등록된 키워드입니다' // SR-F-103
  if (existing.length >= KEYWORD_MAX_COUNT) return `키워드는 최대 ${KEYWORD_MAX_COUNT}개까지 등록할 수 있습니다`
  return null
}

export function validateSettings(form) {
  const errors = {}
  const subject = form.mail_subject.trim()
  if (subject.length === 0) errors.mail_subject = '메일 제목을 입력하세요'
  else if (subject.length > SUBJECT_MAX_LEN) errors.mail_subject = `메일 제목은 ${SUBJECT_MAX_LEN}자 이하여야 합니다`

  const to = form.mail_to.trim()
  if (to.length === 0) errors.mail_to = '수신자 주소를 입력하세요'
  else if (!EMAIL_RE.test(to)) errors.mail_to = '이메일 주소 형식이 아닙니다'

  const n = Number(form.max_per_source)
  if (!Number.isInteger(n) || n < MAX_PER_SOURCE_MIN || n > MAX_PER_SOURCE_MAX) {
    errors.max_per_source = `${MAX_PER_SOURCE_MIN} 이상 ${MAX_PER_SOURCE_MAX} 이하의 정수여야 합니다`
  }

  // SR-F-805: 자동 실행 시각
  const hour = Number(form.schedule_hour)
  if (!Number.isInteger(hour) || hour < 0 || hour > SCHEDULE_HOUR_MAX) {
    errors.schedule_hour = `0 이상 ${SCHEDULE_HOUR_MAX} 이하의 정수여야 합니다`
  }
  const minute = Number(form.schedule_minute)
  if (!Number.isInteger(minute) || minute < 0 || minute > SCHEDULE_MINUTE_MAX) {
    errors.schedule_minute = `0 이상 ${SCHEDULE_MINUTE_MAX} 이하의 정수여야 합니다`
  }

  if (form.keywords.length > KEYWORD_MAX_COUNT) {
    errors.keywords = `키워드는 최대 ${KEYWORD_MAX_COUNT}개까지 등록할 수 있습니다`
  }
  return errors
}

export function validateFeedSource(form) {
  const errors = {}
  const name = form.name.trim()
  if (name.length === 0) errors.name = '표시명을 입력하세요'
  else if (name.length > NAME_MAX_LEN) errors.name = `표시명은 ${NAME_MAX_LEN}자 이하여야 합니다`

  const url = form.url_template.trim()
  if (url.length === 0) errors.url_template = '주소 템플릿을 입력하세요'
  else if (!/^https?:\/\//.test(url)) errors.url_template = 'http:// 또는 https:// 로 시작해야 합니다' // SR-F-202
  else if (url.length > URL_TEMPLATE_MAX_LEN) errors.url_template = `주소 템플릿은 ${URL_TEMPLATE_MAX_LEN}자 이하여야 합니다`

  if (!Number.isInteger(Number(form.sort_order))) errors.sort_order = '정수를 입력하세요'
  return errors
}

// 서버 오류 응답 { code, message, fields? } → 항목별 메시지.
// fields가 있으면 그 항목에 사유를 붙이고, 없으면 전체 메시지로만 쓴다.
export function fieldErrorsFromApiError(err) {
  if (!err || !Array.isArray(err.fields) || err.fields.length === 0) return {}
  const errors = {}
  for (const f of err.fields) errors[f] = err.message
  return errors
}
