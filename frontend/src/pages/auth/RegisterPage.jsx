// RegisterPage — /register（DESIGN §5.1 F3）
// 邮箱 + 昵称 + 密码 + 验证码；CodeSendButton 前端先验邮箱（AC-R1）；
// 注册成功自动登录跳 '/'（AC-R3）。

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { sendRegisterCode } from '../../api/auth'
import useAuth from '../../auth/useAuth'
import AuthCard from '../../components/auth/AuthCard'
import CodeSendButton from '../../components/auth/CodeSendButton'
import ErrorAlert from '../../components/auth/ErrorAlert'
import FormField from '../../components/auth/FormField'
import LangToggle from '../../components/auth/LangToggle'
import SubmitButton from '../../components/auth/SubmitButton'
import { apiErrorMessage } from '../../utils/apiErrorMessage'
import {
  validateCode,
  validateEmail,
  validateNickname,
  validatePassword,
} from '../../utils/validation'
import usePageTitle from '../../utils/usePageTitle'

export default function RegisterPage() {
  const { t } = useTranslation()
  const { registerAndLogin, user, booting } = useAuth()
  const navigate = useNavigate()
  usePageTitle('common.pageTitle.register')

  const [form, setForm] = useState({ email: '', nickname: '', password: '', code: '' })
  const [errors, setErrors] = useState({})
  const [topError, setTopError] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!booting && user) navigate('/', { replace: true })
  }, [booting, user, navigate])

  const set = (field) => (e) => setForm((p) => ({ ...p, [field]: e.target.value }))

  const blurValidators = {
    email: () => validateEmail(form.email),
    nickname: () => validateNickname(form.nickname),
    password: () => validatePassword(form.password),
    code: () => validateCode(form.code),
  }
  const blur = (field) => () =>
    setErrors((p) => ({ ...p, [field]: blurValidators[field]() }))

  /** 发码前邮箱校验（AC-R1）：不合法不发请求，显示行内错误 */
  function validateEmailForCode() {
    const err = validateEmail(form.email)
    setErrors((p) => ({ ...p, email: err }))
    return err
  }

  async function handleSendCode() {
    await sendRegisterCode(form.email)
  }

  async function handleSubmit(e) {
    e.preventDefault()
    const fieldErrors = {
      email: validateEmail(form.email),
      nickname: validateNickname(form.nickname),
      password: validatePassword(form.password),
      code: validateCode(form.code),
    }
    setErrors(fieldErrors)
    setTopError(null)
    if (Object.values(fieldErrors).some(Boolean)) return

    setBusy(true)
    try {
      // 提交口径与校验口径一致（validation.js 对昵称/验证码先 trim 再比对）：
      // 「 小明 」能过前端校验，就必须以 trim 后的值提交，否则会被后端 422 通用文案拒绝
      await registerAndLogin({
        ...form,
        nickname: form.nickname.trim(),
        code: form.code.trim(),
      })
      navigate('/', { replace: true })
    } catch (err) {
      setTopError(apiErrorMessage(t, err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard
      title={t('auth.register.title')}
      sub={t('auth.register.sub')}
      onSubmit={handleSubmit}
    >
      <FormField
        label={t('auth.common.email')}
        name="reg-email"
        type="email"
        value={form.email}
        onChange={set('email')}
        onBlur={blur('email')}
        error={errors.email ? t(errors.email) : null}
        autoComplete="email"
        disabled={busy}
        maxLength={254}
      />
      <FormField
        label={t('auth.common.nickname')}
        name="reg-nickname"
        type="text"
        value={form.nickname}
        onChange={set('nickname')}
        onBlur={blur('nickname')}
        error={errors.nickname ? t(errors.nickname) : null}
        autoComplete="nickname"
        disabled={busy}
        maxLength={30}
      />
      <FormField
        label={t('auth.common.password')}
        name="reg-password"
        type="password"
        value={form.password}
        onChange={set('password')}
        onBlur={blur('password')}
        error={errors.password ? t(errors.password) : null}
        autoComplete="new-password"
        disabled={busy}
        maxLength={64}
      />
      <div className="tfrow">
        <FormField
          label={t('auth.common.code')}
          name="reg-code"
          type="text"
          value={form.code}
          onChange={set('code')}
          onBlur={blur('code')}
          error={errors.code ? t(errors.code) : null}
          inputMode="numeric"
          disabled={busy}
          maxLength={6}
        />
        <CodeSendButton
          validate={validateEmailForCode}
          onSend={handleSendCode}
          onError={(err) => setTopError(apiErrorMessage(t, err))}
          disabled={busy}
        />
      </div>
      <ErrorAlert message={topError} />
      <SubmitButton
        label={t('auth.register.submit')}
        busyLabel={t('auth.register.busy')}
        busy={busy}
      />
      <div className="authlinks">
        <Link to="/login">{t('auth.common.goLogin')}</Link>
      </div>
      <LangToggle />
    </AuthCard>
  )
}
