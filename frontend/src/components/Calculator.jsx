// ============================================================
// Calculator.jsx — 全局悬浮计算器（REQ-20261023-01）
// 右下角浮窗按钮 + 可拖动面板；挂载在 App 路由之外（不绑定页面，
// 切换页面不消失、位置保留）；登录后所有页面可用（认证页自动隐藏）。
// 纯本地工具：不请求接口、不做业务金额渲染（金额纪律不涉）。
// 极简文字风：无图标（红线 13），关闭为文字按钮；标题栏拖动。
// ============================================================

import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import useAuth from '../auth/useAuth'

const MAX_INPUT_LEN = 14
const OPS = ['÷', '×', '−', '+']

/** 四则运算；除零返回 null（由调用方转错误态） */
function compute(a, b, op) {
  switch (op) {
    case '+':
      return a + b
    case '−':
      return a - b
    case '×':
      return a * b
    case '÷':
      return b === 0 ? null : a / b
    default:
      return b
  }
}

/** 展示格式化：隐藏浮点噪声（0.1+0.2 → 0.3），过长走指数形式 */
function fmtNum(n) {
  if (!Number.isFinite(n)) return null
  return String(parseFloat(n.toPrecision(12)))
}

export default function CalculatorWidget() {
  const { t } = useTranslation()
  const { user } = useAuth()

  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState(null) // null=CSS 默认锚定（右下）；拖动后为 {x,y}
  const [display, setDisplay] = useState('0')
  const [acc, setAcc] = useState(null)
  const [op, setOp] = useState(null)
  const [waiting, setWaiting] = useState(false) // 刚按过运算符/等号，下一数字重新起头
  const [error, setError] = useState(false)

  const panelRef = useRef(null)
  const dragRef = useRef(null) // {startX, startY, originX, originY, w, h}

  const reset = useCallback(() => {
    setDisplay('0')
    setAcc(null)
    setOp(null)
    setWaiting(false)
    setError(false)
  }, [])

  const inputDigit = useCallback((d) => {
    if (error) reset()
    setDisplay((prev) => {
      const base = error || waiting ? '0' : prev
      if (waiting) setWaiting(false)
      if (base === '0') return d
      return base.length < MAX_INPUT_LEN ? base + d : base
    })
  }, [error, waiting, reset])

  const inputDot = useCallback(() => {
    if (error) reset()
    setDisplay((prev) => {
      const base = error || waiting ? '0' : prev
      if (waiting) setWaiting(false)
      return base.includes('.') ? base : `${base}.`
    })
  }, [error, waiting, reset])

  const pressOp = useCallback(
    (next) => {
      if (error) return
      const cur = Number.parseFloat(display)
      if (op !== null && !waiting) {
        const r = compute(acc, cur, op)
        if (r === null) {
          setError(true)
          return
        }
        setAcc(r)
        setDisplay(fmtNum(r) ?? '0')
      } else {
        setAcc(cur)
      }
      setOp(next)
      setWaiting(true)
    },
    [error, display, op, waiting, acc],
  )

  const pressEquals = useCallback(() => {
    if (error || op === null) return
    const r = compute(acc, Number.parseFloat(display), op)
    if (r === null) {
      setError(true)
      return
    }
    setDisplay(fmtNum(r) ?? '0')
    setAcc(null)
    setOp(null)
    setWaiting(true)
  }, [error, op, acc, display])

  const backspace = useCallback(() => {
    if (error || waiting) return
    setDisplay((prev) => (prev.length <= 1 || (prev.length === 2 && prev.startsWith('-')) ? '0' : prev.slice(0, -1)))
  }, [error, waiting])

  const negate = useCallback(() => {
    if (error) return
    setDisplay((prev) => (prev === '0' ? prev : prev.startsWith('-') ? prev.slice(1) : `-${prev}`))
  }, [error])

  const percent = useCallback(() => {
    if (error) return
    setDisplay((prev) => fmtNum(Number.parseFloat(prev) / 100) ?? '0')
  }, [error])

  // ---- 拖动（标题栏 Pointer Events；钳制在视口内）----
  const onHeadPointerDown = (e) => {
    const panel = panelRef.current
    if (!panel) return
    const rect = panel.getBoundingClientRect()
    const start = pos ?? { x: rect.left, y: rect.top }
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      originX: start.x,
      originY: start.y,
      w: rect.width,
      h: rect.height,
    }
    e.currentTarget.setPointerCapture(e.pointerId)
  }
  const onHeadPointerMove = (e) => {
    const d = dragRef.current
    if (!d) return
    const x = Math.min(Math.max(0, d.originX + e.clientX - d.startX), window.innerWidth - d.w)
    const y = Math.min(Math.max(0, d.originY + e.clientY - d.startY), window.innerHeight - d.h)
    setPos({ x, y })
  }
  const onHeadPointerUp = (e) => {
    dragRef.current = null
    e.currentTarget.releasePointerCapture(e.pointerId)
  }

  // ---- 键盘（面板打开时）----
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      const k = e.key
      if (/^[0-9]$/.test(k)) inputDigit(k)
      else if (k === '.') inputDot()
      else if (k === '+') pressOp('+')
      else if (k === '-') pressOp('−')
      else if (k === '*') pressOp('×')
      else if (k === '/') pressOp('÷')
      else if (k === 'Enter' || k === '=') pressEquals()
      else if (k === 'Backspace') backspace()
      else if (k === '%') percent()
      else if (k === 'Escape') setOpen(false)
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, inputDigit, inputDot, pressOp, pressEquals, backspace, percent])

  if (!user) return null // 认证页（未登录）不显示

  const btn = (label, onClick, kind = '') => (
    <button type="button" className={`calc-btn ${kind}`} onClick={onClick}>
      {label}
    </button>
  )

  return (
    <>
      <button
        type="button"
        className="calc-fab"
        aria-pressed={open}
        aria-expanded={open}
        aria-label={t('calc.open')}
        onClick={() => setOpen((v) => !v)}
      >
        {t('calc.open')}
      </button>
      {open ? (
        <div
          ref={panelRef}
          className="calc-panel"
          role="dialog"
          aria-label={t('calc.title')}
          style={pos ? { left: pos.x, top: pos.y } : undefined}
        >
          <div
            className="calc-head"
            onPointerDown={onHeadPointerDown}
            onPointerMove={onHeadPointerMove}
            onPointerUp={onHeadPointerUp}
          >
            <span className="calc-title">{t('calc.title')}</span>
            <button type="button" className="calc-close" onClick={() => setOpen(false)}>
              {t('calc.close')}
            </button>
          </div>
          <div className="calc-display" aria-live="polite">
            {error ? t('calc.error') : display}
          </div>
          <div className="calc-keys">
            {btn('C', reset, 'fn')}
            {btn('DEL', backspace, 'fn')}
            {btn('%', percent, 'fn')}
            {btn('÷', () => pressOp('÷'), 'op')}
            {btn('7', () => inputDigit('7'))}
            {btn('8', () => inputDigit('8'))}
            {btn('9', () => inputDigit('9'))}
            {btn('×', () => pressOp('×'), 'op')}
            {btn('4', () => inputDigit('4'))}
            {btn('5', () => inputDigit('5'))}
            {btn('6', () => inputDigit('6'))}
            {btn('−', () => pressOp('−'), 'op')}
            {btn('1', () => inputDigit('1'))}
            {btn('2', () => inputDigit('2'))}
            {btn('3', () => inputDigit('3'))}
            {btn('+', () => pressOp('+'), 'op')}
            {btn('±', negate, 'fn')}
            {btn('0', () => inputDigit('0'))}
            {btn('.', inputDot)}
            {btn('=', pressEquals, 'eq')}
          </div>
        </div>
      ) : null}
    </>
  )
}
