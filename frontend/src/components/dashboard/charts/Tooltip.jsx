// ============================================================
// Tooltip.jsx — 单例 tooltip（portal 定位 + 视口钳制，DESIGN §6.2）
// 对标 HTML showTip/hideTip（fixed + max(8, min(x+14, vw-w-8))）。
// 内容由调用方以 React 节点传入（后端字符串直渲染，无 innerHTML）。
// ============================================================

import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

const TooltipContext = createContext(null)

const NOOP_TIP = { show: () => {}, hide: () => {} }

// eslint-disable-next-line react-refresh/only-export-components -- hook 与 Provider 同文件（图表 tooltip 单例，无独立热更新需求）
export function useTip() {
  // Provider 缺席时退化为无操作（防御：图表组件不因此崩溃）
  return useContext(TooltipContext) || NOOP_TIP
}

export function TooltipProvider({ children }) {
  const [tip, setTip] = useState(null) // { node, x, y }
  const api = useMemo(
    () => ({
      show: (node, x, y) => setTip({ node, x, y }),
      hide: () => setTip(null),
    }),
    [],
  )
  return (
    <TooltipContext.Provider value={api}>
      {children}
      <TipPortal tip={tip} />
    </TooltipContext.Provider>
  )
}

function TipPortal({ tip }) {
  const ref = useRef(null)
  const [pos, setPos] = useState(null)

  useEffect(() => {
    if (!tip) {
      setPos(null)
      return undefined
    }
    const r = ref.current ? ref.current.getBoundingClientRect() : null
    if (!r || !r.width) return undefined
    setPos({
      left: Math.max(8, Math.min(tip.x + 14, window.innerWidth - r.width - 8)),
      top: Math.max(8, Math.min(tip.y + 14, window.innerHeight - r.height - 8)),
    })
    return undefined
  }, [tip])

  if (!tip) return null
  const style = pos
    ? { left: `${pos.left}px`, top: `${pos.top}px` }
    : { left: '-9999px', top: '-9999px' } // 首帧先离屏，量宽后再入视口
  return createPortal(
    <div className="tip" role="status" ref={ref} style={style}>
      {tip.node}
    </div>,
    document.body,
  )
}

/** tooltip 行结构（对标 .tip .row/.head/.key） */
export function TipRow({ colorKey, label, value }) {
  return (
    <div className="row">
      <span>
        {colorKey ? <span className="key" style={{ borderTopColor: colorKey }} /> : null}
        {label}
      </span>
      <span className="v">{value}</span>
    </div>
  )
}

export function TipHead({ children }) {
  return <div className="head">{children}</div>
}
