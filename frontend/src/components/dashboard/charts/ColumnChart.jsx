// ============================================================
// ColumnChart.jsx — 堆叠柱状图（每日双卡 + 广告卡共用，DESIGN §6.2/S1）
// 移植 HTML renderDailyCard/renderAdChart：4 档 y 网格 + niceCeil 轴、
// labelEvery=ceil(n/8) x 标签、段间 2px 缝 / 仅顶段 4px 圆角、
// 透明 bar-hit（tabIndex=0、逐柱 aria-label）、十字准线 + tooltip、图例。
// yMax 由外部传入（双卡共享上限，AC-E2）；广告卡=单序列 --ad 复用本组件。
// 金额纪律：seg.amount 仅几何；展示值用 seg.display（后端字符串 + Intl）。
// ============================================================

import { useRef } from 'react'

import { dayLabel, fullDateLabel } from '../../../dashboard/format'
import useElementSize from './useElementSize'
import { columnPath, axisMoney } from './chartMath'
import { TipHead, TipRow, useTip } from './Tooltip'

const M = { top: 14, right: 12, bottom: 30, left: 56 }
const TICKS = 4

/**
 * @param {{
 *   rows: Array<{date: string, total: number, count: number, totalDisplay: string, countDisplay: string,
 *                segs: Array<{label: string, color: string, amount: number, display: string}>}>,
 *   series: Array<{label: string, color: string}>,
 *   yMax: number, plotH?: number, fallbackW?: number,
 *   ariaLabel: string, totalLabel: string, ordersLabel?: string, showOrders?: boolean,
 *   crosshair?: boolean, fmt: object, emptyLabel?: string,
 * }} props
 */
export default function ColumnChart({
  rows,
  series,
  yMax,
  plotH = 240,
  fallbackW = 800,
  ariaLabel,
  totalLabel,
  ordersLabel = '',
  showOrders = true,
  crosshair = true,
  fmt,
  emptyLabel = '',
}) {
  const [boxRef, width] = useElementSize()
  const tip = useTip()
  const crosshairRef = useRef(null)

  if (emptyLabel) {
    return (
      <div className="chartbox" ref={boxRef}>
        <div className="empty">{emptyLabel}</div>
      </div>
    )
  }

  const W = Math.max(320, width || fallbackW)
  const H = M.top + plotH + M.bottom
  const plotW = W - M.left - M.right
  const safeYMax = yMax || 1
  const yScale = (v) => M.top + plotH - (v / safeYMax) * plotH
  const band = plotW / rows.length
  const barW = Math.max(3, Math.min(24, band * 0.62))
  const labelEvery = Math.ceil(rows.length / 8)

  const buildTipNode = (r) => (
    <div>
      <TipHead>{fullDateLabel(fmt, r.date)}</TipHead>
      <TipRow label={totalLabel} value={r.totalDisplay} />
      {[...r.segs]
        .filter((sg) => sg.amount > 0)
        .sort((a, b) => b.amount - a.amount)
        .map((sg) => (
          <TipRow key={sg.label} colorKey={sg.color} label={sg.label} value={sg.display} />
        ))}
      {showOrders ? <TipRow label={ordersLabel} value={r.countDisplay} /> : null}
    </div>
  )

  const gridValues = []
  for (let i = 0; i <= TICKS; i++) gridValues.push((safeYMax * i) / TICKS)

  return (
    <div className="chartbox" ref={boxRef}>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label={ariaLabel}>
        {gridValues.map((v, i) => {
          const y = yScale(v)
          return (
            <g key={i}>
              {i > 0 ? (
                <line x1={M.left} x2={W - M.right} y1={y} y2={y} stroke="var(--grid)" strokeWidth={1} />
              ) : null}
              <text x={M.left - 8} y={y + 4} textAnchor="end" className="axis-label">
                {axisMoney(v)}
              </text>
            </g>
          )
        })}
        <line
          x1={M.left}
          x2={W - M.right}
          y1={yScale(0)}
          y2={yScale(0)}
          stroke="var(--baseline)"
          strokeWidth={1}
        />
        {crosshair ? (
          <line
            ref={crosshairRef}
            y1={M.top}
            y2={M.top + plotH}
            stroke="var(--baseline)"
            strokeWidth={1}
            visibility="hidden"
          />
        ) : null}
        {rows.map((r, i) => {
          const cx = M.left + band * i + band / 2
          const x = cx - barW / 2
          const visible = r.segs.filter((sg) => sg.amount > 0)
          let cum = 0
          const hitAria = showOrders
            ? `${r.date}: ${r.totalDisplay}, ${r.countDisplay}`
            : `${r.date}: ${r.totalDisplay}`
          return (
            <g key={r.date}>
              {i % labelEvery === 0 ? (
                <text x={cx} y={H - 10} textAnchor="middle" className="axis-label">
                  {dayLabel(fmt, r.date)}
                </text>
              ) : null}
              {/* hit 在前、柱列在后：保持 CSS 兄弟悬停增亮（.bar-hit:hover + g） */}
              <rect
                x={M.left + band * i}
                y={M.top}
                width={band}
                height={plotH}
                className="bar-hit"
                tabIndex={0}
                role="img"
                aria-label={hitAria}
                onPointerMove={(ev) => {
                  if (crosshairRef.current) {
                    crosshairRef.current.setAttribute('x1', cx)
                    crosshairRef.current.setAttribute('x2', cx)
                    crosshairRef.current.setAttribute('visibility', 'visible')
                  }
                  tip.show(buildTipNode(r), ev.clientX, ev.clientY)
                }}
                onPointerLeave={() => {
                  if (crosshairRef.current) crosshairRef.current.setAttribute('visibility', 'hidden')
                  tip.hide()
                }}
                onFocus={(ev) => {
                  const b = ev.currentTarget.getBoundingClientRect()
                  tip.show(buildTipNode(r), b.left + b.width / 2, b.top + 40)
                }}
                onBlur={tip.hide}
              />
              <g>
                {visible.map((sg, k) => {
                  const yTop = yScale(cum + sg.amount)
                  const yBot = yScale(cum)
                  const isTop = k === visible.length - 1
                  let node
                  if (isTop) {
                    node = (
                      <path
                        d={columnPath(x, yTop, barW, Math.max(yBot - yTop, 1.5))}
                        fill={sg.color}
                      />
                    )
                  } else {
                    const gap = yBot - yTop > 3.5 ? 2 : 0
                    node = (
                      <rect
                        x={x}
                        y={yTop + gap}
                        width={barW}
                        height={Math.max(yBot - yTop - gap, 0.8)}
                        fill={sg.color}
                      />
                    )
                  }
                  cum += sg.amount
                  return <g key={sg.label}>{node}</g>
                })}
              </g>
            </g>
          )
        })}
      </svg>
      {series.length > 1 ? (
        <div className="legend">
          {series.map((sr) => (
            <span key={sr.label} className="li">
              <span className="sw" style={{ background: sr.color }} />
              {sr.label}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  )
}
