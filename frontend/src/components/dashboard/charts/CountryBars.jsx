// ============================================================
// CountryBars.jsx — 横向条形图（国家分布，DESIGN §6.2）
// 移植 HTML renderCountries 几何：行高 38、labelW=min(150, W×0.3)、
// 行尾 usdWhole 整美元、行级 hit-rect tooltip（国家+订单数+USD+币种拆分）。
// 折叠（前 9 + __other）由后端完成（bars 数组即渲染序，AC-N1）。
// ============================================================

import { TipHead, TipRow, useTip } from './Tooltip'
import { barPathH } from './chartMath'
import useElementSize from './useElementSize'

const ROW_H = 38
const VALUE_W = 76
const BAR_H = 16

/**
 * @param {{
 *   rows: Array<{label: string, usd: number, usdDisplay: string, ordersDisplay: string,
 *                byCurrency: Array<{currency: string, display: string}>}>,
 *   ariaLabel: string, fallbackW?: number, usdLabel: string,
 * }} props
 */
export default function CountryBars({ rows, ariaLabel, fallbackW = 600, usdLabel }) {
  const [boxRef, width] = useElementSize()
  const tip = useTip()

  if (!rows.length) {
    return (
      <div className="chartbox" ref={boxRef} />
    )
  }

  const W = Math.max(320, width || fallbackW)
  const labelW = Math.min(150, W * 0.3)
  const H = rows.length * ROW_H + 6
  const plotW = W - labelW - VALUE_W - 8
  const maxUsd = Math.max(...rows.map((r) => r.usd))

  const buildTipNode = (r) => (
    <div>
      <TipHead>
        {r.label} · {r.ordersDisplay}
      </TipHead>
      <TipRow label={usdLabel} value={r.usdDisplay} />
      {r.byCurrency.map((bc) => (
        <TipRow key={bc.currency} label={bc.currency} value={bc.display} />
      ))}
    </div>
  )

  return (
    <div className="chartbox" ref={boxRef}>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img" aria-label={ariaLabel}>
        {rows.map((r, i) => {
          const y = i * ROW_H + 6
          const w = maxUsd ? Math.max(2, (r.usd / maxUsd) * plotW) : 2
          return (
            <g key={r.label}>
              <text
                x={labelW - 10}
                y={y + BAR_H / 2 + 4}
                textAnchor="end"
                fill="var(--ink)"
                fontSize={12.5}
              >
                {r.label}
              </text>
              <path d={barPathH(labelW, y, w, BAR_H)} fill="var(--series)" />
              <text
                x={labelW + w + 8}
                y={y + BAR_H / 2 + 4}
                fill="var(--ink2)"
                fontSize={11.5}
                style={{ fontVariantNumeric: 'tabular-nums' }}
              >
                {r.usdDisplay}
              </text>
              <rect
                x={0}
                y={i * ROW_H}
                width={W}
                height={ROW_H}
                className="bar-hit"
                tabIndex={0}
                role="img"
                aria-label={`${r.label}: ${r.usdDisplay}`}
                onPointerMove={(ev) => tip.show(buildTipNode(r), ev.clientX, ev.clientY)}
                onPointerLeave={tip.hide}
                onFocus={(ev) => {
                  const b = ev.currentTarget.getBoundingClientRect()
                  tip.show(buildTipNode(r), b.left + labelW, b.top + 20)
                }}
                onBlur={tip.hide}
              />
            </g>
          )
        })}
      </svg>
    </div>
  )
}
