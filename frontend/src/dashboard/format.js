// ============================================================
// format.js — 本地化格式化 + 国家名映射（DESIGN §5.3/§6.2）
// 数字/货币/日期格式随 locale 重建（AC-I3，对标 HTML buildFormatters）；
// countryOf 集中映射：__unknown → i18n；两位区域码 → Intl.DisplayNames；
// 其余原串直出（AC-N2）。
// 金额纪律：本模块只做「后端字符串 → Intl 展示」，不做任何金额运算。
// ============================================================

import { parseDateKey } from './range'

/**
 * 按 locale 构建格式化器（语言切换时重建，AC-I3）。
 * @param {string} locale 'en-US' | 'zh-CN'
 */
export function buildFormatters(locale) {
  const regionNames = (() => {
    try {
      return new Intl.DisplayNames([locale], { type: 'region' })
    } catch (e) {
      return null
    }
  })()
  return {
    locale,
    usd: new Intl.NumberFormat(locale, { style: 'currency', currency: 'USD' }),
    usdExact: new Intl.NumberFormat(locale, {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 4,
    }),
    usdWhole: new Intl.NumberFormat(locale, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }),
    native: new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    int: new Intl.NumberFormat(locale),
    dayLabel: new Intl.DateTimeFormat(locale, { month: 'short', day: 'numeric' }),
    fullDate: new Intl.DateTimeFormat(locale, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    }),
    time: new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    regionNames,
  }
}

/** 后端金额字符串（主单位 2 位小数）→ 货币展示（渲染，非运算） */
export function money(fmt, amountString) {
  return fmt.usd.format(Number(amountString))
}

/**
 * 后端真值金额字符串（最多 4 位小数，REQ-20261014-01 分成类卡片）→ 货币展示。
 * 不做任何舍入：后端已给真值（如 15549.1635），Intl 仅分组千分位。
 */
export function moneyExact(fmt, amountString) {
  return fmt.usdExact.format(Number(amountString))
}

/** 整美元展示（国家条行尾，HTML usdWhole） */
export function moneyWhole(fmt, amountString) {
  return fmt.usdWhole.format(Number(amountString))
}

/** 原币金额展示（对比卡 native 列 / 国家 by_currency） */
export function nativeMoney(fmt, amountString) {
  return fmt.native.format(Number(amountString))
}

export function intNum(fmt, value) {
  return fmt.int.format(value)
}

/** 'YYYY-MM-DD' → x 轴短标签（HTML dayLabelFmt） */
export function dayLabel(fmt, dateStr) {
  return fmt.dayLabel.format(parseDateKey(dateStr))
}

/** 'YYYY-MM-DD' → tooltip 头部长日期（HTML toLocaleDateString） */
export function fullDateLabel(fmt, dateStr) {
  return fmt.fullDate.format(parseDateKey(dateStr))
}

/** ISO 时间戳 → 状态行本地时间（AC-S2「更新于 {t}」） */
export function timeLabel(fmt, isoString) {
  if (!isoString) return ''
  const d = new Date(isoString)
  if (Number.isNaN(d.getTime())) return ''
  return fmt.time.format(d)
}

/**
 * 国家 key → 展示名（AC-N2 / DESIGN §5.3 countryOf）。
 * @param {string} key 区域码（'US'）/ 原语种串 / '__unknown'
 * @param {object} fmt buildFormatters 产物
 * @param {string} unknownLabel t('dashboard.unknownCountry')
 */
export function countryName(key, fmt, unknownLabel) {
  const k = String(key || '').trim()
  if (!k || k === '__unknown') return unknownLabel
  if (/^[A-Za-z]{2}$/.test(k)) {
    if (fmt.regionNames) {
      try {
        return fmt.regionNames.of(k.toUpperCase()) || k
      } catch (e) {
        return k
      }
    }
    return k.toUpperCase()
  }
  return k
}
