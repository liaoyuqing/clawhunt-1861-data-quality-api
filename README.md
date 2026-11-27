# 资料完整度面板聚合接口 (S3-DASH-007)

管理驾驶舱「资料完整度面板」的后端聚合接口：读取 S2-CRM（只读）的企业、联系人与能力卡镜像，
按**口径库（字段清单版本）**计算完整度，输出整体完整度与 95% 目标的差距、按会员经理的完整度与
企业数、缺失最多的 5 个字段、能力卡完成率与 90 天新鲜度，以及完整度低于 80% 的企业清单
（**只返回 id 与 name**）。

仓库内全部数据均为**虚构测试数据**（星澜科技 / 云栖生物 / 恒泰智造 等），不含任何真实企业、
个人信息、手机号或统一社会信用代码。

---

## 1. 快速开始

```bash
# 1) 安装依赖（Python 3.11+）
python -m venv .venv
. .venv/Scripts/activate        # Windows; Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt

# 2) 起一个 PostgreSQL 16 实例（可选：不接库也能跑全部单元测试）
pwsh -File scripts/start_pg.ps1                  # 端口 55433，数据目录在仓库外

# 3) 建表 + 灌入虚构数据
export DQ_DATABASE_URL="postgresql+psycopg://postgres@127.0.0.1:55433/dq1861"
createdb -h 127.0.0.1 -p 55433 -U postgres dq1861      # 已存在则忽略报错
python -m alembic upgrade head
python scripts/seed_demo.py

# 4) 起服务
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# 打开 http://127.0.0.1:8000/docs 看交互式 OpenAPI

# 5) 调接口（需要带 dash.quality.read 权限的 Bearer Token）
curl -H "Authorization: Bearer $TOKEN" "http://127.0.0.1:8000/api/dash/data-quality?site_id=11111111-1111-4111-8111-111111111111"
```

一次性跑完全部验证（安装依赖 → 测试 → 类型检查 → lint → 构建 → 导出 OpenAPI）：

```bash
python scripts/verify_all.py
```

---

## 2. 依赖与运行环境

| 需要 | 用途 | 缺了会怎样 |
|---|---|---|
| Python 3.11+ | 运行时 | 无法启动 |
| PostgreSQL 16 | CRM 镜像 + 口径库 | 单元测试仍可全绿；生产接库必需 |
| Redis | 60 秒响应缓存 | 自动降级为进程内内存缓存 |
| PyJWT | 校验平台 SSO 的 Bearer Token | 无法鉴权 |

**不需要**的东西：不需要前端构建工具链（本单只交付后端接口）、不需要 Node、
不需要任何真实密钥或第三方服务账号、不需要访问境外服务的 SDK。

所有配置只从环境变量读取（见 `app/config.py`）：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DQ_DATABASE_URL` | `postgresql+psycopg://postgres:postgres@127.0.0.1:55432/dq1861` | PostgreSQL 16 连接串 |
| `DQ_REDIS_URL` | `redis://127.0.0.1:6379/0` | Redis 连接串；生产用 Redis，测试用 fakeredis |
| `DQ_CACHE_TTL_SECONDS` | `60` | 响应缓存 TTL（秒） |
| `DQ_JWT_SECRET` | `insecure-local-development-secret` | 平台 SSO HS256 密钥（生产必须覆盖） |
| `DQ_JWT_AUDIENCE` / `DQ_JWT_ISSUER` | `member-space` / `member-space-sso` | Token 校验项 |
| `DQ_REQUIRED_SCOPE` | `dash.quality.read` | 接口所需权限 |

**Redis 说明**：生产环境使用 Redis（`redis-py`），测试环境使用 `fakeredis`（进程内替身），
两者走同一套 `CacheClient` 协议，缓存键与 TTL 行为完全一致。本机未部署 Redis 时，
`build_cache()` 会降级为进程内 `InMemoryCache`，接口仍然可用。

---

## 3. 接口说明

### `GET /api/dash/data-quality`

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `site_id` | UUID | 是 | 会员空间站点 id |
| `staff_id` | UUID | 否 | 只统计该会员经理负责的企业 |
| `limit` | int | 否 | 低完整度清单条数上限，缺省 50，最大 200 |

权限：`dash.quality.read`（Token 缺失 → 401，无权限 → 403）。

统一响应信封：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "site_id": "11111111-1111-4111-8111-111111111111",
    "caliber_version": "v2",
    "field_count": 7,
    "enterprise_count": 3,
    "cell_total": 21,
    "cell_filled": 17,
    "completeness": 0.8095,
    "target_pct": 95.0,
    "gap_to_target": 0.1405,
    "managers": [
      {"staff_id": "3333...", "staff_name": "会员经理甲", "enterprise_count": 2,
       "completeness": 0.875, "gap_to_target": 0.075}
    ],
    "top_missing_fields": [
      {"field_key": "contact.decision_role", "label": "决策角色", "missing": 1, "total": 3}
    ],
    "capability_cards": {"total": 3, "confirmed": 2, "completion_rate": 0.6667,
                         "fresh_confirmed": 1, "freshness_rate": 0.3333, "fresh_days": 90},
    "low_completeness": [{"id": "e300...", "name": "恒泰智造"}],
    "low_completeness_threshold_pct": 80.0,
    "low_completeness_total": 1,
    "stale": false,
    "cache_hit": false
  },
  "request_id": "9c1f..."
}
```

### 计算口径

* **整体完整度** = 已填格数 / (企业数 × 字段数)。站点没有企业时返回 `null`（HTTP 200，不除零）。
* **与 95% 目标的差距** = `target_pct/100 - completeness`，保留 4 位小数。
* **按会员经理** = 该经理负责企业的格数口径，与整体口径一致（不是"按企业平均"）。
* **缺失最多的 5 个字段** = 按缺失数倒序，并列时按字段 key 升序；只列真正有缺失的字段。
* **能力卡完成率** = 已确认能力卡 / 能力卡总数；**新鲜度** = 90 天内确认的比例（分母同为能力卡总数）。
* **低完整度清单** = 完整度**严格小于** 80% 的企业，按完整度升序；**响应键集合恰为 `{id, name}`**。

---

## 4. 口径库（字段清单版本）

字段清单**不硬编码在代码里**。每次请求都从口径库读当前生效版本：

* 表：`caliber_field_versions`（`version` / `fields` / `labels` / `target_pct` / `low_pct` /
  `fresh_days` / `calc_refs` / `is_active`），见 `app/models/caliber.py`。
* 读法：`CaliberDbProvider`（生产，PostgreSQL）与 `StaticCaliberProvider`（测试，可注入桩），
  接口一致，见 `app/repositories/caliber_repo.py`。
* **缓存键含版本**：`dash:dq:{site_id}:{staff_id|*}:{version}`，TTL 60 秒。切到 v2 之后 v1 的缓存
  永远不会被命中（`app/cache/keys.py`）。
* **口径库缺字段** → HTTP 422，`code=42201`，`message=FIELD_LIST_EMPTY`。
* **口径库不可用** → 用最近一次成功的快照降级，响应里 `stale=true`。

内置两个版本（`build_default_versions()`）：

| 版本 | 字段数 | 字段 |
|---|---|---|
| v1 | 8 | 行业、赛道、阶段、注册地、主营简介、负责人、职位、决策角色 |
| v2 | 7 | v1 去掉「赛道」 |

切换生效版本：

```bash
python scripts/set_caliber_version.py v1     # 或 v2
```

---

## 5. 计算函数注册（口径库白名单）

`app/calc/registry.py` 维护白名单，口径库版本的 `calc_refs` 只能引用注册过的名字，
引用未注册函数会直接报错，不会静默用错实现。

| 注册名 | 作用 |
|---|---|
| `compute_completeness` | 整体完整度（已填格 / 总格） |
| `compute_manager_breakdown` | 按会员经理拆分 |
| `compute_field_gaps` | 各字段缺失数与排序 |
| `compute_low_completeness` | 低于阈值的企业与升序排列 |
| `capability_card_stats` | 能力卡完成率与 90 天新鲜度 |

---

## 6. 对接点（与其它工单的边界）

* **S2-CRM（CRM 核心对象）**：本单只读 `crm_enterprises` / `crm_contacts` / `crm_capability_cards`
  三张镜像表，SQL 在 `app/repositories/crm_repo.py::SqlCrmReader`（批量三条查询，不做 N+1）。
  S2-CRM 尚未上线时，用 `StubCrmReader` 接口桩先行（测试即用此桩）。
* **口径库**：口径库表由管理驾驶舱的数据治理工单维护，本单只读。
* **权限**：Token 由平台 SSO 签发，本单不实现登录。

---

## 7. 测试与验证

```bash
# 单元测试（不需要数据库）
python -m pytest tests -q

# 单元测试 + PostgreSQL 集成测试
export DQ_TEST_DATABASE_URL="postgresql+psycopg://postgres@127.0.0.1:55433/dq1861"
python -m pytest tests -v

# 类型检查 / lint / 构建
python -m mypy          # strict 模式
python -m ruff check .
python -m build --wheel --sdist
```

验收标准与测试的对应关系：

| AC | 测试文件 | 关键断言 |
|---|---|---|
| AC1 整体与按经理完整度 = 手算 | `tests/test_ac1_completeness.py` | 18/24 = 0.75；差距 0.20；经理甲 13/16 = 0.8125、企业数 2；空站点 completeness=null 且 200 |
| AC2 口径库新版本 → 结果变化 | `tests/test_ac2_caliber.py` | v1 8 字段 0.75；v2 7 字段 17/21 = 0.8095；缓存键含版本、切版本不命中旧值；缺字段 422 FIELD_LIST_EMPTY |
| AC3 低完整度清单只两字段 | `tests/test_ac3_projection.py` | 键集合恰为 `{id, name}`；不含 phone/uscc；条数 = 低于 80% 的企业数；升序；恰好 80% 不进清单 |

---

## 8. 目录结构

```
app/
  api/            路由、鉴权依赖、统一异常处理
  calc/           计算函数 + 白名单注册表
  cache/          Redis / 内存缓存与缓存键
  domain/         字段目录（只负责"怎么读"，不决定"读哪些"）
  models/         SQLAlchemy 2 模型（CRM 镜像 + 口径库 + 员工）
  repositories/   口径库读取器、CRM 只读 adapter
  schemas/        Pydantic 响应模型与统一信封
  services/       聚合服务
  main.py         FastAPI 应用工厂
alembic/          迁移脚本
docs/             openapi.yaml 与验证日志
scripts/          建库、灌数、导 OpenAPI、一键验证
tests/           AC1 / AC2 / AC3 与数据库集成测试
```

---

## 9. 已知边界

* 本单只交付后端聚合接口，不含前端面板（提案已声明不含）。
* CRM 数据清洗不在本单范围内；本单读到什么就算什么。
* 口径库管理界面不在本单范围内（提案已声明不含）。