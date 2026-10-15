// ============================================================
// DashboardPage.jsx — 看板页状态中枢（DESIGN §6.1/§6.3，F-T3/F-T9）
// 持有 range/dataset/dailyView/filters/sort/page，向下纯受控分发；
// useSummary/useOrders/useSyncStatus 三 hook 供数（S8，无状态库）。
// 状态行（AC-S1/S2/S4 + D5 常驻注记）、五横幅（AC-S5/S7/S9/C8）、
// CSV 双档（AC-X1）、↻ 手动同步（AC-S3/S4）、币种失效回落（AC-O2）、
// 数据集全局切换（REQ-20261014-01：class 透传 summary/orders/CSV）。
// 金额零运算：展示值全为后端字符串（Number 仅图表几何，硬约束 3）。
// ============================================================

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import useAuth from '../auth/useAuth'
import usePageTitle from '../utils/usePageTitle'
import { customRange, presetRange, todayKey } from '../dashboard/range'
import { buildFormatters, intNum, money, timeLabel } from '../dashboard/format'
import useSummary from '../dashboard/useSummary'
import useOrders from '../dashboard/useOrders'
import useSyncStatus from '../dashboard/useSyncStatus'
import { downloadOrdersCsv } from '../api/dashboard'
import AppBar, { StatusLine } from '../components/dashboard/AppBar'
import TimeFilters from '../components/dashboard/TimeFilters'
import DatasetBar from '../components/dashboard/DatasetBar'
import Banners from '../components/dashboard/Banners'
import KpiSection from '../components/dashboard/KpiSection'
import DailyCard from '../components/dashboard/DailyCard'
import AdCard from '../components/dashboard/AdCard'
import ConvCard from '../components/dashboard/ConvCard'
import CountryCard from '../components/dashboard/CountryCard'
import OrdersCard from '../components/dashboard/OrdersCard'
import GuideModal from '../components/dashboard/GuideModal'
import { niceCeil } from '../components/dashboard/charts/chartMath'
import { TooltipProvider } from '../components/dashboard/charts/Tooltip'

export default function DashboardPage() {
  const { t, i18n } = useTranslation()
  const { logout } = useAuth()
  const navigate = useNavigate()
  usePageTitle('common.pageTitle.dashboard')

  // ---- 页面状态（DESIGN §6.3）----
  const [range, setRange] = useState(() => presetRange('7d')) // AC-T2：默认近 7 天
  const [dataset, setDataset] = useState('all') // REQ-20261014-01：数据集全局切换
  const [dailyView, setDailyView] = useState('chart') // AC-E1：双卡共享
  const [filters, setFilters] = useState({ klass: 'all', currency: 'all', status: 'all' })
  const [sort, setSort] = useState({ key: 'date', dir: 'desc' }) // AC-O3 默认
  const [page, setPage] = useState(1)
  const [csvBusy, setCsvBusy] = useState(false)
  const [csvError, setCsvError] = useState(null)
  const [syncFailed, setSyncFailed] = useState(false)
  const [guideOpen, setGuideOpen] = useState(false)

  const locale = i18n.language === 'zh' ? 'zh-CN' : 'en-US'
  const fmt = useMemo(() => buildFormatters(locale), [locale])

  // 数据集锁死外层范围：dataset ≠ all 时表格类别筛选锁定为该数据集（禁用），
  // 仅 dataset = all 时可自由筛选（REQ-20261014-01，用户定稿语义）
  const effectiveClass = dataset !== 'all' ? dataset : filters.klass

  // ---- 数据（S8 hooks；loading 期间保留上一帧 → loadingdim）----
  const summary = useSummary(range, dataset)
  const orders = useOrders({
    from: range.from,
    to: range.to,
    klass: effectiveClass,
    currency: filters.currency,
    status: filters.status,
    sortKey: sort.key,
    sortDir: sort.dir,
    page,
  })
  const sync = useSyncStatus({
    onDone: () => {
      summary.reload() // idle 后自动重拉（AC-S4）
      orders.reload()
    },
  })

  // summary 报告后台同步中 → 自动接入进度轮询（DESIGN §6.3）
  const syncStatusMeta = summary.data && summary.data.meta ? summary.data.meta.sync_status : ''
  const { ensurePolling, start: startSync } = sync
  useEffect(() => {
    if (syncStatusMeta === 'running') ensurePolling()
  }, [syncStatusMeta, ensurePolling])

  // 币种筛选失效回落 all（AC-O2；选项由当前区间订单动态生成）
  const orderCurrencies = orders.data ? orders.data.currencies : null
  useEffect(() => {
    if (!orderCurrencies) return
    if (filters.currency !== 'all' && !orderCurrencies.includes(filters.currency)) {
      setFilters((f) => ({ ...f, currency: 'all' }))
      setPage(1)
    }
  }, [orderCurrencies, filters.currency])

  // ---- 交互（筛选/排序/区间/数据集变化一律重置页码，AC-T5/O2/O3）----
  const handlePreset = useCallback((preset) => {
    setRange(presetRange(preset))
    setPage(1)
  }, [])

  const handleCustom = useCallback((from, to) => {
    setRange(customRange(from, to))
    setPage(1)
  }, [])

  const handleDataset = useCallback((ds) => {
    setDataset(ds)
    setFilters((f) => ({ ...f, klass: 'all' })) // 数据集切换时重置表格类别筛选
    setPage(1)
  }, [])

  const handleFilterChange = useCallback((patch) => {
    setFilters((f) => ({ ...f, ...patch }))
    setPage(1)
  }, [])

  const handleSort = useCallback((key) => {
    setSort((s) => (s.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' }))
    setPage(1)
  }, [])

  const handleRefresh = useCallback(async () => {
    setSyncFailed(false)
    try {
      await startSync(range.from, range.to) // AC-S3：当前视图区间
    } catch (e) {
      setSyncFailed(true) // AC-S5：同步失败横幅（可重试）
    }
  }, [range.from, range.to, startSync])

  const handleLogout = useCallback(() => {
    logout()
    navigate('/login', { replace: true }) // AC-G3
  }, [logout, navigate])

  const handleCsv = useCallback(
    async (scope) => {
      setCsvBusy(true)
      setCsvError(null)
      try {
        await downloadOrdersCsv({
          from: range.from,
          to: range.to,
          scope, // 'view' 套当前筛选+排序；'all' 全区间（AC-X1）
          klass: effectiveClass,
          currency: filters.currency,
          status: filters.status,
          sort: sort.key,
          dir: sort.dir,
          lang: i18n.language === 'zh' ? 'zh' : 'en',
        })
      } catch (e) {
        setCsvError(e) // 下载失败并入错误横幅（重试=重载）
      } finally {
        setCsvBusy(false)
      }
    },
    [range.from, range.to, effectiveClass, filters.currency, filters.status, sort.key, sort.dir, i18n.language],
  )

  // ---- 状态行（AC-S1/S2/S4 + D5 注记）----
  const meta = summary.data ? summary.data.meta : null
  let dot = 'ok'
  let text = t('dashboard.updated', {
    t: timeLabel(fmt, meta ? meta.latest_orders_sync_at : ''),
    n: intNum(fmt, meta ? meta.orders_total : 0),
  })
  if (summary.error) {
    dot = 'err'
    text = t('dashboard.connFailed')
  } else if (sync.running && sync.current) {
    dot = null
    text = t('dashboard.loadingDays', {
      a: intNum(fmt, sync.current.days_done),
      b: intNum(fmt, sync.current.days_total),
    })
  } else if (summary.loading) {
    dot = null
    text = t('dashboard.loading')
  }
  const notes = []
  if (sync.rejected) notes.push(t('dashboard.syncRejected'))
  if (meta && meta.incomplete_tail) notes.push(t('dashboard.dataIncompleteNote'))
  const statusNode = <StatusLine dot={dot} text={text} note={notes.length ? notes.join(' · ') : null} />

  // ---- 每日双卡共享 y 轴上限（AC-E2：两口径逐日总额最大值 → niceCeil）----
  const data = summary.data
  const sharedMax = useMemo(() => {
    if (!data) return 1
    let m = 0
    for (const arr of [data.daily.est, data.daily.usd]) {
      for (const row of arr) {
        const v = Number(row.total) // 几何比较（约束 3 白名单：仅几何缩放）
        if (v > m) m = v
      }
    }
    return m
  }, [data])
  const dailyYMax = niceCeil(sharedMax || 1)
  const adByDate = useMemo(() => {
    const map = {}
    if (data) for (const a of data.daily.ad) map[a.date] = a.amount
    return map
  }, [data])

  const busyDim = summary.loading || sync.running

  return (
    <TooltipProvider>
      <div className="wrap">
        <AppBar
          sub={t(dataset === 'included' ? 'dashboard.subIncluded' : dataset === 'excluded' ? 'dashboard.subExcluded' : 'dashboard.subAll')}
          status={statusNode}
          nav={{ label: t('customer.navTo'), onClick: () => navigate('/customer') }}
          onGuide={() => setGuideOpen(true)}
          onRefresh={handleRefresh}
          onLogout={handleLogout}
        />
        <TimeFilters range={range} today={todayKey()} onPreset={handlePreset} onCustom={handleCustom} />
        <DatasetBar
          dataset={dataset}
          onDatasetChange={handleDataset}
          onCsvView={() => handleCsv('view')}
          onCsvAll={() => handleCsv('all')}
          csvBusy={csvBusy}
        />
        <Banners
          error={summary.error || csvError}
          syncFailed={syncFailed}
          adError={meta && meta.ad_available === false ? meta.ad_error || '' : null}
          truncatedDays={meta ? meta.truncated_days : []}
          noUsdCurrencies={data && data.conv ? data.conv.no_usd_currencies : []}
          onRetryError={() => {
            setCsvError(null)
            summary.reload()
          }}
          onRetrySync={handleRefresh}
        />
        <main className={busyDim ? 'loadingdim' : undefined}>
          {data ? (
            <>
              <KpiSection kpis={data.kpis} fmt={fmt} />
              <div className="stack">
                <DailyCard
                  variant="est"
                  days={data.daily.days}
                  entries={data.daily.est}
                  adByDate={adByDate}
                  currencyRank={data.daily.currency_rank}
                  totalDisplay={money(fmt, data.conv.legacy_total)} /* aria 合计=后端 conv 合计（AC-V4） */
                  view={dailyView}
                  yMax={dailyYMax}
                  onViewChange={setDailyView}
                  showToggle
                  fmt={fmt}
                />
                <DailyCard
                  variant="usd"
                  days={data.daily.days}
                  entries={data.daily.usd}
                  adByDate={adByDate}
                  currencyRank={data.daily.currency_rank}
                  totalDisplay={money(fmt, data.conv.server_total)}
                  view={dailyView}
                  yMax={dailyYMax}
                  onViewChange={setDailyView}
                  showToggle={false}
                  fmt={fmt}
                />
                <AdCard ad={data.daily.ad} fmt={fmt} />
                <ConvCard conv={data.conv} fmt={fmt} />
                <CountryCard countries={data.countries} fmt={fmt} />
                <OrdersCard
                  data={orders.data}
                  fmt={fmt}
                  filters={filters}
                  classValue={dataset === 'all' ? filters.klass : dataset}
                  classLocked={dataset !== 'all'}
                  sort={sort}
                  page={page}
                  onFilterChange={handleFilterChange}
                  onSort={handleSort}
                  onPageChange={setPage}
                />
              </div>
            </>
          ) : null}
        </main>
        <GuideModal open={guideOpen} onClose={() => setGuideOpen(false)} />
      </div>
    </TooltipProvider>
  )
}
