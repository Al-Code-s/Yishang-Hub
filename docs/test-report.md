# 测试报告（docs/test-report.md）

> 本文件只记录**实际执行过**的命令与输出。未执行的项一律写「未执行」，不写成通过。
> 执行时间：2026-09-17　执行机器：Windows 10/11 开发机（本地 MySQL 8.0.17 + Redis 3.2）

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

## 十、结论

阶段 0、阶段 1 的**已实现部分**以及阶段 2 已完成的三个增量
（第一步：客户与供应商主数据；库存核心：统一库存服务；第三步：采购模块）通过了本报告列出的全部检查：
后端 182 项、前端 66 项自动化测试通过，前后端构建通过，静态检查通过，迁移无漂移。

「通过」仅指上述已执行项。未执行项见第五节、§7.5、§8.3 与 §9.3，
不得据本报告推断这些能力已经可用。