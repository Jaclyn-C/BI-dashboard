// AuthCard — 认证页卡片外壳（迁移参考 HTML .logincard 结构 404-418）

export default function AuthCard({ title, sub, onSubmit, children }) {
  return (
    <div className="authpage">
      <form className="logincard" onSubmit={onSubmit} noValidate>
        <h2>{title}</h2>
        {sub ? <p className="loginsub">{sub}</p> : null}
        {children}
      </form>
    </div>
  )
}
