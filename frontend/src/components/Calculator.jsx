// ============================================================
// Calculator.jsx — 全局悬浮计算器（REQ-20261023-01，v2 带括号）
// 右下角浮窗按钮（自身可拖动）+ 可拖动面板；挂载在 App 路由之外
// （不绑定页面，切换页面不消失、位置保留）。
// v2（用户 2026-10-23 定稿）：表达式计算器——主行=完整算式（所按
// 数字与运算符全程可见，含括号），副行=实时预览结果；自研递归下降
// 解析（~60 行，不引库）：+ − × ÷、括号、后缀 %、一元负号、隐式乘法
// （数字紧贴括号）。纯本地工具，不涉接口与业务金额。
// ============================================================

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import useAuth from '../auth/useAuth'

const MAX_LEN = 40 // 算式长度上限（字符）

// ---------- 表达式求值（递归下降；无效/除零 → null）----------
// expr   := term (('+'|'−') term)*
// term   := unary (('×'|'÷') unary)*
// unary  := '−' unary | postfix
// postfix:= primary '%'*
// primary:= number | '(' expr ')'
function evaluateExpr(src) {
  let i = 0
  const n = src.length

  const peek = () => {
    while (i < n && src[i] === ' ') i += 1
    return src[i]
  }

  function parsePrimary() {
    const c = peek()
    if (c === undefined) return null
    if (c === '(') {
      i += 1
      const v = parseExpr()
      if (v === null || peek() !== ')') return null
      i += 1
      return v
    }
    if (c >= '0' && c <= '9') {
      const start = i
      while (i < n && ((src[i] >= '0' && src[i] <= '9') || src[i] === '.')) i += 1
      const num = Number.parseFloat(src.slice(start, i))
      return Number.isFinite(num) ? num : null
    }
    return null
  }
  function parsePostfix() {
    let v = parsePrimary()
    if (v === null) return null
    while (peek() === '%') {
      i += 1
      v /= 100
    }
    return v
  }
  function parseUnary() {
    if (peek() === '−') {
      i += 1
      const v = parseUnary()
      return v === null ? null : -v
    }
    return parsePostfix()
  }
  function parseTerm() {
    let v = parseUnary()
    for (;;) {
      if (v === null) return null
      const c = peek()
      if (c === '×' || c === '÷') {
        i += 1
        const r = parseUnary()
        if (r === null) return null
        v = c === '×' ? v * r : r === 0 ? null : v / r
      } else if (c !== undefined && (c === '(' || (c >= '0' && c <= '9'))) {
        // 隐式乘法：数字/括号紧贴前一因子（如 3(2+1)、(1+2)(3+4)）
        const r = parseUnary()
        if (r === null) return null
        v *= r
      } else {
        return v
      }
    }
  }
  function parseExpr() {
    let v = parseTerm()
    while (v !== null && (peek() === '+' || peek() === '−')) {
      const op = src[i]
      i += 1
      const r = parseTerm()
      if (r === null) return null
      v = op === '+' ? v + r : v - r
    }
    return v
  }

  const v = parseExpr()
  while (i < n && src[i] === ' ') i += 1
  if (v === null || i !== n || !Number.isFinite(v)) return null
  return v
}

/** 展示格式化：隐藏浮点噪声（0.1+0.2 → 0.3） */
function fmtNum(v) {
  return String(Number.parseFloat(v.toPrecision(12)))
}

const OPS = '+−×÷'
const isOp = (ch) => OPS.includes(ch)

/** 按一个键 → 新算式（纯函数：输入卫生规则 + 等号结算） */
function applyKey(prev, key) {
  const last = prev.slice(-1)
  const before = prev.slice(-2, -1)
  const opens = (prev.match(/\(/g) || []).length - (prev.match(/\)/g) || []).length
  // 尾随的一元负号："(" 后 / 运算符后 / 起头的 −（其后才是操作数）
  const tailIsUnaryMinus = last === '−' && (prev.length === 1 || isOp(before) || before === '(')

  switch (key) {
    case 'C':
      return ''
    case 'DEL':
      return prev.slice(0, -1)
    case '(': {
      // 数字 / ) / % 后接 ( → 隐式乘法
      const sep = /[0-9)%]$/.test(prev) ? '×' : ''
      return (prev + sep + '(').slice(0, MAX_LEN)
    }
    case ')':
      // 有未闭合 ( 且末位是数/) /% 才收口（防空括号与悬空运算符）
      return opens > 0 && /[0-9)%]$/.test(prev) ? prev + ')' : prev
    case '.': {
      const tail = prev.split(/[+(×÷−(]/).pop() // 当前操作数
      if (tail.includes('.')) return prev
      if (tail === '') return (prev + '0.').slice(0, MAX_LEN)
      return (prev + '.').slice(0, MAX_LEN)
    }
    case '=': {
      let src = prev
      for (let k = 0; k < opens; k += 1) src += ')' // 等号自动补齐未闭合括号
      const v = evaluateExpr(src)
      return v === null ? null : fmtNum(v) // null = 无效/除零，由调用方转错误态
    }
    default: {
      if (isOp(key)) {
        let base = prev
        if (tailIsUnaryMinus) base = base.slice(0, -1) // 先剥掉一元负号再按二元规则处理
        if (base === '') return key === '−' ? '−' : '' // 起头仅允许一元 −
        const b = base.slice(-1)
        // 尾随二元运算符：接 − = 一元负号（如 5×−3）；其余二元 → 覆盖前一个
        if (isOp(b)) return key === '−' ? base + key : base.slice(0, -1) + key
        if (b === '(') return key === '−' ? base + key : base // '(' 后仅允许一元 −
        return (base + key).slice(0, MAX_LEN)
      }
      // 数字：) / % 后接数字 → 隐式乘法；单 0 起头不叠 0
      const sep = /[)%]$/.test(prev) ? '×' : ''
      const base = prev === '0' && sep === '' ? '' : prev + sep
      return (base + key).slice(0, MAX_LEN)
    }
  }
}

// ---------- 拖动（视口钳制；面板内按钮点击不受影响）----------
function useDrag(onMove) {
  const dragRef = useRef(null)
  const onPointerDown = useCallback((e) => {
    if (e.button !== 0) return
    // 目标是按钮且拖动宿主不是按钮本身（浮窗按钮 data-draggable）→ 不拖
    if (e.target instanceof Element && e.target.closest('button') && !e.currentTarget.dataset.draggable) {
      return
    }
    const rect = e.currentTarget.getBoundingClientRect()
    dragRef.current = { startX: e.clientX, startY: e.clientY, originX: rect.left, originY: rect.top }
    e.currentTarget.setPointerCapture(e.pointerId)
    e.currentTarget.dataset.moved = '' // 位移 <3px 视为点击不视为拖动
  }, [])
  const onPointerMove = useCallback(
    (e) => {
      const d = dragRef.current
      if (!d) return
      const dx = e.clientX - d.startX
      const dy = e.clientY - d.startY
      if (Math.abs(dx) + Math.abs(dy) > 3) e.currentTarget.dataset.moved = '1'
      const x = Math.min(Math.max(0, d.originX + dx), window.innerWidth - e.currentTarget.offsetWidth)
      const y = Math.min(Math.max(0, d.originY + dy), window.innerHeight - e.currentTarget.offsetHeight)
      onMove({ x, y })
    },
    [onMove],
  )
  const onPointerUp = useCallback((e) => {
    dragRef.current = null
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId)
    }
  }, [])
  return { onPointerDown, onPointerMove, onPointerUp }
}

export default function CalculatorWidget() {
  const { t } = useTranslation()
  const { user } = useAuth()

  const [open, setOpen] = useState(false)
  const [fabPos, setFabPos] = useState(null) // null=CSS 锚定右下；拖动后 {x,y}
  const [pos, setPos] = useState(null) // 面板位置，同上
  const [expr, setExpr] = useState('') // 主行：完整算式（所按即所见）
  const [error, setError] = useState(false)
  const [justEvaluated, setJustEvaluated] = useState(false) // 等号刚结算：数字/./（ 重新起式

  const fabDrag = useDrag(setFabPos)
  const panelDrag = useDrag(setPos)

  // 副行：实时预览结果（刚结算时不重复显示）
  const preview = useMemo(() => {
    if (error || !expr || justEvaluated) return null
    const v = evaluateExpr(expr)
    return v === null ? null : fmtNum(v)
  }, [expr, error, justEvaluated])

  const press = useCallback(
    (key) => {
      let prev = expr
      if (error) prev = '' // 错误态任意键 → 重新开始
      // 等号结算后：数字/./（/C 起新式；运算符/)/% 接在结果后继续
      else if (justEvaluated && (/[0-9.(]/.includes(key) || key === 'C')) prev = ''
      const next = applyKey(prev, key)
      if (key === '=') {
        if (next === null) {
          setError(true) // 无效算式/除零
          return
        }
        setExpr(next)
        setJustEvaluated(true)
        setError(false)
        return
      }
      setExpr(next)
      setError(false)
      setJustEvaluated(false)
    },
    [expr, error, justEvaluated],
  )

  // ---- 键盘 ----
  useEffect(() => {
    if (!open) return undefined
    const onKey = (e) => {
      const k = e.key
      if (/^[0-9]$/.test(k)) press(k)
      else if (k === '.') press('.')
      else if (k === '+') press('+')
      else if (k === '-') press('−')
      else if (k === '*') press('×')
      else if (k === '/') press('÷')
      else if (k === '(' || k === ')') press(k)
      else if (k === '%') press('%')
      else if (k === 'Enter' || k === '=') press('=')
      else if (k === 'Backspace') press('DEL')
      else if (k === 'Escape') setOpen(false)
      else return
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, press])

  if (!user) return null // 认证页（未登录）不显示

  const btn = (label, onPress, kind = '') => (
    <button type="button" className={`calc-btn ${kind}`} onClick={() => press(onPress)}>
      {label}
    </button>
  )

  return (
    <>
      <button
        type="button"
        className="calc-fab"
        data-draggable="1"
        aria-pressed={open}
        aria-expanded={open}
        aria-label={t('calc.open')}
        style={fabPos ? { left: fabPos.x, top: fabPos.y, right: 'auto', bottom: 'auto' } : undefined}
        onPointerDown={fabDrag.onPointerDown}
        onPointerMove={fabDrag.onPointerMove}
        onPointerUp={fabDrag.onPointerUp}
        onClick={(e) => {
          if (e.currentTarget.dataset.moved === '1') return // 拖动尾随的 click 不触发开关
          setOpen((v) => !v)
        }}
      >
        {t('calc.open')}
      </button>
      {open ? (
        <div
          className="calc-panel"
          role="dialog"
          aria-label={t('calc.title')}
          style={pos ? { left: pos.x, top: pos.y, right: 'auto', bottom: 'auto' } : undefined}
          onPointerDown={panelDrag.onPointerDown}
          onPointerMove={panelDrag.onPointerMove}
          onPointerUp={panelDrag.onPointerUp}
        >
          <div className="calc-head">
            <span className="calc-title">{t('calc.title')}</span>
            <button type="button" className="calc-close" onClick={() => setOpen(false)}>
              {t('calc.close')}
            </button>
          </div>
          <div className="calc-display">
            <div className="calc-expr" aria-live="polite">
              {error ? t('calc.error') : expr || '0'}
            </div>
            <div className="calc-main">{preview !== null ? `= ${preview}` : ' '}</div>
          </div>
          <div className="calc-keys">
            {btn('C', 'C', 'fn')}
            {btn('DEL', 'DEL', 'fn')}
            {btn('%', '%', 'fn')}
            {btn('÷', '÷', 'op')}
            {btn('7', '7')}
            {btn('8', '8')}
            {btn('9', '9')}
            {btn('×', '×', 'op')}
            {btn('4', '4')}
            {btn('5', '5')}
            {btn('6', '6')}
            {btn('−', '−', 'op')}
            {btn('1', '1')}
            {btn('2', '2')}
            {btn('3', '3')}
            {btn('+', '+', 'op')}
            {btn('(', '(', 'fn')}
            {btn('0', '0')}
            {btn('.', '.')}
            {btn(')', ')', 'fn')}
            <button type="button" className="calc-btn eq wide" onClick={() => press('=')}>
              =
            </button>
          </div>
        </div>
      ) : null}
    </>
  )
}
