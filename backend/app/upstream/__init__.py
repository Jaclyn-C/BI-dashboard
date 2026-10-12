"""上游 netshort CPS 集成（REQ-20261012-02，DESIGN §3）。

- client：OAuth2 客户端（换票/缓存/60s 提前刷新/双层 401 单次重试）；
- fetcher：日窗拉取 + 时间窗二分补全 + adSummary；
- scheduler：lifespan 定时循环（30 分钟节奏 + 覆盖自愈 + 手动插队）。

出站白名单（AC-U5）：运行时仅 3 个接口路径（client.py 内常量）；
上游 HTTP 调用只出现在本包（CLAUDE.md §4）。
"""
