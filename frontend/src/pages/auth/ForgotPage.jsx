// ForgotPage — /forgot（DESIGN §5.1 F4）
// 邮箱 + 验证码 + 新密码三项一次展示（AC-P1）；发码逻辑同注册；
// 重置成功显示引导后跳 /login（AC-P3）。

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { resetPassword, sendResetCode } from '../../api/auth'
import useAuth from '../../auth/useAuth'
import AuthCard from '../../components/auth/AuthCard'
import CodeSendButton from '../../components/auth/CodeSendButton'
import ErrorAlert from '../../components/auth/ErrorAlert'
import FormField from '../../components/auth/FormField'
import LangToggle from '../../components/auth/LangToggle'
import SubmitButton from '../../components/auth/SubmitButton'
import { apiErrorMessage } from '../../utils/apiErrorMessage'
import { validateCode, validateEmail, validatePassword } from '../../utils/validation'
import usePageTitle from '../../utils/usePageTitle'

const REDIRECT_DELAY_MS = 2500

export default function ForgotPage() {
  const { t } = useTranslation()
  const { user, booting } = useAuth()
  const navigate = useNavigate()
  usePageTitle('common.pageTitle.forgot')

  const [form, setForm] = useState({ email: '', code: '', newPassword: '' })
  const [errors, setErrors] = useState({})
  const [topError, setTopError] = useState(null)
  const [success, setSuccess] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!booting && user) navigate('/', { replace: true })
  }, [booting, user, navigate])

  const set = (field) => (e) => setForm((p) => ({ ...p, [field]: e.target.value }))

  const blurValidators = {
    email: () => validateEmail(form.email),
    code: () => validateCode(form.code),
    newPassword: () => validatePassword(form.newPassword),
  }
  const blur = (field) => () =>
    setErrors((p) => ({ ...p, [field]: blurValidators[field]() }))

  /** 发码前邮箱校验（AC-P6 同注册；不合法不发请求） */
  function validateEmailForCode() {
    const err = validateEmail(form.email)
    setErrors((p) => ({ ...p, email: err }))
    return err
  }

  async function handleSendCode() {
    await sendResetCode(form.email)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const fieldErrors = {
      email: validateEmail(form.email),
      code: validateCode(form.code),
      newPassword: validatePassword(form.newPassword),
    }
    setErrors(fieldErrors)
    setTopError(null)
    if (Object.values(fieldErrors).some(Boolean)) return

    setBusy(true)
    try {
      await resetPassword({
        email: form.email, // api/auth.js 内统一 trim + 小写规范化
        code: form.code.trim(), // 与校验口径一致（validation.js 先 trim 再比对）
        newPassword: form.newPassword,
      })
      // 成功：提示后引导回登录页（AC-P3：新密码登录，旧 token 已全部失效）
      setSuccess(true)
      setTimeout(() => navigate('/login', { replace: true }), REDIRECT_DELAY_MS)
    } catch (err) {
      setTopError(apiErrorMessage(t, err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard
      title={t('auth.forgot.title')}
      sub={t('auth.forgot.sub')}
      onSubmit={handleSubmit}
    >
      <FormField
        label={t('auth.common.email')}
        name="forgot-email"
        type="email"
        value={form.email}
        onChange={set('email')}
        onBlur={blur('email')}
        error={errors.email ? t(errors.email) : null}
        autoComplete="email"
        disabled={busy || success}
        maxLength={254}
      />
      <div className="tfrow">
        <FormField
          label={t('auth.common.code')}
          name="forgot-code"
          type="text"
          value={form.code}
          onChange={set('code')}
          onBlur={blur('code')}
          error={errors.code ? t(errors.code) : null}
          inputMode="numeric"
          disabled={busy || success}
          maxLength={6}
        />
        <CodeSendButton
          validate={validateEmailForCode}
          onSend={handleSendCode}
          onError={(err) => setTopError(apiErrorMessage(t, err))}
          disabled={busy || success}
        />
      </div>
      <FormField
        label={t('auth.common.newPassword')}
        name="forgot-new-password"
        type="password"
        value={form.newPassword}
        onChange={set('newPassword')}
        onBlur={blur('newPassword')}
        error={errors.newPassword ? t(errors.newPassword) : null}
        autoComplete="new-password"
        disabled={busy || success}
        maxLength={64}
      />
      <ErrorAlert message={topError} />
      {success ? <div className="loginsuccess" role="status">{t('auth.forgot.success')}</div> : null}
      <SubmitButton
        label={t('auth.forgot.submit')}
        busyLabel={t('auth.forgot.busy')}
        busy={busy}
        disabled={success}
      />
      <div className="authlinks">
        <Link to="/login">{t('auth.common.goLogin')}</Link>
      </div>
      <LangToggle />
    </AuthCard>
  )
}
