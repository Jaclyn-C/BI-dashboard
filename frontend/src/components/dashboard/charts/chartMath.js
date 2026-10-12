// ============================================================
// chartMath.js — SVG 几何助手（DESIGN §6.2，HTML:1890-1914 逐函数移植）
// ⚠️ 金额纪律：本模块只做几何（路径/刻度/轴缩写），
//    Number() 仅用于把后端字符串转成几何量，绝不做金额加减。
// ============================================================

/** 柱形路径：仅顶端 4px 圆角（堆叠段只有最顶段用它） */
export function columnPath(x, y, w, hgt) {
  const r = Math.min(4, hgt, w / 2)
  const x2 = x + w
  const y0 = y + hgt
  return `M${x},${y0} V${y + r} Q${x},${y} ${x + r},${y} H${x2 - r} Q${x2},${y} ${x2},${y + r} V${y0} Z`
}

/** 横条路径：右端 4px 圆角（国家条形图） */
export function barPathH(x, y, w, hgt) {
  const r = Math.min(4, w, hgt / 2)
  const y2 = y + hgt
  const x2 = x + w
  return `M${x},${y} H${x2 - r} Q${x2},${y} ${x2},${y + r} V${y2 - r} Q${x2},${y2} ${x2 - r},${y2} H${x} Z`
}

/** 环图切片路径（外弧 R → 内弧 RI，顺时针） */
export function donutArc(cx, cy, rO, rI, a0, a1) {
  const large = a1 - a0 > Math.PI ? 1 : 0
  const pt = (r, a) => `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`
  return `M${pt(rO, a0)} A${rO},${rO} 0 ${large} 1 ${pt(rO, a1)} L${pt(rI, a1)} A${rI},${rI} 0 ${large} 0 ${pt(rI, a0)} Z`
}

/** y 轴上限：向上取整到 1/2/2.5/5×10ⁿ（HTML niceCeil，AC-E6） */
export function niceCeil(v) {
  const p = Math.pow(10, Math.floor(Math.log10(v)))
  const n = v / p
  const m = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10
  return m * p
}

/** 轴金额缩写：$K / 整数 / 两位小数（HTML axisMoney，AC-E6） */
export function axisMoney(v) {
  if (v >= 1000) return '$' + (v / 1000).toFixed(v % 1000 ? 1 : 0) + 'K'
  return '$' + (v % 1 ? v.toFixed(2) : v)
}
