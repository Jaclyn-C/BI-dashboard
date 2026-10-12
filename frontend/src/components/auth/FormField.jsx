// FormField — label + input + 行内错误（迁移参考 HTML .tf 结构 407-414）

export default function FormField({
  label,
  type = 'text',
  name,
  value,
  onChange,
  onBlur,
  error = null,
  autoComplete,
  disabled = false,
  inputMode,
  maxLength,
  dir,
}) {
  const fieldId = `field-${name}`
  const errorId = `${fieldId}-error`
  return (
    <label className="tf" htmlFor={fieldId}>
      <span>{label}</span>
      <input
        id={fieldId}
        name={name}
        type={type}
        value={value}
        onChange={onChange}
        onBlur={onBlur}
        autoComplete={autoComplete}
        disabled={disabled}
        inputMode={inputMode}
        maxLength={maxLength}
        dir={dir}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={error ? errorId : undefined}
      />
      {error ? (
        <span className="fielderr" id={errorId} role="alert">
          {error}
        </span>
      ) : null}
    </label>
  )
}
