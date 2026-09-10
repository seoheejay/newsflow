import { useEffect, useRef, useState } from 'react'
import { getExecution, startCollect } from '../api/executions.js'
import { formatSeoul } from '../utils/datetime.js'

const POLL_MS = 2000
const STATUS_LABEL = {
  queued: '대기 중',
  running: '수집 중',
  success: '완료',
  failed: '실패',
}
const FINAL = new Set(['success', 'failed'])

// SR-I-104: 수집 즉시 실행 + 진행 상태 표시. SR-I-105: 실패 사유 표시.
export default function CollectPanel({ onFinished }) {
  const [execution, setExecution] = useState(null) // GET /executions/{id} 응답
  const [requesting, setRequesting] = useState(false)
  const [error, setError] = useState(null)
  // 폴링 콜백이 최신 onFinished를 보도록 ref에 보관한다 (렌더 중이 아니라 효과에서 갱신)
  const onFinishedRef = useRef(onFinished)
  useEffect(() => {
    onFinishedRef.current = onFinished
  }, [onFinished])

  const executionId = execution?.id ?? null
  const polling = executionId !== null && !FINAL.has(execution.status)

  // queued/running 동안 2초마다 상태를 조회한다
  useEffect(() => {
    if (!polling) return undefined
    const controller = new AbortController()
    const timer = setInterval(() => {
      getExecution(executionId, { signal: controller.signal })
        .then((res) => {
          setExecution(res)
          if (res.status === 'success') onFinishedRef.current?.(res)
        })
        .catch((err) => {
          if (err.name === 'AbortError') return
          setError(err.message)
        })
    }, POLL_MS)
    return () => {
      clearInterval(timer)
      controller.abort()
    }
  }, [polling, executionId])

  function handleStart() {
    setRequesting(true)
    setError(null)
    startCollect()
      .then((res) => {
        // 202 응답에는 id/status만 있으므로 조회 형태로 맞춰 둔다
        setExecution({ id: res.execution_id, status: res.status })
      })
      .catch((err) => {
        // 409 EXECUTION_IN_PROGRESS 등은 message를 그대로 보여준다
        setError(err.message)
      })
      .finally(() => setRequesting(false))
  }

  const status = execution?.status
  const busy = requesting || polling

  return (
    <section className="collect-panel" aria-live="polite">
      <div className="collect-panel__row">
        <button type="button" className="btn btn--primary" onClick={handleStart} disabled={busy}>
          {busy ? '수집 중…' : '지금 수집'}
        </button>
        {status && (
          <span className={`badge badge--${status}`}>{STATUS_LABEL[status] ?? status}</span>
        )}
        {status === 'success' && (
          <span className="collect-panel__summary">
            수집 {execution.collected_count ?? 0}건 · 신규 {execution.new_count ?? 0}건
            {execution.finished_at ? ` · ${formatSeoul(execution.finished_at)}` : ''}
          </span>
        )}
      </div>
      {status === 'failed' && (
        <p className="alert alert--error" role="alert">
          실행 실패: {execution.error || '사유가 기록되지 않았습니다'}
        </p>
      )}
      {error && (
        <p className="alert alert--error" role="alert">
          {error}
        </p>
      )}
    </section>
  )
}
