# 实施进度（docs/progress.md）

> 本文件记录**实际执行结果**。未执行的测试一律注明「未执行」，不写成通过。
> 最近更新：2026-09-17（阶段 0 / 阶段 1 交付；阶段 2 第一步：客户与供应商主数据；
> 阶段 2 核心：**统一库存服务（余额 / 流水 / 单据 / 质量放行）**；
> 阶段 2 第三步：**采购模块（采购申请 / 订单 / 收货 / 来料检验放行）**）

## 一、当前状态总览

| 阶段 | 范围 | 状态 |
| --- | --- | --- |
| 0 | 仓库检查、需求矩阵、架构与数据模型、环境与部署编排 | 已完成（Docker 编排未在本机启动验证） |
| 1 | 登录、权限、组织、主数据、仓库储位、基础审批、审计、后台界面 | 已完成（阶段验收待人工确认） |
| 2 | 客户、供应商、采购、销售、WMS 单据 | **进行中**：客户/供应商主数据、**统一库存服务（收发存/移库/质量放行/冲销/幂等）已完成**、**采购模块（申请 → 订单 → 收货 → 来料检验放行）已完成**；销售单据、询价/报价/评价、计划、调拨在途与盘点未开始 |
| 3 | BOM、工艺、MRP、MES、QMS | 未开始 |
| 4 | 设备、备件、保养、点检、维修 | 未开始 |
| 5 | 采集、EMS、能源报表与告警 | 未开始 |
| 6 | CRM 深化、EHS、厂内物流、终端安全 | 未开始 |
| 7 | 综合报表、基础成本、性能、安全、运维与恢复演练 | 未开始 |

当前规模（统计自 `permissions_registry` 与开发库）：**139 个权限点 / 47 项菜单 / 38 个业务页面 / 77 张表**。

**未实施的模块不在左侧导航中展示，也不存在可访问路由**（任务书 8.2）。
`apps/identity/permissions_registry.py` 只登记已实现页面；前端路由按后端菜单动态注册，
菜单组件缺失时会告警而不是渲染白屏。管理员可在「系统管理 → 实施进度」页查看同样的状态。

## 二、阶段 0 输出

1. **已实现功能**：仓库现状检查、技术选型核验、目录结构、配置分环境、健康检查接口、需求追踪矩阵骨架。
2. **数据迁移**：无（阶段 0 不产生业务表；仅自定义 User 的最初迁移在其后落地）。
3. **页面与 API**：`GET /healthz`（存活）、`GET /readyz`（数据库 + 缓存就绪）、`GET /api/v1/schema/`、`GET /api/v1/docs/`。
4. **权限**：无（阶段 0 未引入用户体系）。
5. **演示数据**：无。
6. **测试执行结果**：`manage.py check`、`makemigrations --check --dry-run` 实际执行，结果见 `docs/test-report.md`。
7. **启动验证步骤**：见 `docs/deployment.md` 的「本地开发」一节。
8. **未完成事项**：Docker Compose 编排文件已编写但本机 Docker 守护进程不可达，未启动验证。
9. **下一阶段依赖**：自定义 User 模型必须在首次迁移前确定（已完成）。

## 三、阶段 1 输出

### 3.1 已实现功能

**身份与权限**

- 自定义 User 模型（`AUTH_USER_MODEL = identity.User`），首个迁移即生效；用户名或手机号登录。
- Argon2 密码哈希（生产），密码校验器：长度 ≥ 10、常见口令、纯数字、与账号相似度。
- 登录限流与失败锁定（连续失败 5 次锁定 15 分钟，参数可配置），失败与成功均写 `LoginAttempt`。
- 会话登录（数据库 Session）、CSRF 校验（含登录接口）、退出登录使服务端会话失效、
  修改本人密码后其它设备会话失效、账号停用后会话立即失效。
- 角色、权限点、菜单、数据范围四层权限；`permissions_registry.py` 为唯一契约，
  启动检查（`apps.core.checks`）校验代码中声明的权限编码是否全部登记。
- 数据范围合并规则：超管不受限；多角色操作权限取并集；数据范围取最宽一档；
  始终先受公司边界限制；单一维度范围配置不完整时按最小范围（fail-closed）处理。

**组织与工厂**

- 公司、部门（树形，含层级合法性校验）、工厂、车间、线体、工位。
- 员工档案（与用户一对一可选关联，不是所有员工都有登录账号）。
- 班次（跨夜由后端推导，不允许起止时间相同或休息时长 ≥ 班次跨度）与班组（含成员快照）。

**服饰主数据**

- 颜色、尺码、计量单位、物料分类（面料/辅料/半成品/成品/包装物/备品备件/消耗品）。
- 物料档案，含面料属性（成分、幅宽、克重、色号、缸号、卷号管理、缩水率）。
- 款式（SPU）与 SKU：SKU 由「款式 + 颜色 + 尺码」唯一确定，并一对一关联成品物料，
  不出现两套库存编码；支持按颜色 × 尺码批量生成 SKU。

**仓储基础数据**

- 仓库、库区、储位主数据与「仓库 → 库区 → 储位」树查询。阶段 1 不产生库存余额与流水。

**基础审批**

- 审批模板：顺序多级节点、金额区间与部门范围条件路由、模板版本号、节点变更后版本自增。
- 审批实例：草稿 → 提交 → 通过 / 驳回 / 撤回，支持审批意见与轨迹；允许自审需显式开启并留痕。
- 提交时保存模板快照，历史单据不受模板后续修改影响。
- 审批通过与库存过账是两个独立动作：审批不会改动库存或单据业务状态。

**审计、通知与内部协同**

- 审计日志只写不改（无修改/删除接口），关键业务审计与业务数据同事务保存，
  记录操作人、组织、时间、request_id、对象、操作类型、字段变更摘要与原因。
- 通知按业务事件异步产生，按用户隔离，支持已读/全部已读与未读数。
- 发件箱（Outbox）：事件与业务数据同事务写入，后台轮询投递（至少一次语义），
  支持人工重放，重放不重复产生业务结果（消费者幂等）。
- 单据关系表（DocumentLink）用于跨模块流程追溯，当前阶段尚不产生记录。

**平台支撑**

- 编码规则与编号预演（预演不消耗流水号）。
- 数据字典与字典项。
- 附件上传/下载（扩展名白名单、大小上限、魔数校验、下载权限校验、上传与下载均留痕）。
- 统一错误结构、分页结构（`page_size` 上限 200，超限拒绝）、排序与过滤白名单。
- 请求级 `request_id` 贯穿日志与错误响应。
- OpenAPI 文档（drf-spectacular）：`/api/v1/schema/`、`/api/v1/docs/`。

### 3.2 数据迁移

| 迁移 | 内容 |
| --- | --- |
| `core/0001_initial`、`core/0002_initial` | 通用字段基类相关：审计、发件箱、字典、编码规则、附件、幂等记录、单据关系 |
| `identity/0001_initial` | 自定义 User、角色、权限点、菜单、数据范围授权、登录尝试、通知 |
| `factory/0001_initial`、`factory/0002_initial` | 公司、部门、工厂、车间、线体、工位、员工、班次、班组与成员 |
| `masterdata/0001_initial` | 物料分类、物料、面料属性、颜色、尺码、款式、SKU、计量单位与换算、标识 |
| `wms/0001_initial` | 仓库、库区、储位 |
| `workflow/0001_initial` | 审批模板、模板节点、审批实例、审批节点、审批日志 |
| `integration/0001_initial` | 单据关系 |

全部迁移文件已提交；`makemigrations --check --dry-run` 显示无未提交变更。

### 3.3 页面与 API

页面（阶段 1 时点：27 个业务页面 + 3 个基础页面，均为可操作页面，无占位空壳；
现为 **35 个业务页面** + 3 个基础页面，见 §6.3 / §7.3）：

- 基础：登录、403、404。
- 工作台：`/workspace`。
- 基础资料：物料档案、物料分类、款式、颜色尺码、SKU、计量单位。
- 工厂与排班：公司、部门、工厂、车间/线体/工位、员工、班次、班组。
- 仓储管理：仓库/库区/储位。
- 审批：我的待办、我的申请、审批模板。
- 内部协同：发件箱与单据关系。
- 系统管理：用户、角色与权限、权限与菜单、数据字典、编码规则、审计日志、我的通知、实施进度。

API 统一前缀 `/api/v1/`，清单与示例见 `docs/api-conventions.md`。

### 3.4 权限

- 权限编码形如 `module.resource.action`；阶段 1 时点共 100 个权限点、33 个菜单
  （阶段 2 库存核心后为 **124 个权限点、43 个菜单**，见 §6.4 / §7.4）。
- 内置角色：`super_admin`、`platform_admin`、`masterdata_admin`、`factory_admin`、
  `warehouse_admin`、`approver`、`viewer`；可按角色自由组合。
- 角色 × 权限分配矩阵见 `docs/permission-matrix.md`。

### 3.5 演示数据

- `bootstrap_system`：登记权限点与菜单、创建内置角色、初始化编码规则与数据字典、
  创建管理员账号（密码来自环境变量或随机构建并仅打印一次，不写死在代码里）。
- `seed_demo`：2 个工厂、车间/线体/工位、6 个款式与颜色尺码 SKU、物料与包装备件、
  原料/成品/备件仓与库区储位、客户/供应商基础数据、岗位账号、审批模板与审批单据。
  幂等可重复执行；在 `DJANGO_ENV=production` 下直接拒绝执行。

### 3.6 测试执行结果

真实输出见 `docs/test-report.md`：

- 后端 `pytest`：**90 项通过**（阶段 1 时点；当前 148 项，见 §7.6）。
- 前端 `vitest`：**55 项通过**（阶段 1 时点；当前 63 项，见 §7.6）。
- 前端 `vue-tsc` 类型检查：通过；`vite build`：通过。
- 后端 `ruff check`：通过。
- 真实 HTTP 端到端验证脚本：**19 项全部通过**（登录、CSRF、权限拒绝、唯一约束、审计、退出会话失效）。

### 3.7 启动验证步骤

见 `README.md` 与 `docs/deployment.md`。已实际执行的启动验证：

1. `manage.py check`、`makemigrations --check --dry-run`、`ruff check`、`pytest` 全部执行。
2. `manage.py runserver 127.0.0.1:8010`（本机 8000 端口被其它进程占用）实际启动，
   用真实 HTTP 会话完成 19 项验证。
3. `vite` 开发服务器实际启动（端口 5199），
   `/`、`/src/main.ts` 与经代理的 `/api/v1/identity/auth/csrf/` 均返回 200。

### 3.8 未完成事项

- **阶段 1 验收结论**：已出具（见 `docs/acceptance.md`）——阶段 0 通过（1 项部分完成：Docker 未启动验证），阶段 1 通过（本地开发环境）。
- **Docker**：`compose.yaml` 与 `deploy/` 已编写，但本机 Docker 守护进程不可达，未启动验证。
- **Celery worker / beat**：配置与任务代码已就绪，未实际运行验证。
- **Playwright 端到端测试**：未执行（未安装浏览器依赖）。
- **Excel 导入导出**：阶段 1 未提供业务导入导出；仅审计页提供当前页 CSV 导出。
- **菜单级细粒度隐藏**：采用后端菜单表控制，未实现按角色的字段级权限。
- 阶段 2 及以后全部功能未开始。

### 3.9 下一阶段依赖

- 库存服务（统一库存入口、余额维度、冻结/占用口径、幂等过账）必须先在阶段 2 落地，
  采购收货与销售发货都不得直接改库存余额。
- 质检放行与库存质量状态的最小可用实现应随阶段 2 一并交付，避免「收货即可销售」的临时改动。
- 备件主数据与库存能力由共享模块提供，阶段 4 不再重复建设。

## 四、已知风险与偏差

| 项 | 说明 |
| --- | --- |
| 本机 MySQL | 实际为 MySQL 8.0.17，任务书要求 8.4 LTS；SQL 模式、字符集与排序规则已按目标配置，但版本差异未在 8.4 上验证 |
| 本机 Redis | 实际为 Redis 3.2，任务书要求较新版本；生产编排使用官方 7.x 镜像（未启动验证） |
| 数据库驱动 | Windows 开发机无 C 编译工具链，开发使用 PyMySQL；生产镜像目标为 mysqlclient，未验证 |
| Docker | 未启动验证，编排文件属「已编写未验证」 |
| 依赖锁定 | `backend/uv.lock`、`package-lock.json` 已提交；锁文件在沙箱内需在临时目录生成后回拷 |
| 演示口令 | 仅存于本机 `.tmp/`（已被 `.gitignore` 忽略），未提交仓库 |
| 遗留文件 | `frontend/.probe.mjs`（早期探测脚本）已在本轮删除；另有 `backend/.venvX` 残留虚拟环境目录，已在 `.gitignore` 增加 `.venv*/`、`venv*/` 规则确保不会被提交 |
| 后台进程 | 本轮曾启动开发服务器（8010 / 5199），已确认端口释放 |
## 五、补充交付：部署编排与文档基线（本轮增量）

在阶段 0/1 主体功能之后，本轮补齐了**部署编排文件**与**完整文档基线**，
使"已完成"与"未完成"都有明确书面依据。

### 5.1 新增文件

| 文件 | 内容 | 验证状态 |
| --- | --- | --- |
| `compose.yaml` | nginx / backend / worker / beat / migrate / mysql / redis / object-storage 八个服务；健康检查、依赖顺序、命名卷、内部网络 | YAML 结构已解析校验（8 服务、2 网络、5 卷齐备）；**未实际启动** |
| `deploy/docker/Dockerfile.backend` | 多阶段构建；`mysqlclient` 编译依赖；非 root（uid 10001） | **未构建验证** |
| `deploy/docker/Dockerfile.frontend` | Node 构建 + nginx 非特权镜像（8080） | **未构建验证** |
| `deploy/docker/entrypoint.sh` | 等待数据库就绪后启动；**不自动 migrate** | 逻辑已完成，**未在容器内运行** |
| `deploy/nginx/nginx.conf` | SPA 回退、`/api` 反代、安全响应头、CSP、`/media` 走鉴权接口 | 语法未用 `nginx -t` 校验 |
| `deploy/mysql/my.cnf` | utf8mb4 + `utf8mb4_0900_ai_ci`、UTC、严格模式、binlog | **未加载验证** |
| `scripts/backup_mysql.sh`、`scripts/restore_mysql.sh` | 备份与恢复流程（含二次确认、加密、保留周期） | **未执行** |
| `scripts/dev_backend.ps1`、`dev_frontend.ps1`、`smoke_check.ps1` | 本地开发与一键冒烟 | 命令源自本轮实际执行过的同名命令 |

> `scripts/smoke_check.ps1` 已**实际执行验证**：依次通过 `manage.py check`、
> `makemigrations --check`、`ruff`、`pytest`（90 passed）、`vue-tsc`、`vitest`（55 passed）、
> `vite build`，最终输出「全部检查通过。」（退出码 0）。
>
> 注意：三个 `.ps1` 脚本必须保存为**带 BOM 的 UTF-8**，否则 Windows PowerShell 5.1
> 会按 ANSI 解析中文导致语法错误——本仓库已因此问题修复过一次。

### 5.2 新增文档（本轮补齐 13 份）

`architecture.md`、`data-model.md`、`business-flows.md`、`permission-matrix.md`、
`api-conventions.md`、`inventory-rules.md`、`energy-calculation.md`、`assumptions.md`、
`deployment.md`、`backup-restore.md`、`hardware-integration.md`、`acceptance.md`、`requirements.md`，
以及根目录 `PROJECT_SPEC.md`、`AGENTS.md`、重写的 `README.md` 与 `backend/README.md`。

### 5.3 需求追踪矩阵完成

`docs/requirements-matrix.md` 已覆盖任务书**全部章节**（1–19）：

| 章节 | 覆盖内容 |
| --- | --- |
| 一 | 阶段 0/1 逐条需求（REQ-20-*） |
| 二 | 技术方案（REQ-3.1-*） |
| 三 | 架构与代码组织（REQ-3.3-* / 3.4-* / 4.*） |
| 四 | 数据设计（REQ-5.*） |
| 五 | 认证、权限与审计（REQ-6.*） |
| 六 | 接口、异步与文件（REQ-7.*） |
| 七 | 界面与导航（REQ-8.*） |
| 八 | 主数据与服饰模型（REQ-9.1-* ～ 9.5-*） |
| 九 | 业务模块 **10.1–10.16 逐子项**（REQ-10.x-*） |
| 十 | 硬件采集（REQ-11.*） |
| 十一 | 五条业务闭环（REQ-12.*） |
| 十二 | 报表与数据口径（REQ-13-*） |
| 十三 | 测试与质量（REQ-14.*，含 22 条必测案例逐条对照） |
| 十四 | 演示数据与初始化（REQ-15-*） |
| 十五 | 部署、备份与运维（REQ-16.*） |
| 十六 | 分阶段实施计划 |
| 十七 | 追踪完整性与状态定义 |

**无静默遗漏**：每条任务书条目均给出「实现位置」「合并到共享功能」或「实施边界 / 计划阶段」。

### 5.4 本轮修正的问题

| 问题 | 处理 |
| --- | --- |
| `docs/requirements-matrix.md` 中"三、架构与代码组织"标题被并入上一行表格，导致该章节标题缺失 | 拆分为独立的表格行与标题行 |
| `.env.example` 缺少代码实际读取的变量（`DJANGO_USE_X_FORWARDED_FOR`、`YISHANG_ADMIN_*`、`YISHANG_DEMO_PASSWORD`、附件限制、CSP、`YISHANG_API_PREFIX`、幂等 TTL 等） | 按 `config/settings/*.py` 实际读取项重写，并修正 `OBJECT_STORAGE_ENDPOINT_URL` → `OBJECT_STORAGE_ENDPOINT` 的变量名不一致 |
| 文档中引用了不存在的测试文件 `test_core_api.py`、`test_analytics` | 改为真实存在的 `test_core_services.py` 与具体用例名 |
| `backend/README.md` 内容为无意义的占位文本（`deltest`） | 重写为真实的后端说明（`pyproject.toml` 的 `readme` 指向该文件） |
| `compose.yaml` 中 nginx 使用 root 镜像监听 80 | 改为 nginx 非特权镜像，监听 8080，符合"非 root 容器运行"要求 |

### 5.5 本轮实际执行的检查（真实输出）

```text
backend:  manage.py check                      -> System check identified no issues (0 silenced)
backend:  makemigrations --check --dry-run     -> No changes detected
backend:  ruff check apps config tests         -> All checks passed!
backend:  pytest tests -q --reuse-db           -> 90 passed
frontend: npm run typecheck                    -> 退出码 0
frontend: npm run test                         -> 6 files / 55 tests passed
frontend: npm run build                        -> 构建成功
数据库:   SELECT VERSION()                     -> 8.0.17, utf8mb4 / utf8mb4_0900_ai_ci, 严格模式
           SHOW TABLES                         -> 62 张表
Redis:    PING                                 -> True (3.2.100)
compose:  YAML 解析                            -> 8 服务 / 2 网络 / 5 卷
```

### 5.6 本轮未完成事项

- **Docker Compose 未启动验证**（本机 Docker 守护进程不可达）——八个服务、镜像构建、
  健康检查、卷挂载、Nginx 配置均属"已编写未验证"。
- **Celery worker / beat 未实际运行**；Outbox 的分发仅通过测试用例验证逻辑。
- **Playwright 端到端测试未执行**。
- **备份/恢复脚本未执行演练**。
- 阶段 2 及以后功能未开始。

## 六、阶段 2 第一步：客户与供应商主数据（本轮增量）

任务书 10.2（CRM）与 10.4（SRM）中属于**主数据**的部分在本轮落地；
寻源、报价、供应商评分、准入审批流程、投诉与服务工单**明确未实现**，
不在界面上伪造任何评分或审批结果。

### 6.1 已实现功能

- **客户档案**（`apps/crm`）：编码/名称/简称、客户分类与等级、合作状态、信用额度、
  结算方式、纳税人识别号、地址、主要联系人、关联业务员、标签字段、启停。
- **客户联系人**：同一客户下姓名唯一；**同一客户只能有一个主联系人**，
  切换主联系人时自动取消原标记（服务层在写事务内完成）。
- **供应商档案**（`apps/srm`）：编码/名称/简称、供货类别、供应商等级、准入状态、
  结算方式、纳税人识别号、地址、主要联系人、关联采购员、启停。
- **供应商联系人**：与客户联系人同构（姓名唯一 + 唯一主联系人）。
- **供应商资质**：资质类型、证书编号、发证机构、发证/到期日期；
  `到期日期 >= 发证日期` 由数据库检查约束强制；
  后端计算并返回 `days_to_expiry` / `is_expired`，**未登记到期日时返回 `null`**，
  前端显示「未登记到期日」而不是「未过期」。
- **资质证书编号规范化去重**：填写编号时按「供应商 + 类型 + 编号（忽略大小写）」判重；
  未填写编号时 `dedup_key` 为 `NULL`，同类型可并存多条（详见 `docs/data-model.md` §三 srm、§六）。
- **数据范围**：客户/供应商按公司过滤；联系人与资质分别通过
  `customer__company_id`、`supplier__company_id` **继承父级范围**，
  避免「看不到客户却看得到其联系人」的越权读取。
- **审计**：新增/修改/启停写入 `AuditLog`，与业务操作同事务。

### 6.2 数据迁移

| 应用 | 迁移 | 状态 |
| --- | --- | --- |
| `crm` | `0001_initial`（`crm_customer`、`crm_customercontact`） | 已应用到开发库 |
| `srm` | `0001_initial`（`srm_supplier`、`srm_suppliercontact`、`srm_supplierqualification`） | 已应用到开发库 |

`makemigrations --check --dry-run` → `No changes detected`；开发库表数由 62 张增至 **67 张**。

### 6.3 页面与 API

| 页面（前端） | 组件 | 接口前缀 |
| --- | --- | --- |
| 客户管理 → 客户档案 | `views/crm/CustomerList.vue` | `/api/v1/crm/customers/` |
| 客户管理 → 客户联系人 | `views/crm/CustomerContactList.vue` | `/api/v1/crm/customer-contacts/` |
| 供应商管理 → 供应商档案 | `views/srm/SupplierList.vue` | `/api/v1/srm/suppliers/` |
| 供应商管理 → 供应商联系人 | `views/srm/SupplierContactList.vue` | `/api/v1/srm/supplier-contacts/` |
| 供应商管理 → 供应商资质 | `views/srm/SupplierQualificationList.vue` | `/api/v1/srm/supplier-qualifications/` |

每个资源提供 `list / retrieve / create / partial_update / set-active`（**不提供 DELETE**）。

`GET /api/v1/meta/` 新增 7 个枚举键：`customer_categories`、`customer_levels`、
`customer_statuses`、`supplier_categories`、`supplier_grades`、`admission_statuses`、
`qualification_types`。前端不硬编码中文标签。

### 6.4 权限

新增权限点 **17 条**（`crm` 7 条、`srm` 10 条），注册表总数由 100 条增至 **117 条**；
菜单由 33 项增至 **40 项**（新增 `crm`、`crm.customer`、`crm.customer-contact`、
`srm`、`srm.supplier`、`srm.supplier-contact`、`srm.supplier-qualification`）。

| 权限编码 | 说明 |
| --- | --- |
| `crm.customer.view / create / update / deactivate` | 客户档案查看、新增、修改、启停 |
| `crm.customer_contact.view / create / update` | 客户联系人（启停复用 `update`） |
| `srm.supplier.view / create / update / deactivate` | 供应商档案 |
| `srm.supplier_contact.view / create / update` | 供应商联系人 |
| `srm.supplier_qualification.view / create / update` | 供应商资质 |

菜单排序按任务书 §8.2 一级菜单顺序重排：客户管理目录 40、供应商管理目录 60、仓储管理目录 80（其子页面 81）。

### 6.5 演示数据

`seed_demo` 新增客户与供应商主数据（幂等、生产环境拒绝执行）：

```text
crm.Customer: 3            crm.CustomerContact: 4
srm.Supplier: 3            srm.SupplierContact: 3        srm.SupplierQualification: 4
```

其中包含：已过期资质（演示「到期提醒」与红色逾期标签）、未登记到期日的资质
（`days_to_expiry = null`）、以及未填写证书编号的资质（`dedup_key IS NULL`）。
重复执行 `seed_demo` 第二次输出 `合计新建 0 条`，幂等性已实测。

### 6.6 测试执行结果（真实输出）

```text
backend:  ruff check apps config tests         -> All checks passed!
backend:  manage.py check                      -> System check identified no issues (0 silenced)
backend:  makemigrations --check --dry-run     -> No changes detected
backend:  pytest tests -q --reuse-db           -> 112 passed（新增 test_crm_api.py 11 条、test_srm_api.py 11 条）
frontend: npm run typecheck                    -> 退出码 0
frontend: npm run test                         -> 6 files / 60 tests passed（菜单契约用例随 40 项菜单增至 36 条）
frontend: npm run build                        -> ✓ built in 9.84s（含 5 个新页面 chunk）
smoke:    scripts\smoke_check.ps1             -> 全部检查通过，退出码 0
```

真实 HTTP 验证（非测试框架，直连开发库）：

```text
/api/v1/crm/customers/             200 count=3
/api/v1/crm/customer-contacts/     200 count=4
/api/v1/srm/suppliers/             200 count=3
/api/v1/srm/supplier-contacts/     200 count=3
/api/v1/srm/supplier-qualifications/ 200 count=4
  quality_system  ISO9001-DEMO-001  expiry=2026-02-28  days=-201  expired=True
  test_report     ''                expiry=None        days=None  expired=None
dedup_key IS NULL rows: 1
meta 新增枚举键: admission_statuses, customer_categories, customer_levels,
                customer_statuses, qualification_types, supplier_categories, supplier_grades
```

### 6.7 启动验证步骤

```powershell
# 1) 依赖与数据库
cd backend; .\.venv\Scripts\python.exe manage.py migrate

# 2) 演示数据（幂等；生产环境会被拒绝）
.\.venv\Scripts\python.exe manage.py seed_demo --skip-users

# 3) 启动后端
.\..\scripts\dev_backend.ps1     # 或 uv run gunicorn，开发环境用 runserver 仅限本机

# 4) 启动前端
cd ..\frontend; npm run dev        # http://localhost:5173
```

验证路径：登录 → 左侧导航「客户管理 → 客户档案」新增一条客户 →
「客户联系人」新增两条并把第二条设为主联系人 → 回到第一条确认「主联系人」标记已取消 →
「供应商管理 → 供应商资质」新增一条到期日早于发证日的记录，应被拒绝并提示字段错误。

### 6.8 未完成事项（阶段 2 剩余）

- **寻源、候选供应商、准入审批流程、供应商报价、供应商评分评价**：未实现
  （评分权重、缺失数据不计零分等规则未落地，界面上不展示任何评分数字）。
- **供应商资质到期提醒（Celery 定时任务）**：未实现；本轮只提供到期数据与剩余天数。
- **采购、销售、MRP、WMS 单据与库存余额/流水**：未开始（阶段 2 主体）。
- **客户服务工单、投诉、满意度、CRM 统计**：属阶段 6，未开始。
- **标签（`tags`）字段未提供界面编辑**：模型与接口已支持，前端通用表单暂不支持数组字段，
  已在页面上不展示，避免出现「看着能填、实际不生效」的假输入。
- 阶段 1 遗留：Docker Compose / Celery / Playwright / 备份恢复仍未实际运行（原因见 §四）。

### 6.9 下一阶段依赖

- 采购与销售单据将复用本轮客户/供应商主数据；报价与评分需先定义权重配置模型。
- 库存余额与流水落地时，必须沿用 `dedup_key` 同思路的 `dimension_key` 方案（`docs/data-model.md` §六），
  并补齐并发测试（必测案例 6、7）。

## 七、阶段 2 核心：统一库存服务（本轮增量）

任务书 10.8 中**库存核心**部分在本轮落地：库存余额、库存流水、库存单据（收货/出库/移库/调整/质量）
与质量放行。**本节写作时采购、销售、生产等业务单据尚未实现**，因此本轮库存单据由通用库存服务与演示数据驱动，
不是由采购单/销售单驱动。（后续增量：**采购单已接入**，见 §八；销售单仍未实现。）

### 7.1 已实现功能

- **库存余额**（`wms.InventoryBalance`）：按
  `公司 + 物料 + 仓库 + 储位 + 批次 + 卷号 + 质量状态` 维度唯一。
  四类数量口径：`on_hand`（实存）/ `frozen`（冻结）/ `reserved`（占用）/ `available`（可用，计算属性）。
  检查约束保证三者非负且 `frozen + reserved <= on_hand`。
- **规范化维度键**：`dimension_key CHAR(32) UNIQUE NOT NULL`，
  `sha256(company|material|warehouse|location|normalize(batch)|normalize(roll)|normalize(quality))[:32]`；
  `None` 与 `""` 统一编码为 `"-"`，绕过 MySQL「NULL 不相等」导致的联合唯一索引失效（`docs/data-model.md` §六）。
- **库存流水**（`wms.InventoryTransaction`）：**只追加**。不是 `BaseModel`；
  对既有行 `save()` 抛 `ImmutableLedgerError`，`delete()` 永远抛异常。无写入/修改/删除 HTTP 路由。
- **库存单据**（`wms.InventoryDocument` / `InventoryDocumentLine`）：
  类型 `receipt / issue / move / adjustment / quality`，
  状态机 `draft → posted → reversed`（`cancelled` 仅限草稿）。
  **编号在创建时分配**（`(company, document_no)` 唯一），已过账不可编辑（服务层拒绝）。
- **统一库存服务**（`apps/wms/services/stock.py`）：
  `create_document / update_draft_document / post_document / reverse_document / release_quality / allocate_document_no`。
- **加锁顺序**：按 `dimension_key` **升序**上锁，降低死锁风险；对**尚不存在的余额行**使用
  「保存点内 INSERT + 捕获 `IntegrityError` 后重新 SELECT FOR UPDATE」，不假设 `select_for_update()` 提供锁。
- **默认禁止负库存**：服务层 `_assert_available` **始终**拒绝导致负数的出库；数据库检查约束是第二道硬墙。
- **待检/不合格不可动用**：`ISSUE` 类单据要求 `quality_status = qualified`
  （`_assert_quality_allowed`）。
- **质量放行**：`release_quality` 生成并过账一张 `QUALITY` 单据，把库存从待检/不合格转为合格。
- **幂等**：`Idempotency-Key` 与业务结果**同事务提交**；同键同内容返回原单据，
  同键被其他单据占用则冲突。
- **死锁/锁超时重试**：`MAX_LOCK_RETRIES = 3`，**仅** MySQL 1213 / 1205 重试，
  重试重跑完整事务；非可重试错误直接上抛（不掩盖真实故障）。
- **冲销**：必须填写原因；下游已消耗时**拒绝**并引导退货/更正流程，不做强行反冲。
- **审计 + Outbox**：`AuditAction.POST` / `AuditAction.REVERSE` 与业务**同事务**写入；
  Outbox 事件同样同事务写入。
- **只读查询接口**：库存余额（支持 `has_stock` 过滤）与库存流水为只读 ViewSet，无写路由。

### 7.2 数据迁移

| 应用 | 迁移 | 状态 |
| --- | --- | --- |
| `wms` | `0002_inventorydocument_inventorydocumentline_and_more`（4 张库存核心表） | 已应用到开发库 |
| `core` | `0003_alter_auditlog_action`（新增 `POST` / `REVERSE` 审计动作枚举值） | 已应用到开发库 |

`makemigrations --check --dry-run` → `No changes detected`；开发库表数由 67 张增至 **71 张**。

### 7.3 页面与 API

| 页面（前端） | 组件 | 接口前缀 |
| --- | --- | --- |
| 仓储管理 → 库存余额 | `views/wms/InventoryBalanceList.vue` | `GET /api/v1/wms/inventory-balances/` |
| 仓储管理 → 库存流水 | `views/wms/InventoryTransactionList.vue` | `GET /api/v1/wms/inventory-transactions/` |
| 仓储管理 → 库存单据 | `views/wms/InventoryDocumentList.vue` | `/api/v1/wms/inventory-documents/` |

单据动作（`POST`）：

```text
/api/v1/wms/inventory-documents/{id}/post/             过账（幂等，带 Idempotency-Key）
/api/v1/wms/inventory-documents/{id}/reverse/          冲销（必填 reason）
/api/v1/wms/inventory-documents/{id}/release-quality/  质量放行
```

余额与流水为**只读**资源：`list / retrieve` 之外无路由（写操作返回 405，已测）。

`GET /api/v1/meta/` 新增 5 个枚举键：`quality_statuses`、`inventory_document_types`、
`inventory_document_statuses`、`inventory_transaction_types`、`inventory_directions`。
前端不硬编码中文标签。

### 7.4 权限

新增权限点 **7 条**（注册表由 117 条增至 **124 条**）；菜单由 40 项增至 **43 项**
（新增 `wms.inventory-balance`、`wms.inventory-transaction`、`wms.inventory-document`）。

| 权限编码 | 说明 |
| --- | --- |
| `wms.inventory.view` | 查看库存余额与流水 |
| `wms.document.view` | 查看库存单据 |
| `wms.document.create` | 新建库存单据（草稿） |
| `wms.document.update` | 修改草稿单据 |
| `wms.document.post` | 过账 |
| `wms.document.reverse` | 冲销 |
| `wms.quality.release` | 质量放行 |

数据范围按 `warehouse__factory_id`（单据）与 `warehouse_id`（余额/流水）过滤；
服务层另有 `_resolve_warehouse` → `assert_in_scope` 二次校验，**不依赖前端传入的仓库 ID**。
现有内置角色 `warehouse_admin`（`include=("wms.",)` + `WAREHOUSE` 范围）自动获得全部新权限。

### 7.5 演示数据

`seed_demo` 新增 `_inventory()` 步骤，**只调用库存服务**（`create_document` → `post_document` →
`release_quality`），**绝不直接写余额或流水表**：

```text
演示单据（biz_no 标记）：DEMO-GR-FAB-001 / DEMO-GR-ACC-002 / DEMO-GR-FG-001
                        DEMO-IS-FAB-001 / DEMO-TR-ACC-002 / DEMO-AD-ACC-002
                       + 1 张质量放行单
当前开发库：5 条库存余额、9 条库存流水
```

幂等性通过 `biz_no` 存在性检查保证；第二次执行 `seed_demo` 输出 `合计新建 0 条`（已实测）。

### 7.6 测试执行结果（真实输出）

```text
backend:  ruff check apps config tests         -> All checks passed!
backend:  manage.py check                      -> System check identified no issues (0 silenced)
backend:  makemigrations --check --dry-run     -> No changes detected
backend:  pytest tests -q --reuse-db           -> 148 passed（新增 test_wms_inventory.py 36 条）
frontend: npm run typecheck                    -> 退出码 0
frontend: npm run test                         -> 6 files / 63 tests passed
frontend: npm run build                        -> ✓ built（含 3 个新库存页面 chunk）
smoke:    scripts\smoke_check.ps1             -> 全部检查通过，退出码 0
```

并发用例设计（任务书 14.2 要求「必须使用真实独立事务与连接」）：
`threading` + `connections.close_all()` + `threading.Barrier`，
`@pytest.mark.django_db(transaction=True)`，`committed_data_cleanup` fixture 调用
`flush --inhibit-post-migrate` 清理**已提交**数据，因此不依赖外层测试事务掩盖问题。

必测案例结果：案例 5/6/7/8/9/10 **已通过**；
案例 11 的**同仓移库守恒**已通过，**跨仓在途**部分**未执行**（功能未实现）。

### 7.7 启动验证步骤

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo --skip-users
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

```powershell
cd frontend; npm run dev    # http://localhost:5173
```

验证路径：登录 → 「仓储管理 → 库存余额」应看到 5 条余额（`available = on_hand - frozen - reserved`）→
「库存流水」应看到 9 条且**页面上没有编辑/删除按钮** →
「库存单据」新建一张 `issue` 单（数量大于可用量）→ 过账应被拒绝并提示可用量不足 →
改为可满足的数量再过账 → 余额与流水同步变化 → 对该单冲销（填写原因）→ 库存回滚，单据状态变为 `reversed`。

### 7.8 未完成事项

- **跨仓调拨与在途状态**：当前 `move` 仅支持**同仓移库**，跨仓被服务层拒绝；必测案例 11 的跨仓部分未执行。
- **盘点与范围冻结**：`adjustment` 可用于调整，但盘点单、范围内冻结变动、差异审批未实现。
- **冻结/解冻、占用/释放的业务动作**：数量桶已建模并有约束，但尚无对应服务入口
  （需由销售订单、工单等调用方驱动；采购侧的待检库存**不参与占用**）。
- **库位推荐、标签打印**：未实现。
- **库存成本**：余额表只存数量、不存金额；移动加权平均属阶段 7。
- **`allow_negative_stock`**：已建模为仓库字段，但服务层**不考虑**该开关，始终拒绝负库存。
- **采购、销售、生产单据**：写作本节时均未开始（阶段 2 主体剩余）。
  **后续进展**：采购单据已于下一增量完成（见 §八）；销售与生产单据仍未开始。
- 阶段 1 遗留：Docker Compose / Celery worker+beat / Playwright / 备份恢复仍未实际运行。

### 7.9 下一阶段依赖

- 采购收货、销售发货、生产领料/完工入库将**只调用**本轮库存服务，不新建库存体系
  （任务书 17 补充：备件库存由共享模块提供，阶段 4 不重复创建）。
- 单据过账需要「待检 → 放行」的质量状态流转作为前置，本轮已提供 `release_quality` 接口，
  QMS 检验单在阶段 3 落地时接入。
- 冻结/占用需要销售订单与工单作为分配来源，将在阶段 2 剩余与阶段 3 补齐。

## 八、阶段 2 第三步：采购模块（本轮增量）

任务书 10.5「采购管理」的**主体链路**在本轮落地：
`申请 → 审批 → 采购订单 → 审批 → 到货收货 → 待检库存 → 来料检验放行 / 不合格`。

收货过账与检验放行**全部经由阶段 2 已有的同一套库存服务**（`apps/wms/services/stock.py`）；
采购模块**不直接读写** `InventoryBalance` / `InventoryTransaction`，也不新建库存体系
（任务书 17 补充：备件库存由共享模块提供，阶段 4 不重复创建）。

### 8.1 已实现功能

- **采购申请**（`procurement.PurchaseRequisition` + `PurchaseRequisitionLine`）：
  单号 `PR{YYYYMMDD}{SEQ:4}`；类型 `normal / planned / urgent`；
  状态 `draft → submitted → approved / rejected`，另有 `cancelled`。
- **申请转订单**（`services.create_order_from_requisition`）：只转「已批准且未转数量 > 0」的申请行，
  同事务累加申请行的 `ordered_quantity`，**重复转单被拦截**（与任务书 10.6「同一建议不得重复转单」同一口径）。
- **采购订单**（`PurchaseOrder` + `PurchaseOrderLine`）：单号 `PO{YYYYMMDD}{SEQ:4}`；
  状态机 `draft → submitted → approved → partially_received → received → closed`，
  另有 `rejected / cancelled`；`close_order` 可关闭未收完的订单。
- **金额一律由后端计算**：未税金额 = `Σ(数量 × 单价)`（`ROUND_HALF_UP`，4 位小数）、
  税额 = 未税 × 税率(%)、价税合计 = 两者之和；序列化器把金额与 `received_quantity` 全部设为**只读**，
  前端传入的金额被忽略（已测）。
- **供应商可用性校验**：未准入或已停用的供应商**不能下单**（`SUPPLIER_NOT_USABLE`）；
  持 `procurement.order.override_supplier` 并填写例外原因时可例外，订单落
  `supplier_exception` / `supplier_exception_reason` 并写审计（无权限被拒亦有用例）。
- **收货**（`GoodsReceipt` + `GoodsReceiptLine`）：单号 `RC{YYYYMMDD}{SEQ:4}`；
  只能引用**本订单**的订单行（`ORDER_LINE_MISMATCH`）；
  **不允许超收**（`OVER_RECEIPT`），且**草稿收货单同样占用订单未收数量**（两张草稿合计超额也会被拒）。
- **收货过账**：`stock.create_document(RECEIPT)` + `post_document`，库存落 `quarantine`（待检）；
  订单行 `received_quantity` 与订单状态同步推进；**待检库存不可领用**（出库被服务层拒绝，已测）。
- **来料检验判定**：`stock.release_quality` 生成并过账一张 `QUALITY` 单据；
  `qualified` → 待检转合格（此后可领用/销售）；`rejected` → 转不合格（留在仓内但不可动用，
  退货走库存出库，**本轮不伪造退货单**）。
  **多行收货单逐行放行**，内部幂等键按行隔离。
  未接入真实检测设备，因此这是**人工判定**（任务书 10.9「未配置真实检测接口时标明人工录入」），
  结论、判定人、说明与依据单据一并留痕。
- **审批回写**：新增 `apps/workflow/registry.py`，以**显式注册的回调**把审批终态回写到业务单据
  （`register_biz_handler` / `apply_biz_outcome`），**未使用 Django signals**（任务书 4.3）。
  审批通过与库存过账是**两个独立动作**，互不触发。
- **幂等**（任务书 7.2）：`Idempotency-Key` 覆盖「收货过账」与「检验判定」两个动作，
  同键同内容返回首次结果并回 `Idempotency-Replayed: true`；单据状态机与唯一约束是第二道保障。
### 8.2 数据迁移

| 应用 | 迁移 | 表 | 状态 |
| --- | --- | --- | --- |
| `procurement` | `0001_initial` | `procurement_purchaserequisition` / `_line`、`procurement_purchaseorder` / `_line`、`procurement_goodsreceipt` / `_line`（6 张） | 已应用到开发库 |

`makemigrations --check --dry-run` → `No changes detected`；开发库表数由 71 张增至 **77 张**。

唯一约束：`uq_requisition_company_no`、`uq_order_company_no`、`uq_receipt_company_no` 与
`uq_*_line_no`（头 + 行号唯一）；检查约束：数量 > 0、`received_quantity` 非负且不超过订单数量、
税率 ∈ [0, 100]。**`received_quantity` 只能由库存过账推进**，前端与普通更新接口均不可写。

### 8.3 页面与 API

| 页面（前端） | 组件 | 接口 |
| --- | --- | --- |
| 采购管理 → 采购申请 | `views/procurement/RequisitionList.vue` | `/api/v1/procurement/requisitions/` |
| 采购管理 → 采购订单 | `views/procurement/PurchaseOrderList.vue` | `/api/v1/procurement/orders/` |
| 采购管理 → 采购收货 | `views/procurement/GoodsReceiptList.vue` | `/api/v1/procurement/receipts/` |

单据动作（`POST`）：

```text
/api/v1/procurement/requisitions/{id}/submit/     提交审批
/api/v1/procurement/requisitions/{id}/cancel/     取消（必填 reason）
/api/v1/procurement/requisitions/{id}/convert/    转采购订单（必填 supplier_id）
/api/v1/procurement/orders/{id}/submit/           提交审批
/api/v1/procurement/orders/{id}/cancel/           取消（必填 reason）
/api/v1/procurement/orders/{id}/close/            关闭（必填 reason）
/api/v1/procurement/receipts/{id}/post/           收货过账（幂等，记待检库存）
/api/v1/procurement/receipts/{id}/inspect/        来料检验判定（qualified / rejected）
/api/v1/procurement/receipts/{id}/cancel/         取消草稿收货单
```

`GET /api/v1/meta/` 新增 5 个枚举键：`requisition_types`、`requisition_statuses`、
`purchase_order_statuses`、`receipt_statuses`、`inspection_results`。前端不硬编码中文标签。

### 8.4 权限

新增权限点 **15 条**（注册表由 124 条增至 **139 条**）；菜单由 43 项增至 **47 项**
（新增 `procurement` 目录与 `procurement.requisition`、`procurement.order`、`procurement.receipt` 三个页面）。

| 权限编码 | 说明 |
| --- | --- |
| `procurement.requisition.view` / `create` / `update` / `submit` | 采购申请 |
| `procurement.order.view` / `create` / `update` / `submit` / `close` | 采购订单 |
| `procurement.order.override_supplier` | 对未准入/停用供应商下单的**例外授权** |
| `procurement.receipt.view` / `create` / `update` / `post` / `inspect` | 采购收货与来料检验 |

**跨模块动作按「与」语义校验**：`wms.document.create`、`wms.document.post`、`wms.quality.release`
等库存侧权限通过 `required_permissions` 的**列表**形式与采购权限**同时**要求
（`apps/core/permissions.py::require_codes` 为 AND 语义）。**不因为持有采购权限就绕过库存授权。**

内置角色：`procurement_admin`（15 条中的 14 条，**刻意不含 `receipt.inspect`**，与质检职责分离）、
`quality_inspector`（含 `procurement.receipt.view` / `inspect` 与 `wms.quality.release`）。
数据范围按 `factory` / `department` / `warehouse` 过滤，服务层另有 `assert_in_scope` 二次校验。
### 8.5 演示数据

`seed_demo` 新增 `_procurement()` 步骤，**只调用服务层**（不直接改表）：
固定单号 `PR-DEMO-0001` / `PO-DEMO-0001` / `RC-DEMO-0001`，
走「申请 → 审批 → 转订单 → 审批 → 收货过账 → 检验放行」的真实链路。

实测结果：

```text
PR-DEMO-0001 approved   FAB-001 1200 已转 1200 / ACC-002 3000 已转 3000
PO-DEMO-0001 partially_received  51360.0000 / 6676.8000 / 58036.8000
    FAB-001 1200 已收 800 / ACC-002 3000 已收 3000
RC-DEMO-0001 inspected qualified   receipt_document_id=9 / quality_document_id=11
库存：FAB-001 批次 PO-DEMO-FAB-01  待检 0 / 合格 800
      ACC-002 批次 PO-DEMO-BTN-01  待检 0 / 合格 3000
```

新增员工 `E1015 钱进`（采购专员）与演示账号 `prc_admin`（`procurement_admin`）、
`qc_inspect`（`quality_inspector`）；新增审批模板 `AP-PRC-REQ`（`procurement.requisition`）与
`AP-PRC-ORDER`（`procurement.order`）。第二次执行 `seed_demo` 输出 `合计新建 0 条`（已实测）。

### 8.6 测试执行结果（真实输出）

```text
backend:  ruff check apps config tests         -> All checks passed!
backend:  manage.py check                      -> System check identified no issues (0 silenced)
backend:  makemigrations --check --dry-run     -> No changes detected
backend:  pytest tests -q --reuse-db           -> 183 passed（新增 tests/test_procurement.py 35 条）
frontend: npm run typecheck                    -> 退出码 0
frontend: npm run test                         -> 6 files / 66 tests passed
frontend: npm run build                        -> ✓ built（含 3 个新采购页面 chunk）
smoke:    scripts\smoke_check.ps1             -> 全部检查通过，退出码 0
```

采购用例覆盖：申请/订单/收货的 CRUD 与状态机、金额后端计算、只读字段防篡改、
供应商未准入与例外授权、超收与草稿占用额度、订单行归属校验、待检库存不可领用、
放行后可领用、不合格仍被拦截、多行逐行放行、幂等重放、跨公司与数据范围隔离、
「提交 → 审批 → 回写」完整链路。

必测案例（任务书 14.2）本轮新增通过：案例 9「不合格库存不可发货」、
案例 5「重复过账不重复扣库存」（收货侧）；案例 1 / 2 / 3 / 4 在采购接口上复验。

### 8.7 启动验证步骤

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo --skip-users
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

```powershell
cd frontend; npm run dev    # http://localhost:5173
```

验证路径：用 `prc_admin` 登录 → 「采购管理 → 采购申请」新建申请（选物料与数量）→ 提交 →
审批账号在「审批中心 → 我的待办」通过 → 回申请页「转订单」（选供应商）→
「采购订单」应出现草稿单且金额已由后端算出 → 提交并审批 → 「采购收货」新建收货单
（从订单带出明细，数量不得超过未收量）→ 过账 → 「仓储管理 → 库存余额」应看到该批次 `quarantine` 库存 →
回到收货单执行「来料检验」（用 `qc_inspect` 登录）→ 判定合格 → 余额转为 `qualified`，
此后可在「库存单据」新建 `issue` 单领用。

### 8.8 未完成事项（阶段 2 采购模块剩余）

- **询价比价 / 报价单**：未实现（依赖 SRM 的「可供物料 + 报价及有效期」，见 §10.4-03）。
- **到货差异处理**：短交/超交的差异单与扣款未实现；当前只有「不允许超收」一条硬规则。
- **采购退货**：未实现；不合格库存目前只能留在仓内（质量状态 `rejected`），
  退货需要出库单据与供应商侧退货记录。
- **应付与付款登记**：未实现（任务书明确「登记不等于完整财务记账」，随阶段 7 处理）。
- **备件采购**：流程本身可直接复用本模块，但备件档案属阶段 4，本轮不预建。
- **采购价格与交付分析报表**：未实现（属阶段 7 报表中心；准时率需先定义按行/按量口径）。
- **打印**：采购申请/订单/收货单的打印模板未实现。
- **供应商准入审批流程**：`admission_status` 仍是档案字段，未接入 `workflow`（§10.4-02）。
- 阶段 1 / 2 遗留：Docker Compose / Celery worker+beat / Playwright / 备份恢复仍未实际运行。

### 8.9 下一阶段依赖

- **销售模块**（阶段 2 剩余）与采购共用 `crm` / `srm` 主数据与统一库存服务，不再新建库存体系。
- **MRP**（阶段 3）将消费采购订单的未到货量与销售需求，因此订单行的 `received_quantity`
  与状态必须保持权威；本轮已把 `received_quantity` 设为**只读、只能由库存过账推进**。
- **QMS**（阶段 3）落地检验单后，`procurement.receipt.inspect` 的**人工判定**应升级为
  引用检验单结果，届时保留人工录入作为兜底并明确标注数据来源。
- **冻结/占用**：销售订单占用库存时调用库存服务；采购侧的待检库存不参与占用。

## 九、全局改名：弋尚集成平台 → 意尚智造集成平台

按要求把项目内的平台名称与演示数据中的旧品牌名统一替换。

### 9.1 替换映射

| 旧值 | 新值 | 出现位置 |
| --- | --- | --- |
| 弋尚集成平台 | 意尚智造集成平台 | 平台名（24 处） |
| 弋尚服饰有限公司 | 意尚智造服饰有限公司 | 演示数据：租户企业（`seed_demo.COMPANY`） |
| 弋尚服饰（`short_name`） | 意尚智造服饰 | 同上 |
| 弋尚一号工厂 / 弋尚二号工厂 | 意尚智造一号工厂 / 意尚智造二号工厂 | 演示数据：工厂档案 |
| 弋尚（款式/物料 `brand`） | 意尚智造 | 演示数据：6 个款式 + 物料默认品牌 |

### 9.2 修改文件（23 个，35 处）

- 平台名：`.env.example`、`AGENTS.md`、`PROJECT_SPEC.md`（2）、`README.md`、`compose.yaml`、
  `backend/README.md`、`backend/manage.py`、`backend/pyproject.toml`、
  `backend/config/settings/base.py`（含 OpenAPI `TITLE`，2）、`docs/requirements.md`、
  `frontend/index.html`（`<title>`）、`frontend/src/layouts/BasicLayout.vue`（顶栏标题）、
  `frontend/src/views/LoginView.vue`（登录页大标题）、
  `scripts/backup_mysql.sh`、`scripts/restore_mysql.sh`、`scripts/dev_backend.ps1`、
  `scripts/dev_frontend.ps1`、`scripts/smoke_check.ps1`、
  `deploy/docker/Dockerfile.backend`、`deploy/mysql/my.cnf`、`deploy/nginx/nginx.conf`、
  `frontend/src/styles/index.css`（后 4 个在首次扫描时因扩展名过滤被漏掉，已补改）。
- 演示数据：`backend/apps/core/management/commands/seed_demo.py`（11 处）。

**未改动**（有意保留）：

- 仓库目录名 `Yishang-Hub`、Python 包名/环境变量前缀 `YISHANG_*`、数据库名
  `yishang_platform`、前端包名 `yishang-platform-frontend`、`.env` 变量名——
  均为拉丁化标识，「意尚」的拼音同样是 `Yishang`，改动会带来部署与迁移风险而无收益。
- `README.md` 标题后的英文名 `（Yishang Platform）`。

### 9.3 数据同步与验证（真实输出）

`seed_demo` 使用 `update_or_create`，重跑即把已存在记录的固定字段同步为新名称：

```text
合计新建 0 条；其余演示对象已存在并已同步固定字段。
公司: [('YS', '意尚智造服饰有限公司', '意尚智造服饰')]
工厂: [('F01', '意尚智造一号工厂'), ('F02', '意尚智造二号工厂')]
款式品牌集合: ['意尚智造']   物料品牌集合: ['', '意尚智造']
```

回归检查（改名后重跑）：

```text
backend:  ruff check apps config tests         -> All checks passed!
backend:  manage.py check                      -> no issues (0 silenced)
backend:  makemigrations --check --dry-run     -> No changes detected
backend:  pytest tests -q --reuse-db           -> 183 passed
frontend: npm run typecheck                    -> 退出码 0
frontend: npm run test                         -> 6 files / 66 tests passed
frontend: npm run build                        -> ✓ built
```

全仓库扫描：`弋尚` 仅剩本文档 §9.1 映射表的「旧值」列（8 处，属改名记录本身），
代码、配置与其余文档中为 **0** 处。
