// ============================================================
// DonutChart.jsx — 环图（DESIGN §6.2；REQ-20261015-01 单环）
// 移植 HTML convDonut：SIZE 200 / R 90 / RI 55、surface 描边 2px、
// 切片 class=「slice」可键盘聚焦（tabIndex=0）触发 tooltip、
// 环心 usdWhole 合计。切片占比仅几何比例；展示值用 display/shareDisplay。
// 占比标注：切片 ≥5.5% 时在弧带中点画百分比（窄切片挤不下，悬停提示兜底）；
// 文字 surface 色 + 切片色描边（paint-order），任何切片色上都可读。
// ============================================================

import { TipHead, TipRow, useTip } from './Tooltip'
import { donutArc } from './chartMath'

const SIZE = 200
const CX = 100
const CY = 100
const R = 90
const RI = 55
const RLABEL = (R + RI) / 2 // 占比标注半径（弧带中点）
const SHARE_LABEL_MIN_FRAC = 0.055

/**
 * @param {{
 *   slices: Array<{label: string, color: string, value: number, display: string, shareDisplay: string}>,
 *   centerDisplay: string, ariaLabel: string, shareLabel: string,
 * }} props
 */
export default function DonutChart({ slices, centerDisplay, ariaLabel, shareLabel }) {
  const tip = useTip()
  const withValue = slices.filter((sl) => sl.value > 0)
  const total = withValue.reduce((a, sl) => a + sl.value, 0) // 几何归一化基数（仅用于弧长比例）

  if (!withValue.length || total <= 0) {
    return (
      <div className="chartbox">
        <div className="empty">—</div>
      </div>
    )
  }

  const buildTipNode = (sl) => (
    <div>
      <TipHead>
        {ariaLabel} · {sl.label}
      </TipHead>
      <TipRow colorKey={sl.color} label="USD" value={sl.display} />
      <TipRow label={shareLabel} value={sl.shareDisplay} />
    </div>
  )

  let angle = -Math.PI / 2
  const arcs = withValue.map((sl) => {
    const frac = sl.value / total
    const a0 = angle
    const a1 = angle + Math.min(frac * 2 * Math.PI, 2 * Math.PI - 1e-4)
    angle = a1
    // 占比标注：弧带中点坐标（frac 过小不标，避免文字相撞）
    const labelled = frac >= SHARE_LABEL_MIN_FRAC
    const mid = (a0 + a1) / 2
    return {
      sl,
      a0,
      a1,
      pct: labelled
        ? {
            x: CX + RLABEL * Math.cos(mid),
            y: CY + RLABEL * Math.sin(mid),
            text: sl.shareDisplay,
          }
        : null,
    }
  })

  return (
    <div className="chartbox">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} width={SIZE} height={SIZE} role="img" aria-label={ariaLabel}>
        {arcs.map(({ sl, a0, a1 }) => (
          <path
            key={sl.label}
            d={donutArc(CX, CY, R, RI, a0, a1)}
            fill={sl.color}
            className="slice"
            tabIndex={0}
            role="img"
            stroke="var(--surface)"
            strokeWidth={2}
            strokeLinejoin="round"
            aria-label={`${sl.label}: ${sl.display}, ${sl.shareDisplay}`}
            onPointerMove={(ev) => tip.show(buildTipNode(sl), ev.clientX, ev.clientY)}
            onPointerLeave={tip.hide}
            onFocus={(ev) => {
              const b = ev.currentTarget.getBoundingClientRect()
              tip.show(buildTipNode(sl), b.left + b.width / 2, b.top + b.height / 2)
            }}
            onBlur={tip.hide}
          />
        ))}
        {arcs.map(({ sl, pct }) =>
          pct ? (
            <text
              key={`${sl.label}-pct`}
              x={pct.x}
              y={pct.y}
              textAnchor="middle"
              dominantBaseline="central"
              fontSize={10.5}
              fontWeight={500}
              fill="var(--surface)"
              stroke={sl.color}
              strokeWidth={2.5}
              strokeLinejoin="round"
              paintOrder="stroke"
              pointerEvents="none"
            >
              {pct.text}
            </text>
          ) : null,
        )}
        <text
          x={CX}
          y={CY + 4}
          textAnchor="middle"
          fill="var(--ink)"
          fontSize={17}
          fontWeight={700}
        >
          {centerDisplay}
        </text>
      </svg>
    </div>
  )
}
