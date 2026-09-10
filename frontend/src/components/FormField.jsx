// 라벨 + 입력 + 항목별 오류 사유 (SR-I-106)
export default function FormField({ label, error, hint, children }) {
  return (
    <div className={`field${error ? ' field--error' : ''}`}>
      <label className="field__label">
        <span>{label}</span>
        {children}
      </label>
      {error ? (
        <p className="field__error" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p className="field__hint">{hint}</p>
      ) : null}
    </div>
  )
}
