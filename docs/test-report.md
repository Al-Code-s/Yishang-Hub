# 测试报告（docs/test-report.md）

> 本文件只记录**实际执行过**的命令与输出。未执行的项一律写「未执行」，不写成通过。
> 执行时间：2026-09-17 ～ 2026-09-18　执行机器：Windows 10/11 开发机（本地 MySQL 8.0.17 + Redis 3.2）

## 一、测试环境

| 项 | 值 |
| --- | --- |
| 操作系统 | Windows（PowerShell 7） |
| Python | 3.12.14（`backend/.venv`） |
| Node.js / npm | v22.17.1 / 10.9.2 |
| 数据库 | MySQL 8.0.17，utf8mb4 / utf8mb4_0900_ai_ci，InnoDB，严格 SQL 模式 |
| 测试库 | `test_yishang_platform`（MySQL，不使用 SQLite） |
| 缓存 | 开发：Redis 3.2；测试：LocMem |
| 测试机器配置 | 见「性能测试」一节（本轮未执行性能测试） |

## 二、后端

### 2.1 Django 系统检查

```
$ .\.venv\Scripts\python.exe manage.py check
System check identified no issues (0 silenced).
```

### 2.2 迁移一致性

```
$ .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
No changes detected
```

含义：模型与已提交迁移一致，仓库内不存在「忘记提交迁移」的情况。

### 2.3 静态检查

```
$ .\.venv\Scripts\python.exe -m ruff check apps config tests
All checks passed!
```

### 2.4 单元与集成测试（pytest + MySQL）

```
$ .\.venv\Scripts\python.exe -m pytest tests -q --reuse-db
90 passed in 18.31s
```

覆盖的关键场景（每条都有对应的测试函数，不是只做覆盖率统计）：

| 用例（按测试函数归组） | 所在文件 |
| --- | --- |
| 未登录访问被拒绝、无操作权限不能调用接口 | `tests/test_permissions.py::test_unauthenticated_requests_are_rejected`、`::test_operation_permission_required` |
| 数据范围：工厂 / 仓库 / 部门 / 本人 / 公司边界不能越权 | `tests/test_permissions.py`（`test_factory_scope_filters_list_and_blocks_out_of_range_create`、`test_warehouse_scope_limits_locations`、`test_company_boundary_is_applied`、`test_self_scope_only_returns_own_records`、`test_user_management_scope_is_enforced`） |
| 单维度范围配置不完整时 fail-closed | `tests/test_permissions.py::test_scope_missing_dimension_fails_closed` |
| 角色变更后权限缓存与菜单立即收敛 | `tests/test_permissions.py`（`test_permission_cache_invalidated_on_role_change`、`test_deactivating_role_revokes_permissions`、`test_role_delete_or_permission_change_affects_session_payload`） |
| 附件下载需要权限 | `tests/test_permissions.py::test_attachment_download_requires_permission` |
| CSRF、登录成功/失败、锁定、手机号登录 | `tests/test_auth_api.py` |
| 退出登录使会话失效、改密使其它会话失效、密码策略 | `tests/test_auth_api.py` |
| 编号生成按周期重置、并发取号唯一、预演不消耗流水 | `tests/test_core_services.py` |
| 幂等键：缺失拒绝、重复返回首次结果、内容不同拒绝、失败后释放 | `tests/test_core_services.py` |
| 发件箱：去重、重试与死信、投递只产生一次通知 | `tests/test_core_services.py` |
| 审计只写不改、与业务同事务回滚、不记录密码 | `tests/test_core_services.py` |
| 金额字段使用 Decimal 而非 float | `tests/test_core_services.py::test_decimal_fields_use_decimal_not_float` |
| 审批：顺序多级、金额与部门路由、无匹配节点拒绝、自审门禁、驳回必填理由、撤回、模板快照、待办可见性 | `tests/test_workflow_api.py` |
| 组织：部门树与跨公司父级、班次跨夜与非法时间、班组人员快照、已使用主数据不可物理删除 | `tests/test_factory_api.py` |
| 管理命令：bootstrap 幂等 / 不覆盖密码 / 生产要求密码、菜单权限编码存在、seed_demo 生产禁用 | `tests/test_management_commands.py` |
| 通知：按 source_event_id 幂等、发件箱重复投递不重复通知、按用户隔离 | `tests/test_notifications_api.py` |
| 冒烟：主数据 CRUD、部门树、仓储树、SKU 生成、工作台指标、健康检查 | `tests/test_smoke_api.py` |

### 2.5 数据库级与并发测试的边界

- 唯一约束、外键约束、NOT NULL 与 CHECK 约束的用例运行在 **MySQL** 上。
- **库存并发测试（并发出库不产生负库存、库存余额行并发创建不重复、死锁重试不重复生成单据）
  未执行**：阶段 1 尚未引入库存服务，无法构造这些用例。它们属于阶段 2 的必测项，
  已登记在 `docs/requirements-matrix.md`。
- 测试框架的外层事务会掩盖部分并发问题，因此阶段 2 的并发用例将使用独立连接与真实事务，
  而不是依赖 `pytest-django` 的单事务模式。

## 三、前端

### 3.1 TypeScript 类型检查

```
$ npm run typecheck          # vue-tsc --build --force
（无输出即通过，退出码 0）
```

### 3.2 组件与工具测试（vitest）

```
$ npm run test

 RUN  v3.0.5 E:/github/Yishang-Hub/frontend

 ✓ tests/decimal.spec.ts (10 tests) 10ms
 ✓ tests/http-error.spec.ts (2 tests) 3ms
 ✓ tests/format.spec.ts (5 tests) 19ms
 ✓ tests/router.spec.ts (31 tests) 4ms
 ✓ tests/pro-table.spec.ts (4 tests) 341ms
 ✓ tests/views-compile.spec.ts (3 tests) 4124ms

 Test Files  6 passed (6)
      Tests  55 passed (55)
```

说明：

- `decimal.spec.ts`：锁定「不用 float 累计金额/库存」这一条——例如累计 1000 个 `0.01` 必须精确得到 `10.00`，
  `round` 使用 HALF_UP，除数为 0 抛异常，非法输入不静默当 0。
- `format.spec.ts`：UTC → Asia/Shanghai 的跨日边界（`2026-09-17T16:00:00Z` 必须显示为 `2026-09-18`）。
- `router.spec.ts`：以 `tests/fixtures/menu-components.json`（由后端权限注册表导出）为准，
  校验后端声明的每个页面菜单组件都能被前端解析——把「菜单点了没反应」变成显式测试失败。
- `pro-table.spec.ts`：通用表格组件的真实挂载测试（列与行渲染、布尔/空值展示、空状态、错误提示）。
- `views-compile.spec.ts`：让 Vite 真正编译并加载每一个视图模块。
  该用例的引入原因是一个真实缺陷：`EntityListPage.vue` 缺少 `</script>` 结束标签，
  类型检查不报错而 `vite build` 直接失败；现在这类问题会在测试阶段被拦住。

> 测试环境补丁见 `tests/setup.ts`：jsdom 不实现 `ResizeObserver` / `matchMedia`，
> 而 Element Plus 的表格依赖它们，缺失时组件会静默渲染不出内容，导致测试误报。

### 3.3 生产构建

```
$ npm run build              # vue-tsc --build --force && vite build
...
dist/assets/UserList-BkXIv7JH.js      16.26 kB │ gzip:   5.60 kB
dist/assets/RoleList-tWqAO2t5.js      17.19 kB │ gzip:   5.59 kB
dist/assets/element-DVsXJcZ4.js      986.97 kB │ gzip: 309.44 kB
dist/assets/chart-Bb6yjXMn.js      1,034.91 kB │ gzip: 343.41 kB
✓ built in 10.05s
```

按页面拆包（每个页面独立 chunk），Element Plus 与 ECharts 单独分包。
未做进一步体积优化（阶段 1 不作为验收项，已登记为后续优化事项）。

## 四、真实 HTTP 端到端验证（非测试框架）

使用独立 HTTP 会话客户端（`urllib` + CookieJar）访问**真实运行中的开发服务器**，
覆盖登录态、CSRF、权限、唯一约束、审计与会话失效。脚本位于 `.tmp/verify_api.py`（开发辅助脚本，未提交仓库）。

实际输出：

```
[PASS] 存活探针 /healthz :: HTTP 200
[PASS] 就绪探针 /readyz（数据库+缓存） :: HTTP 200 {"status": "ok", "checks": {"database": "ok", "cache": "ok"}, ...}
[PASS] 未登录访问被拒绝 :: HTTP 403
[PASS] 下发 CSRF Cookie :: HTTP 200
[PASS] 管理员会话登录 :: HTTP 200, 权限 1 个, 菜单包含工作台与实施进度
[PASS] 会话恢复 /auth/session/ :: HTTP 200
[PASS] 物料列表（分页结构） :: HTTP 200, count=65
[PASS] 仓库-库区-储位树 :: HTTP 200
[PASS] 工作台指标由业务数据计算 :: HTTP 200, 指标卡 11 张
[PASS] 新增物料（真实落库） :: HTTP 201, id=66
[PASS] 回读刚创建的物料 :: HTTP 200
[PASS] 业务编码唯一约束生效 :: HTTP 400, code=VALIDATION_FAILED
[PASS] 关键操作写入审计 :: HTTP 200, 命中 1 条审计记录
[PASS] 缺少 CSRF 令牌的写操作被拒绝 :: HTTP 403 {"code":"PERMISSION_DENIED","message":"CSRF Failed: CSRF token missing."}
[PASS] 演示账号登录（主数据管理员） :: HTTP 200
[PASS] 越权访问用户管理被拒绝 :: HTTP 403, code=PERMISSION_DENIED
[PASS] 有权限的主数据接口可访问 :: HTTP 200
[PASS] 退出登录 :: HTTP 200
[PASS] 退出后会话失效 :: HTTP 403

合计 19 项，通过 19 项，失败 0 项
```

说明：

- 管理员权限显示为 `1` 个，是因为超级管理员的权限集合表示为通配符 `*`（后端约定），不是权限缺失。
- 验证过程中创建的物料 `VERIFY-API-001` 已在验证结束后通过 `set-active` 停用，
  演示数据列表不会因此混入验证数据。
- 开发服务器实际监听 `127.0.0.1:8010`：本机 8000 端口已被其它进程占用（`netstat` 显示 PID 2920 监听 0.0.0.0:8000）。

前端开发服务器启动验证（`vite`，端口 5199，代理到 8010）：

```
/                        -> 200  <!doctype html> ... <script type="module" src="/@vite/client">
/src/main.ts             -> 200  import { createApp } from "/node_modules/.vite/deps/vue.js?v=..."
/api/v1/identity/auth/csrf/ -> 200  {"detail":"CSRF Cookie 已下发。"}
```

即：前端可启动，且同源代理 `/api` 到 Django 的链路可用。

## 五、未执行的测试（明确列出）

| 项 | 原因 |
| --- | --- |
| Docker Compose 启动与健康检查 | 本机 Docker 守护进程不可达，无法启动任何容器 |
| Celery worker / beat 运行验证 | 同上；任务与调度配置已就绪但未运行 |
| Playwright 端到端业务测试 | 未安装浏览器依赖，本轮未执行 |
| ~~库存并发测试（负库存、余额行并发创建、死锁重试幂等）~~ | **已执行**（见 §8）；必测案例 6/7/8 已通过 |
| MySQL 8.4 版本验证 | 本机为 MySQL 8.0.17 |
| 生产部署与恢复演练（备份可恢复） | 阶段 7 必测 |
| 性能测试（百万级库存流水、百万级采集读数、大文件导出） | 阶段 1 无对应数据量场景；测试机器配置与并发模型需在阶段 0 之后按实际资源确认 |
| 硬件采集接入（模拟器 → HTTP 采集入口） | 阶段 5 实施 |

## 六、复验记录（部署编排与文档基线增量）

在补齐 `compose.yaml`、`deploy/`、`scripts/` 与文档基线之后，重新执行了一遍完整检查，
确认未引入回归。**以下为本轮真实输出。**

### 6.1 后端

```
$ .\.venv\Scripts\python.exe -m ruff check apps config tests
All checks passed!

$ .\.venv\Scripts\python.exe -m pytest tests -q --reuse-db
........................................................................ [ 80%]
..................                                                       [100%]
90 passed in 18.51s
```

### 6.2 前端

```
$ npm run typecheck
> vue-tsc --build --force
（无错误输出，退出码 0）

$ npm run test
 ✓ tests/http-error.spec.ts (2 tests) 4ms
 ✓ tests/format.spec.ts (5 tests) 26ms
 ✓ tests/router.spec.ts (31 tests) 4ms
 ✓ tests/pro-table.spec.ts (4 tests) 356ms
 ✓ tests/views-compile.spec.ts (3 tests) 4304ms
 Test Files  6 passed (6)
      Tests  55 passed (55)

$ npm run build
✓ built in 9.74s
（产出 index / element / chart / vue 等分包 chunk）
```

### 6.3 环境连通的独立验证

直接连接（不依赖 netstat，因为 `Get-NetTCPConnection` 未列出这些监听端口）：

```
DB engine: django.db.backends.mysql
DB name  : yishang_platform
MySQL    : ('8.0.17', 'utf8mb4', 'utf8mb4_0900_ai_ci',
            'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION')
tables   : 62
Redis    : True 3.2.100
```

结论：MySQL 与 Redis 均实际连通；字符集、排序规则与严格模式与 `docs/data-model.md` 的记录一致。

### 6.4 部署编排的结构校验

`compose.yaml` 经 YAML 解析（**仅结构校验，未启动任何容器**）：

```
top keys: ['name', 'networks', 'services', 'volumes', 'x-backend-env']
services: ['backend', 'beat', 'migrate', 'mysql', 'nginx', 'object-storage', 'redis', 'worker']
networks: ['edge', 'internal']
volumes: ['backend-media', 'backend-static', 'mysql-data', 'object-storage-data', 'redis-data']
  mysql           healthcheck=yes depends_on=[]
  redis           healthcheck=yes depends_on=[]
  object-storage  healthcheck=yes depends_on=[]
  migrate         healthcheck=no  depends_on=['mysql']
  backend         healthcheck=yes depends_on=['migrate', 'mysql', 'redis']
  worker          healthcheck=yes depends_on=['migrate', 'mysql', 'redis']
  beat            healthcheck=no  depends_on=['migrate', 'mysql', 'redis']
  nginx           healthcheck=yes depends_on=['backend']
```

**这只能证明编排文件的语法与依赖关系成立，不能证明镜像可构建、服务可启动。**
Docker 相关项仍列为「未执行」。

### 6.5 文档与代码一致性修正

本轮扫描并修正了文档中与代码不一致的引用：

| 问题 | 修正 |
| --- | --- |
| 引用了不存在的测试文件 `test_core_api.py`、`test_analytics` | 改为 `test_core_services.py` 与真实用例名 |
| `.env.example` 缺少代码实际读取的 10 余个变量，且 `OBJECT_STORAGE_ENDPOINT_URL` 与代码读取的 `OBJECT_STORAGE_ENDPOINT` 不一致 | 按 `config/settings/*.py` 实际读取项重写 |
| `docs/requirements-matrix.md` 缺少「三、架构与代码组织」标题（被并入上一行表格） | 拆分修正 |

修正后重新扫描：`docs/` 下不再存在指向不存在的测试文件或变量的引用。

### 6.6 交付的冒烟脚本实际执行

`scripts/smoke_check.ps1` 本身也执行了一遍（验证该交付物可用）：

```
=== django check ===            System check identified no issues (0 silenced).
=== makemigrations --check ===  No changes detected
=== ruff check ===              All checks passed!
=== pytest ===                  90 passed in 18.10s
=== vue-tsc 类型检查 ===        （通过）
=== vitest ===                  Test Files 6 passed (6) / Tests 55 passed (55)
=== vite build ===              ✓ built in 9.78s
全部检查通过。
```

> 首次执行时脚本报 `ParserError`，原因是 PowerShell 脚本以**无 BOM 的 UTF-8** 保存，
> Windows PowerShell 5.1 按 ANSI 解析中文导致语法错误。已改为 `utf-8-sig` 保存并复验通过。

## 七、阶段 2 第一步复验记录（客户与供应商主数据增量）

新增 `apps/crm`、`apps/srm` 两个模块、5 个页面、17 个权限点与 22 条后端用例后，
重新执行完整检查。**以下为本轮真实输出。**

### 7.1 后端

```
$ .\.venv\Scripts\python.exe -m ruff check apps config tests
All checks passed!

$ .\.venv\Scripts\python.exe manage.py check
System check identified no issues (0 silenced).

$ .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
No changes detected

$ .\.venv\Scripts\python.exe -m pytest tests -q --reuse-db
........................................................................ [ 64%]
........................................                                 [100%]
112 passed in 25.13s
```

> 首次运行时 ruff 报出 14 处 `W292 No newline at end of file`（文件写入工具未补行尾换行），
> 已用 `ruff check --fix` 修正并复验通过；修正范围为行尾换行，不含语义变更。

### 7.2 前端

```
$ npm run typecheck
> vue-tsc --build --force
（无错误输出，退出码 0）

$ npm run test
 ✓ tests/decimal.spec.ts (10 tests)
 ✓ tests/http-error.spec.ts (2 tests)
 ✓ tests/format.spec.ts (5 tests)
 ✓ tests/router.spec.ts (36 tests)
 ✓ tests/pro-table.spec.ts (4 tests)
 ✓ tests/views-compile.spec.ts (3 tests)
 Test Files  6 passed (6)
      Tests  60 passed (60)

$ npm run build
✓ built in 9.84s
（新增 CustomerList / CustomerContactList / SupplierList / SupplierContactList /
  SupplierQualificationList 五个页面 chunk）
```

### 7.3 新增的后端用例（22 条，全部通过）

| 文件 | 条数 | 覆盖 |
| --- | --- | --- |
| `tests/test_crm_api.py` | 11 | 未登录拒绝、公司范围（列表/详情/写入）、越权写入回滚、编码公司内唯一（含数据库约束兜底）、审计落库、联系人继承范围、唯一主联系人、同名联系人、只读账号越权写入拒绝、`meta` 新增枚举 |
| `tests/test_srm_api.py` | 11 | 未登录拒绝、公司范围（列表/详情/写入）、编码公司内唯一、联系人/资质继承供应商范围、唯一主联系人、证书编号大小写不敏感去重、未填编号可并存多条（`dedup_key IS NULL`）、到期日早于发证日被拒、`days_to_expiry`/`is_expired` 由后端计算且未登记时为 `null`、只读账号越权写入拒绝 |

### 7.4 真实 HTTP 验证（直连开发库，非测试框架）

```
/api/v1/crm/customers/               200 count=3
/api/v1/crm/customer-contacts/       200 count=4
/api/v1/srm/suppliers/               200 count=3
/api/v1/srm/supplier-contacts/       200 count=3
/api/v1/srm/supplier-qualifications/ 200 count=4
  绍兴柯桥恒源纺织  quality_system   ISO9001-DEMO-001  expiry=2026-02-28  days=-201  expired=True
  宁波北仑辅料      test_report      ''                expiry=None        days=None  expired=None
dedup_key IS NULL rows: 1
meta 新增枚举键: admission_statuses, customer_categories, customer_levels,
                customer_statuses, qualification_types, supplier_categories, supplier_grades
```

`seed_demo` 连续执行两次：第一次新建 17 条（客户 3 / 客户联系人 4 / 供应商 3 /
供应商联系人 3 / 供应商资质 4），第二次 `合计新建 0 条`，幂等性成立。

### 7.5 本轮仍未执行的测试

- 数据库并发测试（必测案例 6、7）：当时库存余额尚未落地，**当时未执行**；
  **已在 §8（阶段 2 库存核心增量）执行并通过**。
- Docker Compose 启动、Celery、Playwright、备份恢复演练：状态与第五节一致，**仍未执行**。

## 八、阶段 2 库存核心增量复验记录（本轮）

集中开发统一库存服务（`apps/wms/services/stock.py`、迁移 `wms/0002`、`core/0003`）后重跑全量检查。
**以下为真实输出。**

```text
python -m ruff check apps config tests
  -> All checks passed!

python manage.py check
  -> System check identified no issues (0 silenced)

python manage.py makemigrations --check --dry-run
  -> No changes detected

python -m pytest tests -q --reuse-db
  -> 148 passed

npm run typecheck      -> vue-tsc，退出码 0
npm run test           -> 6 test files / 63 tests passed
npm run build          -> ✓ built（含 3 个新库存页面 chunk）
scripts\smoke_check.ps1 -> 全部检查通过，退出码 0
```

数量变化：pytest 112 → **148**（+36，均为 `tests/test_wms_inventory.py`）；
vitest 60 → **63**；权限点 117 → **124**；菜单 40 → **43**；业务页面 32 → **35**；开发库表 67 → **71**。

### 8.1 并发用例的真实性说明

任务书 14.2 要求「并发锁测试应使用真实独立事务和连接，不能仅依赖被测试框架外层事务掩盖的问题」。
`test_wms_inventory.py` 的 3 个并发用例严格按此执行：

- `@pytest.mark.django_db(transaction=True)`，不走测试框架的层包事务；
- 每个线程先 `connections.close_all()` 后重新获取独立连接；
- 用 `threading.Barrier` 同时放行，保证真正并发而非串行；
- `committed_data_cleanup` fixture 在用例结束后调用
  `flush --inhibit-post-migrate`，清理**已提交**的数据（否则会污染后续用例）。

三个用例断言：

| 用例 | 断言 |
| --- | --- |
| `test_concurrent_balance_creation_yields_single_row` | 3 并发入库 → 余额行恰好 1 行、流水 3 条、`on_hand = 3.000000` |
| `test_concurrent_issue_never_produces_negative_stock` | 可用 8、每单出 3、共 4 并发 → 仅 2 单成功，其余报 `InsufficientStock`，余额 `>= 0` |
| `test_concurrent_transfer_keeps_total` | 3 并发移库 → 两个储位各 15，合计 = 30（守恒） |

### 8.2 死锁重试与幂等的注入方式

`test_deadlock_retry_does_not_duplicate_ledger` 通过
`monkeypatch` 让 `apps.wms.services.stock.publish_event` 抛出
`OperationalError(1213, "Deadlock found")`，验证：

- 重试后业务结果**只产生一次**（流水数、余额变化均为单次）；
- `test_non_retryable_error_is_not_retried` 验证非 1213/1205 错误**不重试**，避免掩盖真实故障。

> 注：测试必须 `from apps.wms.services import stock` 后
> `monkeypatch.setattr(stock, "publish_event", ...)`，直接 import 函数对象无法被替换。

### 8.3 本轮仍未执行的测试

- **跨仓调拨与在途状态**：功能未实现，必测案例 11 的跨仓部分**未执行**。
- Docker Compose 启动、Celery worker/beat、Playwright E2E、备份恢复演练、
  性能压测、MySQL 8.4 版本验证：状态与第五节一致，**仍未执行**。


## 九、阶段 2 采购模块增量复验记录（本轮）

集中开发采购模块（`apps/procurement/`、迁移 `procurement/0001`、新增 `apps/workflow/registry.py`）后重跑全量检查。
**以下为真实输出。**

```text
python -m ruff check apps config tests
  -> All checks passed!

python manage.py check
  -> System check identified no issues (0 silenced)

python manage.py makemigrations --check --dry-run
  -> No changes detected

python -m pytest tests -q --reuse-db
  -> 183 passed

npm run typecheck      -> vue-tsc，退出码 0
npm run test           -> 6 test files / 66 tests passed
npm run build          -> ✓ built（含 3 个新采购页面 chunk）
scripts\smoke_check.ps1 -> 全部检查通过，退出码 0
```

数量变化：pytest 148 → **183**（+35，均为 `tests/test_procurement.py`）；
vitest 63 → **66**；权限点 124 → **139**；菜单 43 → **47**；业务页面 35 → **38**；开发库表 71 → **77**。

### 9.1 新增用例清单（35 条，全部通过）

| 分组 | 用例 | 说明 |
| --- | --- | --- |
| 鉴权与权限 | `test_procurement_endpoints_require_authentication`、`test_view_only_user_cannot_create_order`、`test_receipt_permission_is_enforced` | 未登录被拒、只读身份不能建单、缺权限时动作被拒 |
| 采购申请 | `test_requisition_create_persists_lines_and_generates_no`、`test_requisition_approval_writes_back_status`、`test_draft_requisition_cannot_be_converted` | 建单取号、审批回写、草稿不可转单 |
| 申请转订单 | `test_convert_requisition_to_order_and_block_duplicates` | 转单后申请行 `ordered_quantity` 累加，重复转单被拦截 |
| 金额计算 | `test_order_amount_is_computed_by_backend`、`test_order_tax_rounding_is_half_up`、`test_order_rejects_non_positive_quantity` | 金额由后端计算、`ROUND_HALF_UP`、非正数量被拒 |
| 供应商校验 | `test_suspended_supplier_cannot_be_used_without_reason`、`test_inactive_supplier_needs_override_permission`、`test_override_supplier_requires_reason_and_is_audited` | 停用/未准入拒绝；例外需专用权限 + 原因并留痕 |
| 审批回写 | `test_order_submit_then_approve_writes_back_status`、`test_order_approval_rejection_writes_back_rejected` | 通过/驳回回写业务状态（显式回调，非 signals） |
| 收货数量 | `test_receipt_over_order_quantity_is_rejected`、`test_draft_receipts_reserve_remaining_quantity`、`test_receipt_line_must_belong_to_the_order`、`test_unapproved_order_cannot_be_received` | 不允许超收、草稿占额度、跨订单行被拒、未批准订单不可收货 |
| 过账与质量 | `test_post_receipt_creates_quarantine_stock_and_blocks_issue`、`test_inspect_qualified_releases_stock_for_issue`、`test_inspect_rejected_keeps_stock_blocked`、`test_multi_line_receipt_inspect_releases_every_line_once` | 过账落待检且不可领用；放行后可领用；不合格仍被拦截；多行逐行放行 |
| 状态机 | `test_inspect_requires_posted_state`、`test_inspect_requires_remark`、`test_repeated_inspect_is_rejected`、`test_posted_receipt_cannot_be_cancelled`、`test_receipt_cancel_requires_reason`、`test_order_cannot_be_cancelled_once_receipt_exists`、`test_order_can_be_closed_after_receipt` | 未过账不能检验、必须填说明、不能重复判定、已过账不可取消、有收货后不可取消订单 |
| 幂等 | `test_receipt_post_is_idempotent_with_header`、`test_inspect_with_idempotency_key_replays_without_second_release` | 同键重放返回首次结果且不重复记账 / 放行 |
| 数据范围 | `test_orders_are_company_scoped`、`test_receipts_of_other_company_orders_are_not_visible` | 跨公司订单与收货不可见 |
| 枚举字典 | `test_meta_exposes_procurement_enums` | `/api/v1/meta/` 的 5 个采购枚举键 |
### 9.2 本轮修复的真实缺陷

开发过程中发现并修复（不是绕过）：

1. `create_order_from_requisition` 传入的是 `material_id` 等主键键名，而服务层只认对象键 →
   行参数构造已同时接受两者。
2. 视图层与序列化器的输入行键名不一致 → 统一映射后再交给服务层。
3. `post_receipt` / `inspect_receipt` 实际会调用 `wms.document.create` / `post` / `quality.release`，
   视图原先只声明采购权限 → 改为**列表形式**（AND 语义）并补齐内置角色的库存侧权限。
4. 测试侧：多身份共用一个 `APIClient` 会互相覆盖会话 → 新增 `api_user_client` fixture（每个身份独立 client）。
5. `tax_rate` 语义是百分数（0~100），测试原按小数比率传 0.13 → 修正为 13。
6. 多行收货单检验：外部 `Idempotency-Key` 若被所有行共用会相互顶掉 → 多行时改为按行号隔离，
   并新增 `test_multi_line_receipt_inspect_releases_every_line_once` 固化该行为。
7. `seed_demo` 审批后必须 `refresh_from_db()` 才能读到新事务写入的状态（`approve_instance` 在新事务提交）。

### 9.3 本轮仍未执行的测试

- Docker Compose 启动、Celery worker/beat、Playwright E2E、备份恢复演练、性能压测、
  MySQL 8.4 版本验证：状态与第五节一致，**仍未执行**。
- 采购侧：询价比价、到货差异、退货、应付与付款登记**未实现**，因此**无可执行用例**（未执行不等于通过）。

## 十、阶段 2 第四步复验记录（销售模块增量，本轮）

本轮新增 `apps/sales/`（销售订单 / 发货 / 退货）以及 `apps/wms` 的**库存占用**能力。
库存占用**不写库存流水**（流水只记实存量增减），只维护「实存 / 冻结 / 占用 / 可用」中的占用量；
发货出库、退货入库、检验放行**全部调用统一库存服务** `apps/wms/services/stock.py`，
没有第二套库存逻辑，也没有在 View / Serializer 里写库存代码。

### 10.1 后端

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| 系统检查 | `manage.py check` | `System check identified no issues (0 silenced).` |
| 迁移一致性 | `manage.py makemigrations --check --dry-run` | `No changes detected` |
| 静态检查 | `ruff check apps config tests` | `All checks passed!` |
| 自动化测试 | `pytest tests -q --reuse-db` | `217 passed`（原 183 + 新增 `tests/test_sales.py` 34 例） |

新增迁移（已实际执行 `migrate`，非只生成文件）：

| 迁移 | 内容 |
| --- | --- |
| `apps/wms/migrations/0003_stockreservation.py` | `wms_stockreservation` 表：`request_key` 单列唯一（幂等的最终保障）+ 3 个检查约束 + 2 个索引 |
| `apps/sales/migrations/0001_initial.py` | 销售订单 / 订单行 / 发货单 / 发货行 / 退货单 / 退货行共 6 张表 |

### 10.2 前端

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| 类型检查 | `npm run typecheck` | 退出码 0（无输出） |
| 组件测试 | `npm run test` | `Test Files 6 passed (6)` / `Tests 69 passed (69)` |
| 生产构建 | `npm run build` | `✓ built in 14.39s` |

新增页面 `SalesOrderList.vue` / `SalesShipmentList.vue` / `SalesReturnList.vue`；
`tests/fixtures/menu-components.json` 由后端权限注册表重新导出（51 项），
`router.spec.ts` 逐项校验页面菜单组件可被前端解析（路由用例 31 → 45）。

### 10.3 新增用例清单（34 条，全部通过）

| 分组 | 用例 | 覆盖的真实风险 |
| --- | --- | --- |
| 权限与数据范围 | `test_sales_endpoints_require_authentication`、`test_view_only_user_cannot_create_order`、`test_user_without_reserve_permission_cannot_reserve`、`test_sales_clerk_cannot_inspect_returns`、`test_orders_are_company_scoped` | 未登录拒绝；只读用户不能建单；无占用权限不能占用；**业务员不能自行判定退货**（职责分离）；跨公司不可见 |
| 订单与金额 | `test_order_amount_is_computed_by_backend`、`test_order_rejects_non_positive_quantity`、`test_suspended_customer_cannot_be_used` | 金额由后端算，前端传入被忽略；数量必须为正；停用客户不可下单 |
| 审批回写 | `test_order_submit_then_approve_writes_back_status`、`test_order_approval_rejection_writes_back_rejected` | 显式回调写回业务状态（不是 signals） |
| 库存占用 | `test_reserve_requires_approved_order`、`test_reserve_moves_available_to_reserved_without_touching_on_hand`、`test_reserve_is_idempotent`、`test_reserve_rejects_insufficient_available`、`test_reserve_rejects_quarantine_stock`、`test_reserve_uses_matching_batch_dimension`、`test_release_order_stock_returns_available`、`test_cancel_order_releases_open_reservations`、`test_order_without_warehouse_cannot_reserve` | 未批准不可占用；**占用只改可用量、不动实存量**；同键重放不重复占；可用不足拒绝；待检库存不可占用；按批次维度占用；释放归还可用量；取消订单自动释放未结占用；订单无仓库时拒占用 |
| 发货 | `test_shipment_requires_reservation`、`test_shipment_quantity_cannot_exceed_remaining`、`test_shipment_post_consumes_reservation_and_decrements_on_hand`、`test_shipment_post_is_idempotent` | 未占用不允许发货；不允许超发；过账消耗占用并减实存；过账幂等不重复扣减 |
| 退货与检验 | `test_return_requires_posted_shipment`、`test_return_quantity_cannot_exceed_shipped`、`test_return_must_be_posted_before_inspect`、`test_inspect_requires_remark`、`test_return_post_lands_in_quarantine`、`test_return_inherits_original_batch`、`test_inspect_qualified_returns_stock_to_qualified`、`test_inspect_rejected_keeps_stock_unusable`、`test_repeated_inspect_is_rejected` | 退货必须基于已过账发货；不允许超退；未收货不能判定；判定必须填说明；**退货先入待检**；批次继承原发货维度；合格回库可再用；不合格留在仓内不可动用；不能重复判定 |
| 链路与字典 | `test_chain_endpoint_lists_related_documents`、`test_meta_exposes_sales_enums` | `chain` 接口返回关联库存单据（任务书 12.1）；`/api/v1/meta/` 暴露 6 个销售枚举键 |

### 10.4 真实数据链路验证（直连开发库，非测试框架）

`seed_demo` 新增的 `_sales()` 全部经服务层执行，读取开发库真实数据核对：

```text
订单 SO-DEMO-0001 shipped 23940.0000 27052.2000
  行 1 YS-M-2401-NV-170A 60.000000 已发 60.000000 已退 6.000000 可退 54.000000
发货 SH-DEMO-0001 posted 出库单据 15
退货 SR-DEMO-0001 inspected qualified [('FG-2509-01', 42, '6.000000')]
  余额 42 FG-2509-01 qualified 实存 186.000000 占用 0.000000 可用 186.000000
未结占用 0
```

即成品批次 `FG-2509-01`：入库 240 → 占用 60 → 发货出库 60 → 退货 6 进待检 → 检验合格回库 6，
最终实存与可用均为 186，占用归零，与库存流水一致。

### 10.5 本轮修复的真实缺陷

1. 销售视图的过账动作把幂等结果写进了 `_replayed`，响应头 `Idempotency-Replayed` 实际丢失 →
   已改为 `replayed` 并在用例中固化（重放语义对客户端可见）。
2. 内置角色 `quality_inspector` 缺少 `wms.document.create` / `wms.document.post`，
   而质量放行要经统一库存服务创建并过账质量转换单 → **质检员实际无法完成放行**
   （采购来料检验同样受影响）。已补齐权限并重跑 `bootstrap_system`（9 → 11 个权限点）。
3. `frontend/src/utils/decimal.ts` 的 `places` 参数被收窄为字面量类型导致 `vue-tsc` 报 TS2322 →
   显式声明为 `number`。

### 10.6 本轮仍未执行的测试

- **并发多连接实测未执行**：占用的并发保障是 `request_key` 单列唯一约束 + `select_for_update()`
  加锁顺序（余额 → 占用），但没有用真实多进程 / 多连接压测验证「同键并发占用只成功一次」，
  与第五节、§8.1 的口径一致，**不得据用例断言等同于并发压测通过**。
- Docker Compose、Celery Worker/Beat、Playwright、备份恢复、性能压测、MySQL 8.4：
  状态与第五节一致，**仍未执行**。
- 销售侧未实现能力因此**无可执行用例**（未执行 ≠ 通过）：销售计划、颜色尺码矩阵批量录入、
  折扣、订单变更版本快照、分销商、基础预测、应收与收款登记、跨维度自动拆分占用、
  多批次部分退货的批次分摊。

## 十二、界面样式增量复验记录（本轮）

本轮只改前端样式与导航组件（后端零改动），新增侧边导航层级区分的契约测试。

### 12.1 前端检查（真实输出）

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| 类型检查 | `npm run typecheck` | 退出码 0（无输出） |
| 组件测试 | `npm run test` | `Test Files 7 passed (7)` / `Tests 79 passed (79)` |
| 生产构建 | `npm run build` | `✓ built in 12.48s` |

新增 `tests/side-menu.spec.ts`（10 条，全部通过）：

| 用例 | 覆盖点 |
| --- | --- |
| 一级目录渲染为 `ys-menu-group--d0`、二级页面渲染为 `ys-menu-node--d1` | DOM 层级 class 真实区分，且二级不会带一级 class |
| 展开的子菜单容器带 `el-menu--inline`，二级条目位于其中 | 分组容器结构 |
| 一级与二级在样式表中有不同的排版规则 | 用 **postcss 真实解析**样式表，断言一级 12px / 字重 600 / 有字距，二级 13px / 有缩进，且两者字号不同 |
| 只有二级条目带圆点标记，一级目录不带 | 层级标记不被误用 |
| 二级选中态是高亮块、一级展开态是分组底色 | 选中态可区分 |
| 展开的子菜单容器有独立底色 | 「同一目录下的页面」成组 |
| 折叠态有专门规则 | 折叠时不残留圆点/箭头 |
| 样式表能被真实 CSS 解析器完整解析 | 语法合法性（112 组花括号配平） |
| 菜单行高由侧边栏变量统一收窄 | 断言 `--el-menu-item-height: 40px` / `--el-menu-sub-item-height: 36px`，以及一级 40px / 二级 36px 的显式高度，防止回到 Element 默认 56px |
| 当前页面所属的一级目录有定位提示 | 父级目录的 `is-active` 状态有左侧竖条与提亮规则（`::after`），并与展开态一致 |

### 12.2 开发服务器实际下发校验

```
$ Invoke-WebRequest http://127.0.0.1:5173/src/styles/index.css
status=200  len=18144
  ys-menu-group--d0        => True
  ys-menu-node--d1         => True
  --el-color-primary: #1668dc => True
  el-menu--inline          => True
```

### 12.3 本轮未执行

- **浏览器截图级像素校验未执行**：浏览器自动化被安全策略拒绝（自动审核失败，非人工拒绝），
  因此最终观感未经我截图确认，仅以「DOM 层级 class + postcss 解析 + 开发服务器下发」替代。
  观感确认需人工在浏览器打开 `http://127.0.0.1:5173/` 查看。
- 响应式（窄屏/平板）与暗色主题未实现，因此无可执行用例。

## 十三、视图样式统一复验记录（本轮）

> 说明：第十二节记录的是「侧边导航层级区分」当轮的输出（当时为 7 文件 / 79 项），本节**不改写**该记录，
> 只追加紧随其后的「视图样式统一」增量的真实输出，两者互不覆盖。

本轮只改前端样式与视图模板（后端零改动）：把各视图重复手写的白色面板、区块标题、统计卡、
代码块下沉为 `frontend/src/styles/index.css` 的共享类，并新增契约测试防止再次分叉。

### 13.1 前端检查（真实输出）

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| 类型检查 | `npm run typecheck` | 退出码 0（无输出） |
| 组件测试 | `npm run test` | `Test Files 8 passed (8)` / `Tests 110 passed (110)` |
| 生产构建 | `npm run build` | `✓ built in 12.02s` |

`npm run test` 的分文件输出：

```text
 RUN  v3.0.5 E:/github/Yishang-Hub/frontend

 ✓ tests/styles.spec.ts (31 tests) 9ms
 ✓ tests/decimal.spec.ts (10 tests) 8ms
 ✓ tests/http-error.spec.ts (2 tests) 3ms
 ✓ tests/format.spec.ts (5 tests) 40ms
 ✓ tests/router.spec.ts (45 tests) 7ms
 ✓ tests/side-menu.spec.ts (10 tests) 91ms
 ✓ tests/pro-table.spec.ts (4 tests) 525ms
 ✓ tests/views-compile.spec.ts (3 tests) 5770ms

 Test Files  8 passed (8)
      Tests  110 passed (110)
```

### 13.2 新增用例清单（`tests/styles.spec.ts`，31 条，全部通过）

| 用例 | 覆盖点 |
| --- | --- |
| 共享类在全局样式中有定义（22 条，每类一条 `it.each`） | 类清单与样式表一致，删掉某个类会导致失败 |
| 任何 .vue 的 scoped 样式都不得重新定义共享类 | **防止再次分叉**（当前 offenders 断言为 `[]`） |
| 面板类使用同一份视觉令牌 | `.ys-panel` 与 `.ys-table-card` 的圆角、边框、阴影完全一致 |
| 区块标题带主色竖条、统计数值用品牌深蓝 | `.ys-section-title::before`、`font-weight: 600`、`var(--ys-navy-900)` |
| 5 个页面确实改用了共享类且不再手写同款 | 逐文件断言模板含共享类、scoped 样式不含同名定义 |

### 13.3 样式表与重名度量（真实输出）

```text
.tmp/checkcss.py    -> BOM False / CRLF 0 / bytes 20702 / braces 129 = 129
.tmp/scan_styles.py -> vue files with style block: 16
                       distinct .ys- selectors in view styles: 17
                       selectors defined in more than one file: 0
```

改造前 `.ys-section-title` 有 4 份不同定义，改造后视图内重名共享类为 **0**。

`styles.spec.ts` 共 31 条的构成：22（每个共享类一条）+ 1（仓库中存在带 scoped 样式的组件）
+ 1（禁止视图重定义共享类）+ 1（`.ys-panel` 与 `.ys-table-card` 视觉令牌一致）
+ 1（区块标题竖条 / 字重 600 / 统计数值品牌深蓝）+ 5（5 个页面已改用共享类）。

### 13.4 一键冒烟（`scripts/smoke_check.ps1`）

下列为各步骤**关键输出行的汇总**（非终端逐行原始输出，每行均取自实际执行结果）：

```text
$ powershell -ExecutionPolicy Bypass -File scripts\smoke_check.ps1
=== django check ===                System check identified no issues (0 silenced).
=== makemigrations --check ===      No changes detected
=== ruff check ===                  All checks passed!
=== pytest ===                      217 passed in 81.12s
=== vue-tsc 类型检查 ===            退出码 0
=== vitest ===                      Test Files 8 passed (8) / Tests 110 passed (110)
=== vite build ===                  ✓ built in 15.44s

全部检查通过。
```

退出码 0，**7 个步骤全部通过**。

### 13.5 本轮未执行

- **浏览器截图级像素校验未执行**：浏览器自动化被安全策略拒绝（自动审核失败，非人工拒绝），
  因此最终观感未经截图确认，仅以「DOM/模板断言 + postcss 解析样式表 + 生产构建」替代。
  观感确认需人工在浏览器打开 `http://127.0.0.1:5173/` 查看。
- 窄屏响应式与暗色主题未实现，因此无可执行用例。

## 十四、窄屏响应式复验记录（本轮）

> 本节只追加本轮（窄屏响应式）的真实输出，**不改写**第十二、十三节的历史记录。

本轮只改前端布局与样式（后端零改动）：新增 `src/composables/useAutoCollapse.ts`，
侧边栏改为窄屏自动折叠；统计卡由 `el-row` + 固定 `:span` 改为共享 flex 栅格；
「列多时表格横向滚动」写进样式表。

### 14.1 前端检查（真实输出）

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| 类型检查 | `npm run typecheck` | 退出码 0（无输出） |
| 组件测试 | `npm run test` | `Test Files 9 passed (9)` / `Tests 125 passed (125)` |
| 生产构建 | `npm run build` | `✓ built in 11.65s` |

`npm run test` 的分文件输出：

```text
 RUN  v3.0.5 E:/github/Yishang-Hub/frontend

 ✓ tests/styles.spec.ts (31 tests) 13ms
 ✓ tests/decimal.spec.ts (10 tests) 11ms
 ✓ tests/http-error.spec.ts (2 tests) 5ms
 ✓ tests/responsive.spec.ts (15 tests) 41ms
 ✓ tests/format.spec.ts (5 tests) 24ms
 ✓ tests/router.spec.ts (45 tests) 7ms
 ✓ tests/side-menu.spec.ts (10 tests) 88ms
 ✓ tests/pro-table.spec.ts (4 tests) 435ms
 ✓ tests/views-compile.spec.ts (3 tests) 5146ms

 Test Files  9 passed (9)
      Tests  125 passed (125)
```

### 14.2 新增用例清单（`tests/responsive.spec.ts`，15 条，全部通过）

| 分组 | 用例 | 覆盖的真实风险 |
| --- | --- | --- |
| 断点 | JS 断点常量与样式表 1200px 断点一致 | **改一边忘另一边**：`NARROW_BREAKPOINT` 与 `@media` 失配会让「自动折叠」和视觉断点错位 |
| 断点 | ≤1440px 表格横向滚动（`overflow-x: auto` + `min-width: 720px`） | 列多时不再把每列压到不可读 |
| 断点 | ≤1200px 页面/面板内边距与统计卡最小宽收窄 | 窄屏留白过大挤占内容 |
| 断点 | ≤992px 标题竖排、统计卡整行、`.ys-grid-2` 单列 | 固定 `:span` 在窄屏会压出「半张卡」 |
| 断点 | ≤992px 弹窗/抽屉 `width: 92% !important` | Element 内联宽度无法用普通选择器覆盖 |
| 默认值 | `.ys-grid-2` 默认双列、`.ys-stat-card` 默认 `flex: 1 1 168px` | 默认值被误删后窄屏规则会失去对照基准 |
| 折叠 | 宽屏默认展开 | 回归检查 |
| 折叠 | 窄屏默认折叠，且用户可手动展开 | 自动折叠不能变成「用户无法展开」 |
| 折叠 | 视口变窄时自动折叠 | 拖窗口即生效，不需要刷新页面 |
| 折叠 | 视口跨断点后清除手动偏好 | 窗口拉宽后侧边栏不应停在收起状态 |
| 折叠 | 卸载后不再响应 resize | 离开页面后仍改状态会留下隐蔽的状态泄漏 |
| 视图 | `OutboxList.vue` 不再含 `<el-row` / `:span=` | 防止改回固定栅格 |
| 视图 | `ProgressView.vue` 改用 `.ys-stat-cards` 与 `.ys-grid-2` | 同上 |
| 视图 | `BasicLayout.vue` 使用 `useAutoCollapse`，无固定 `collapsed = ref(false)` | 防止把自动折叠改回写死 |

### 14.3 一键冒烟（`scripts/smoke_check.ps1`，真实输出汇总）

```text
=== django check ===            System check identified no issues (0 silenced).
=== makemigrations --check ===  No changes detected
=== ruff check ===              All checks passed!
=== pytest ===                  217 passed in 76.26s (0:01:16)
=== vue-tsc 类型检查 ===        退出码 0
=== vitest ===                  Test Files 9 passed (9) / Tests 125 passed (125)
=== vite build ===              ✓ built in 11.25s

全部检查通过。
```

退出码 0，**7 个步骤全部通过**。

### 14.4 本轮未执行

- **浏览器截图级像素校验未执行**：浏览器自动化被安全策略拒绝（自动审核失败，非人工拒绝），
  拖拽窗口时的折叠平滑度、≤768px 手机竖屏观感**均未经我实测**，需人工在浏览器确认。
- 未做「筛选栏折叠面板」、暗色主题、触摸手势与横竖屏旋转验证。

## 十五、阶段 3 第一步复验记录（BOM 与工艺路线版本快照，本轮）

> 本节只追加本轮真实输出，**不改写**前面各节的历史记录。本轮改动全部是新文件 +
> 少量接线（`LOCAL_APPS`、`config/urls.py`、权限注册表、`bootstrap_system`、`seed_demo`、`MetaView`），
> **不触碰库存服务与阶段 2 已验收代码**。

### 15.1 后端（真实输出）

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| Django 系统检查 | `manage.py check` | `System check identified no issues (0 silenced).` |
| 迁移一致性 | `manage.py makemigrations --check --dry-run` | `No changes detected` |
| 静态检查 | `ruff check apps config tests` | 首跑 **失败**（4 处，见 §15.3）；修复后 `All checks passed!` |
| 全量测试 | `pytest tests -q --reuse-db` | `267 passed in 105.84s (0:01:45)` |
| 计划模块测试 | `pytest tests/test_planning.py -q --reuse-db` | `50 passed in 21.40s` |

`pytest` 分文件构成（`tests/` 目录）：本轮新增 `test_planning.py`（50 条），
阶段 2 及之前的全部用例保持不变（234 → 全量 267 条），说明本轮**未破坏既有行为**。

### 15.2 前端（真实输出）

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| 类型检查 | `npm run typecheck` | 退出码 0（无输出） |
| 组件测试 | `npm run test` | `Test Files 9 passed (9)` / `Tests 127 passed (127)` |
| 生产构建 | `npm run build` | `✓ built in 13.14s` |

`npm run test` 分文件输出：

```text
 ✓ tests/styles.spec.ts (31 tests) 10ms
 ✓ tests/decimal.spec.ts (10 tests) 12ms
 ✓ tests/http-error.spec.ts (2 tests) 4ms
 ✓ tests/responsive.spec.ts (15 tests) 40ms
 ✓ tests/format.spec.ts (5 tests) 27ms
 ✓ tests/router.spec.ts (47 tests) 8ms
 ✓ tests/side-menu.spec.ts (10 tests) 93ms
 ✓ tests/pro-table.spec.ts (4 tests) 490ms
 ✓ tests/views-compile.spec.ts (3 tests) 5765ms
 Test Files  9 passed (9)
      Tests  127 passed (127)
```

`tests/router.spec.ts` 由 45 → 47 条：`frontend/tests/fixtures/menu-components.json` 已用
`.tmp/menufixture.py` 按最新后端菜单重新生成（54 条），新增的
`views/planning/BomList.vue`、`views/planning/RoutingList.vue` 会被
`views-compile.spec.ts` 逐个编译（能捕获"菜单登记了组件但文件不存在/编译不过"）。

生产构建产物包含 `dist/assets/BomList-B_Xq9rdS.js`（15.38 kB）与
`dist/assets/RoutingList-BoeDw3JC.js`（14.65 kB），两个页面已进入按路由分割的产物。

### 15.3 一键冒烟（`scripts/smoke_check.ps1`，真实输出汇总）

首次执行（**真实失败，不是假定通过**）：

```text
=== django check ===                System check identified no issues (0 silenced).
=== makemigrations --check ===      No changes detected
=== ruff check ===                  tests\test_planning.py:17:1: I001 Import block is un-sorted or un-formatted
                                    tests\test_planning.py:24:34: F401 `StateConflict` imported but unused
                                    tests\test_planning.py:26:49: F401 `RoleScopeGrant` imported but unused
                                    tests\test_planning.py:508:5: SIM117 Use a single `with` statement ...
                                    Found 4 errors.
!! ruff check 失败（退出码 1）
=== pytest ===                      267 passed in 105.84s (0:01:45)
=== vue-tsc 类型检查 ===            退出码 0
=== vitest ===                      Test Files 9 passed (9) / Tests 127 passed (127)
=== vite build ===                  ✓ built in 13.14s

以下检查失败：ruff check
```

修复内容（只改 `backend/tests/test_planning.py`，**不放松检查规则**）：

1. `from apps.factory.models import Workshop` 移到 `apps.identity` 之前（isort 顺序）。
2. 删除未使用的 `StateConflict`、`RoleScopeGrant` 导入。
3. 嵌套 `with pytest.raises(IntegrityError): with transaction.atomic():` 合并为
   `with pytest.raises(IntegrityError), transaction.atomic():`。
4. 修完重跑 `ruff check apps config tests` → `All checks passed!`，
   重跑 `pytest tests/test_planning.py` → `50 passed in 21.40s`。

> 说明：这次失败是**冒烟脚本的价值体现**——单元测试全绿（267 passed）时 ruff 仍能发现
> 导入顺序与残留导入。修复后全量测试与静态检查同时通过，未通过"忽略规则"绕过。

修复后**再次执行完整冒烟**（最终状态，真实输出汇总）：

```text
=== django check ===            System check identified no issues (0 silenced).
=== makemigrations --check ===  No changes detected
=== ruff check ===              All checks passed!
=== pytest ===                  267 passed in 94.82s (0:01:34)
=== vue-tsc 类型检查 ===        退出码 0
=== vitest ===                  Test Files 9 passed (9) / Tests 127 passed (127)
=== vite build ===              ✓ built in 10.65s

全部检查通过。
```

退出码 0，**7 个步骤全部通过**。

### 15.4 新增用例清单（`tests/test_planning.py`，48 个函数 / 50 条用例，全部通过）

| 分组 | 用例（节选，共 48 个函数） | 覆盖的真实风险 |
| --- | --- | --- |
| 权限与范围 | `test_planning_endpoints_require_authentication`、`test_view_only_user_cannot_create_bom`、`test_routing_permission_does_not_grant_bom_write`、`test_cross_company_objects_are_rejected`、`test_routing_step_workshop_outside_scope_is_rejected` | 匿名 403；只读不能写；**工艺权限不得顺带授予 BOM 写权限**；跨公司/越权车间必须被拒 |
| 明细校验 | `test_create_bom_persists_lines_and_computes_gross_quantity`、`test_client_supplied_gross_quantity_is_ignored`、`test_bom_loss_rate_out_of_range_is_rejected`、`test_bom_quantity_must_be_positive`、`test_bom_without_lines_is_rejected`、`test_duplicate_normal_material_is_rejected`、`test_bom_effective_range_must_be_ordered`、`test_inactive_style_cannot_be_used`、`test_sku_must_belong_to_style` | **含损耗用量必须由后端算**（前端传值被忽略）；损耗率边界 [0,1)；空明细与重复用料拒绝 |
| 替代料 | `test_substitute_line_links_to_normal_line`、`test_substitute_for_unknown_line_is_rejected`、`test_normal_line_cannot_reference_substitute_target` | 替代料只能指向同一 BOM 的正常用料行，反向引用被拒 |
| 版本 | `test_version_no_increments_within_scope`、`test_scope_version_unique_constraint_is_enforced`、`test_new_version_from_submitted_is_rejected`、`test_draft_can_be_updated_but_submitted_cannot`、`test_optimistic_lock_rejects_stale_version` | 版本号在范围内自增；**数据库唯一约束兜底（真实 `IntegrityError`）**；提交后冻结；乐观锁 409 |
| 审批 | `test_submit_requires_approval_template`、`test_approve_activates_version_and_obsoletes_previous`、`test_reject_returns_document_to_rejected_state`、`test_withdraw_returns_document_to_draft` | 无模板**拒绝提交**而非跳过；通过时旧生效版本转 `obsolete`；驳回/撤回状态正确 |
| 快照 | `test_snapshot_matches_version_and_survives_new_version`、`test_bom_snapshot_service_equals_api` | **派生新版本后旧版本快照不变**（必测案例 13）；接口与服务输出逐字段相等 |
| 作废 | `test_obsolete_requires_reason`、`test_obsolete_marks_version_inactive`、`test_obsolete_submitted_is_rejected` | 作废必填原因；作废后不再是生效版本；审核中不能作废 |
| 生效版本 | `test_effective_bom_returns_approved_only` | 只有 `approved` 可被 MRP/MES 取用 |
| 审计 | `test_key_actions_are_audited` | 关键动作落 `AuditLog` |
| 工艺路线 | `test_create_routing_applies_default_steps`、`test_create_routing_with_explicit_steps`、`test_duplicate_routing_sequence_is_rejected`、`test_negative_standard_hours_is_rejected`、`test_routing_requires_at_least_one_step`、`test_routing_submit_and_approve`、`test_routing_new_version_copies_steps_and_obsoletes_previous`、`test_routing_snapshot_contains_quality_gate`、`test_routing_update_locks_after_submit`、`test_routing_obsolete_requires_reason` | 默认工艺（含质检点）生效；**显式空工序列表被拒**；重复顺序/负标工拒绝；派生新版本复制工序 |
| 服务层边界 | `test_meta_exposes_planning_enums`、`test_service_rejects_style_from_another_company`、`test_service_rejects_material_from_another_company`、`test_service_rejects_out_of_range_loss_rate`、`test_service_requires_reason_to_obsolete` | 绕过接口直接调服务也必须做公司校验与边界校验 |

### 15.5 真实数据链路验证（直连开发库，非测试框架）

用 Django `Client`（`SERVER_NAME=127.0.0.1`）+ `admin` 账号直连**开发库** `yishang_platform`，
读取 `seed_demo` 造的演示数据（真实输出）：

```text
anonymous /api/v1/planning/boms/ -> 403
admin login -> True
admin /api/v1/planning/boms/ -> 200，count = 1
BOM: BOM202609180001 v1 approved，lines = 5，scope = 款式通用，style = YS-W-2401
  line1: FAB-001 qty=0.280000 loss=0.0600000000 gross=0.296800
snapshot lines = 5，service == api -> True
Routing: RT202609180001 v1 approved，steps = 5
  steps: 1.裁剪 / 2.缝制 / 3.整烫 / 4.检验(质检点) / 5.包装
meta bom_statuses: ['draft','submitted','approved','rejected','obsolete']
meta bom_line_types: ['normal','substitute']
GET /api/v1/schema/ -> 200（application/vnd.oai.openapi），planning 路径 14 个
```

`planning` 的 14 个 OpenAPI 路径：`boms/`、`boms/{id}/`、`boms/{id}/submit|obsolete|new-version|snapshot|set-active`、
`routings/` 下同样 7 个。`set-active` 由 `ScopedModelViewSet` 基类提供（启停，任务书 5.5「主数据优先停用」），
业务方仍**没有 `DELETE`**。

关键点核实：`gross_quantity` 为 `0.296800`（= 0.28 × (1 + 0.06)，已按 6 位小数量化，无浮点尾数）；
**服务层快照与接口快照逐字段相等**；「检验」工序带质检点标记；匿名访问被拒。

### 15.6 本轮修复的真实缺陷

| # | 缺陷 | 发现方式 | 修复 |
| --- | --- | --- | --- |
| 1 | `Routing` 缺 `scope_label`（只有 `Bom` 有），序列化器取属性时 `AttributeError` | 前端页面/序列化首次实跑 | 抽出 `ScopeLabelMixin` 给 `Bom` / `Routing` 共用 |
| 2 | `gross_quantity` 未量化，输出 `0.2968000000000000` 浮点尾数 | 真实库读取演示数据时发现 | 加 `ROUND_HALF_UP` 量化到 6 位小数 |
| 3 | `create_routing(steps=[])` 静默回落默认工艺，把错误输入变成"有效"数据 | 写用例时推演 `steps=[]` 分支 | 显式空列表抛 `ROUTING_STEP_REQUIRED`，只有完全不传才套默认 |
| 4 | 服务层缺公司一致性校验，绕过接口直接调服务可跨公司建 BOM | 补服务层边界用例时发现 | 增加 `_assert_company_scope` + BOM 明细逐行物料公司校验 |
| 5 | `RoutingList.vue` 模板内联箭头函数触发 `TS7006`（隐式 any） | `npm run typecheck` | 抽成具名函数 `qualityGateCount(row)` |
| 6 | `BomList.vue` 的 `filters` 引用了 `meta.options()` 快照数组，meta 异步加载后下拉项为空 | 复查数据流 | 改为 `computed(() => [...])`（下拉项随 meta 更新） |
| 7 | `tests/test_planning.py` 4 处 ruff 违规（导入顺序、2 个未使用导入、嵌套 `with`） | 一键冒烟脚本 | 见 §15.3；修完重跑通过 |

> 第 1、2、3、4 条是**代码缺陷**，第 5、6 条是**前端类型/数据流缺陷**，第 7 条是**静态检查问题**。
> 全部是实际执行暴露的，未虚构；发现后都补了对应断言或直接修代码，未用"放宽检查"绕过。

### 15.7 本轮仍未执行的测试（不得视为通过）

- **Docker Compose 未启动验证**（本机无 Docker）；`deploy/` 下的编排文件只做过结构检查。
- **`mysqlclient` 生产驱动未验证**：本地用 `DB_DRIVER=pymysql`；`mysqlclient` 未安装/未编译验证。
- **Celery Worker / Beat 未运行**：本轮无异步任务依赖（快照是同步计算）。
- **MySQL 版本偏差**：本机为 MySQL 8.0.17，任务书要求 8.4 LTS，**未在 8.4 上验证**。
- **Playwright 端到端未执行**：浏览器自动化被安全策略拒绝（自动审核失败，非人工拒绝），
  因此「登录 → 打开 BOM 页面 → 新建版本 → 提交审批」的全链路**未经浏览器实测**，
  仅以「真实 HTTP Client 调用 + 组件编译 + 生产构建」替代。
- **并发测试未针对 planning 编写**：本轮唯一并发敏感点是「同一范围同时只有一个生效版本」，
  当前靠 `select_for_update` + 服务层校验；**未做独立连接的真实并发用例**（阶段 2 库存已有并发用例，
  但那是库存键，不能替代本场景）。这是本模块已知的测试缺口。
- **未做性能压测**：BOM 明细行数量与多层展开的性能未评估（MRP 阶段需要）。
- **≤768px 手机布局、暗色主题、触摸手势**未验证（承前）。

## 十六、阶段 3 第二步复验记录（MRP，本轮）

> 本节只追加本轮真实输出，**不改写**前面各节的历史记录。本轮新增 `apps/planning/mrp.py`
> 计算内核、4 张 MRP 表、2 个前端页面，并修复 6 个真实缺陷（§16.6）；
> MRP 对库存与采购**只读**，建议转单只产出**草稿**采购申请，生产建议**不伪造工单**。

### 16.1 后端（真实输出）

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| Django 系统检查 | `manage.py check` | `System check identified no issues (0 silenced).` |
| 迁移一致性 | `manage.py makemigrations --check --dry-run` | `No changes detected` |
| 静态检查 | `ruff check apps config tests` | `All checks passed!` |
| 全量测试 | `pytest backend/tests -q --reuse-db` | `301 passed in 112.01s (0:01:52)` |
| MRP 专项 | `pytest backend/tests/test_mrp.py -q --reuse-db` | `32 passed in 4.64s` |
| 登录 / CSRF 专项 | `pytest backend/tests/test_auth_api.py -q --reuse-db` | `14 passed in 1.47s` |

用例总数 299 → **301**（新增 `test_mrp.py` 32 条、登录 CSRF 回归 2 条；
`test_auth_api.py` 由 12 → 14 条）。全部既有用例保持通过，说明本轮**未破坏既有行为**。

### 16.2 MRP 用例构成（`backend/tests/test_mrp.py`，32 条）

| 分组 | 用例 |
| --- | --- |
| 时间分段净算 | `test_net_requirement_nets_on_hand_and_on_order`（面 210 毛需求 − 60 库存 − 40 在途 = 110）、`test_purchase_on_order_reduces_net_requirement`、`test_usable_stock_excludes_frozen_reserved_and_unqualified`、`test_overdue_demand_lands_in_first_bucket`、`test_demand_outside_horizon_ignored`、`test_partially_shipped_demand_uses_remaining_quantity`、`test_draft_order_produces_no_demand` |
| BOM 展开 | `test_explosion_uses_parent_net_requirement`（父件净 70 × 2 = 140，而非毛 100 × 2）、`test_low_level_code_net_calculated_once`（同一子件合并为 15）、`test_suggestion_type_rules_and_unexploded_materials` |
| 异常与边界 | `test_cycle_bom_rejected_and_failed_run_recorded`（`BOM_CYCLE_DETECTED` + 1 条 `failed` 运行 + 无 `completed`）、`test_mrp_is_read_only_for_inventory`、`test_invalid_bucket_and_horizon_rejected`、`test_week_bucket_normalises_to_monday`（9/2 → 8/31）、`test_audit_and_outbox_event_written_with_business_data` |
| 转单与状态机 | `test_convert_creates_draft_requisition_with_document_link`、`test_convert_twice_rejected`、`test_convert_stale_suggestion_rejected`、`test_convert_production_suggestion_rejected`（`PRODUCTION_ORDER_NOT_IMPLEMENTED`）、`test_convert_inactive_material_rejected`、`test_cancel_requires_reason_and_blocks_convert`、`test_archive_run_blocks_conversion_and_repeat_archive_rejected` |
| API 与权限 | `test_anonymous_access_rejected`（403）、`test_view_only_user_cannot_run_mrp`、`test_user_without_convert_permission_cannot_convert`、`test_convert_requires_procurement_requisition_create`、`test_run_api_creates_run_with_counts_and_detail_endpoints`、`test_api_convert_and_repeat_rejected`、`test_api_run_rejects_invalid_parameters`、`test_api_run_scoped_to_company_and_warehouse`、`test_mrp_permissions_do_not_grant_other_modules`、`test_archive_api_requires_permission_and_is_audited` |

### 16.3 前端（真实输出）

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| 类型检查 | `npm run typecheck` | 退出码 0（无输出） |
| 组件测试 | `npm run test` | `Test Files 9 passed (9)` / `Tests 129 passed (129)` |
| 生产构建 | `npm run build` | `✓ built in 11.99s` |

`tests/router.spec.ts` 由 47 → 49 条：`frontend/tests/fixtures/menu-components.json` 已按最新后端菜单
重新生成（**56 条**），新增的 `views/planning/MrpRunList.vue`、`views/planning/MrpSuggestionList.vue`
被 `views-compile.spec.ts` 逐个编译。`vitest` 分文件输出：

```text
 ✓ tests/http-error.spec.ts (2 tests) 3ms
 ✓ tests/responsive.spec.ts (15 tests) 38ms
 ✓ tests/format.spec.ts (5 tests) 25ms
 ✓ tests/router.spec.ts (49 tests) 9ms
 ✓ tests/side-menu.spec.ts (10 tests) 98ms
 ✓ tests/pro-table.spec.ts (4 tests) 479ms
 ✓ tests/views-compile.spec.ts (3 tests) 5491ms
   ✓ 视图模块 > 每个视图都能被编译并加载 5488ms
 Test Files  9 passed (9)
      Tests  129 passed (129)
```

生产构建产物包含 `dist/assets/MrpRunList-D1oXWkdZ.js`（12.32 kB）、
`dist/assets/MrpSuggestionList-B8mYygLV.js`（6.52 kB）。

### 16.4 一键冒烟（`scripts/smoke_check.ps1`，真实输出）

```text
全部检查通过。
```

7 步（`django check` / `makemigrations --check` / `ruff` / `pytest` / `vue-tsc` / `vitest` / `vite build`）
退出码 0，脚本自身判定 `$failed.Count -eq 0`。

### 16.5 真实 HTTP 链路验证（非测试框架，对着运行中的开发服务器）

验收脚本使用 `urllib` + CookieJar，走**真实的 Session 登录、CSRF 校验、DRF 权限与生产同源的
URL 路径**（不是 `django.test.Client`，也不是 SQLite），脚本按收尾约定删除、结论以本节为准。
脚本逐项计 **29 项请求检查全部通过**；下表按业务阶段归并展示：

| # | 检查 | 期望 | 真实结果 |
| --- | --- | --- | --- |
| 1 | 未登录访问 `GET /api/v1/planning/mrp-runs/` | 403 | 403 `NOT_AUTHENTICATED` |
| 2 | 取 CSRF Cookie 后**不带令牌**登录 | 403 | 403 `CSRF_FAILED`（`CSRF token missing.`） |
| 3 | 带正确令牌用 `.env` 口令登录 `admin` | 200 | 200 |
| 4 | 读会话 / 读用户列表 | 200 | 200（`company_id=None`，超管无归属公司） |
| 5 | 运行 MRP 不传 `company_id` | 400 | 400 `COMPANY_REQUIRED` |
| 6 | `bucket=month` | 400 | 400 `VALIDATION_FAILED`（`"month" 不是合法选项`） |
| 7 | 区间颠倒 | 400 | 400 `VALIDATION_FAILED`（`需求区间结束日期不能早于开始日期`） |
| 8 | 运行 MRP（`company_id=2`，90 天，按日） | 201 | 201 `MRP202609180005`，`item_count=7 / suggestion_count=5` |
| 9 | `GET .../{id}/demands/` | 200 | 200 `count=7`（`L0` 成品 300 + 5 条 `L1` 子件） |
| 10 | `GET .../{id}/supplies/` | 200 | 200 `count=3`（面料 1280 库存 + 400 在途、成品 186 库存） |
| 11 | `GET .../{id}/suggestions/` | 200 | 200 `count=5`（1 生产 + 4 采购） |
| 12 | `GET /mrp-suggestions/?run_id=` | 200 | 200（过滤生效） |
| 13 | 旧运行建议转单 | 409 | 409 `SUGGESTION_STALE` |
| 14 | 归档旧运行 | 200 | 200（`MRP202609180004` → `archived`，写审计） |
| 15 | 已归档运行的建议转单 | 409 | 409 `MRP_RUN_NOT_ACTIVE` |
| 16 | 生产建议转单 | 409 | 409 `PRODUCTION_ORDER_NOT_IMPLEMENTED` |
| 17 | 采购建议转单 | 200 | 200 `status=converted`，`converted_document_no=PR202609180002` |
| 18 | 重复转单 | 409 | 409 `SUGGESTION_ALREADY_CONVERTED` |
| 19 | 查询转出的采购申请 | 200 | 200，`PR202609180002` 状态 **`draft`** |
| 20 | 取消建议缺原因 | 400 | 400 `VALIDATION_FAILED`（`reason` 必填） |
| 21 | 取消建议（带原因） | 200 | 200 `status=cancelled` |
| 22 | 已取消建议转单 | 409 | 409 `SUGGESTION_NOT_OPEN` |
| 23 | 退出登录 | 200 | 200 |
| 24 | 退出后访问 MRP 列表 | 403 | 403 `NOT_AUTHENTICATED` |

数据库侧核对（同一轮的直连读取，非推测）：

```text
run MRP202609180004 archived  archived_by=1
run MRP202609180005 completed
建议（MRP202609180005）：1 生产 open / 2 采购 converted → PR202609180002 / 3 采购 cancelled（原因已存）
                        / 4、5 采购 open
审计：create planning.MrpRun ×5、update planning.MrpRun（归档）、
      update planning.MrpSuggestion（转单 ×2、取消 ×1）
Outbox：planning.mrp.completed ×5、planning.mrp.suggestion_converted ×2（status=pending，未消费）
单据关联：MRP202609180005#2 → procurement.PurchaseRequisition PR202609180002（generated_from，数量 1.260000）
转出采购申请行：ACC-001 数量 1.260000，需求日期 2026-10-02，备注「MRP MRP202609180005 第 2 行建议」
```

### 16.5b 经 Vite 开发代理的浏览器路径验证（CSRF 修复回归）

CSRF 校验是**新增的服务端强制项**，因此额外从「浏览器实际会走的那条路」复验一次：
经 `http://127.0.0.1:5173`（Vite 开发代理）访问 `/api/v1/...`，并带上浏览器会发送的
`Origin` / `Referer`（`http://127.0.0.1:5173`）。**5 项检查结果**：

```text
[1] GET  /api/v1/identity/auth/csrf/  (经代理)          200，下发 yishang_csrftoken
[2] POST /api/v1/identity/auth/login/ (带 CSRF 令牌)     200，user=admin，menus=12
[3] GET  /api/v1/identity/auth/session/                 200
[4] GET  /api/v1/planning/mrp-runs/                     200，count=2
    runs = [('MRP202609180005', 'completed'), ('MRP202609180004', 'archived')]
[5] POST /api/v1/identity/auth/login/ (不带 CSRF 令牌)    403 CSRF_FAILED
```

结论：前端「先取 CSRF Cookie 再登录」的既有实现与新的服务端校验兼容，
登录、会话与 MRP 查询在代理链路上均正常；不带令牌的登录被拒绝。

### 16.6 本轮修复的 7 个真实缺陷

| # | 缺陷 | 影响 | 修复 |
| --- | --- | --- | --- |
| 1 | `apps/core/checks.py` **从未被导入** | `yishang.E001`（视图声明了未登记权限码）**永远不会触发**，权限契约形同失效 | `CoreConfig.ready()` 显式 `from apps.core import checks`；修复后立即抓出既有遗漏 `masterdata.identifier.update` 未登记并补齐 |
| 2 | MRP 低层码排序**预先过滤"当前已有需求"的物料** | BOM 展开出的子件需求**永远不被净算**，BOM 展开形同失效（净需求只剩顶层成品） | 改为按低层码全量升序遍历，无需求 `continue`；由 `test_low_level_code_net_calculated_once` 锁定 |
| 3 | `MrpRunSerializer` 声明 `demand_count`/`supply_count`/`suggestion_count` 但未加入 `Meta.fields` | `/api/v1/planning/mrp-runs/` 一旦被访问即 `AssertionError` | 三个字段加入 `Meta.fields` |
| 4 | `seed_demo` 打印转单**前的**建议实例 | `convert_suggestion` 内部 `select_for_update` 重新取行，导致日志里采购申请号为空 | 改用服务返回值 |
| 5 | **登录接口缺少 CSRF 校验** | 违反任务书 6.1「登录接口同样防护 CSRF」；`LoginView` 清空 `authentication_classes` 后 DRF `SessionAuthentication` 对匿名请求不调用 `enforce_csrf` | `@method_decorator(csrf_protect, name="dispatch")` + 2 条回归用例 |
| 6 | `EntityListPage.vue` 缺 `initialFilters` prop | 「按 `?run_id=` 打开建议页」初始过滤无法生效 | 新增可选 prop 并透传 `defaultFilters`（默认 `undefined`，向后兼容） |
| 7 | `views/system/ProgressView.vue` 的「阶段实施状态」停留在初始快照 | 阶段 2、3 被标为「未开始」，告警还称「采购、销售、仓储单据不会出现在左侧导航」，与已实现菜单和 `docs/progress.md` 相反 —— 管理员看到的是**与事实相反**的状态 | 按 `docs/progress.md` §一 更新阶段 2/3 行、已完成 / 未完成清单与提示文案（该页本来就声明为「文档镜像」，非业务报表数据） |

第 1、5 项属**安全 / 契约类**缺陷（已在修复后补充可复现的测试）；第 7 项属**文档 / 界面一致性**缺陷，由 `frontend/tests/responsive.spec.ts`、`frontend/tests/styles.spec.ts` 与 `views-compile.spec.ts` 在改动后复跑确认未破坏既有断言。

### 16.7 本轮仍未执行的测试（不得视为通过）

- **Docker Compose 未启动验证**（本机 Docker 守护进程不可达）。
- **Celery Worker / Beat 未运行**：MRP 为**同步计算**，不依赖 worker；但 Outbox 事件仍为 `pending`，
  未验证消费副作用。
- **MySQL 8.4 LTS 未验证**（本机为 8.0.17）、**`mysqlclient` 生产驱动未验证**（本地 `DB_DRIVER=pymysql`）。
- **并发 / 多连接压测未执行**：MRP 运算本身不修改库存，但"同一运行的建议并发转单"未做真实并发验证
  （当前靠 `select_for_update` + 建议状态唯一性 + 单据唯一约束保证）。
- **Playwright 端到端未执行**；**浏览器截图级样式校验未执行**（本轮只能确认组件编译与构建产物）。
- **性能压测未执行**（百万级流水 / 读数）。
- **备份与恢复演练未执行**。

## 十七、文档同步与使用说明增量复验记录（本轮）

> 本节只追加本轮**真实输出**，不改写前面各节的历史记录。

### 17.1 变更范围

本轮无业务代码变更，无新增迁移、无新增 API、无新增页面。变更文件：

| 类型 | 文件 |
| --- | --- |
| 新增文档 | `docs/user-guide.md`、`docs/user-guide.html`（生成物） |
| 新增脚本 | `scripts/build_user_guide.py`（Markdown → 单文件网页，纯标准库） |
| 新增前端资源 | `frontend/public/guide.html`（生成物）、`BasicLayout.vue` 增加「使用说明」入口 |
| 新增测试 | `backend/tests/test_docs_sync.py` |
| 修改文档 | `README.md`、`docs/acceptance.md`、`docs/inventory-rules.md`、`docs/requirements-matrix.md`、`docs/api-conventions.md`、`docs/deployment.md`、`docs/progress.md`、`docs/user-guide.md` |

### 17.2 后端检查（真实输出）

```
System check identified no issues (0 silenced).
No changes detected
All checks passed!
```

### 17.3 后端全量测试

| 项 | 命令 | 结果 |
| --- | --- | --- |
| 全量测试 | `pytest backend/tests -q --reuse-db` | `308 passed in 101.34s (0:01:41)` |

用例总数 301 → **308**（新增 `tests/test_docs_sync.py` 7 条；其余 301 条无删改）。

### 17.4 新增用例 `tests/test_docs_sync.py`（7 条）

| 用例 | 校验内容 |
| --- | --- |
| `test_user_guide_declares_all_sync_facts` | `docs/user-guide.md` 存在事实行且键齐全、取值 > 0 |
| `test_user_guide_sync_facts_match_code[permissions]` | 事实行 `permissions` == `len(PERMISSIONS)` |
| `...[menus]` | == `len(MENUS)` |
| `...[models]` | == 受管且非自动生成的模型数 |
| `...[migrations]` | == `backend/apps/*/migrations/0*.py` 文件数 |
| `...[builtin_roles]` | == `len(BUILTIN_ROLES)` |
| `test_published_guide_html_is_up_to_date` | 执行 `scripts/build_user_guide.py --check`，校验 `docs/user-guide.html` 与 `frontend/public/guide.html` 与 Markdown 源一致 |

### 17.5 反向验证（确认用例真的会拦住失同步）

把 `docs/user-guide.md` 事实行临时改为 `menus=99`，单跑该用例：

```
E       AssertionError: docs/user-guide.md 的事实行已过期：menus=99，代码实际为 56。
1 failed, 5 passed in 0.46s
```

还原后：`6 passed`。**说明该用例确实会因文档与代码不一致而失败**，不是永远通过的摆设。

### 17.6 本轮未执行的测试（不得视为通过）

| 项 | 原因 |
| --- | --- |
| 前端 `typecheck` / `vitest` / `build` | 本轮**未改动前端代码**，未重跑 |
| Docker Compose 启动 | 本机 Docker 不可用，**未执行** |
| Celery Worker / Beat | **未运行** |
| Playwright 端到端 | **未执行** |
| 备份 / 恢复演练、性能压测、MySQL 8.4 验证 | **未执行**（与 §16.7 口径一致） |
| 浏览器截图级 UI 校验、≤768px 布局 | **未执行** |

## 十一、结论

阶段 0、阶段 1 的**已实现部分**、阶段 2 已完成的四个增量
（第一步：客户与供应商主数据；核心：统一库存服务；第三步：采购模块；第四步：销售模块）、
**阶段 3 第一步：BOM 与工艺路线版本快照**（第十五节）、
**阶段 3 第二步：MRP**（时间分段净算 / 多层 BOM 展开 / 缺料建议 / 采购建议转单，第十六节），
以及**界面样式增量**（第十二节）、**视图样式统一增量**（第十三节）、**窄屏响应式增量**（第十四节）、
**文档同步与使用说明增量**（第十七节）、**枚举值中文化增量**（第十八节）与**超级管理员权限修复增量**（第十九节）
通过了本报告列出的全部检查：
后端 313 项、前端 135 项自动化测试通过，前后端构建通过，静态检查通过，迁移无漂移，
一键冒烟 7 步全过，并在运行中的开发服务器上完成 **29 项真实 HTTP 链路检查**。

「通过」仅指上述已执行项。未执行项见第五节、§7.5、§8.3、§9.3、§10.6、§12.3、§13.5、§14.4、§15.7 与 §16.7，
不得据本报告推断这些能力已经可用。

## 十八、枚举值中文化复验记录（本轮）

> 起因：用户反馈「仓库类型 / 部门类型 / 计量类型」等在界面上显示英文。
> 排查确认是**两层缺陷**：①接口未返回中文标签；②库里存在连 `get_FOO_display()` 都翻译不出的
> **非法枚举值**（历史演示数据写入错误）。两层都已修复，本节是**实际执行**的记录。

### 18.1 变更范围

- 后端：`apps/core/serializers.py::DisplayLabelsMixin`（新增）、`ReferenceIdSerializer` 继承它；
  `apps/identity/serializers.py` 7 个序列化器显式继承；`apps/factory/models.py` 扩展
  `Department.department_type` / `Workshop.workshop_type` 的 choices；
  `apps/core/management/commands/seed_demo.py` 修正枚举源头数据。
- 新增迁移：`apps/factory/migrations/0003_alter_department_department_type_and_more.py`
  （`RunPython` 修数据 + 2 个 `AlterField` 扩 choices，反向迁移为空操作）。
- 前端：`ProTable.vue::displayValue()`、`EntityListPage.vue::renderCell()` 优先使用后端 `_display`。

### 18.2 后端检查（真实输出）

| 检查 | 命令 | 实际输出 |
| --- | --- | --- |
| 系统自检 | `manage.py check` | `System check identified no issues (0 silenced).` |
| 迁移一致性 | `manage.py makemigrations --check --dry-run` | `No changes detected` |
| 迁移应用 | `manage.py migrate factory` | `Applying factory.0003_alter_department_department_type_and_more... OK` |
| 静态检查 | `ruff check --no-cache apps config tests ../scripts/build_user_guide.py` | `All checks passed!` |
| 全量测试 | `pytest tests -q --reuse-db -p no:logging` | `312 passed in 115.05s (0:01:55)` |

> `ruff` 默认缓存目录在沙箱内不可写，本轮以 `--no-cache` 执行（检查规则完全相同）。

### 18.3 数据与契约扫描（直连开发库，非测试框架）

| 扫描 | 脚本 | 修复前 | 修复后（本轮输出） |
| --- | --- | --- | --- |
| 非法枚举值 | `.tmp/enumbad.py` | **12 条**（性别 `男/女` 15、用工性质 15、线体类型 6、部门类型 4、车间类型 2） | `非法枚举值条目数: 0` |
| 序列化器中文标签覆盖 | `.tmp/verifymixin.py` | 多数字段无 `_display` | `带 choices 的序列化字段数: 59` / `缺少 _display 的: 0` |

接口实测片段（真实响应）：

```text
仓库:     {'code': 'WH-FG-01', 'warehouse_type': 'finished',   'warehouse_type_display': '成品仓'}
库区:     {'code': 'RCV',      'zone_type': 'receiving',       'zone_type_display': '收货区'}
储位:     {'code': 'A01-01-01', 'location_type': 'floor',      'location_type_display': '地面储位'}
部门:     {'code': 'GM',       'department_type': 'management', 'department_type_display': '职能部门'}
员工:     {'gender': 'male',   'gender_display': '男',          'employment_type_display': '正式'}
计量单位: {'code': 'M2',       'category': 'area',             'category_display': '面积'}
```

### 18.4 新增用例清单

| 用例文件 | 条数 | 覆盖内容 |
| --- | --- | --- |
| `backend/tests/test_enum_labels.py` | 4 | ①全量遍历所有 `ModelSerializer`，任一 choices 字段缺 `_display` 即失败；②仓库/部门/计量单位接口的 `_display` 必须是中文；③`/api/v1/meta/` 枚举 `label != value` 且部门类型含新增三项；④`seed_demo` 后全库无非法枚举值 |
| `frontend/tests/pro-table.spec.ts` | +2（共 6） | 后端 `_display` 优先展示；无标签时退回原值且不显示 `undefined` |

用例总数：后端 308 → **312**；前端 129 → **131**。

### 18.5 前端检查（真实输出）

| 检查 | 命令 | 实际输出 |
| --- | --- | --- |
| 组件测试 | `vitest run` 等价配置 | `Test Files 9 passed (9)` / `Tests 131 passed (131)` |
| 类型检查 | `vue-tsc --noEmit` 等价配置 | 退出码 0（无错误） |
| 生产构建 | `vite build` | `✓ built in 13.21s`，产物写入 `frontend/dist` |

> 运行环境说明：本轮沙箱**仅在命令工作目录为仓库根目录时允许写文件**，且不允许写入
> `node_modules`。因此前端三条命令改为在仓库根目录以等价配置执行（`cache: false`、
> `tsBuildInfoFile` 改指向可写目录），**检查内容与 `package.json` 脚本一致**，
> 未修改仓库内的 `vitest.config.ts` / `vite.config.ts` / `tsconfig*.json`。

### 18.6 本轮未执行的测试（不得视为通过）

| 项目 | 状态 |
| --- | --- |
| 浏览器截图级 UI 校验（中文标签是否真的显示在页面上） | **未执行**——本机浏览器自动化被安全策略拒绝。需人工打开「仓储管理 → 仓库与储位」「工厂与排班 → 部门/车间/线体/员工」「基础资料 → 计量单位」核对 |
| Playwright 端到端测试 | **未执行**（项目仍未编写 E2E 用例） |
| Docker Compose / Celery / 真实硬件 | **未执行**（同前几节结论） |

## 十九、超级管理员权限修复复验记录（本轮）

> 用户反馈：「超级管理员好像什么也新增不了。」本节是**实际执行**的复验记录。
> 结论：后端一直是对的，**缺陷在前端的权限判断**——它把后端下发的通配符 `["*"]`
> 当成普通权限编码去比较，于是超级管理员被判成「没有任何操作权限」，
> 所有「新增 / 编辑 / 删除 / 提交」按钮都被隐藏。

### 19.1 缺陷定位（真实数据）

```text
/auth/session/  →  admin    : permissions = ["*"]        ← 只有通配符
                    wh_admin : permissions = [24 条编码]  含 wms.warehouse.create
前端判断        →  permissions.includes('wms.warehouse.create')  →  false
结果            →  按钮用 v-if="canCreate" 渲染，全部不显示
```

附带缺口：`bootstrap_system` 创建管理员时只设置 `is_superuser/is_staff`，
**从未绑定**内置的 `super_admin` 角色 → 该角色 0 个用户、个人中心显示「角色：未分配」。

### 19.2 变更范围

| 文件 | 改动 |
| --- | --- |
| `frontend/src/stores/auth.ts` | 新增 `hasFullAccess`（`permissions.includes('*')`）；`hasPermission` / `hasAnyPermission` 在通配符存在时直接放行 |
| `backend/apps/core/management/commands/bootstrap_system.py` | 新增 `_ensure_admin_role()`；管理员**创建后**与**已存在**两条路径都确保绑定 `super_admin`（幂等，`--dry-run` 只打印） |
| `backend/tests/test_management_commands.py` | +1 条：管理员必须绑定 `super_admin`、该角色 173 权限、范围 `all`、重复执行不重复绑定 |
| `frontend/tests/auth-store.spec.ts` | 新增 4 条：通配符放行、普通角色按权限点、空权限/空编码、退出清空 |
| `docs/permission-matrix.md` | §五规则 1 明确「`*` 必须被客户端解释为全部权限」 |
| `docs/user-guide.md` | §4.1 增加「角色」行、§4.3 补充说明、§9.1 增加「看不到新增按钮」排错项（并重新生成网页版） |

### 19.3 真实 HTTP 验证（对运行中的开发服务器，非测试框架）

以 `admin` 通过 `POST /api/v1/identity/auth/login/` 登录后（真实会话 + CSRF）：

| 请求 | 结果 | 判定 |
| --- | --- | --- |
| `POST /api/v1/identity/auth/login/` | `200`，`roles=[超级管理员]`，`permissions=["*"]` | 角色绑定已生效 |
| `POST /api/v1/wms/warehouses/`（空表单） | `400 VALIDATION_FAILED` | **权限门通过**，仅字段校验失败 |
| `POST /api/v1/identity/roles/`（空表单） | `400 ROLE_CODE_REQUIRED` | 同上 |
| `POST /api/v1/factory/departments/`（空表单） | `400 VALIDATION_FAILED` | 同上 |

说明：故意发空表单是为了**不写入任何数据**又能区分「403 权限不足」与「400 表单校验」。
若权限判断仍有问题，这三条会返回 `403 PERMISSION_DENIED`。

### 19.4 后端与前端检查（真实输出）

| 检查 | 命令 | 实际输出 |
| --- | --- | --- |
| 系统自检 | `manage.py check` | `System check identified no issues (0 silenced).` |
| 全量测试 | `pytest tests -q --reuse-db -p no:logging` | `313 passed in 104.03s (0:01:44)` |
| 幂等重跑 | `manage.py bootstrap_system` | `管理员账号 admin 已绑定角色：超级管理员（173 个权限点）` |
| 静态检查 | `ruff check --no-cache apps config tests ../scripts/build_user_guide.py` | `All checks passed!` |
| 前端组件测试 | `vitest run`（等价配置） | `Test Files 10 passed (10)` / `Tests 135 passed (135)` |
| 前端类型检查 | `vue-tsc --noEmit`（等价配置） | 退出码 0 |
| 生产构建 | `vite build` | `✓ built in 11.14s` |

用例总数：后端 312 → **313**；前端 131 → **135**。

### 19.5 本轮未执行的测试（不得视为通过）

| 项目 | 状态 |
| --- | --- |
| 浏览器截图级 UI 核对（按钮是否真的出现） | **未执行**——本机浏览器自动化被安全策略拒绝。请人工用 `admin` 登录，确认「系统管理 → 用户管理 / 角色管理」出现「新增」按钮，个人中心显示「角色：超级管理员」 |
| 其他内置角色（`sales_admin` / `crm_admin` / `srm_admin` / `planning_admin` / `platform_admin`）的端到端演练 | **未执行**——这些角色当前没有绑定任何账号 |
| Playwright 端到端 / Docker / Celery / 真实硬件 | **未执行**（同前几节结论） |

## 二十、客户编码自动生成复验记录（本轮）

> 本轮需求：「新增客户的时候不需要手动输入客户编码，自动按规律生成。」
> 本节是**实际执行**的复验记录；未执行的项目见 20.5，不写成通过。

### 20.1 变更范围

| 文件 | 改动 |
| --- | --- |
| `backend/apps/crm/services.py` | 新增 `CUSTOMER_CODE_RULE = "CUS"` 与 `next_customer_code()`（引用编码规则取号，不硬编码格式） |
| `backend/apps/crm/serializers.py` | `code` 改为 `CharField(allow_blank=True, default="", max_length=32)`；`validate_code` 只在编辑时拒绝空值 |
| `backend/apps/crm/views.py` | `CustomerViewSet.perform_create()`：编码留空时补号；显式编码原样保留 |
| `backend/apps/core/management/commands/bootstrap_system.py` | `CODE_RULES` 登记 `("CUS", "客户编码", "CUS{YYYY}{SEQ:4}", ResetPeriod.YEARLY)` |
| `frontend/src/components/EntityListPage.vue` | `FormFieldDef` 新增 `onlyOnUpdate`；`visibleFormFields` 在新增模式过滤 |
| `frontend/src/views/crm/CustomerList.vue` | 编码字段设 `onlyOnUpdate: true`；页面说明补充自动生成口径 |
| `backend/tests/test_crm_api.py` | +6 条用例 |
| `frontend/tests/entity-list-form.spec.ts` | 新增文件，3 条用例 |
| `docs/user-guide.md`（+ 网页版）、`docs/progress.md`、`docs/requirements-matrix.md` | 同步更新 |

**没有新增数据库迁移**（规则是数据，不是结构）。

### 20.2 后端检查（真实输出）

| 检查 | 命令 | 实际输出 |
| --- | --- | --- |
| 系统自检 | `manage.py check` | `System check identified no issues (0 silenced).` |
| 迁移漂移 | `manage.py makemigrations --check --dry-run` | `No changes detected` |
| 静态检查 | `ruff check --no-cache apps config tests ../scripts/build_user_guide.py` | `All checks passed!` |
| 全量测试 | `pytest tests -q --reuse-db -p no:logging` | `319 passed in 117.64s (0:01:57)`（本轮前为 313） |

### 20.3 开发库（非测试框架）验证

先同步规则（幂等命令，未改动管理员口令）：

```text
$ python manage.py bootstrap_system
编码规则：新增 1，共计 15 条。
管理员账号 admin 已存在（版本 0），保留原密码，仅同步权限属性。
```

再直连开发库取号（外层事务回滚，不落库）：

```text
规则: CUS 客户编码 CUS{YYYY}{SEQ:4} yearly 启用= True
预演(不消耗流水): CUS20260001
事务内实际取号: CUS20260001
客户数 before/after: 3 3
流水是否随回滚退回: None      ← 取号流水随事务回滚，没有残留
```

最后用 `django.test.Client` 打**真实 HTTP**（真实登录 + 真实 POST，整个事务回滚）：

```text
登录: 200
POST /api/v1/crm/customers/ 不带 code        -> 201  CUS20260001  冒烟-自动编码客户
第二次 POST                                  -> 201  CUS20260002
PATCH {"code": ""}                           -> 400  VALIDATION_FAILED（"客户编码不能为空。"）
GET  /api/v1/audit-logs/?object_type=crm.Customer&object_id={id}
                                             -> 200  create / changes.code = CUS20260001
客户数 before/after: 3 3
```

结论：**不传编码可建档、编码逐号递增、编辑不可清空、自动编码进入审计**，且验证过程未污染开发库。

### 20.4 前端检查（真实输出）

| 检查 | 命令 | 实际输出 |
| --- | --- | --- |
| 组件测试 | `vitest run` | `Test Files 11 passed (11)` / `Tests 138 passed (138)`（本轮前 10 / 135） |
| 类型检查 | `vue-tsc --build --force` | 退出码 0 |
| 生产构建 | `vite build` | `✓ built in 12.66s` |

新用例 `tests/entity-list-form.spec.ts` 直接挂载 `EntityListPage`：
① 新增模式不出现 `onlyOnUpdate` 字段（客户编码）、出现 `onlyOnCreate` 字段；
② 编辑模式相反；③ 新增提交的载荷里**不含**被隐藏的编码字段（后端因此走自动取号分支）。

> 说明：断言只取**弹窗内表单**的文本。整页文本里本来就有表头列名（「客户编码」），
> 用整页判断会永远命中——第一版用例就是这样误报的，已修正。

### 20.5 本轮未执行的测试（不得视为通过）

| 项目 | 状态 |
| --- | --- |
| 浏览器截图级 UI 核对（新增表单里是否真的没有编码输入框） | **未执行**——本机浏览器自动化被安全策略拒绝。请人工打开「客户管理 → 客户档案 → 新增客户」确认 |
| Playwright 端到端 / Docker Compose / Celery / 真实硬件采集 | **未执行**（同前几节结论） |
| 供应商 / 物料 / 款式等其它主数据编码自动生成 | **未实施**——本轮只按用户要求改了客户编码；模式可复用（见 `docs/progress.md` §19.8） |

## 二十一、数值显示 2 位小数复验记录（本轮）

### 21.1 变更范围

- **纯前端显示层**：`frontend/src/utils/decimal.ts`、`components/ProTable.vue`、
  `components/EntityListPage.vue`、13 个业务视图列定义。
- **后端未改动**，因此**无迁移**、`makemigrations --check` 无漂移、后端用例数保持基线。
- 存储与接口精度不变：数量 6 位、金额 4 位、费率 10 位（`toApiString` 未改）。

### 21.2 前端检查（真实输出）

```text
$ node node_modules/vitest/vitest.mjs run
 ✓ tests/styles.spec.ts (31 tests) 11ms
 ✓ tests/decimal.spec.ts (23 tests) 10ms
 ✓ tests/responsive.spec.ts (15 tests) 50ms
 ✓ tests/http-error.spec.ts (2 tests) 4ms
 ✓ tests/auth-store.spec.ts (4 tests) 9ms
 ✓ tests/format.spec.ts (5 tests) 25ms
 ✓ tests/router.spec.ts (49 tests) 9ms
 ✓ tests/side-menu.spec.ts (10 tests) 107ms
 ✓ tests/pro-table.spec.ts (7 tests) 730ms
 ✓ tests/entity-list-form.spec.ts (5 tests) 911ms
 ✓ tests/views-compile.spec.ts (3 tests) 5211ms
 Test Files  11 passed (11)
      Tests  154 passed (154)
```

```text
$ vue-tsc --build --force
vue-tsc-exit=0

$ vite build
✓ built in 12.13s
```

### 21.3 数据侧扫描（直连开发库，非测试框架）

遍历全部 **58 个 `DecimalField` 列**，按**有效小数位**（`Decimal.normalize()` 后）统计：

```text
小数（DecimalField）列总数: 58
非空值里存在 >2 位有效小数的列: 2 处
  masterdata.UoMConversion.factor: 1 条 | 例: 0.9144000000
  planning.BomLine.quantity: 1 条 | 例: 0.004000
```

结论：统一显示 2 位**不会**把批量真实数据抹成 0；
唯一会被截断展示的 `0.004` 由「非零值不显示成 0」保护分支处理（显示为 `0.004`）。
`masterdata.UoMConversion.factor`（码 → 米 `0.9144`）当前**未在任何页面展示**，不构成显示问题。

> 注意：首轮扫描用 `Decimal.as_tuple().exponent` 直接判断，会把 `12.000000`
> 这类**带末尾 0** 的存储形式误判为「6 位小数」（得到 17 处假阳性）。
> 改用 `normalize()` 后的有效小数位才是正确口径，上表是修正后的结果。

### 21.4 本轮新增 / 修改用例清单

| 文件 | 用例 | 锁定行为 |
| --- | --- | --- |
| `frontend/tests/decimal.spec.ts` | 把 6 位小数的接口值显示成 2 位 | `12.000000` → `12.00`、`1234.567800` → `1,234.57` |
| 同上 | 四舍五入遵循 HALF_UP | `1.005` → `1.01`、`1.004` → `1.00` |
| 同上 | 非零值不会被显示成 0 | `0.004` 保留、`-0.0000001` → `0.00` |
| 同上 | 会进位的值仍按 2 位显示 | `0.055` → `0.06`、`0.995` → `1.00` |
| 同上 | 整数计数列（places = 0）不出现小数点 | `12` → `12`、`1234` → `1,234` |
| 同上 | 空值显示 `-` | `null` / `undefined` / `''` |
| 同上 | 显示口径不影响提交精度 | `toApiString(formatNumber('12.5'))` → `12.500000` |
| 同上 | 编辑表单回填（`toEditableText`） | `12.000000` → `12`；`0.055` **保持** `0.055`（不回写四舍五入） |
| 同上 | `formatNumericText` 只处理数值文本 | 手机号 / 税号 / `M-001` / `2026-09-20` 返回 `null` |
| 同上 | `numberFormatter` 非数值原样返回 | `E1001` 原样、`null` → `-` |
| `frontend/tests/pro-table.spec.ts` | ProTable 数值显示口径 | 表格里 `12.000000` 渲染为 `12.00`，`13800138000` 不被加上千分位 |
| `frontend/tests/entity-list-form.spec.ts` | 列表数值列按 2 位展示 | `12.000000` → `12.00` |
| 同上 | 编辑回填去尾 0 | 输入框值为 `12` 而不是 `12.000000` |

**测试写法提醒**（本轮踩到的坑，已写入用例注释）：操作列使用 `fixed="right"` 时
Element Plus 会把固定列 DOM 渲染**两份**，`findAll('button')` 取到的第一份属于虚拟表，
点击它拿到的是空行数据。取**最后一个**匹配按钮才是页面上的真实按钮。

### 21.5 后端检查（真实输出）

```text
$ python manage.py check
System check identified no issues (0 silenced).

$ python manage.py makemigrations --check --dry-run
No changes detected

$ ruff check --no-cache apps config tests ..\scripts\build_user_guide.py
All checks passed!

$ pytest tests -q --reuse-db -p no:logging
319 passed, 1 warning in 116.99s
```

### 21.6 本轮未执行的测试（不得视为通过）

| 项目 | 状态 |
| --- | --- |
| 浏览器截图级 UI 核对（列表 / 详情是否真的显示 2 位） | **未执行**——本机浏览器自动化被安全策略拒绝。请人工打开采购订单、BOM、销售订单列表确认 |
| Excel 导出文件里的数值格式 | **未验证**——导出格式本轮未改（仍为后端原始精度），见 `docs/progress.md` §21.7 |
| Playwright 端到端 / Docker Compose / Celery / 真实硬件采集 | **未执行**（同前几节结论） |

## 二十二、权限一级分组中文名复验记录（本轮）

### 22.1 变更范围

- **后端**：`permissions_registry.py` 新增 `MODULE_LABELS` / `module_label()`；
  `selectors.py` 的 `permission_groups()` 增加 `module_name`；`core/checks.py` 新增 `yishang.E002`。
- **前端**：新增 `utils/permissionLabels.ts`；`PermissionList.vue`、`RoleList.vue`、
  `types/models.ts` 相应调整。
- **无迁移**（未改任何模型字段）。

### 22.2 后端检查（真实输出）

```text
$ python manage.py check
System check identified no issues (0 silenced).

$ python manage.py makemigrations --check --dry-run
No changes detected

$ ruff check --no-cache apps config tests ..\scripts\build_user_guide.py
All checks passed!

$ pytest tests -q --reuse-db -p no:logging
322 passed, 1 warning in 120.49s
```

第 22.2 节的 `check` 输出同时验证了新检查项：若某个权限模块没有中文名，
`check` 会以 `yishang.E002` 报错（由 `test_module_label_check_reports_missing_module`
用 monkeypatch 证明该分支真的会触发，而不是只在注册表完整时才通过）。

### 22.3 前端检查（真实输出）

```text
$ node node_modules/vitest/vitest.mjs run
 ✓ tests/decimal.spec.ts (23 tests) 16ms
 ✓ tests/styles.spec.ts (31 tests) 14ms
 ✓ tests/responsive.spec.ts (15 tests) 51ms
 ✓ tests/http-error.spec.ts (2 tests) 3ms
 ✓ tests/format.spec.ts (5 tests) 24ms
 ✓ tests/auth-store.spec.ts (4 tests) 9ms
 ✓ tests/router.spec.ts (49 tests) 11ms
 ✓ tests/side-menu.spec.ts (10 tests) 123ms
 ✓ tests/permission-module-label.spec.ts (5 tests) 395ms
 ✓ tests/pro-table.spec.ts (7 tests) 744ms
 ✓ tests/entity-list-form.spec.ts (5 tests) 951ms
 ✓ tests/views-compile.spec.ts (3 tests) 5980ms
 Test Files  12 passed (12)
      Tests  159 passed (159)

$ vue-tsc --build --force
vue-tsc-exit=0

$ vite build
✓ built in 13.23s
```

### 22.4 开发库实际数据（直连 `config.settings.dev`，非测试夹具）

调用真实的 `permission_groups()`：

```text
开发库分组数: 13
  analytics      -> 工作台与看板 : 1 项
  core           -> 公共基础 : 12 项
  crm            -> 客户管理 : 7 项
  factory        -> 工厂与排班 : 27 项
  identity       -> 用户与权限 : 15 项
  integration    -> 内部协同 : 3 项
  masterdata     -> 基础资料 : 27 项
  planning       -> 计划管理 : 15 项
  procurement    -> 采购管理 : 15 项
  sales          -> 销售管理 : 16 项
  srm            -> 供应商管理 : 10 项
  wms            -> 仓储管理 : 18 项
  workflow       -> 审批中心 : 7 项
缺少中文名的模块: 无
```

合计 `1+12+7+27+15+3+27+15+15+16+10+18+7 = 173`，与权限注册表条目数一致。

### 22.5 新增 / 修改用例清单

| 文件 | 用例 | 锁定行为 |
| --- | --- | --- |
| `backend/tests/test_permissions.py` | `test_every_permission_module_has_chinese_label` | 注册表里每个模块都有中文名（漏登记直接失败） |
| 同上 | `test_module_label_check_reports_missing_module` | `yishang.E002` 在缺中文名时真的报错，并指出缺失模块名 |
| 同上 | `test_permission_groups_api_returns_module_chinese_name` | 接口返回 `module_name`；权限点总数 == 注册表条目数（防漏项） |
| `frontend/tests/permission-module-label.spec.ts` | 文案函数 3 条 | `core（公共基础）`；无中文名时不出现空括号；树节点带「· N 项」 |
| 同上 | 页面渲染 2 条 | 一级分组同时显示英文 + 中文；**按关键字过滤后中文名仍然保留**（回归用例） |

### 22.6 本轮未执行的测试（不得视为通过）

| 项目 | 状态 |
| --- | --- |
| 浏览器截图级 UI 核对（`core（公共基础）` 在真实页面上的排版与换行） | **未执行**——本机浏览器自动化被安全策略拒绝。请人工打开「系统管理 → 权限与菜单」与「系统管理 → 角色权限 → 分配操作权限」确认 |
| Playwright 端到端 / Docker Compose / Celery / 真实硬件采集 | **未执行**（同前几节结论） |

## 二十三、登录页改版复验记录（本轮）

### 23.1 变更范围

- **纯前端**：`frontend/src/views/LoginView.vue`（结构 + 样式重写）、
  `frontend/src/styles/index.css`（删除重复的登录页小节并重新编号）、
  新增 `frontend/tests/login-view.spec.ts`。
- 登录 / 会话 / CSRF 逻辑、后端接口、权限判定**均未改动**；**无迁移**。

### 23.2 前端检查（真实输出）

```text
$ node node_modules/vitest/vitest.mjs run
 ✓ tests/styles.spec.ts (31 tests) 13ms
 ✓ tests/decimal.spec.ts (23 tests) 14ms
 ✓ tests/responsive.spec.ts (15 tests) 44ms
 ✓ tests/http-error.spec.ts (2 tests) 5ms
 ✓ tests/auth-store.spec.ts (4 tests) 9ms
 ✓ tests/router.spec.ts (49 tests) 8ms
 ✓ tests/format.spec.ts (5 tests) 28ms
 ✓ tests/side-menu.spec.ts (10 tests) 114ms
 ✓ tests/login-view.spec.ts (11 tests) 326ms
 ✓ tests/permission-module-label.spec.ts (5 tests) 405ms
 ✓ tests/pro-table.spec.ts (7 tests) 784ms
 ✓ tests/entity-list-form.spec.ts (5 tests) 935ms
 ✓ tests/views-compile.spec.ts (3 tests) 4677ms
 Test Files  13 passed (13)
      Tests  170 passed (170)

$ vue-tsc --build --force
vue-tsc-exit=0

$ vite build
✓ built in 12.83s
```

### 23.3 后端检查（真实输出）

本轮无后端改动，下列检查用于确认没有意外影响：

```text
$ python manage.py check
System check identified no issues (0 silenced).

$ ruff check --no-cache apps config tests ..\scripts\build_user_guide.py
All checks passed!
```

后端测试本轮未重跑全量；上一次全量结果为 `322 passed`（见 §22.2），本轮改动不触及后端。
**不得据此认为后端在本轮被验证过。**

### 23.4 新增用例清单（`frontend/tests/login-view.spec.ts`，11 条）

| 分组 | 用例 | 锁定行为 |
| --- | --- | --- |
| 渲染 | 渲染品牌、表单与登录按钮 | 品牌名、`账号登录`、账号/密码、按钮、安全提示都在 |
| 渲染 | 输入框 autocomplete 正确 | `username` / `current-password`（密码管理器依赖） |
| 渲染 | 只陈述已具备的能力 | 不出现 MES / WMS / QMS 等未实施模块字样 |
| 提交 | 先取 CSRF 再登录 | 断言 `csrf` 调用顺序早于 `login`，且参数为 `('admin','secret')` |
| 提交 | 成功后跳转 redirect | `/login?redirect=/system/users` → 最终在 `/system/users` |
| 提交 | 账号两侧空格被去掉 | `'  admin  '` → 提交 `'admin'` |
| 样式 | 样式单一定义处 | 组件内定义 `.ys-login`；全局 `index.css` **不再包含** `.ys-login` |
| 样式 | 窄屏规则 | `max-width: 960px` 下隐藏左栏、显示紧凑品牌；宽屏下紧凑品牌为 `display:none` |
| 样式 | 登录按钮 | 宽度 100% + 品牌渐变 |
| 样式 | 动效保护 | `prefers-reduced-motion: no-preference` 内声明 `ys-login-rise` 动画 |
| 样式 | 离线可用 | 装饰层 `pointer-events: none`；样式块内无 `http(s)` 外链资源 |

### 23.5 本轮发现的环境限制（重要，不得当作通过）

排查「空表单不能提交」时发现：**Element Plus 的表单校验在 jsdom 下不生效**。

最小复现（一个 `el-form` + 一个带 `required` 规则的 `el-form-item` + 按钮调用
`formRef.validate()`）：

```text
MINIMAL valid = true
MINIMAL errors: 0
```

即：空值下 `validate()` 返回 `true` 且不渲染错误文案。原因是 `el-form-item`
在 jsdom 中没有注册进 `el-form` 的 `fields`，`validate()` 走
`fields.length === 0 → return true` 分支。

- 这是**环境限制**，不是登录页缺陷：真实浏览器不受影响，且本项目所有表单页
  （含 `EntityListPage`）使用同一套 Element Plus 写法。
- 因此本轮的登录页用例**刻意不断言校验行为**，避免写一条恒真断言冒充覆盖。
- 顺带说明一个容易误判的假象：如果用例里 `vi.mock('@/api/identity')`（整模块自动 mock），
  `csrf` 会变成直接返回 `undefined` 的桩，于是流程会一路走到 `login('','')`，
  看起来像「校验没拦住」。本轮改用 `vi.spyOn(identityApi, 'csrf')` 只替换单个方法，
  既保留真实模块形状，也让断言反映真实调用链。

### 23.6 本轮未执行的测试（不得视为通过）

| 项目 | 状态 |
| --- | --- |
| 浏览器截图级 UI 核对（双栏布局、渐变按钮、960px 断点折叠） | **未执行**——本机浏览器自动化被安全策略拒绝。请人工打开 `http://127.0.0.1:5173/login` 并把窗口拖到 960px 以下验证 |
| 表单必填校验与错误文案（「请输入账号 / 请输入密码」） | **未执行（jsdom 无法覆盖）**，原因见 23.5。需人工点击一次登录确认 |
| Playwright 端到端 / Docker Compose / Celery / 真实硬件采集 | **未执行**（同前几节结论） |


## 二十四、登录页左栏文案改为面向使用者的业务描述复验记录（本轮）

> 变更：`frontend/src/views/LoginView.vue`（文案 + `features` 图标）、
> `frontend/tests/login-view.spec.ts`（断言同步）。
> 后端、接口、会话 / CSRF 逻辑未改，**无迁移**。

### 24.1 变更范围

| 文件 | 改动 |
| --- | --- |
| `frontend/src/views/LoginView.vue` | 主标题、定位文案、4 条要点文案重写为使用者视角；图标 `Document` → `ShoppingCart`；注释更新 |
| `frontend/tests/login-view.spec.ts` | 重命名 1 条用例、改 2 条断言、新增开发术语黑名单断言、补主标题断言、补文件头说明 |

### 24.2 前端检查（真实输出）

```text
$ node node_modules/vitest/vitest.mjs run
 Test Files  13 passed (13)
      Tests  170 passed (170)
   Duration  8.47s

$ node_modules/.bin/vue-tsc.cmd --build --force
TSC_EXIT=0

$ node_modules/.bin/vite.cmd build
✓ built in 11.07s
```

### 24.3 本轮相关用例（`frontend/tests/login-view.spec.ts`，共 11 条，内容有调整）

| 用例 | 锁定行为 |
| --- | --- |
| 渲染品牌、表单与登录按钮 | 补断言主标题 `服饰企业一体化经营管理平台`；安全提示仍在 |
| **左侧要点用面向使用者的业务描述，不出现开发术语** | 4 条新要点文案存在；页面文本不含 `四层权限` / `后端` / `前端` / `接口` / `SKU` / `BOM`；仍不含 `MES` / `WMS` / `QMS` |
| 其余 9 条（autocomplete、CSRF 顺序、redirect、trim、样式 5 条） | 未改动，全部通过 |

### 24.4 本轮未执行的测试（不得视为通过）

| 项目 | 状态 |
| --- | --- |
| 浏览器截图级 UI 核对（新文案变长后左栏是否溢出、与右侧卡片是否挤压） | **未执行**——浏览器自动化被安全策略拒绝。请人工打开 `http://127.0.0.1:5173/login` 确认 |
| 表单必填校验与错误文案 | **未执行（jsdom 无法覆盖）**，原因见 23.5 |
| 后端测试 / Playwright 端到端 / Docker Compose / Celery / 真实硬件采集 | **未执行**（本轮无后端改动；端到端等与前几节结论相同） |


## 二十五、空白工作台修复与全站文案去开发化复验记录（本轮）

> 变更：`frontend/src/router/index.ts`、`frontend/src/layouts/BasicLayout.vue`、
> `frontend/src/views/**`（40 余处文案）、`frontend/src/types/models.ts`、
> `backend/apps/core/services.py`、`backend/apps/core/serializers.py`、
> `backend/apps/analytics/services.py`、`backend/tests/test_audit_display.py`（新增）、
> `frontend/tests/menu-home.spec.ts`（新增）。
> **无迁移**（新增字段都是只读计算字段）。

### 25.1 变更范围

| 区域 | 改动 |
| --- | --- |
| 路由 | `resolveHomePath` / `menuTrail` 新增；守卫把 `/` 重定向到菜单第一个页面 |
| 布局 | 面包屑按菜单层级渲染，不再写死「工作台」 |
| 后端展示层 | `object_type_label` / `display_value` / `describe_changes` / `AUDIT_CHANGE_LABELS`；审计与工作台接口返回中文展示字段 |
| 前端渲染 | 工作台时间线改句子；审计列表与详情改中文列与表格 |
| 全站文案 | 40 余处页面说明、空状态、表单提示、弹窗、通用错误提示改写 |

### 25.2 后端检查（真实输出）

```text
$ python manage.py check
System check identified no issues (0 silenced).

$ python manage.py makemigrations --check --dry-run
No changes detected

$ ruff check --no-cache apps config tests
All checks passed!

$ pytest tests -q --reuse-db -p no:logging
331 passed in 130.91s (0:02:10)
```

### 25.3 前端检查（真实输出）

```text
$ node node_modules/vitest/vitest.mjs run
 Test Files  14 passed (14)
      Tests  177 passed (177)
   Duration  8.95s

$ node_modules/.bin/vue-tsc.cmd --build --force
TSC_EXIT=0

$ node_modules/.bin/vite.cmd build
✓ built in 14.84s

$ pytest tests/test_docs_sync.py -q
7 passed
```

### 25.4 新增用例清单

`frontend/tests/menu-home.spec.ts`（7 条）：

| 分组 | 用例 | 锁定行为 |
| --- | --- | --- |
| 落地页解析 | 菜单里第一个页面就是落地页 | `resolveHomePath([工作台, 客户管理…]) === '/workspace'` |
| 落地页解析 | 目录不是页面 | 只有「客户管理」目录时落到 `/crm/customers` |
| 落地页解析 | 没有页面返回空串 | 由调用方保留原地址，不强行跳转 |
| 面包屑 | 二级页面返回目录 + 页面 | `['客户管理', '客户档案']` |
| 面包屑 | 一级页面只返回自身 | `['工作台']` |
| 面包屑 | 不在菜单里的地址返回空 | 避免显示错误层级 |
| 守卫 | 访问 `/` 自动跳到第一个页面 | 用**真实 router** `push('/')`，断言最终地址是 `/workspace`（即「不再停在空白布局」） |

`backend/tests/test_audit_display.py`（9 条）：

| 分组 | 用例 | 锁定行为 |
| --- | --- | --- |
| 对象类型 | 已登记模型翻译成中文名 | `identity.Role` → 角色 等 |
| 对象类型 | 解析不到时原样返回 | `unknown.Thing` / `noDot` / `''` 不编名字 |
| 对象类型 | 所有真实模型都能翻译成中文 | 遍历 `apps.*` 全部模型，白名单仅 `SKU` |
| 取值展示 | 空值布尔集合转可读文字 | `None`→空、`True`→是、`["a","b"]`→`a、b` |
| 变更摘要 | 模型字段用中文名、非字段键用登记表 | `company_id`→归属公司、`grants`→数据范围 |
| 变更摘要 | 未登记的键保留原键名 | 不猜含义 |
| 变更摘要 | 空摘要返回空列表 | `{}` / `None` |
| 接口 | `/api/v1/audit-logs/` 同时返回原始值与中文展示值 | 原始 `object_type` 保留（排查用），展示值给用户 |
| 接口 | 工作台 `recent_activity` 带中文操作与对象名 | `action_display` / `object_type_display` 必须来自接口 |

### 25.5 本轮未执行的测试（不得视为通过）

| 项目 | 状态 |
| --- | --- |
| 浏览器观感核对（空白工作台是否消失、面包屑层级、工作台时间线、审计中文列） | **未执行**——本机未安装 Playwright，浏览器自动化被安全策略拒绝。请人工登录 `http://127.0.0.1:5173/` 逐条确认 |
| 表单必填校验与错误文案 | **未执行（jsdom 无法覆盖）**，原因见 §23.5 |
| Playwright 端到端 / Docker Compose / Celery / 真实硬件采集 | **未执行**（与前几节结论相同） |
## 二十六、冒烟脚本拆除竞态修复 + 剩余文案去开发化复验记录（本轮）

### 26.1 变更范围

| 区域 | 改动 |
| --- | --- |
| 测试基建 | `frontend/tests/setup.ts`：`enableAutoUnmount(afterEach)` + `afterAll` 静默期 120ms + `requestAnimationFrame` 兜底桩 |
| 后端展示层 | `apps/integration/serializers.py` 新增只读 `aggregate_type_display`（复用 `object_type_label`） |
| 前端文案 | 采购申请 / 销售订单「审批单号」、角色「对象编号」、通知「关联业务编号」、内部协同「对象编号 / 事件编号 / 中文业务对象名」、数据范围弹窗提示、实施进度说明 |
| 前端类型 | `types/models.ts`：`OutboxEvent` 增加 `aggregate_type_display` |
| 文档 | `docs/user-guide.md` §6.9 补内部协同标识说明（并重建网页版）、`docs/progress.md` §26、本文 §26、`docs/requirements-matrix.md` 一之十六 |

### 26.2 后端检查（真实输出）

```text
$ python manage.py check
System check identified no issues (0 silenced).

$ python manage.py makemigrations --check --dry-run
No changes detected

$ ruff check --no-cache apps config tests
All checks passed!

$ pytest tests -q --reuse-db -p no:logging
332 passed in 126.38s (0:02:06)
```

### 26.3 前端与冒烟检查（真实输出）

```text
$ npm run test
 Test Files  15 passed (15)
      Tests  181 passed (181)

$ node_modules/.bin/vue-tsc.cmd --build --force
TSC_EXIT=0

$ node_modules/.bin/vite.cmd build
✓ built in 12.62s

$ powershell -ExecutionPolicy Bypass -File scripts/smoke_check.ps1
全部检查通过。
SMOKE_EXIT=0
```

### 26.4 新增用例清单

`frontend/tests/copy-tone.spec.ts`（4 条）：

| 用例 | 锁定行为 |
| --- | --- |
| 表格与详情不用内部标识当列标题 | 全部视图与组件源码里不出现 `label="对象 ID"`、`label="业务 ID"`、`label="事件 ID"`、`label="审批实例"` |
| 内部协同页展示中文业务对象名 | `OutboxList.vue` 用 `aggregate_type_display`，且不再有 `prop="aggregate_type"` |
| 审计页展示后端算好的中文字段 | `AuditLogList.vue` 含 `object_type_display` 与 `changes_display` |
| 工作台最近动态用中文句子 | `workspace/Index.vue` 含 `object_type_display` / `action_display`，不渲染原始变更 JSON |

`backend/tests/test_audit_display.py`（新增 1 条，共 10 条）：

| 用例 | 锁定行为 |
| --- | --- |
| 内部协同事件带中文业务对象名 | `/api/v1/integration/outbox-events/` 返回 `aggregate_type="sales.SalesOrder"`（原值）与 `aggregate_type_display="销售订单"`（展示值） |

### 26.5 本轮未执行的测试（不得视为通过）

| 项目 | 状态 |
| --- | --- |
| 浏览器观感核对（空白工作台、面包屑、工作台时间线、审计中文列、内部协同中文业务对象） | **未执行**——本机未安装 Playwright，浏览器自动化被安全策略拒绝。请人工登录 `http://127.0.0.1:5173/` 逐条确认 |
| Playwright 端到端 / Docker Compose / Celery / 真实硬件采集 | **未执行**（与前几节结论相同） |
| 表单必填校验与错误文案的浏览器级校验 | **未执行（jsdom 无法覆盖）**，原因见 §23.5 |
