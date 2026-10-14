"""仓库红线断言（B-T9 grep 验收的测试化形态，随 CI 常态生效）。

- 凭据/遗留依赖：backend 源码中不得出现 tfctechnology（CLAUDE.md 红线 11）；
- 上游出站白名单：app/ 内出现的 "/open/..." 路径字面量恰好等于 3 个常量
  （AC-U5；新增上游路径必须先登记 client.py 常量并修订需求）；
- 打标盐值纪律：ORDER_FILTER_SALT 的实际值不得出现在源码/迁移/测试字面量
  （REQ-20261014-01；测试用独立盐值 unit-test-salt 除外）。

B1 说明：旧「share_service 禁止被输出路径 import」断言已随 REQ-20261014-01
解除（分类规则由业务重定义为哈希过滤，share_service 即为分成口径的唯一实现）。
"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

WHITELIST = {
    "/open/oauth2/token",
    "/open/order/list",
    "/open/order/adSummary",
}


def test_no_legacy_backend_domain_in_source():
    for directory in ("app", "alembic"):
        for path in (BACKEND / directory).rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            assert "tfctechnology" not in content, f"发现遗留自建后端域名：{path}"


def test_upstream_path_literals_match_whitelist():
    pattern = re.compile(r"[\"'](/open/[^\"']+)[\"']")
    found: set[str] = set()
    for path in (BACKEND / "app").rglob("*.py"):
        found.update(pattern.findall(path.read_text(encoding="utf-8")))
    assert found == WHITELIST


def test_real_filter_salt_not_committed():
    """真实盐值只允许存在于 .env：源码/迁移/测试中不得出现其字面量。"""
    from app.config import get_settings

    salt = get_settings().order_filter_salt.strip()
    if not salt or salt == "unit-test-salt":
        return  # 本地未配真实盐值时跳过
    for directory in ("app", "alembic", "tests"):
        for path in (BACKEND / directory).rglob("*.py"):
            assert salt not in path.read_text(encoding="utf-8"), (
                f"真实盐值泄露进源码：{path}"
            )
    # .env.example 模板也不含真实值
    example = (BACKEND.parent / ".env.example").read_text(encoding="utf-8")
    assert salt not in example, "真实盐值泄露进 .env.example"


