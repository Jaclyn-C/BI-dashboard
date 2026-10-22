// ============================================================
// CustomerViewPage.jsx — 客户视图页（REQ-20261015-02）
// 展示下游客户调用供应商接口能看到的全部数据：仅已计入订单、纯订单信息
// （后端 /dashboard/customer-orders 已做 included-only + 字段裁剪，页面
// 不引入任何分类信息）。复用 TimeFilters + OrdersCard(hideClass) + Banners；
// 卡片头部提供"当前视图（CSV）"下载（当前筛选+排序透传，导出全部行、跨页）。
// ============================================================

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

import useAuth from '../auth/useAuth'
import usePageTitle from '../utils/usePageTitle'
import { downloadCustomerOrdersCsv } from '../api/dashboard'
import { customRange, presetRange, todayKey } from '../dashboard/range'
import { buildFormatters, intNum } from '../dashboard/format'
import useCustomerOrders from '../dashboard/useCustomerOrders'
import AppBar from '../components/dashboard/AppBar'
import Sidebar from '../components/Sidebar'
import TimeFilters from '../components/dashboard/TimeFilters'
import Banners from '../components/dashboard/Banners'
import OrdersCard from '../components/dashboard/OrdersCard'

export default function CustomerViewPage() {
  const { t, i18n } = useTranslation()
  const { logout } = useAuth()
  const navigate = useNavigate()
  usePageTitle('common.pageTitle.customer')

  const [range, setRange] = useState(() => presetRange('7d'))
  const [filters, setFilters] = useState({ currency: 'all', status: 'all', upstream: 'all' })
  const [sort, setSort] = useState({ key: 'date', dir: 'desc' })
  const [page, setPage] = useState(1)
  const [csvBusy, setCsvBusy] = useState(false)
  const [csvError, setCsvError] = useState(null)

  const locale = i18n.language === 'zh' ? 'zh-CN' : 'en-US'
  const fmt = useMemo(() => buildFormatters(locale), [locale])

  const orders = useCustomerOrders({
    from: range.from,
    to: range.to,
    currency: filters.currency,
    status: filters.status,
    upstream: filters.upstream,
    sortKey: sort.key,
    sortDir: sort.dir,
    page,
  })

  // 币种/上游筛选失效回落 all（选项由当前区间动态生成，同看板 AC-O2）
  const orderCurrencies = orders.data ? orders.data.currencies : null
  useEffect(() => {
    if (!orderCurrencies) return
    if (filters.currency !== 'all' && !orderCurrencies.includes(filters.currency)) {
      setFilters((f) => ({ ...f, currency: 'all' }))
      setPage(1)
    }
  }, [orderCurrencies, filters.currency])
  const orderUpstreams = orders.data ? orders.data.upstreams : null
  useEffect(() => {
    if (!orderUpstreams) return
    if (filters.upstream !== 'all' && !orderUpstreams.includes(filters.upstream)) {
      setFilters((f) => ({ ...f, upstream: 'all' }))
      setPage(1)
    }
  }, [orderUpstreams, filters.upstream])

  const handlePreset = useCallback((preset) => {
    setRange(presetRange(preset))
    setPage(1)
  }, [])

  const handleCustom = useCallback((from, to) => {
    setRange(customRange(from, to))
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

  // 当前视图 CSV：筛选+排序原样透传，导出该条件下的全部行（跨页，同主看板 scope=view 语义）
  const handleCsv = useCallback(async () => {
    setCsvBusy(true)
    setCsvError(null)
    try {
      await downloadCustomerOrdersCsv({
        from: range.from,
        to: range.to,
        currency: filters.currency,
        status: filters.status,
        sort: sort.key,
        dir: sort.dir,
        lang: i18n.language === 'zh' ? 'zh' : 'en',
      })
    } catch (e) {
      setCsvError(e) // 下载失败并入错误横幅（重试=重载，同看板）
    } finally {
      setCsvBusy(false)
    }
  }, [range.from, range.to, filters.currency, filters.status, sort.key, sort.dir, i18n.language])

  const handleLogout = useCallback(() => {
    logout()
    navigate('/login', { replace: true })
  }, [logout, navigate])

  const total = orders.data ? orders.data.total : 0
  const totalInRange = orders.data ? orders.data.total_in_range : 0

  return (
    <div className="shell">
      <Sidebar />
      <div className="shell-main">
        <div className="wrap">
          <AppBar
            sub={t('customer.subBar')}
            onRefresh={orders.reload}
            onLogout={handleLogout}
          />
          <TimeFilters range={range} today={todayKey()} onPreset={handlePreset} onCustom={handleCustom} />
          <Banners
            error={orders.error || csvError}
            onRetryError={() => {
              setCsvError(null) // 同主看板：重试先清下载错误，避免横幅残留
              orders.reload()
            }}
          />
          <main className={orders.loading ? 'loadingdim' : undefined}>
            <div className="custnote">{t('customer.note')}</div>
            <div className="stack">
              <OrdersCard
                data={orders.data}
                fmt={fmt}
                filters={filters}
                classValue="all"
                classLocked
                hideClass
                title={t('customer.title')}
                sub={t('customer.ordersSub', { n: intNum(fmt, total), m: intNum(fmt, totalInRange) })}
                actions={
                  <button
                    type="button"
                    className="btn-tonal"
                    onClick={handleCsv}
                    disabled={csvBusy || !total}
                  >
                    {'⤓'} <span>{t('dashboard.csvView')}</span>
                  </button>
                }
                sort={sort}
                page={page}
                onFilterChange={handleFilterChange}
                onSort={handleSort}
                onPageChange={setPage}
              />
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}
