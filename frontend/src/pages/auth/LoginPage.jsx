// LoginPage — /login（DESIGN §5.1）
// 邮箱 + 密码 + 「记住密码」勾选（默认不勾，只管密码，§5.6）；
// ?expired=1 时优先显示会话过期提示（AC-L4）；邮箱必回填、密码按历史勾选回填（AC-L5）。

import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'

import useAuth from '../../auth/useAuth'
import AuthCard from '../../components/auth/AuthCard'
import ErrorAlert from '../../components/auth/ErrorAlert'
import FormField from '../../components/auth/FormField'
import LangToggle from '../../components/auth/LangToggle'
import SubmitButton from '../../components/auth/SubmitButton'
import { clearPassword, loadRemembered, rememberEmail, rememberPassword } from '../../utils/remember'
import { apiErrorMessage } from '../../utils/apiErrorMessage'
import { normalizeEmail, validateEmail, validatePassword } from '../../utils/validation'
import usePageTitle from '../../utils/usePageTitle'

export default function LoginPage() {
  const { t } = useTranslation()
  const { login, user, booting } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  usePageTitle('common.pageTitle.login')

  // 挂载时回填：邮箱始终回填；密码视历史勾选（AC-L5）
  const initial = useMemo(() => loadRemembered(), [])
  const [email, setEmail] = useState(initial.email)
  const [password, setPassword] = useState(initial.password)
  const [remember, setRemember] = useState(initial.rememberedPassword)
  const [errors, setErrors] = useState({})
  const [topError, setTopError] = useState(null)
  const [busy, setBusy] = useState(false)

  const expired = searchParams.get('expired') === '1'
  const from = location.state?.from?.pathname || '/'

  // 已登录访问登录页 → 跳走（路由表已处理，双保险）
  useEffect(() => {
    if (!booting && user) navigate(from, { replace: true })
  }, [booting, user, navigate, from])

  async function handleSubmit(e) {
    e.preventDefault()
    // 会话过期提示在用户再次操作后让位给新错误
    const fieldErrors = {
      email: validateEmail(email),
      password: validatePassword(password),
    }
    setErrors(fieldErrors)
    setTopError(null)
    if (fieldErrors.email || fieldErrors.password) return

    setBusy(true)
    try {
      await login({ email, password })
      // 登录记忆（AC-L5）：邮箱必记；密码按勾选存/清
      rememberEmail(normalizeEmail(email))
      if (remember) rememberPassword(password)
      else clearPassword()
      navigate(from, { replace: true })
    } catch (err) {
      setTopError(apiErrorMessage(t, err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard
      title={t('auth.login.title')}
      sub={t('auth.login.sub')}
      onSubmit={handleSubmit}
    >
      <FormField
        label={t('auth.common.email')}
        name="login-email"
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        onBlur={() => setErrors((p) => ({ ...p, email: validateEmail(email) }))}
        error={errors.email ? t(errors.email) : null}
        autoComplete="username"
        disabled={busy}
      />
      <FormField
        label={t('auth.common.password')}
        name="login-password"
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        onBlur={() => setErrors((p) => ({ ...p, password: validatePassword(password) }))}
        error={errors.password ? t(errors.password) : null}
        autoComplete="current-password"
        disabled={busy}
      />
      <label className="checkrow">
        <input
          type="checkbox"
          checked={remember}
          onChange={(e) => setRemember(e.target.checked)}
          disabled={busy}
        />
        {t('auth.login.rememberMe')}
      </label>
      <ErrorAlert message={topError || (expired ? t('auth.error.sessionExpired') : null)} />
      <SubmitButton
        label={t('auth.login.submit')}
        busyLabel={t('auth.login.busy')}
        busy={busy}
      />
      <div className="authlinks">
        <Link to="/forgot">{t('auth.common.goForgot')}</Link>
        <Link to="/register">{t('auth.common.goRegister')}</Link>
      </div>
      <LangToggle />
    </AuthCard>
  )
}
