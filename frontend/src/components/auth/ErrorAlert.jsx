// ErrorAlert — 顶部错误条（对标参考 .loginerror，role="alert"，HTML:415）

export default function ErrorAlert({ message }) {
  if (!message) return null
  return (
    <div className="loginerror" role="alert">
      {message}
    </div>
  )
}
