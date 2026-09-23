# 实施进度（docs/progress.md）

> 本文件记录**实际执行结果**。未执行的测试一律注明「未执行」，不写成通过。
> 最近更新：2026-09-18（阶段 0 / 阶段 1 交付；阶段 2 第一步：客户与供应商主数据；
> 阶段 2 核心：**统一库存服务（余额 / 流水 / 单据 / 质量放行）**；
> 阶段 2 第三步：**采购模块（采购申请 / 订单 / 收货 / 来料检验放行）**；
> 阶段 2 第四步：**销售模块（销售订单 / 库存占用 / 发货出库 / 销售退货与检验判定）**；
> 阶段 3 第一步：**BOM 与工艺路线版本快照**；阶段 3 第二步：**MRP（时间分段净算 / 多层 BOM 展开 / 缺料建议 / 建议转单）**；
> 界面：**侧边导航层级区分**、**视图样式统一（共享样式类）**与**窄屏响应式（侧边栏自动折叠）**；
> 本轮增量：**枚举值中文化**（所有 choices 字段随接口返回中文标签）与**历史非法枚举数据修复**（见 §十七）；
> **超级管理员权限通配符修复**（前端把 `*` 当普通编码比较，导致新增 / 编辑按钮全部消失）与**管理员账号绑定「超级管理员」角色**（见 §十八）；
> **客户编码自动生成**（新增客户不再手工输入编码，复用平台既有编码规则引擎，规则可配置，见 §十九））

## 一、当前状态总览

| 阶段 | 范围 | 状态 |
| --- | --- | --- |
| 0 | 仓库检查、需求矩阵、架构与数据模型、环境与部署编排 | 已完成（Docker 编排未在本机启动验证） |
| 1 | 登录、权限、组织、主数据、仓库储位、基础审批、审计、后台界面 | 已完成（阶段验收待人工确认） |
| 2 | 客户、供应商、采购、销售、WMS 单据 | **进行中**：客户/供应商主数据、**统一库存服务（收发存/移库/质量放行/冲销/幂等）已完成**、**采购模块（申请 → 订单 → 收货 → 来料检验放行）已完成**、**销售模块（订单 → 库存占用 → 发货出库 → 退货 → 检验判定）已完成**；**客户编码改为按编码规则自动生成**（见 §十九）；询价/报价/供应商评价、销售计划与预测、应收/收款登记、调拨在途与盘点未开始 |
| 3 | BOM、工艺、MRP、MES、QMS | **进行中**：BOM 与工艺路线版本快照已完成（见 §十四）；**MRP（任务书 10.6）已完成**——时间分段净需求、多层 BOM 展开与损耗、循环 BOM 检查、缺料清单、采购 / 生产建议、供需追溯、计算快照、采购建议转单（见 §十五）；**MES、QMS 未开始** |
| 4 | 设备、备件、保养、点检、维修 | **已完成**（设备台账 / 类型 / 零部件 / 备品备件 / 配件 / 故障报修 / 备件库存台账 / 保养 / 维修 / 点巡检 / 异常上报，见 §二十八） |
| 5 | 采集、EMS、能源报表与告警 | **部分完成**：EMS（区域、仪表、价格、阈值、抄表、运行记录、报警、看板 / 报表 / 统计）已完成；**硬件采集未开始**（见 §二十八） |
| 6 | CRM 深化、EHS、厂内物流、终端安全 | **部分完成**：EHS（安全 / 环保 / 消防 / 设备设施安全）与厂内物流已完成；**CRM 深化（投诉、产品评价）与终端安全未开始**（见 §二十八） |
| 7 | 综合报表、基础成本、性能、安全、运维与恢复演练 | 未开始 |

当前规模（统计自 `permissions_registry` 与开发库，2026-09-22 实测）：**368 个权限点 / 144 项菜单（含目录）/
146 个数据模型**（`apps.get_models()` 全量，含 Django 框架自带模型）；数据库共 **154 张表**（其中框架表 13 张、业务表 141 张）；
已提交迁移文件 **30 个**；前端 **133 个 `.vue` 视图**；内置角色 **19 个**（`bootstrap_system` 19 个，另有 `seed_demo_xjys` 演示角色）。

**使用说明**见 `docs/user-guide.md`（面向客户的业务操作手册，另有网页版 `docs/user-guide.html`）；
文档同步的事实行在 `AGENTS.md` §九，由 `backend/tests/test_docs_sync.py` 与代码比对，防止文档静默过期。

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
| 本机 MySQL | 实际为 MySQL 8.0.17；项目方已确认版本基线由任务书的 8.4 LTS 调整为 MySQL 8.0 系列（部署镜像 `mysql:8.0`），与本机同一主版本；SQL 模式、字符集与排序规则按目标配置；容器镜像仍未实际启动验证 |
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

### 5.2 新增文档（阶段 0 本轮补齐 13 份）

> 后续补充：`docs/user-guide.md`（**项目使用说明**，阶段 3 第二步之后新增），文档共 **17** 份。
> 该文档内置 `<!-- yishang-doc-sync: ... -->` 事实行，由 `backend/tests/test_docs_sync.py`
> 与注册表 / 模型 / 迁移比对，保证「代码更新后使用文档同步变动」。

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
| 弋尚服饰有限公司 | 新疆意尚智造科技有限公司 | 演示数据：租户企业（`seed_demo_xjys.COMPANY`，见 §三十七） |
| 弋尚服饰（`short_name`） | 新疆意尚智造 | 同上 |
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

`seed_demo`（现为 `seed_demo_xjys` 的兼容入口）使用 `update_or_create`，重跑即把已存在记录的固定字段同步为新名称。
下面是本次改名的执行输出；其中的租户与 F01 / F02 工厂属旧演示数据，已在 §三十七 整体清理：

```text
合计新建 0 条；其余演示对象已存在并已同步固定字段。
公司: [('XJYS', '新疆意尚智造科技有限公司', '新疆意尚智造')]
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

## 十、阶段 2 第四步：销售模块（本轮增量）

### 10.1 已实现功能

销售订单 → 库存占用 → 发货出库 → 客户退货 → 检验判定，**全部通过
`apps/sales/services.py` 调用统一库存服务 `apps/wms/services/stock.py` 完成**，
没有新建第二套库存体系，也没有在 View / Serializer 里写库存逻辑。

| 能力 | 实现位置 | 说明 |
| --- | --- | --- |
| 销售订单 | `sales.SalesOrder` / `SalesOrderLine` | 草稿 → 提交审批 → 批准 → 部分发货 → 已发货 → 关闭 / 驳回 / 取消；关闭与取消是不同语义 |
| 金额计算 | `services.compute_line_amount` / `recalculate_order_amounts` | 行金额、单头金额与税额**全部由后端计算**后落库；前端传入的金额字段被忽略（用例 `test_order_amount_is_computed_by_backend`） |
| 颜色尺码 | `SalesOrderLine.sku` | 订单行可关联成品 SKU（款式 + 颜色 + 尺码）；SKU 与库存物料一对一，不产生两套编码 |
| 客户校验 | `_assert_customer_usable` | 停用 / 终止客户不能新建订单（`CUSTOMER_INACTIVE`） |
| 库存占用 | `stock.reserve_stock` / `release_reservation` / `release_reservations_for_biz` | 占用**只改可用量、不写库存流水**；`request_key` 唯一约束保证幂等 |
| 库位推荐 | `stock.choose_reservation_dimension` | 未指定储位/批次时按「可用量最大的合格维度」占用；库存分散在多个维度时报明确错误而不是静默少占 |
| 销售发货 | `sales.SalesShipment` / `SalesShipmentLine` | 草稿 → 出库过账 → 取消（仅草稿可取消） |
| 先占用后发货 | `stock._assert_reservation_covers`（经 `require_full_reservation=True`） | 出库数量必须由**本订单**占用覆盖；未占用返回 `RESERVATION_REQUIRED`，且不会动用其他订单的占用 |
| 出库维度一致 | `_shipment_document_lines` + `stock.open_reservation_hint` | 发货行留空的储位/批次/卷号由占用维度推导，避免「前端选错储位 → 误判占用不足」 |
| 销售退货 | `sales.SalesReturn` / `SalesReturnLine` | 草稿 → 收货过账（**待检**）→ 检验判定（合格回库 / 不合格）→ 取消 |
| 退货批次追溯 | `_inherit_return_dimensions` + `stock.document_line_hint` | 退货行未填维度时继承**原发货出库单据**的储位/批次/卷号并写回退货行，检验放行复用同一维度，批次追溯不断链 |
| 退货数量口径 | `SalesOrderLine.returnable_quantity` | 可退数量 = 已发货 − 已退货；超出即 `OVER_RETURN` |
| 订单到交付链路 | `GET /api/v1/sales/orders/{id}/chain/` | 一次返回订单、行交付进度、发货单、退货单与关联库存单据（任务书 12.1） |
| 幂等 | `Idempotency-Key` + `idempotent_execute` | 发货过账、退货收货过账支持幂等重放，重放时响应头 `Idempotency-Replayed: true` |
| 审计与事件 | `record_audit` + `publish_event` | 订单、占用、释放、发货、退货、判定全部留痕并写入 Outbox |

**库存口径（本轮新增，详见 `docs/inventory-rules.md` 第十节）**

- 占用**不写库存流水**：`InventoryTransaction` 只记录实存量增减；占用有自己的生命周期。
- 一致性口径：`InventoryBalance.reserved == 该维度所有未结占用数量之和`。
- 占用结束分两种：**消耗结束**（`closed`）与**释放结束**（`cancelled`），便于排查「占用去哪了」。
- 占用 / 释放 / 过账三处的加锁顺序统一为「余额 → 占用」，降低多维度并发死锁风险（任务书 5.6）。

### 10.2 数据迁移

| 迁移 | 内容 |
| --- | --- |
| `apps/wms/migrations/0003_stockreservation.py` | `wms_stockreservation` 表 + 3 个检查约束 + 2 个索引 |
| `apps/sales/migrations/0001_initial.py` | `sales_salesorder`、`sales_salesorderline`、`sales_salesshipment`、`sales_salesshipmentline`、`sales_salesreturn`、`sales_salesreturnline` |

`makemigrations --check --dry-run` 输出 `No changes detected`。

### 10.3 页面与 API

新增左侧一级目录「销售管理」下的 3 个页面（路由由后端菜单动态注册）：

| 页面 | 组件 | 主要交互 |
| --- | --- | --- |
| 销售订单 | `frontend/src/views/sales/SalesOrderList.vue` | 新增/编辑（颜色尺码 SKU、行金额后端算）、提交审批、库存占用、释放占用、关闭、取消；详情抽屉展示链路进度 |
| 销售发货 | `frontend/src/views/sales/SalesShipmentList.vue` | 按订单未发货数量生成发货单、发货过账（带幂等键）、取消；详情展示出库库存单据 |
| 销售退货 | `frontend/src/views/sales/SalesReturnList.vue` | 退货登记、退货收货（进待检）、检验判定（人工录入，标注未接入检测设备）、取消 |

新增 API（统一前缀 `/api/v1/`）：

| 方法 | 路径 | 权限 |
| --- | --- | --- |
| GET / POST | `/sales/orders/` | `sales.order.view` / `sales.order.create` |
| PATCH | `/sales/orders/{id}/` | `sales.order.update` |
| POST | `/sales/orders/{id}/submit/` | `sales.order.submit` |
| POST | `/sales/orders/{id}/cancel/` | `sales.order.update` |
| POST | `/sales/orders/{id}/close/` | `sales.order.close` |
| POST | `/sales/orders/{id}/reserve/` | `sales.order.reserve` + `wms.inventory.reserve` |
| POST | `/sales/orders/{id}/release/` | `sales.order.release` + `wms.inventory.release` |
| GET | `/sales/orders/{id}/chain/` | `sales.order.view` |
| GET / POST / PATCH | `/sales/shipments/`、`/sales/shipments/{id}/` | `sales.shipment.view` / `.create` / `.update` |
| POST | `/sales/shipments/{id}/post/` | `sales.shipment.post` + `wms.document.create` + `wms.document.post` |
| POST | `/sales/shipments/{id}/cancel/` | `sales.shipment.update` |
| GET / POST / PATCH | `/sales/returns/`、`/sales/returns/{id}/` | `sales.return.view` / `.create` / `.update` |
| POST | `/sales/returns/{id}/post/` | `sales.return.post` + `wms.document.create` + `wms.document.post` |
| POST | `/sales/returns/{id}/inspect/` | `sales.return.inspect` + `wms.quality.release` |
| POST | `/sales/returns/{id}/cancel/` | `sales.return.update` |

`/api/v1/meta/` 新增枚举：`sales_order_statuses`、`sales_order_priorities`、`shipment_statuses`、
`return_statuses`、`return_dispositions`、`reservation_statuses`（前端不硬编码枚举）。

### 10.4 权限

- 新增 18 个权限点：`wms.inventory.reserve/release` + `sales.order.*`（7）+ `sales.shipment.*`（4）+
  `sales.return.*`（5）。权限总数 **139 → 157**。
- 新增 4 项菜单（1 个目录 + 3 个页面）。菜单总数 **47 → 51**。
- 新增内置角色 `sales_admin`（27 个权限），**不含** `sales.return.inspect`：
  销售与质检职责分离，退货检验判定只能由质检角色执行。
- **修正缺陷**：内置角色 `quality_inspector`（质检员）此前缺少 `wms.document.create` /
  `wms.document.post`，而质量放行要经统一库存服务创建并过账「质量转换单」，
  导致质检员实际无法完成放行（采购来料检验同样受影响）。本轮补齐并重跑 `bootstrap_system`。
  权限数 9 → 11。

### 10.5 演示数据

`seed_demo` 新增 `_sales()`：全部经服务层完成，固定单号 + 状态推进，重复执行不重复建单、
不重复扣库存。真实输出：

```text
演示数据写入完成（本次新建数量）：
  sales.SalesOrder: 1
  sales.SalesReturn: 1
  sales.SalesShipment: 1
  workflow.ApprovalTemplate: 1
  workflow.ApprovalTemplateNode: 3
```

链路核对（读取开发库真实数据）：

```text
订单 SO-DEMO-0001 shipped 23940.0000 27052.2000
  行 1 YS-M-2401-NV-170A 60.000000 已发 60.000000 已退 6.000000 可退 54.000000
发货 SH-DEMO-0001 posted 出库单据 15
退货 SR-DEMO-0001 inspected qualified [('FG-2509-01', 42, '6.000000')]
  余额 42 FG-2509-01 qualified 实存 186.000000 占用 0.000000 可用 186.000000
未结占用 0
```

即：成品批次 `FG-2509-01` 入库 240 → 占用 60 → 发货出库 60 → 退货 6 件进待检 →
检验合格回库 6，最终合格可用 186，与流水一致。

### 10.6 测试执行结果（真实输出）

```text
backend:  ruff check apps config tests         -> All checks passed!
backend:  manage.py check                      -> System check identified no issues (0 silenced).
backend:  makemigrations --check --dry-run     -> No changes detected
backend:  pytest tests -q --reuse-db           -> 217 passed（新增 tests/test_sales.py 34 例）
frontend: npm run typecheck                    -> 退出码 0
frontend: npm run test                         -> 6 files / 69 tests passed
frontend: npm run build                        -> ✓ built
```

销售用例覆盖（`backend/tests/test_sales.py`）：

- 未登录 / 无权限 / 无占用权限 / 无检验权限的拒绝（含**职责分离**：销售岗位不能做质量判定）；
- 金额后端计算、非正数量拒绝、停用客户拒绝；
- 提交 → 审批 → 批准 / 驳回回写状态；
- 占用幂等、占用**不改实存量且不写流水**、可用量不足拒绝、**待检库存不可占用**；
- 释放占用、**取消订单自动释放未结占用**；
- **未占用不允许发货**（`RESERVATION_REQUIRED`，且失败整体回滚）；
- 发货过账消耗占用并扣减实存量、**过账幂等**（同键重放 + 重复过账）；
- 发货数量不得超过未发货数量；
- **占用维度与出库维度按批次对齐**（`test_reserve_uses_matching_batch_dimension`）；
- 退货必须先有已出库发货单、可退数量不得超过「已发货 − 已退货」；
- 退货必须先收货再过账才能判定、判定必须填写说明、重复判定拒绝；
- 退货收货进**待检**且待检库存不可出库；合格回库 / 判为不合格后**不合格库存不可出库**；
- **退货入库继承原发货批次**（`test_return_inherits_original_batch`）；
- 订单到交付链路接口、跨公司隔离、`/api/v1/meta/` 销售枚举。

未执行：Playwright 端到端、并发多连接压测（见 10.8）。

### 10.7 启动验证步骤

```powershell
# 1) 数据库迁移（含本轮 2 个迁移）
cd E:\github\Yishang-Hub\backend
.\.venv\Scripts\python.exe manage.py migrate

# 2) 系统初始化（会同步权限/菜单/编码规则，含新增 SH / SR 单号规则）
.\.venv\Scripts\python.exe manage.py bootstrap_system

# 3) 演示数据（幂等，可重复执行）
.\.venv\Scripts\python.exe manage.py seed_demo

# 4) 启动后端 / 前端
powershell -ExecutionPolicy Bypass -File ..\scripts\dev_backend.ps1
powershell -ExecutionPolicy Bypass -File ..\scripts\dev_frontend.ps1
```

人工验证路径：登录 → 销售管理 → 销售订单（SO-DEMO-0001）→ 详情查看链路 →
「库存占用」→ 销售发货（SH-DEMO-0001）「发货过账」→ 销售退货（SR-DEMO-0001）「退货收货」→
「检验判定」。注意：**未做过库存占用的订单直接发货会被后端拒绝**，这是设计行为。

### 10.8 未完成事项（销售模块剩余）

1. 颜色尺码矩阵录入界面（当前按行选择 SKU，未提供矩阵批量录入）。
2. 订单变更版本快照与变更审批（任务书 10.3「订单变更保存版本」）。
3. 分批发货界面细化、发货单与运单/物流对接、箱码与标签打印。
4. 分销商、销售计划、基础预测（任务书 10.3）。
5. 应收与收款登记（`sales.receivable` / `payment registration`）——未开始。
6. 跨储位/跨批次**自动拆分占用**：当前占用落在单个可用量最大的维度，
   库存分散时返回 `STOCK_SPLIT_ACROSS_DIMENSIONS` 引导先移库合并。
7. 退货入库维度仅在「行未填维度」时继承原发货批次；多批次部分退货尚未按批次分摊。
8. 并发多连接压测未执行（现有并发保障是 `request_key` 唯一约束 + `select_for_update`，
   但未做真实多进程并发验证）。

### 10.9 下一阶段依赖

- 阶段 2 剩余：供应商询价/报价/评价 → 采购到货差异与退货（需先定义差异口径）→ 调拨在途与盘点。
- 阶段 3：BOM/工艺版本快照 → MRP（消费销售订单未发货量与需求）→ MES 工单报工 →
  QMS 检验单（届时把销售退货与来料检验的**人工判定**升级为引用检验单）。

## 十一、界面样式优化（本轮增量）

### 11.1 需求来源

用户反馈：「进入页面后左侧一级目录和二级目录样式看起来一样」，并要求整体观感更接近商用后台。
本轮**只改前端样式与导航组件**，不动任何业务逻辑、接口与数据结构（后端文件零改动）。

### 11.2 侧边导航层级区分（主要变更）

| 层级 | class（由 `SideMenu.vue` 的 `depth` 生成） | 视觉处理 |
| --- | --- | --- |
| 一级目录 | `ys-menu-group--d0` | 12px / 字重 600 / 字距 0.08em、低对比度，作为「分组标题」；展开时提亮并高亮图标；**当前页面所属目录**再叠加左侧竖条 + 提亮（Element 的 `is-active`）；分组之间加分隔线 |
| 一级叶子页面（工作台） | `ys-menu-node--d0` | 与一级目录同一排版等级 + 图标，选中为蓝色渐变块 |
| 二级页面 | `ys-menu-node--d1` | 13px、缩进 + 4px 圆点、悬停提亮；选中为蓝色渐变块 + 阴影 + 圆点放大 |
| 展开的子菜单容器 | `.el-menu--inline` | 半透明深色底 + 圆角，把「同一目录下的页面」框成一组 |
| 折叠态 | `.ys-layout__aside--collapsed` | 图标居中、隐藏圆点与展开箭头 |
| 折叠后的弹出菜单 | `.el-menu--popup`（teleport 到 body，必须写全局规则） | 白底、圆角、蓝色选中块 |

### 11.3 其他样式统一

- 主题：Element Plus 主色替换为品牌科技蓝 `#1668dc`，并补齐 light-3/5/7/8/9 与 dark-2 梯度。
  （只覆盖基色会让 hover、浅色态仍是 Element 默认蓝，页面上出现两种蓝。）
- 菜单行高：Element Plus 的行高来自 CSS 变量 `--el-menu-item-height`（默认 56px），
  只覆盖 `height` 会让其它派生计算仍按 56px 走；已在侧边栏统一设置
  `--el-menu-item-height: 40px` / `--el-menu-sub-item-height: 36px` / `--el-menu-base-level-padding: 12px`，
  并由用例锁死，避免回退。
- 顶部栏：轻阴影、面包屑末级加重、用户区胶囊 hover、头像渐变。
- 标签页：由卡片式改为「选中块 + 底部 2px 主色下划线」。
- 页面骨架：标题左侧主色竖条、卡片统一 8px 圆角 + 轻阴影、筛选栏与表格卡风格一致。
- 组件：表格表头浅灰 + 行 hover 淡蓝、按钮/标签圆角与字重、弹窗与抽屉标题分隔线、滚动条细化。
- 工作台：看板卡片 hover 上浮、区块标题竖条。
- 登录页：卡片圆角与阴影、登录按钮字距。

### 11.4 涉及文件

| 文件 | 变更 |
| --- | --- |
| `frontend/src/styles/index.css` | 重写为 8 个小节：设计令牌 / 基础重置 / 页面骨架 / 主布局 / 侧边导航 / 顶部栏与标签页 / 组件细节 / 登录页 / 辅助类 |
| `frontend/src/components/SideMenu.vue` | 新增 `depth` prop，按层级输出 `ys-menu-group--dN` / `ys-menu-node--dN` |
| `frontend/src/layouts/BasicLayout.vue` | 品牌标识尺寸、面包屑与折叠按钮的样式钩子 class |
| `frontend/src/views/workspace/Index.vue` | 看板卡片 hover、区块标题竖条 |
| `frontend/tests/side-menu.spec.ts` | 新增 10 条用例：DOM 层级 class + 样式表规则（用 postcss 真实解析样式表） |

### 11.5 验证结果（真实输出）

- `npm run typecheck` → 退出码 0
- `npm run test` → **7 个文件 / 79 项通过**（原 6 / 69，新增 `side-menu.spec.ts` 10 项）
- `npm run build` → `✓ built in 13.27s`
- 开发服务器实际下发校验：`GET http://127.0.0.1:5173/src/styles/index.css` → 200、18144 字节，
  内容包含 `ys-menu-group--d0`、`ys-menu-node--d1`、`--el-color-primary: #1668dc`
- 本轮无后端文件变更，`manage.py check` 与迁移一致性不受影响。

### 11.6 未完成 / 未执行

- **未做浏览器截图级像素校验**：浏览器自动化被安全策略拒绝（非人工拒绝），本轮无法由我截图确认最终观感；
  已改用「DOM 层级 class 断言 + postcss 解析样式规则 + 开发服务器实际下发」三重检查替代，
  最终观感仍需人工在浏览器确认。
- 未做响应式（窄屏 / 平板）适配；未引入暗色主题。
- 各业务视图内部的局部样式（`RoleList`、`OutboxList`、`ProgressView` 等）未逐一美化，仍是阶段 1/2 的默认观感。
  **（本条已由第十二节部分处理：面板、区块标题、统计卡、代码块已下沉为共享类；剩余项见 §12.6。）**

## 十二、视图样式统一（本轮增量）

### 12.1 背景

第十一节把侧边导航的层级区分做完了，但各业务视图内部仍是阶段 1/2 各自手写的样式。
用 `.tmp/scan_styles.py` 扫描 16 个带 `<style scoped>` 的 .vue 文件后发现：
**同一个界面元素在不同页面的写法不同**——`.ys-section-title` 被 4 个视图各自定义（字号、边距、竖条都不一致），
统计「标签 + 数值」有 3 套写法，白色面板有 3 份重复的「白底 + 边框 + 圆角」声明。
结果就是「切换页面时，看起来是同一类卡片，长相却不一样」。本轮把这三类重复下沉为全局共享类。

### 12.2 新增共享样式原语（唯一定义处：`frontend/src/styles/index.css`）

| 类 | 用途 | 关键视觉 |
| --- | --- | --- |
| `.ys-panel` | 通用白色面板（与 `.ys-table-card` 合并为同一条规则） | padding 16 / 1px 边框 / `var(--ys-radius)` / `var(--ys-shadow-card)` |
| `.ys-panel--flush` | 承载 `el-tabs` 的面板（标签页需贴边，故去掉上内边距） | `padding: 0 12px 12px` |
| `.ys-section-title` | 区块标题 | 14px / 字重 600 / 深蓝 + 主色竖条 `::before` |
| `.ys-stat-cards` / `.ys-stat-card` | 统计卡容器与卡片 | flex 自动换行 + hover 上浮 |
| `.ys-stat__label` / `.ys-stat__value` / `.ys-stat__hint` | 统计卡内文字 | 12px 灰标签 / 22px 深蓝数值 / 12px 说明文字 |
| `.ys-code-block` | 代码、Outbox 报文、审计变更明细 | 等宽字体、浅灰底、圆角 6px、`max-height: 320px` 可滚动 |
| `.ys-ml-4` | 小间距辅助类（原先分散在 2 个视图） | `margin-left: 4px` |

同时补齐 Element Plus 细节：`.el-drawer__body` 上内边距、`.el-drawer__footer` 上边框、
`.el-drawer .el-descriptions__label` 标签列加宽 108px + 浅灰底，让详情抽屉观感一致。

### 12.3 改造的视图

| 文件 | 改动 |
| --- | --- |
| `views/workspace/Index.vue` | 看板统计卡改用 `ys-stat-cards` / `ys-stat-card` / `ys-stat__label` / `ys-stat__value` |
| `views/integration/OutboxList.vue` | 统计块改用共享类；标签页容器改 `ys-panel ys-panel--flush`；事件报文改 `ys-code-block` |
| `views/system/ProgressView.vue` | 统计卡统一；说明文字改 `ys-stat__hint` |
| `views/system/PermissionList.vue` | 标签页容器改 `ys-panel ys-panel--flush` |
| `views/system/AuditLogList.vue` | 变更明细改 `ys-code-block` |
| `views/system/RoleList.vue`、`views/system/UserList.vue`、`views/workflow/TemplateList.vue`、`components/ApprovalDetailDrawer.vue` | 删除本地重复的 `ys-section-title` / `ys-ml-4` 定义 |

### 12.4 度量（改造前后）

| 指标 | 改造前 | 改造后 |
| --- | --- | --- |
| `.ys-section-title` 定义份数 | 4 | 1（全局唯一定义处） |
| 视图内重名的共享类 | 3 类（`ys-section-title`、`ys-ml-4`、统计标签/数值） | **0** |
| 全局样式表体积 | 18144 字节 | 20702 字节 |

### 12.5 验证结果（真实输出）

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| 类型检查 | `npm run typecheck` | 退出码 0（无输出） |
| 组件测试 | `npm run test` | `Test Files 8 passed (8)` / `Tests 110 passed (110)` |
| 生产构建 | `npm run build` | `✓ built in 12.02s` |
| 样式表编码与配平 | `.tmp/checkcss.py` | BOM False / CRLF 0 / 20702 字节 / 花括号 129 = 129 |
| 共享类重名扫描 | `.tmp/scan_styles.py` | 16 个带样式块的 .vue；重名选择器 **0** |

新增 `frontend/tests/styles.spec.ts`（31 项，全部通过）把约定固化为测试，其中最关键的一条是
「**任何 .vue 的 scoped 样式都不得再重新定义共享类**」，防止以后再次分叉。

### 12.6 未完成 / 未执行

- **浏览器截图级像素校验未执行**（原因同 §11.6，浏览器自动化被安全策略拒绝，非人工拒绝）；
  最终观感仍需人工在浏览器打开 `http://127.0.0.1:5173/` 确认。
- `OutboxList` / `ProgressView` 的统计卡外层仍是 `el-row` + 固定 `:span` 栅格，未改为 `.ys-stat-cards` 的 flex 布局
  （窄屏下换行不整齐，属于「窄屏响应式」的范围）。
- `NotificationDrawer.vue`、`CodeRuleList.vue`、`WarehouseList.vue`、`DepartmentList.vue` 的局部样式尚未统一。
- 窄屏响应式与暗色主题仍未实现，因此无可执行用例。

## 十三、窄屏响应式（本轮增量）

### 13.1 背景

第十二节统一了观感，但布局仍按「宽屏」假设写死：侧边栏恒定 220px，统计卡用
`el-row` + 固定 `:span="4"` / `:span="6"`，列多的表格只能靠挤压列宽。
在 1366×768 的笔记本上表格可用宽度不足，一屏读不下几列。本轮只改前端布局与样式（后端零改动）。

### 13.2 断点约定

| 断点 | 处理 |
| --- | --- |
| ≤1440px | 表格改为容器内横向滚动（`.ys-table-card { overflow-x: auto }` + `.ys-table-card .el-table { min-width: 720px }`），不再把每列压到不可读 |
| ≤1200px | **侧边栏自动折叠为图标态**；页面内边距 16 → 12px；统计卡最小宽 168 → 140px |
| ≤992px | 标题与操作区上下排列；统计卡整行铺满；`.ys-grid-2` 双列改单列；弹窗与抽屉宽度铺到 92% |

`useAutoCollapse.ts` 的 `NARROW_BREAKPOINT = 1200` 与样式表里的 `@media (max-width: 1200px)`
必须一致，已由 `responsive.spec.ts` 断言两边相等——「JS 与 CSS 各写一份断点」是最容易改一边忘一边的地方。

弹窗与抽屉的宽度是 Element Plus 的**内联样式**（`width: 600px` 之类），普通选择器无法覆盖，
因此那两条规则必须带 `!important`，样式表里已就地注明原因，避免后人误删。

### 13.3 侧边栏自动折叠规则

| 场景 | 行为 |
| --- | --- |
| 宽屏加载 | 展开 |
| 窄屏加载（≤1200px） | 折叠（setup 阶段先取一次视口宽度，不会出现「先展开再跳变」） |
| 用户在窄屏点折叠按钮 | 手动展开，并保持到视口变化 |
| 视口跨过断点 | 清除手动偏好，回到「跟随视口」，避免窗口拉宽后侧边栏仍停在收起状态 |
| 组件卸载 | 移除 resize 与 matchMedia 监听，离开页面后不再改状态 |

### 13.4 涉及文件

| 文件 | 变更 |
| --- | --- |
| `frontend/src/composables/useAutoCollapse.ts` | 新增：视口 → 折叠状态（手动偏好优先，跨断点重置） |
| `frontend/src/layouts/BasicLayout.vue` | 改用该组合式函数；折叠按钮补 `title` 提示（展开/收起） |
| `frontend/src/styles/index.css` | 新增第 9 节「窄屏响应式」；新增 `.ys-grid-2`；`.ys-stat-card` 改为 `flex: 1 1 168px` |
| `frontend/src/views/integration/OutboxList.vue` | 统计卡由 `el-row` + `:span="4"` 改为 `.ys-stat-cards` flex |
| `frontend/src/views/system/ProgressView.vue` | 统计卡同上；双列区块由 `el-row` + `:span="12"` 改为 `.ys-grid-2` |
| `frontend/tests/responsive.spec.ts` | 新增 15 条：断点一致性 + 响应式规则 + 自动折叠行为 + 视图不再用固定栅格 |

### 13.5 验证结果（真实输出）

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| 类型检查 | `npm run typecheck` | 退出码 0（无输出） |
| 组件测试 | `npm run test` | `Test Files 9 passed (9)` / `Tests 125 passed (125)` |
| 生产构建 | `npm run build` | `✓ built in 11.65s` |
| 一键冒烟 | `scripts/smoke_check.ps1` | 7 个步骤全部通过，退出码 0（`全部检查通过。`） |
| 样式表编码与配平 | `.tmp/checkcss.py` | BOM False / CRLF 0 / 23034 字节 / 花括号 151 = 151 |
| 共享类重名扫描 | `.tmp/scan_styles.py` | 15 个带样式块的 .vue（原 16：`OutboxList` 的空样式块随统计卡改造删除）；重名 **0** |
| 开发服务器下发 | `GET /src/styles/index.css`、`GET /src/layouts/BasicLayout.vue` | 均 200，样式含 `@media`，布局模块含 `useAutoCollapse` / `toggleCollapsed` |

`responsive.spec.ts`（15 条，全部通过）覆盖：断点一致性、三个断点的规则内容、
`.ys-grid-2` 与 `.ys-stat-card` 的默认值、宽屏/窄屏初始态、手动切换、
视口跨断点重置偏好、卸载后不再响应 resize，以及三个文件「不再使用固定栅格 / 固定展开状态」。

### 13.6 未完成 / 未执行

- **浏览器截图级像素校验未执行**（原因同 §11.6，浏览器自动化被安全策略拒绝，非人工拒绝）；
  真实观感与「拖动窗口时侧边栏是否平滑折叠」需人工在浏览器里拖窗口确认。
- 只覆盖统计卡栅格与表格容器：`EntityListPage` 的筛选栏在窄屏仍靠换行，未做「展开/收起筛选面板」。
- ≤768px（手机竖屏）未单独处理，未做移动端专用布局。
- 暗色主题未实现；触摸手势、横竖屏旋转未验证。

## 十四、阶段 3 第一步：BOM 与工艺路线版本快照（本轮增量）

### 14.1 背景与范围

阶段 2 结束时本文件 §10.9 给出的下一步是「阶段 3：BOM/工艺版本快照 → MRP → MES 工单报工 → QMS 检验单」。
本轮只做**第一步**：把工程数据（BOM、工艺路线）按任务书 9.5 建成**版本化、可审批、可快照**的实体，
为 MRP 展开与 MES 工单下达提供唯一的数据来源。**本轮不碰库存**（`planning` 不 import 任何 wms 服务）。

| 任务书 9.5 要求 | 本轮实现 |
| --- | --- |
| BOM 版本、生效日期、审核状态 | `planning.Bom`（`version_no` + `effective_from/to` + `status`），走 `workflow` 审批 |
| SKU 差异用料、标准用量、损耗 | `Bom.sku`（空=款式通用，填写=该 SKU 差异版本）+ `BomLine.quantity` / `loss_rate` / `gross_quantity` |
| 替代料审批 | `BomLine.line_type=substitute` + `substitute_for` 指向同一 BOM 的正常用料行；随所属版本一起审批 |
| 工艺路线、标准工时、设备要求、工序质检点 | `planning.Routing` + `RoutingStep.standard_hours` / `equipment_requirement` / `is_quality_gate` |
| 默认工艺 裁剪→缝制→整烫→检验→包装 | `DEFAULT_ROUTING_STEPS`；不传工序即套用，「检验」自动带质检点标记 |
| 工单下达保存版本快照 | `build_bom_snapshot()` / `build_routing_snapshot()` 输出不可变 dict；工单本身在阶段 3 后续增量实现 |

**范围边界（本轮明确不做）**：不建空的快照表（快照由 MES 工单在阶段 3 后续增量落库）；
不做 MRP 展开与建议转单；不做 MES 工单/派工/报工；不做 QMS 检验单；不引入 signals
（版本与状态迁移只由 `services` 修改，任务书 4.3/4.4）。

### 14.2 已实现功能

**BOM**

1. **版本化**：同一「款式 + SKU 范围」可有多个版本；草稿可改（`is_editable`），提交后冻结，审核通过后生效。
2. **同一范围同时只有一个生效版本**：审核通过时旧 `approved` 版本自动转 `obsolete`（只改状态，内容与快照不动）。
3. **变更只能派生新版本**：`POST /planning/boms/{id}/new-version/` 复制明细行生成 `version_no + 1` 的新草稿；
   已审核版本不被覆盖，因此**已下达工单引用的版本内容不变**（任务书 9.5、14.2 必测案例 13）。
4. **用量口径**：`quantity` 是单位成品净用量；`gross_quantity = quantity × (1 + loss_rate)` **由后端计算**，
   前端传入会被忽略；统一按数量精度 **6 位小数 `ROUND_HALF_UP`** 舍入，且**只在这一处**舍入（任务书 5.3）。
5. **明细校验**（序列化器 + 服务层两级，绕过接口直接调服务也拦得住）：用量必须 > 0；损耗率 ∈ [0, 1)；
   至少 1 行；同一 BOM 内同一正常用料不可重复（`NORMAL_MATERIAL_DUPLICATED`）；替代料行必须指向同一 BOM
   内的正常用料行、正常用料行不得指向替代料行（`SUBSTITUTE_TARGET_INVALID`）；生效区间必须有序；
   款式 / SKU / 物料必须属于同一公司。
6. **状态机**：`draft → submitted → approved / rejected`；`submitted` 可撤回（`withdraw` 回 `draft`）；
   `obsolete` 必须填原因；审核中不允许派生新版本或作废。
7. **快照一致**：`GET /planning/boms/{id}/snapshot/` 与 `services.build_bom_snapshot()` 输出**逐字段相等**
   （`test_bom_snapshot_service_equals_api` 断言），且派生新版本后旧版本快照不变。

**工艺路线**

8. 版本 / 审批 / 作废 / 派生新版本规则与 BOM **完全一致**（共用同一套服务骨架），工序随版本冻结。
9. 工序校验：`sequence` 在同一路线内唯一、`standard_hours ≥ 0`、至少 1 道工序；
   `is_quality_gate` 标记工序质检点（MES 必须在该工序产生检验记录，任务书 9.5）。
10. **默认工艺**：不传 `steps` 时套用 `DEFAULT_ROUTING_STEPS`（裁剪 / 缝制 / 整烫 / **检验(质检点)** / 包装）；
    **显式传空列表会被拒绝**（`ROUTING_STEP_REQUIRED`）——避免把错误输入悄悄变成"有效"的默认工艺。
11. 工序可挂车间（`workshop`，受数据范围校验，越权车间被拒）；`equipment_requirement` 记录设备要求。

**审批集成**

12. 复用 `workflow`，**不新建审批体系**：`apps/planning/apps.py::PlanningConfig.ready()` 显式
    `register_biz_handler("planning.bom" / "planning.routing", ...)`，审批结果回写单据状态并（通过时）执行版本切换。
13. **没有审批模板时直接拒绝提交**（`APPROVAL_TEMPLATE_NOT_FOUND`），不静默跳过审批；
    `seed_demo` 已为两个 biz_type 各建 1 个模板（`AP-BOM` / `AP-ROUTING`）。
14. 审批通过 / 驳回 / 撤回都留痕：单据状态 + `approved_by` / `approved_at` + `AuditLog`。

**数值与一致性**

15. 全程 `Decimal`，禁止 float；API 中 Decimal 以字符串输出（任务书 5.3）。
16. 服务层额外做**公司一致性校验**（`_assert_company_scope` + BOM 明细逐行校验物料公司），
    覆盖"绕过接口直接调用服务"的路径（`test_service_requires_reason_to_obsolete` 等同组用例）。
17. 乐观锁：`version` 字段，PATCH 传过时版本返回 409（`test_optimistic_lock_rejects_stale_version`）。

### 14.3 数据迁移

新增 App `backend/apps/planning/`，迁移 `planning/migrations/0001_initial.py`：**4 张表 + 17 个数据库约束**。

| 表 | 关键约束 |
| --- | --- |
| `planning_bom` | `uq_bom_company_code`、`uq_bom_scope_version`、`ck_bom_version_positive`、`ck_bom_effective_range` |
| `planning_bomline` | `uq_bom_line_no`、`ck_bom_line_quantity_positive`、`ck_bom_line_loss_non_negative`、`ck_bom_line_loss_lt_one` |
| `planning_routing` | `uq_routing_company_code`、`uq_routing_scope_version`、`ck_routing_version_positive` |
| `planning_routingstep` | `uq_routing_step_sequence`、`ck_routing_step_sequence_positive`、`ck_routing_step_hours_non_negative` |

**规范化唯一键（任务书 5.4 重点）**：MySQL 的联合唯一索引不约束 `NULL`（多行 NULL 互不冲突），
因此**不能**直接对 `(company, style, sku, version_no)` 建唯一索引。实现上把范围压成非空字符串
`scope_key`（`engineering_scope_key()` → `"style:1"` 或 `"style:1:sku:3"`），唯一约束建在
`(company, scope_key, version_no)` 上 —— 与 `wms_inventorybalance.dimension_key` **同一个坑、同一套解法**，
已由 `test_scope_version_unique_constraint_is_enforced`（真实 `IntegrityError`）覆盖。

**「同一范围只有一个生效版本」不用索引兜底**：MySQL 没有部分唯一索引（`WHERE status='approved'`），
因此靠服务层在 `transaction.atomic()` + `select_for_update()` 内切换状态，并在锁内重新校验。

配置接线：`config/settings/base.py` 的 `LOCAL_APPS` 新增 `"apps.planning"`；
`config/urls.py` 新增 `path("api/v1/planning/", include("apps.planning.urls"))`。

### 14.4 页面与 API

| 页面 | 前端组件 | 路由 | 菜单权限 |
| --- | --- | --- | --- |
| 物料清单（BOM） | `views/planning/BomList.vue` | `/planning/boms` | `planning.bom.view` |
| 工艺路线 | `views/planning/RoutingList.vue` | `/planning/routings` | `planning.routing.view` |

一级菜单目录「计划管理」（`/planning`，`sort_order=75`，排在「仓储管理」80 之前）。
两个页面均基于共享组件 `EntityListPage.vue`（筛选 / 分页 / 排序 / 详情抽屉 / 表单弹窗 / 状态标签 /
审批轨迹 / 防重复提交 / 离开未保存提示），未新增页面骨架代码。

| 方法与路径 | 说明 | 权限点 |
| --- | --- | --- |
| `GET/POST /api/v1/planning/boms/` | 列表 / 新建（含明细行，后端算含损耗用量） | `planning.bom.view` / `.create` |
| `GET/PATCH /api/v1/planning/boms/{id}/` | 详情 / 改草稿（PATCH 带 `expected_version` 乐观锁） | `.view` / `.update` |
| `POST /api/v1/planning/boms/{id}/submit/` | 提交审批（无模板即拒绝） | `.submit` |
| `POST /api/v1/planning/boms/{id}/obsolete/` | 作废版本（必填原因） | `.obsolete` |
| `POST /api/v1/planning/boms/{id}/new-version/` | 派生新草稿版本（唯一变更方式） | `.create` |
| `GET /api/v1/planning/boms/{id}/snapshot/` | 版本快照（供 MES 工单引用） | `.view` |
| `POST /api/v1/planning/boms/{id}/set-active/` | 启停（基类提供，任务书 5.5 主数据优先停用） | `planning.bom.update` |
| `/api/v1/planning/routings/` 下同样 7 个端点 | 工艺路线，规则与 BOM 一致 | `planning.routing.*` |

**不提供 `DELETE`**（任务书 5.5：已审核单据不物理删除，工程数据用「作废 + 派生新版本」）。
OpenAPI 由 drf-spectacular 自动同步：`GET /api/v1/schema/` 返回 200，其中 planning 共 **14 个路径**（每个视图集 7 个：`/`、`/{id}/`、`submit/`、`obsolete/`、`new-version/`、`snapshot/`、`set-active/`）。
`GET /api/v1/meta/` 新增 3 个枚举键：`bom_statuses`、`routing_statuses`、`bom_line_types`。

### 14.5 权限

新增 **10 个权限点**（`planning.bom.view/create/update/submit/obsolete`、
`planning.routing.view/create/update/submit/obsolete`）与 **3 个菜单**（1 个目录 + 2 个页面），
全部登记在 `apps/identity/permissions_registry.py`，由 `bootstrap_system` 幂等同步到数据库
（`apps/core/checks.py` 会在权限/菜单未登记时让 `manage.py check` 失败，因此不存在"只加接口不加权限"的漏网）。

新增内置角色 **`planning_admin`（计划管理员）**，数据范围 `COMPANY`，共 20 个权限
（BOM / 工艺路线全部动作 + 物料、款式查看等）。

权限边界已实测：`planning.routing.*` **不会**顺带授予 BOM 写权限
（`test_routing_permission_does_not_grant_bom_write`）；只读用户不能新建（`test_view_only_user_cannot_create_bom`）；
跨公司对象被拒（`test_cross_company_objects_are_rejected`）；匿名访问 `403`
（`test_planning_endpoints_require_authentication`）。

### 14.6 演示数据

`seed_demo` 新增 `_engineering()`（幂等，可重复执行）：

| 数据 | 内容 |
| --- | --- |
| 审批模板 | `AP-BOM`（biz_type `planning.bom`）、`AP-ROUTING`（`planning.routing`），单节点，审批人 `demo_dept_manager` |
| BOM | `BOM202609180001` v1，款式通用（`YS-W-2401`），**5 行明细**，已提交并审批通过 |
| 工艺路线 | `RT202609180001` v1，**5 道工序**：裁剪 / 缝制 / 整烫 / 检验（`is_quality_gate=True`）/ 包装，已审批通过 |
| 编码规则 | `BOM{YYYYMMDD}{SEQ:4}`、`RT{YYYYMMDD}{SEQ:4}`（`bootstrap_system` 同步，共 13 条） |

真实库中读取到的演示 BOM 明细（面料行）：`quantity=0.280000`、`loss_rate=0.0600000000`、
`gross_quantity=0.296800` —— 含损耗用量由后端算出且已按 6 位小数量化。

### 14.7 测试执行结果（真实输出）

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| Django 系统检查 | `manage.py check` | `System check identified no issues (0 silenced).` |
| 迁移一致性 | `manage.py makemigrations --check --dry-run` | `No changes detected` |
| 静态检查 | `ruff check apps config tests` | `All checks passed!` |
| 后端测试（全量） | `pytest tests -q --reuse-db` | `267 passed in 105.84s (0:01:45)` |
| 计划模块用例 | `pytest tests/test_planning.py` | `50 passed in 21.40s` |
| 类型检查 | `npm run typecheck` | 退出码 0（无输出） |
| 组件测试 | `npm run test` | `Test Files 9 passed (9)` / `Tests 127 passed (127)` |
| 生产构建 | `npm run build` | `✓ built in 13.14s`（含 `BomList-B_Xq9rdS.js`、`RoutingList-BoeDw3JC.js`） |

新增 `backend/tests/test_planning.py`：48 个测试函数 / **50 条用例**（含 2 个参数化），覆盖分组：
权限与数据范围、BOM 明细校验、版本自增与唯一约束、提交 / 审核 / 驳回 / 撤回、派生新版本、
快照不变性、作废必填原因、生效版本查询、审计留痕、工艺路线（默认工序 / 重复顺序 / 负标工 /
质检点 / 车间范围）、服务层公司校验与边界。前端两个新页面已被 `tests/router.spec.ts`（47 条）
与 `tests/views-compile.spec.ts`（菜单 fixture 逐组件编译）纳入回归。

一键冒烟 `scripts/smoke_check.ps1` 7 步全过（`django check` / `makemigrations --check` / `ruff` /
`pytest` / `vue-tsc` / `vitest` / `vite build`，退出码 0）。**注意**：本轮首跑冒烟脚本时 ruff 报出
4 处真实违规（导入顺序、2 个未使用导入、嵌套 `with`），修复后才通过 —— 详见 `docs/test-report.md` §15。

修复后复跑完整冒烟（最终状态，真实输出）：

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

### 14.8 启动验证步骤

```powershell
# 1) 迁移（含 planning 0001）
cd backend
.\.venv\Scripts\python.exe manage.py migrate
# 2) 系统初始化（同步 10 个权限点 / 3 个菜单 / 2 条编码规则 / planning_admin 角色）
.\.venv\Scripts\python.exe manage.py bootstrap_system
# 3) 演示数据（幂等；生产环境会被拒绝）
.\.venv\Scripts\python.exe manage.py seed_demo
# 4) 启动后端
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
# 5) 启动前端（另开一个终端）
cd ..\frontend
npm run dev
```

验证：浏览器打开 `http://127.0.0.1:5173/` → 左侧「计划管理」→「物料清单（BOM）」/「工艺路线」；
用 `admin` 登录可看到演示 BOM（5 行明细、含损耗用量只读）与工艺路线（5 道工序、检验为质检点）；
匿名 `GET http://127.0.0.1:8000/api/v1/planning/boms/` 返回 **403**，登录后返回 200。

### 14.9 未完成事项（阶段 3 剩余）

- **MRP 未开始**（任务书 10.6）：时间分段净需求、多层 BOM 展开、损耗、循环 BOM 检查、缺料清单、
  采购建议 / 生产建议、供需追溯、计算快照、建议审核转单。
- **MES 未开始**（任务书 10.7）：工单、线体排产、裁剪任务、派工、报工、在制转移、返工报废、完工入库。
  工单下达时必须保存 `build_bom_snapshot()` / `build_routing_snapshot()` 的结果（快照表届时落库）。
- **QMS 未开始**（任务书 10.9）：检验项目 / 标准 / 版本、来料 / 首件 / 过程 / 成品 / 出货检验、不合格处置。
  `procurement.receipt.inspect` 目前仍是**人工判定**，待升级为引用检验单（阶段 3 后续增量）。
- 工艺路线未与 `factory.Station.process_name`、阶段 4 的设备主数据建立外键关联，
  当前用文本 `workcenter` / `equipment_requirement` 记录。
- `standard_hours` 尚未参与任何计算（OEE 理论产能、工序效率在阶段 3/4 使用）。
- 无 BOM / 工艺路线的 Excel 导入导出（导入导出框架阶段 2 已有基础，本轮未接线）。
- 无 BOM 成本卷算（基础成本属阶段 7）。

### 14.10 下一阶段依赖

1. **MRP** 依赖本轮的 `services.get_effective_bom(company, style, sku)` 与 `BomLine.gross_quantity`，
   同时依赖阶段 2 的可用库存（统一库存服务）与采购在途（`procurement` 未收货数量）。
2. **MES 工单**依赖 `build_bom_snapshot()` / `build_routing_snapshot()`；落库前需把
   `docs/data-model.md` 的 BOM 章节与工单快照字段对齐，避免"快照结构 vs 源头字段"漂移。
3. **QMS** 用工艺路线的 `is_quality_gate` 决定"哪些工序必须产生检验记录"，
   与 `procurement.receipt.inspect` 的升级路径共用同一检验单实体。


## 十五、阶段 3 第二步：MRP（本轮增量）

### 15.1 背景与范围

任务书 10.6 要求 MRP 具备：时间分段净需求、多层 BOM 展开、损耗计算、循环 BOM 检查、缺料清单、
采购建议、生产建议、供需追溯、计算快照、建议审核转单。本轮实现**全部条目**，但按任务书
2.3 与「先做可运行增量」的要求划出明确边界：

- **只读**库存与在途，**不写**任何库存 / 采购 / 生产单据；建议转单只创建**草稿采购申请**，
  后续仍走采购审批（MRP 不绕过审批产生采购承诺）。
- **生产建议本轮明确拒绝转单**（`PRODUCTION_ORDER_NOT_IMPLEMENTED`），MES 工单属阶段 3 第三步，
  **不伪造工单**。
- MRP 需求来源只有**销售订单**；在制供给、替代料、提前期与批量规则均未参与计算（见
  `docs/assumptions.md` §四之六，逐条列明）。

### 15.2 已实现功能

**计算内核（`apps/planning/mrp.py`，纯同步、无 Celery）**

- **低层码（low-level code）分层净算**：先算父件再算子件，父件净需求展开子件需求后在本轮循环内
  动态产生，保证同一物料在多层 BOM 中只净算一次（不多算、不漏算）。
- **时间分段（bucket）净需求**：`day` 与 `week` 两种分段；`week` 归一到周一；逾期需求统一落在
  第一个分段；区间外需求不参与计算。
- **供给认读**：现有**可用库存**（`on_hand − frozen − reserved`，且**只认合格质量状态**）+
  采购**未收货在途**（`purchase` 订单未收数量，按承诺交期落段）。
- **BOM 展开**：只展 `line_type=normal` 的行（替代料不展开），用量取 `BomLine.gross_quantity`
  （= 净用量 × (1+损耗率)，含损耗），版本来自阶段 3 第一步的
  `services.get_effective_bom(company, style, sku)`。
- **异常与保护**：循环 BOM（`BOM_CYCLE_DETECTED`）、层级超限（`BOM_TOO_DEEP`，`MAX_LEVEL=10`）、
  非法分段 / 区间（`INVALID_BUCKET` / `INVALID_HORIZON`）均拒绝；**失败也落一条 `failed` 运行记录**并写明原因。
- **建议类型规则**：有生效 BOM 或分类属成品 / 半成品 → **生产建议**；否则 → **采购建议**；
  无生效 BOM 的成品会记入 `unexploded_materials`（演示"缺 BOM"告警），不伪造展开结果。
- **快照与追溯**：需求行保存 `source_type/source_id/source_no/source_line_no` 与 `path` 来源路径，
  建议的 `detail` 保存 `level` / `bom_code` / `bom_version_no` / `trace` / `demand_sources`，
  计算参数完整存入 `MrpRun.parameters`（含 `lead_time_mode=lot_for_lot`、`in_progress_supply=not_implemented`、
  `frozen_and_reserved=excluded_from_available`、`include_substitutes=false`）。

**转单与状态机**

- `convert_suggestion()`：锁内重取建议（`select_for_update`）→ 校验运行状态 → 校验未转单 →
  校验运行仍是**最新已完成运行**（否则 `SUGGESTION_STALE`）→ 校验物料启用 → 生产建议拒绝 →
  调 `procurement.services.create_requisition()` 建**草稿**采购申请 →
  写 `integration.DocumentLink`（`generated_from`）→ 建议置 `converted` → 审计 + Outbox 事件（同事务）。
- `cancel_suggestion()`：**必填原因**，已转单不可取消，已取消不可转单。
- `archive_run()`：归档运行（`UPDATE` 审计），归档后其建议不可再转单（`MRP_RUN_NOT_ACTIVE`）。

**只读边界（已用测试锁定）**：`test_mrp_is_read_only_for_inventory` 断言运算前后
`InventoryBalance` / `StockLedger` 行数与数量完全不变。

### 15.3 数据迁移

| 迁移文件 | 内容 |
| --- | --- |
| `backend/apps/planning/migrations/0002_mrprun_mrpdemandline_mrpsuggestion_mrpsupplyline_and_more.py` | 4 张表（`MrpRun` / `MrpDemandLine` / `MrpSupplyLine` / `MrpSuggestion`）+ 8 个约束 |

约束明细（4 表 × 2 条 = 8 条）：
`uq_mrp_run_company_no`（同一公司运行编号唯一）、`ck_mrp_horizon_ordered`（区间不可颠倒）、
`uq_mrp_demand_line_no` / `ck_mrp_demand_quantity_positive`、`uq_mrp_supply_line_no` /
`ck_mrp_supply_quantity_positive`、`uq_mrp_suggestion_line_no` / `ck_mrp_suggestion_quantity_positive`
（后三组分别为「同一运行内行号唯一」与「数量必须为正」）。

> 说明：`bucket` / `status` 的**枚举取值**由 `choices` 在应用层校验，未建 `CHECK` 约束
> （与既有模块一致）；「同一建议不得重复转单」由服务层状态机 + `select_for_update` 保证，
> 数据库层通过建议行号唯一与目标单据的外键关系兜底。

已提交迁移文件累计 **18 个**。

### 15.4 页面与 API

| 方法与路径 | 说明 | 权限 |
| --- | --- | --- |
| `GET /api/v1/planning/mrp-runs/` | 运行列表（含 `demand_count` / `supply_count` / `suggestion_count` 注记） | `planning.mrp.view` |
| `POST /api/v1/planning/mrp-runs/` | 运行一次 MRP（同步计算后返回运行与 `summary`） | `planning.mrp.run` |
| `GET /api/v1/planning/mrp-runs/{id}/demands/` | 展开后的需求行（含来源路径） | `planning.mrp.view` |
| `GET /api/v1/planning/mrp-runs/{id}/supplies/` | 本次认到的供给（可用库存 / 采购在途） | `planning.mrp.view` |
| `GET /api/v1/planning/mrp-runs/{id}/suggestions/` | 缺料清单 / 建议清单（可按类型过滤） | `planning.mrp.view` |
| `POST /api/v1/planning/mrp-runs/{id}/archive/` | 归档运行（必填原因） | `planning.mrp.archive` |
| `GET /api/v1/planning/mrp-suggestions/` | 建议列表（支持 `run_id` / `suggestion_type` / `status` / `material_id` 过滤） | `planning.mrp.view` |
| `POST /api/v1/planning/mrp-suggestions/{id}/convert/` | 采购建议 → 草稿采购申请 | `planning.mrp.convert` **+** `procurement.requisition.create` |
| `POST /api/v1/planning/mrp-suggestions/{id}/cancel/` | 取消建议（必填原因） | `planning.mrp.cancel` |

前端新增 2 个页面（均为真实可用页面，非静态原型）：

- `frontend/src/views/planning/MrpRunList.vue` ：`/planning/mrp-runs`。运行表单（**公司选择框**、
  需求区间、按日 / 按周分段、限定仓库、备注）、运行列表、详情抽屉（摘要 + 需求行 / 供给行 / 缺料建议三个页签）、归档。
- `frontend/src/views/planning/MrpSuggestionList.vue` ：`/planning/mrp-suggestions`。建议列表
  （支持 `?run_id=` 初始过滤）、转采购申请（填写需求日期）、取消（必填原因）、详情抽屉含分段净算过程。

`POST /api/v1/planning/mrp-runs/` 不传 `company_id` 时若用户无归属公司会返回 **400 `COMPANY_REQUIRED`**
（超级管理员 `admin` 即属此情况），前端因此提供公司选择框；服务端仍会按数据范围重新校验公司。

### 15.5 权限

新增 **5 个权限点**（`planning.mrp.view` / `run` / `convert` / `cancel` / `archive`）与 **2 个菜单**
（`planning.mrp`、`planning.mrp_suggestion`，`planning` 目录下 `sort_order` 78 / 79），
全部登记在 `apps/identity/permissions_registry.py`，由 `bootstrap_system` 幂等同步。

- `planning_admin` 角色新增 5 个 MRP 权限 + `procurement.requisition.view/create`
  （**转单必需**：MRP 转单落点是采购申请，缺该权限时服务层会拒绝）。
- `procurement_admin` 角色新增 `planning.mrp.view`（只读缺料清单，便于采购据此备货）。
- 权限边界已实测：`planning.mrp.*` **不会**顺带授予其它模块权限；只有 `planning.mrp.view` 的用户
  不能运行 MRP；有 `planning.mrp.convert` 但无 `procurement.requisition.create` 时转单仍被拒绝。

同步真实输出：

```text
权限点：新增 6，更新 167，注册表共 173 条。
菜单：新增 2，更新 54，注册表共 56 条。
编码规则：新增 1，共计 14 条。
```

（"新增 6"含本轮补登记的 `masterdata.identifier.update`，见 §15.7 缺陷修复。）

### 15.6 演示数据

`seed_demo` 新增 `_mrp()`（幂等，可重复执行；第二次执行新建 0 条）：

| 数据 | 内容 |
| --- | --- |
| 需求单 | `SO-MRP-0001`：客户 `CUS-001`，`YS-W-2401-BK-L` **300 件**，单价 399，金额 135,261 元，走多级金额审批直至 `approved` 且**保持未发货** |
| 审批推进 | `_approve_fully()` 按模板节点审批人角色（`demo_dept_manager` / `demo_gm` / `demo_finance`）循环推进到 `approved`，避免金额路由导致停在"审批中" |
| MRP 运行 | `run_mrp(horizon=今天+90 天, bucket=day)`；已存在 `completed` 运行则跳过（幂等） |
| 建议转单 | 取第 1 条 `purchase` + `open` 建议调 `convert_suggestion()`，产出**草稿采购申请** |

真实库中的运行结果（`MRP202609180004`，一次真实运算）：

```text
item_count=7  level_count=2  bucket_count=3
demand_quantity=1422.300000  supply_quantity=1866.000000  suggestion_quantity=1213.260000
demand_line_count=7  supply_line_count=3  suggestion_count=5
purchase_suggestion_count=4  production_suggestion_count=1  unexploded_materials=[]
```

需求行示例：`L0 SO-MRP-0001 成品 300.000000`（`exploded=True`）展开出 5 条 `L1 parent_item` 子件需求
（面料 `89.040000`、缝纫线 `1.260000`、主唛 `306.000000`、包装 303.000000 ×2）；
`SO-DEMO-0002`（120 件、成品无 BOM）产生生产建议并进入 `unexploded_materials`，
用于演示"成品缺 BOM"告警（**故意保留**，见 `docs/assumptions.md` §四之六）。

### 15.7 测试执行结果（真实输出）

| 检查 | 命令 | 真实输出 |
| --- | --- | --- |
| Django 系统检查 | `manage.py check` | `System check identified no issues (0 silenced).` |
| 迁移一致性 | `manage.py makemigrations --check --dry-run` | `No changes detected` |
| 静态检查 | `ruff check apps config tests` | `All checks passed!` |
| 后端测试（全量） | `pytest backend/tests -q --reuse-db` | `301 passed in 112.01s (0:01:52)` |
| MRP 用例 | `pytest backend/tests/test_mrp.py` | `32 passed` |
| 类型检查 | `npm run typecheck` | 退出码 0 |
| 组件测试 | `npm run test` | `Test Files 9 passed (9)` / `Tests 129 passed (129)` |
| 生产构建 | `npm run build` | `✓ built in 11.99s`（含 `MrpRunList-*.js`、`MrpSuggestionList-*.js`） |
| 一键冒烟 | `scripts/smoke_check.ps1` | 7 步全过，`全部检查通过。` |
| 真实 HTTP 链路 | 临时验收脚本（`urllib` + CookieJar，对运行中的开发服务器逐项请求；已按收尾约定删除） | **29 项请求检查全部通过**（清单见 `docs/test-report.md` §16.5） |
| 经 Vite 代理的浏览器路径 | 同上脚本，经 `127.0.0.1:5173` 并带浏览器 `Origin`/`Referer` | **5 项检查通过**（登录 / 会话 / MRP 查询 200，无令牌登录 403），见 §16.5b |

`backend/tests/test_mrp.py` 共 **32 条用例**，覆盖：净算（含在途、冻结 / 占用、质量状态、逾期落段、
区间外忽略、部分发货用剩余量、草稿单不产生需求）、展开（父件净需求展开、低层码只净算一次）、
异常（循环 BOM 记 `failed` 运行、库存只读、非法参数、按周归一到周一、审计与 Outbox 同事务）、
转单与状态机（草稿申请 + 单据关联、重复转单、过期建议、生产建议拒绝、停用物料、取消必填原因、
归档后不可转单）、API（匿名 403、只读用户不能运行、缺权限不能转单、转单需采购申请权限、
运行与明细接口、参数校验、公司/仓库范围、权限不外溢、归档审计）。

**真实 HTTP 链路（`docs/test-report.md` §十六有完整清单）**：未登录 403 → 无 CSRF 令牌登录 403 →
取 token 后登录 200 → 缺 `company_id` 400 `COMPANY_REQUIRED` → 运行 MRP 201（7 需求 / 3 供给 / 5 建议）→
需求行、供给行、建议清单、`run_id` 过滤全部 200 → 旧运行建议转单 409 `SUGGESTION_STALE` →
归档旧运行 200 → 归档后转单 409 `MRP_RUN_NOT_ACTIVE` → 生产建议 409 `PRODUCTION_ORDER_NOT_IMPLEMENTED` →
采购建议转单 200（`PR202609180002`，`DocumentLink` `generated_from`）→ 重复转单 409 →
转出单据确为 `draft` → 取消缺原因 400、取消 200、已取消转单 409 → 退出登录后 403。
数据库侧核对：审计 5 条（运行创建 / 归档、建议转单 / 取消）、Outbox 事件 2 类 pending、单据关联 2 条。

**本轮修复的 7 个真实缺陷**（详见 `docs/test-report.md` §十六）：

1. `apps/core/checks.py` **从未被导入**——`yishang.E001`（视图声明未登记权限码）永远不会触发。
   修复：`CoreConfig.ready()` 显式 `from apps.core import checks`。修复后立刻抓出既有遗漏
   `masterdata.identifier.update` 未登记，已补。
2. MRP 低层码排序**预先过滤了"当前已有需求"的物料**，导致 BOM 展开出的子件需求永远不被净算
   （BOM 展开形同失效）。修复为按低层码全量遍历、无需求即 `continue`。
3. `MrpRunSerializer` 声明了 `demand_count` / `supply_count` / `suggestion_count` 但未加入
   `Meta.fields`，`/api/v1/planning/mrp-runs/` 一旦被访问即 `AssertionError`。
4. `seed_demo` 打印的是**转单前的建议实例**（`convert_suggestion` 内部 `select_for_update` 重新取行），
   日志里采购申请号为空。修复为使用服务返回值。
5. **登录接口缺少 CSRF 校验**（任务书 6.1「登录接口同样防护 CSRF」）：`LoginView` 清空了
   `authentication_classes`，而 DRF `SessionAuthentication` 只对**已登录会话**调用 `enforce_csrf`，
   匿名请求根本不校验 → 登录成为无 CSRF 防护的写接口。修复：
   `@method_decorator(csrf_protect, name="dispatch")`，并新增 2 条回归用例
   （`test_login_requires_csrf_token` / `test_login_succeeds_with_csrf_token`）。
6. `EntityListPage.vue` 缺 `initialFilters` prop，"按 `?run_id=` 打开建议页"无法生效（前端缺陷）。
7. `views/system/ProgressView.vue`（系统管理 → 实施进度）的阶段状态仍是初始快照——阶段 2、3 标为
   「未开始」，告警文案还声称"采购、销售、仓储单据不会出现在左侧导航"，与已实现的菜单和文档相反。
   管理员据此会得到**与事实相反**的实施状态（任务书 8.2 / 19.3）。已按 `docs/progress.md` §一
   的真实状态更新阶段 2/3 行、已完成 / 未完成清单与提示文案。

### 15.8 启动验证步骤

```powershell
# 1) 迁移（含 planning 0002：4 张 MRP 表）
cd backend
.\.venv\Scripts\python.exe manage.py migrate
# 2) 系统初始化（同步 5 个 MRP 权限点 / 2 个菜单 / 1 条 MRP 编码规则）
.\.venv\Scripts\python.exe manage.py bootstrap_system
# 3) 演示数据（幂等；生产环境会被拒绝）
.\.venv\Scripts\python.exe manage.py seed_demo
# 4) 启动后端
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
# 5) 启动前端（另开一个终端）
cd ..rontend
npm run dev
```

验证步骤：

1. 浏览器打开 `http://127.0.0.1:5173/`，用 `admin` 登录（口令取自 `backend/.env` 的 `YISHANG_ADMIN_PASSWORD`）。
2. 左侧「计划管理 → MRP 运算」→ 选择公司「新疆意尚智造科技有限公司」→ 需求区间默认今天起 90 天 → 点「运行 MRP」，
   列表出现新运行，`summary` 显示需求行 / 供给行 / 建议数。
3. 打开该运行详情 → 三个页签可看到需求行（含来源路径）、供给行（可用库存 / 采购在途）、缺料建议。
4. 左侧「计划管理 → 缺料与建议」→ 对一条**采购建议**点「转采购申请」→ 状态变「已转单」并显示申请号；
   再点一次应提示已转单；对**生产建议**点转单应提示"MES 尚未实现"。
5. 命令行复验：`GET http://127.0.0.1:8000/api/v1/planning/mrp-runs/` 匿名返回 **403**，登录后返回 200。

### 15.9 未完成事项（MRP 与阶段 3 剩余）

- **MRP 未做**（已在 `docs/assumptions.md` §四之六逐条登记）：
  采购提前期与批量规则（当前 `lot_for_lot`，不提前、不合并）、**在制供给**（`in_progress_supply=not_implemented`，
  MES 未实现故恒为 0）、**替代料参与净算**（当前只展 `normal` 行）、安全库存缓冲、
  除销售订单外的需求来源（生产计划 / 预测 / 安全库存补货）、**生产建议转工单**（等 MES）、
  MRP 的 Excel 导出与定时重算（Celery Beat）、多工厂 / 多仓库维度的独立净算（当前按公司 + 可选单仓过滤）。
- **MES 未开始**（任务书 10.7）：工单、线体排产、裁剪任务、派工、报工、在制转移、返工报废、完工入库。
  工单下达时必须保存 `build_bom_snapshot()` / `build_routing_snapshot()` 的结果。
- **QMS 未开始**（任务书 10.9）：`procurement.receipt.inspect` 目前仍是**人工判定**，待升级为引用检验单。
- 生产建议当前**只能线下评审**，缺 MES 工单落点；`PRODUCTION_ORDER_NOT_IMPLEMENTED` 是**刻意**的拒绝，不是缺陷。
- `SO-DEMO-0002`（成品无 BOM）会持续进入 `unexploded_materials`，属演示"缺 BOM"告警的**故意**数据。
- Celery Worker / Beat 未在本机启动，Outbox 事件处于 `pending`（未消费）——**未执行**。

### 15.10 下一阶段依赖

1. **MES 工单**：MRP 生产建议将在此转单（`convert_suggestion` 已预留分支与错误码），
   工单下达需保存 BOM / 工艺路线快照，并把工单"在制数量"回流成 MRP 的 `in_progress` 供给。
2. **QMS 检验单**：`procurement.receipt.inspect` 的人工判定升级为引用检验单后，
   MRP 的"可用库存"口径（只认合格质量状态）自动受益，无需改 MRP 代码。
3. **提前期与批量规则**：需要采购 / 生产的提前期数据，依赖阶段 4 的设备 / 产能数据与供应商交期统计。

## 十六、文档同步与项目使用说明（本轮增量）

**本轮性质**：不新增业务模块；只做「文档按最新代码对齐 + 新增项目使用说明」，
并给使用说明加一条**机器可校验**的同步保障（回应「代码更新后使用文档也要变」的要求）。

### 16.1 新增文档 `docs/user-guide.md`

| 章节 | 内容 |
| --- | --- |
| 一～二 | 文档定位与用法、平台能力边界（已可用 / 还没有 / 当前实测规模） |
| 三 | 环境准备、环境变量、首次启动、日常启动停止（含 `scripts/dev_*.ps1`）、访问地址、**数据库在哪里 / 怎么连接**、上传文件与日志 |
| 四～五 | 账号与权限（10 个演示账号、16 个内置角色及权限点数、四层权限）、界面结构、通用交互约定、**56 项菜单清单** |
| 六～七 | 按模块操作指南（基础资料 / 工厂排班 / 仓储库存 / 采购 / 销售 / BOM 与工艺 / MRP / 审批 / 系统管理）与三条端到端演练 |
| 八 | 测试与自检：一键冒烟 7 步、分步命令与**最近一次真实结果**、数据库自检、权限菜单自检 |
| 九 | 常见问题与错误码：认证权限 / 单据库存 / 计划 MRP / 环境类，全部取自代码中真实存在的 `code` |
| 十 | 未执行 / 未验证事项清单 |
| 十一 | **代码更新后本文档必须同步**：触发清单、每轮收尾清单、核对方法与兜底机制 |

### 16.2 新增机器可校验的「文档事实行」

- `docs/user-guide.md` §11.5 内嵌
  `<!-- yishang-doc-sync: permissions=173 menus=56 models=86 migrations=18 builtin_roles=13 -->`。
- 新增 `backend/tests/test_docs_sync.py`（7 条），把该行与代码里的权威来源逐项比对，并校验网页版是否最新：
  `identity.permissions_registry.PERMISSIONS` / `MENUS`、`django.apps.get_models()`（受管且非自动生成）、
  `backend/apps/*/migrations/0*.py` 文件数、`bootstrap_system.BUILTIN_ROLES`。
- **反向验证（真做）**：临时把事实行改成 `menus=99` 后单跑该用例，按预期失败并提示
  「docs/user-guide.md 的事实行已过期：menus=99，代码实际为 56」（`1 failed, 5 passed`）；已还原，复原后 `6 passed`。
- 效果：以后**代码里的权限点 / 菜单 / 模型 / 迁移 / 内置角色数量一变**，用例即失败，
  强制同步使用说明，不再依赖自觉。

### 16.3 按最新代码修正的文档

| 文件 | 修正内容 |
| --- | --- |
| `docs/acceptance.md` | 顶部加「最新核对（2026-09-18）」块（173 权限 / 56 菜单 / 86 模型 / 92 表 / 18 迁移 / 后端 307 + 前端 129）；阶段 0 表「**当前 71 张**」→ 92 张；「后端 112 / 前端 60」标注为该阶段当时快照并给出最新值 |
| `docs/inventory-rules.md` | §八 第 3 条原写「冻结/解冻与占用/释放均无业务入口」**已过时**：改为占用/释放已由 `reserve_stock()` / `release_reservation()` / `release_reservations_for_biz()` 落地（销售订单占用、销售发货、销售退货、MRP 只读扣减），**冻结/解冻仍无入口** |
| `docs/requirements-matrix.md` | §一之六「明确未包含」移除 MRP（已由 §一之七 交付）；`REQ-7.4-01` 补注「MRP 为同步计算，不经 Celery（ADR-09）」；`REQ-12.1-01` 由「MRP / MES 未实现」→「MRP 已打通，MES 工单 / 报工 / 成品入库未实现」；`REQ-20-16` 测试数更新；新增 `REQ-14.1-08` 文档一致性校验 |
| `docs/api-conventions.md` | §九 Celery 长任务清单移除 MRP，并新增一条「MRP 为同步计算（ADR-09），不经 Celery」 |
| `README.md` | 文档地图新增 `docs/user-guide.md` 并置顶（标注「面向使用者，先看这份」）；登录账号段与「下一步」指向使用说明及其 §十一 同步规则 |
| `docs/deployment.md` | 顶部加交叉引用：使用者操作手册见 `user-guide.md`，**启动命令与环境变量变化必须同步其 §三** |
| `docs/progress.md` | §5.2 补注 `user-guide.md` 为后续新增，文档总数 17 份；§一 当前状态总览加使用说明指引 |

### 16.4 本轮执行的检查（真实输出）

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| Django 自检 | `manage.py check` | `System check identified no issues (0 silenced).` |
| 迁移无漂移 | `manage.py makemigrations --check --dry-run` | `No changes detected` |
| 后端静态检查 | `ruff check apps config tests` | `All checks passed!` |
| 后端全量测试 | `pytest tests -q --reuse-db` | **`308 passed in 101.34s`**（原 301 + 新增 7 条文档同步用例） |
| 文档同步用例单跑 | `pytest tests/test_docs_sync.py -q` | `7 passed` |
| 反向验证 | 故意改错事实行后单跑 | `1 failed, 5 passed`（**按预期失败**，已还原） |
| 网页版是最新的 | `scripts/build_user_guide.py --check` | `使用说明网页版是最新的。` |

前端 `typecheck` / `vitest` / `build` 本轮**未重跑**：本轮未改动任何前端代码。

### 16.5 使用说明网页版（给客户直接看）

`docs/user-guide.md` 现在同时产出**一份自包含的单文件网页**，便于直接交付客户：

| 产物 | 位置 | 用途 |
| --- | --- | --- |
| `docs/user-guide.html` | 仓库内 | 单文件、离线可用，双击打开或作为附件发送 |
| `frontend/public/guide.html` | 随前端发布 | 浏览器访问 `/guide.html`（开发 `http://127.0.0.1:5173/guide.html`） |

- 生成器：新增 `scripts/build_user_guide.py`（**纯标准库**，不引入 npm/pip 依赖）。
  只实现 `user-guide.md` 实际用到的 Markdown 子集（标题 / 表格 / 围栏代码 / 引用 / 列表 /
  行内代码与加粗），输出左侧**可搜索目录**、平台配色的表格与代码块、
  「打印 / 导出 PDF」按钮、窄屏自适应；**CSS/JS 全部内联，无外链无 CDN**。
- 系统入口：顶部工具栏新增「使用说明」按钮，个人中心下拉新增「使用说明」（打开 `/guide.html`）。
- 防过期：`tests/test_docs_sync.py` 新增 1 条用例执行 `build_user_guide.py --check`，
  比对两份产物与 Markdown 源是否一致——**改了 Markdown 忘了重新生成就会测试失败**。
- 生成器两个真实缺陷已修：① `**加粗**` 内含行内代码时不再漏转；② 标题锚点不再保留全角标点。
- 结构校验（真实执行）：Markdown 28 张表 ↔ HTML 28 张表；11 个 h2 / 44 个 h3 / 10 个代码块；
  目录 55 项且锚点全部命中；标签配对无异常；加粗标记 0 处残留。

> ⚠️ `frontend/public/` 由 nginx 作为静态资源直接发布、**不校验登录**；
> 如说明中含不便外发的内容，请只把 `docs/user-guide.html` 发给客户，
> 或为 `/guide.html` 单独加访问控制。该提醒已写入 `docs/user-guide.md` §11.7。

### 16.6 未完成事项

- 文档**正文**（菜单名称、操作步骤、错误码解释）没有自动校验，只能按
  `docs/user-guide.md` §11.3 的收尾清单人工维护——这是已知缺口，已写入该文档 §十。
- 使用说明中的界面截图、≤768px 手机布局、浏览器截图级校验：**未执行**。
- 前端测试本轮未重跑（无前端改动）。

### 16.7 下一阶段依赖

阶段 3 第三步：**MES 工单与报工 → QMS 检验单**。MES 落地后必须同步
`docs/user-guide.md` 的 §二（能力边界）、§五（菜单清单）、§六（操作指南）、
§九（`PRODUCTION_ORDER_NOT_IMPLEMENTED` 分支将被打开）与 §11.5（事实行）。

## 十八、超级管理员权限修复（本轮增量）

### 18.1 用户反馈与定位

用户反馈：「超级管理员好像什么也新增不了。」排查后确认是**一个真实缺陷**，
而且**与「超级管理员」这个角色本身无关**：

| 现象 | 真实原因 |
| --- | --- |
| 登录 `admin` 后，各列表页的「新增 / 编辑 / 删除 / 提交 / 审批」按钮全部不可见 | 后端对 `is_superuser=True` 的账号下发的是**通配符** `permissions: ["*"]`（`User.permission_codes()`），而前端 `hasPermission()` 只做 `permissions.includes(code)` → 永远为 `false` |
| 个人中心显示「角色：未分配」 | `bootstrap_system` 创建管理员时只设置 `is_superuser/is_staff`，**从未绑定**内置的 `super_admin` 角色，该角色当时 0 个用户 |

关键点：**超级管理员的能力来自 `is_superuser`，不是来自角色**。
后端 `resolve_data_scope()` 对超管直接返回 `all`、`permission_codes()` 返回 `{"*"}`，
所以后端一直允许全部操作；只有前端的「按钮显示」判断错了，
于是「后端能过、界面没入口」——表现就是「什么也新增不了」。

### 18.2 修复内容

1. **前端通配符支持**（`frontend/src/stores/auth.ts`）：
   - 新增 `hasFullAccess`（`permissions.includes('*')`）；
   - `hasPermission()` / `hasAnyPermission()` 在 `hasFullAccess` 为真时直接放行；
   - 保持既有语义：空编码 = 不做限制，前端仍只负责「显示与引导」，越权请求由后端拒绝。
2. **管理员账号绑定角色**（`backend/apps/core/management/commands/bootstrap_system.py`）：
   - 新增 `_ensure_admin_role()`，在管理员**创建后**与**已存在**两条路径上都确保绑定 `super_admin` 角色；
   - 幂等（重复执行不重复绑定）、`--dry-run` 只打印；
   - 目的：个人中心 / 用户管理显示真实角色，让「角色 → 权限」矩阵与账号能力一致，便于审计。
3. **打通既有开发库**：直接重跑 `manage.py bootstrap_system`（幂等），真实输出：
   `管理员账号 admin 已绑定角色：超级管理员（173 个权限点）`。

### 18.3 内置角色清单（实测，数据库当前状态）

| 角色编码 | 名称 | 数据范围 | 权限点 | 菜单 | 当前账号数 |
| --- | --- | --- | --- | --- | --- |
| `super_admin` | 超级管理员 | `all` | 173 | 56 | 1（admin） |
| `platform_admin` | 平台管理员 | `company` | 65 | 24 | 0 |
| `masterdata_admin` | 主数据管理员 | `company` | 38 | 17 | 1 |
| `factory_admin` | 工厂与组织管理员 | `company` | 34 | 13 | 1 |
| `warehouse_admin` | 仓储管理员 | `warehouse` | 24 | 9 | 1 |
| `sales_admin` | 销售管理员 | `company` | 27 | 15 | 0 |
| `planning_admin` | 计划管理员 | `company` | 27 | 17 | 0 |
| `procurement_admin` | 采购管理员 | `company` | 25 | 18 | 1 |
| `srm_admin` | 供应商管理员 | `company` | 16 | 10 | 0 |
| `crm_admin` | 客户管理员 | `company` | 13 | 9 | 0 |
| `quality_inspector` | 质检员 | `company` | 11 | 8 | 1 |
| `approver` | 审批人 | `department` | 5 | 4 | 3 |
| `viewer` | 只读用户 | `company` | 51 | 56 | 2 |

> 说明：`viewer` 的 51 个权限点全部是 `*.view` 类，菜单却能挂 56 项（含目录），
> 因此「看得到菜单」不等于「有写权限」，这正是只读账号的预期表现。
> `crm_admin` / `srm_admin` / `sales_admin` / `planning_admin` / `platform_admin`
> 目前**没有绑定任何账号**，属于「建好了但还没人用」，不是失效角色。

### 18.4 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| `manage.py bootstrap_system`（幂等重跑 + 绑定角色） | 权限点更新 173、菜单更新 56、角色更新 13、`admin 已绑定角色：超级管理员（173 个权限点）` |
| `/api/v1/identity/auth/session/`（admin） | `permissions=["*"]`、`roles=[超级管理员]`、menus 12 个根节点 |
| `/api/v1/identity/auth/session/`（wh_admin） | `permissions=24` 条、`roles=[仓储管理员]`、含 `wms.warehouse.create` |
| 后端全量测试 | `313 passed`（新增 1 条角色绑定用例） |
| 前端测试 | `Test Files 10 passed (10)` / `Tests 135 passed (135)`（新增 `tests/auth-store.spec.ts` 4 条） |
| 前端类型检查 / 构建 | `vue-tsc` 退出码 0；`vite build` `built in 11.14s` |
| `ruff check` | `All checks passed!` |

### 18.5 新增测试

- `backend/tests/test_management_commands.py::test_bootstrap_system_binds_super_admin_role_to_admin_account`：
  管理员账号必须有 `super_admin` 角色、该角色 173 个权限点、数据范围为 `all`、重复执行不重复绑定。
- `frontend/tests/auth-store.spec.ts`（4 条）：
  ① 超级管理员（`["*"]`）对任意权限点返回 true；② 普通角色只放行自己的权限点；
  ③ 空权限不放行、空编码不做限制；④ 退出登录后权限清空。

### 18.6 未完成事项

- **浏览器截图级验证未执行**（本机浏览器自动化被安全策略拒绝）。请用 `admin` 登录后
  打开「系统管理 → 用户管理 / 角色管理」，确认「新增」「编辑」按钮已出现；个人中心应显示「角色：超级管理员」。
- 其他内置角色（`sales_admin` / `crm_admin` / `srm_admin` / `planning_admin` / `platform_admin`）
  尚无账号绑定，未做过端到端角色演练；如需演示，可在「用户管理」里新建账号并分配角色。

## 十七、枚举值中文化（本轮增量）

### 17.1 问题与范围

界面多处把枚举显示为**英文原始键**，例如仓库类型 `finished`、部门类型 `management`、
计量单位类别 `area`、员工用工性质 `full_time`。排查后确认是**两层缺陷叠加**，
用户看到的只是表层：

1. **展示层**：接口只返回英文枚举键，前端仅靠 `meta` 字典兜底，未覆盖的枚举直接显示英文。
2. **数据层（更严重）**：库里存在**非法枚举值**——这些值连 `get_FOO_display()` 都翻译不出来，
   属于历史演示数据的写入错误，界面无论如何都会显示英文。

### 17.2 修复一：`DisplayLabelsMixin`（choices 字段自动带中文标签）

- 新增 `apps/core/serializers.py::DisplayLabelsMixin`：在 `get_fields()` 中为
  **序列化器 `Meta.fields` 里确实包含**且**模型字段带 `choices`** 的字段自动追加
  `<field>_display = CharField(source="get_<field>_display", read_only=True)`。
- `ReferenceIdSerializer` 继承该 Mixin，因此全部 **71 个 ModelSerializer** 自动生效；
  `apps/identity/serializers.py` 中 7 个未继承的序列化器（User / Role / RoleScopeGrant /
  Permission / Menu / LoginAttempt / Notification）显式补上。
- 约定：**写入与筛选仍用英文键**，只读中文标签走 `<field>_display`；
  已显式声明的同名字段不被覆盖；只新增只读字段，**不产生数据库迁移**。
- 扫描结果（真实执行）：**59 个 choices 序列化字段，0 个缺少 `_display`**。

实测接口返回片段：

```text
仓库:     {'code': 'WH-FG-01', 'warehouse_type': 'finished',  'warehouse_type_display': '成品仓'}
库区:     {'code': 'RCV',      'zone_type': 'receiving',      'zone_type_display': '收货区'}
储位:     {'code': 'A01-01-01', 'location_type': 'floor',     'location_type_display': '地面储位'}
部门:     {'code': 'GM',       'department_type': 'management','department_type_display': '职能部门'}
员工:     {'gender': 'male',   'gender_display': '男',        'employment_type_display': '正式'}
计量单位: {'code': 'M2',       'category': 'area',            'category_display': '面积'}
```

### 17.3 修复二：历史非法枚举数据与 choices 缺口

直连开发库扫描发现 **12 条非法枚举值**：

| 模型 / 字段 | 非法值 | 条数 |
| --- | --- | --- |
| `factory.Employee.gender` | `男` / `女` | 9 / 6 |
| `factory.Employee.employment_type` | `management` / `worker` / `professional` | 6 / 6 / 3 |
| `factory.ProductionLine.line_type` | `sewing` / `finishing` / `cutting` | 3 / 2 / 1 |
| `factory.Department.department_type` | `supply` / `marketing` / `equipment` | 2 / 1 / 1 |
| `factory.Workshop.workshop_type` | `finishing` | 2 |

处理方式：

- `Department.department_type` 补充 `procurement`（采购部门）/ `sales`（销售部门）/ `equipment`（设备部门）；
  `Workshop.workshop_type` 补充 `finishing`（整烫包装）——它们本就是业务上合法的类型，只是 choices 漏登记。
- `seed_demo` 修正数据源头：部门 `supply→procurement`、`marketing→sales`；员工性别改英文键；
  用工性质统一 `full_time`；线体类型改合法值。
- 新增迁移 `factory/0003_alter_department_department_type_and_more.py`：先 `RunPython`
  按部门编码（`PUR/SALES/WH/EAM`）/ 性别 / 用工性质映射**修正历史数据**，再 `AlterField`
  扩展 choices；反向迁移为显式空操作。
- 迁移执行后复扫：**全库非法枚举值 0 条**。

### 17.4 前端

- `frontend/src/components/ProTable.vue::displayValue()` 与
  `frontend/src/components/EntityListPage.vue::renderCell()` **优先**使用后端下发的
  `<field>_display`；没有该字段时退回原值，不会显示 `undefined`。
- 前端 `meta` 字典机制保留作为回退，两者不冲突（后端标签优先）。

### 17.5 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `makemigrations --check --dry-run` | `No changes detected` |
| `manage.py migrate factory` | `Applying factory.0003_... OK` |
| 枚举合法性复扫（直连开发库） | 修复前 12 条非法 → 修复后 **0 条** |
| `ruff check --no-cache ...` | `All checks passed!` |
| 后端全量测试 | `312 passed` |
| 前端类型检查（`vue-tsc --noEmit`） | 通过（退出码 0） |
| 前端测试 | `Test Files 9 passed (9)` / `Tests 131 passed (131)` |
| 前端构建（`vite build`） | `built in 13.21s`，产物写入 `frontend/dist` |

### 17.6 新增测试

- `backend/tests/test_enum_labels.py`（4 条）：
  ① 遍历全部 ModelSerializer，任一 choices 字段缺 `_display` 即失败；
  ② 仓库 / 部门 / 计量单位接口返回的 `_display` 必须是中文；
  ③ `/api/v1/meta/` 的枚举 `label != value`，且部门类型含新增的三项；
  ④ `seed_demo` 执行后全库无非法枚举值。
- `frontend/tests/pro-table.spec.ts` 新增 2 条：中文标签优先；无标签时退回原值且不显示 `undefined`。

### 17.7 未完成事项

- **浏览器截图级 UI 校验未执行**（本机浏览器自动化被安全策略拒绝）。请人工打开
  「仓储管理 → 仓库与储位」「工厂与排班 → 部门 / 车间 / 线体 / 员工」「基础资料 → 计量单位」
  核对中文标签。
- `docs/user-guide.md` 正文（菜单名称、操作步骤、错误码解释）仍只能人工维护，见该文档 §十。

### 17.8 下一阶段依赖

阶段 3 第三步：**MES 工单与报工 → QMS 检验单**。新增枚举时必须同时：
① 在模型 `choices` 里给中文标签；② 跑 `pytest tests/test_enum_labels.py` 确认
序列化器自动带 `_display`；③ 若改动了 `docs/user-guide.md`，重新生成网页版
（`python scripts/build_user_guide.py`）。

## 十九、客户编码自动生成（本轮增量）

> 用户诉求：「新增客户的时候不需要手动输入客户编码，自动按照规律生成。」
> 结论：**不新造取号逻辑**，复用平台既有的编码规则引擎（`core.CodeRule` / `core.CodeSequence` /
> `core.services.generate_code`），把「新增时由谁给编码」这件事收敛到一处。

### 19.1 编码规律与可配置性

| 项 | 取值 | 说明 |
| --- | --- | --- |
| 规则编码 | `CUS` | 登记在 `bootstrap_system.CODE_RULES`，由 `manage.py bootstrap_system` 幂等同步 |
| 编号格式 | `CUS{YYYY}{SEQ:4}` | 生成形如 **`CUS20260001`** |
| 重置周期 | `yearly`（每年） | 主数据编码会被订单长期引用，不适合把「日」写进编码；按年重置既短又可读 |

**格式不写死在代码里**：`apps/crm/services.py` 只引用规则编码 `CUS`，格式与重置周期全部来自
`CodeRule`。管理员可在「系统管理 → 编码规则」改格式（含**编号预演**，预演不消耗流水号），
已有用例把「改规则即改编号」锁死，避免出现两套口径。

### 19.2 后端改动

| 文件 | 改动 |
| --- | --- |
| `apps/crm/services.py` | 新增 `CUSTOMER_CODE_RULE = "CUS"` 与 `next_customer_code()`：在事务内引用规则取号（先锁规则行再锁流水行） |
| `apps/crm/serializers.py` | `code` 显式声明为 `CharField(allow_blank=True, default="", max_length=32)`；`validate_code` 只在**编辑**（`self.instance` 非空）时拒绝空值 |
| `apps/crm/views.py` | `CustomerViewSet.perform_create()`：编码缺失 / 空白 / 空串时调用 `next_customer_code()` 补号；显式传入的编码**原样保留** |
| `apps/core/management/commands/bootstrap_system.py` | `CODE_RULES` 登记 `("CUS", "客户编码", "CUS{YYYY}{SEQ:4}", ResetPeriod.YEARLY)` |

**为什么是 `default=""` 而不是 `required=False`**（踩坑记录）：模型上的
`uq_customer_company_code` 会派生 DRF 的 `UniqueTogetherValidator('company_id', 'code')`，
它**强制要求**这两个字段同时出现在输入里，只有带默认值的字段才能合法缺省。
实测：写成 `required=False` 时，不带 `code` 的新增请求返回
`400 {"code": ["该字段是必填项。"]}`；改成 `default=""` 后通过。

**事务与并发**：补号发生在 `ScopedModelViewSet.create()` 的 `transaction.atomic()` 内，
与客户落库**同事务**——取号成功但写入失败时流水一并回滚（已实测：事务回滚后
`CodeSequence` 无残留）。并发取号由 `generate_code` 的行锁 + `(rule, period_key)` 唯一约束保证不重号。

### 19.3 前端改动

| 文件 | 改动 |
| --- | --- |
| `frontend/src/components/EntityListPage.vue` | `FormFieldDef` 新增 `onlyOnUpdate`（与既有 `onlyOnCreate` 对称）；`visibleFormFields` 在**新增**模式过滤该类字段 |
| `frontend/src/views/crm/CustomerList.vue` | 客户编码字段改为 `onlyOnUpdate: true`——新增表单里不再出现编码输入框，编辑时展示以便核对；页面说明补充「编码自动生成」 |

未展示的字段不会进入提交载荷（前端用例锁定），后端因此走自动取号分支。

### 19.4 本轮执行的检查（真实输出）

| 检查 | 命令 | 实际输出 |
| --- | --- | --- |
| 系统自检 | `manage.py check` | `System check identified no issues (0 silenced).` |
| 迁移漂移 | `manage.py makemigrations --check --dry-run` | `No changes detected`（**本轮不产生迁移**，仍为 19 个） |
| 规则同步（开发库） | `manage.py bootstrap_system` | `编码规则：新增 1，共计 15 条。`；`管理员账号 admin 已存在（版本 0），保留原密码，仅同步权限属性。` |
| 开发库取号（事务回滚） | 直连 `config.settings.dev` | 规则 `CUS 客户编码 CUS{YYYY}{SEQ:4} yearly`；预演 `CUS20260001`；回滚后客户数与流水均无残留 |
| 开发库 HTTP 冒烟 | `django.test.Client` + 真实登录（事务回滚） | 见 19.5 |
| 静态检查 | `ruff check --no-cache apps config tests ../scripts/build_user_guide.py` | `All checks passed!` |
| 后端全量测试 | `pytest tests -q --reuse-db -p no:logging` | `319 passed in 117.64s (0:01:57)` |
| 前端测试 | `vitest run` | `Test Files 11 passed (11)` / `Tests 138 passed (138)` |
| 前端类型检查 | `vue-tsc --build --force` | 退出码 0 |
| 生产构建 | `vite build` | `✓ built in 12.66s` |

### 19.5 开发库 HTTP 冒烟（真实执行，整个事务已回滚，库中无残留）

```text
POST /api/v1/identity/auth/login/  (admin)            -> 200
POST /api/v1/crm/customers/  {"company_id":2,"name":"冒烟-自动编码客户"}
                                                      -> 201  code=CUS20260001
POST /api/v1/crm/customers/  （第二户）                -> 201  code=CUS20260002
PATCH /api/v1/crm/customers/{id}/  {"code": ""}        -> 400  VALIDATION_FAILED
                                                              （"客户编码不能为空。"）
GET  /api/v1/audit-logs/?object_type=crm.Customer&object_id={id}
                                                      -> 200  create / changes.code=CUS20260001
客户数 before/after: 3 3
```

即：**不传编码能建档、编码逐号递增、编辑不允许清空、自动编码写入审计**，且验证过程未污染开发库。

### 19.6 新增测试

- `backend/tests/test_crm_api.py`（11 → **17** 条）：不传 `code` 自动取号并按年+4 位流水匹配；
  提交空白串同样取号；**改规则即改编号**（把 `CUS` 改成 `KH{YY}{SEQ:3}` 后新编号随之变化）；
  显式编码仍然保留；编辑时清空编码被拒绝且原值不变；规则被删除时返回
  `404 CODE_RULE_NOT_FOUND` 且不落数据。
- `frontend/tests/entity-list-form.spec.ts`（新增 **3** 条）：新增模式不展示 `onlyOnUpdate` 字段、
  展示 `onlyOnCreate` 字段；编辑模式相反；新增提交的载荷里**不含**被隐藏的编码字段。

### 19.7 未完成事项

- **浏览器截图级 UI 校验未执行**（本机浏览器自动化被安全策略拒绝）。请人工打开
  「客户管理 → 客户档案 → 新增客户」，确认表单里**没有**「客户编码」输入框；
  保存后列表出现 `CUS...` 编码；点「编辑」时该字段出现。
- 供应商编码（`srm.Supplier.code`）、物料 / 款式等主数据编码**仍是手工录入**，
  本轮只按用户要求改了客户。若要统一，按 19.8 的方式逐条登记规则即可。
- 已有的手工编码客户（如演示数据 `CUS-001`）不受影响，不会自动改写。

### 19.8 下一阶段依赖

- 若要继续统一主数据编码：在 `CODE_RULES` 追加规则（例如 `("SUP", "供应商编码", "SUP{YYYY}{SEQ:4}", ResetPeriod.YEARLY)`），
  在对应 `services.py` 里加取号函数，在 `ViewSet.perform_create()` 里补号，
  前端字段加 `onlyOnUpdate: true`——四处改动，模式与本轮一致。
- 阶段 3 的 MRP 建议转单、MES 工单 / QMS 检验单依赖本轮的取号模式（单据号沿用 `bootstrap_system.CODE_RULES`）。

## 二十、开发库数据清理：备注中的「演示数据」标记（本轮，仅数据）

> 用户要求：把「备注」字段里是「演示数据」的内容**清空**。
> 这是**开发库的数据清理**，不涉及代码、不涉及表结构（**无迁移**）。

### 20.1 影响面（清理前实测）

`seed_demo` 用常量 `DEMO_REMARK = "演示数据"`（`apps/core/management/commands/seed_demo.py:60`）
给演示数据打标。直连开发库扫描全部含 `remark` 字段的模型：

- **37 个模型 / 624 条记录**含该字样；其中 **597 条正好是「演示数据」**，
  **27 条是「演示数据：说明」**（例如 `演示数据：整单发货`、`演示数据：生产计划主管`）。

### 20.2 执行方式与可恢复性

1. **先备份**：受影响记录（模型 + 主键 + 原备注）写入
   `.tmp/backup/demo_remark_<时间戳>.json`（本次为 `demo_remark_20260920-094644.json`，
   624 条 / 37 个模型）。该目录被 `.gitignore` 忽略，**不进版本库**。
2. **再清空**：逐模型 `QuerySet.update(remark="")`，**整个操作包在一个事务里**，
   任一模型条数与预期不符即 `assert` 失败并整体回滚。
3. 用 `update()` 而不是逐条 `save()`：不改 `updated_at`（避免所有历史数据看起来
   「刚刚被改过」），也不触发任何 `save()` 覆盖逻辑——这是数据清理，不是业务操作。
4. **复核**：清理后重扫，仍含该字样的 `remark` = **0 条**。

### 20.3 清理结果（实测）

| 模型 | 条数 | 模型 | 条数 |
| --- | --- | --- | --- |
| `wms.Location` | 228 | `factory.Department` | 13 |
| `masterdata.Material` | 65 | `identity.User` | 10 |
| `masterdata.Sku` / `masterdata.Identifier` | 50 / 50 | `masterdata.Color` / `masterdata.Size` | 8 / 8 |
| `factory.Station` | 48 | `factory.Team` / `factory.Shift` | 7 / 3 |
| `wms.Zone` | 24 | `wms.Warehouse` / `wms.InventoryDocument` | 6 / 6 |
| `masterdata.MaterialCategory` | 16 | `crm.Customer` / `crm.CustomerContact` | 3 / 4 |
| `factory.Employee` | 15 | `sales.SalesOrder` | 3 |
| `masterdata.UoM` | 14 | 其余（供应商、采购、计划、公司/工厂等） | 见备份文件 |

**合计清空 624 条**；抽样复核（客户、仓库、储位、物料、部门、员工、销售订单、库存单据）
`remark` 均为 `''`；不含该字样的备注（如盘点单「来料检验合格，允许投产」）**未被改动**。

### 20.4 已知影响与恢复方式

- **27 条带说明的备注**（`演示数据：xxx`）被整体清空，其中的说明文字一并消失。
  原文完整保存在上述备份 JSON 中，需要时可逐条恢复；典型如
  `sales.SalesOrder pk=2 → 演示数据：订单到交付链路（订单 → 占用 → 发货 → 退货 → 检验）`。
- **重新执行 `seed_demo` 会把标记写回来**：`_upsert` 以业务编码为键、会把 `remark`
  更新回 `DEMO_REMARK`（这是幂等更新，不会产生重复记录）。
  若以后不希望演示数据再带这个标记，需要显式修改 `seed_demo.DEMO_REMARK`
  ——注意任务书 §15 要求「演示数据与真实采集来源明显区分」，改动前需先确定替代的区分方式。
- **未清理的两处非「备注」字段**（用户只要求清备注，且其中一处是审计证据）：
  - `core.AuditLog.reason`（11 条）：**审计留痕，按任务书 §5.5 不通过普通接口修改**，未动。
  - `workflow.ApprovalInstance.summary`（3 条）：审批实例摘要，未动。

### 20.5 本轮执行的检查

| 检查 | 结果 |
| --- | --- |
| 清理前扫描（直连开发库） | 37 个模型 / 624 条含「演示数据」 |
| 备份写出 | `.tmp/backup/demo_remark_20260920-094644.json`（624 条） |
| 清理（单事务） | 合计 624 条，逐模型条数与扫描值一致 |
| 清理后重扫 | 仍含该字样的 `remark` = **0 条** |
| 抽样复核 | 8 个模型各 3 条，`remark` 均为 `''` |
| 代码 / 迁移 | 无代码改动、**无迁移** |

## 二十一、数值显示口径统一为 2 位小数（本轮增量）

> 用户要求：「涉及到数字的内容，都是小数点后 2 位即可」。
> 结论：**只统一「显示」口径，不改存储与接口精度**——任务书 5.3 要求数量 6 位小数、
> 金额按币种精度、API 的 Decimal 以字符串输出；把存储改成 2 位会**真实截断已有业务数据**。
> 本轮**无迁移、无后端改动**（纯前端显示层 + 测试 + 文档）。

### 21.1 显示口径（`frontend/src/utils/decimal.ts`）

统一入口 `formatNumber(value, places = DISPLAY_PLACES)`，`DISPLAY_PLACES = 2`：

| 输入 | 输出 | 说明 |
| --- | --- | --- |
| `"12.000000"` | `12.00` | 接口的 6 位 Decimal 字符串 |
| `"1234.567800"` | `1,234.57` | HALF_UP 四舍五入 + 千分位 |
| `"-1234.500000"` | `-1,234.50` | 负数保留符号 |
| `"0.000000"` | `0.00` | 真值就是 0 |
| `null` / `undefined` / `""` | `-` | 空值不当作 0 |
| `"13800138000"` | `13800138000` | **纯整数文本不参与格式化**（手机号、税号、数字型编码） |
| `"M-001"` / `"2026-09-20"` | 原样 | 非小数文本不参与格式化 |

`formatAmount` / `formatDecimal` 保留为 `formatNumber` 的别名（默认 2 位），
调用处不再传 6 / 4 / 3 这类精度参数，避免同一个界面出现多种小数位。

### 21.2 边界一：非零值不允许被显示成 0

若某个**非零**值四舍五入到 2 位后恰好是 `0.00`，则保留其真实精度显示，
否则会把「有」说成「没有」。直连开发库扫描全部 **58 个 `DecimalField` 列**，
真实会触发该保护的数据只有 **2 处**：

| 列 | 条数 | 实际值 | 是否在页面展示 |
| --- | --- | --- | --- |
| `masterdata.UoMConversion.factor` | 1 | `0.9144000000`（码 → 米） | 否（该字段未出现在任何页面） |
| `planning.BomLine.quantity` | 1 | `0.004000`（涤纶缝纫线 BOM 用量） | 是 → 显示为 `0.004` |

区分要点：**会进位的值仍按 2 位显示**（`0.055` → `0.06`、`0.995` → `1.00`），
保护只在「四舍五入结果恰好为 0」时生效。极小值（如 `-0.0000001`）在 6 位数量精度内
仍为 0、无法保留有效信息，回退显示 `0.00`。

### 21.3 边界二：编辑表单回填只去尾 0，不四舍五入

新增 `toEditableText(value)`（`decimal.ts`）：把接口值 `"12.000000"` 回填成 `"12"`，
`"0.055"` 保持 `"0.055"`，且**不加千分位**（千分位会让回填值无法被再解析）。

**为什么回填不能复用 `formatNumber`**：编辑表单的值会被再次提交。
若回填时按 2 位四舍五入，用户「打开编辑 → 直接保存」就会把 `0.055` 悄悄改成 `0.06`，
属于任务书 §5.5 禁止的「未经明确机制改写已过账数据」。回填去掉无意义的末尾 0 即可，
提交精度仍由后端 `DecimalField` 与 `toApiString` 决定。

### 21.4 改动清单

| 文件 | 改动 |
| --- | --- |
| `frontend/src/utils/decimal.ts` | 新增 `DISPLAY_PLACES`、`formatNumber`、`formatNumericText`、`numberFormatter`、`toEditableText`；`formatAmount` / `formatDecimal` 改为统一入口的别名；`toApiString` / `round` / `DECIMAL_PLACES` **未改**（提交精度不变） |
| `frontend/src/components/ProTable.vue` | `displayValue()` 追加数值文本分支（通用表格自动生效） |
| `frontend/src/components/EntityListPage.vue` | `renderCell()` 同上；`decimal` 字段编辑回填走 `toEditableText`；输入框 placeholder 改为 `十进制数值，例如 12.50` |
| `frontend/src/views/planning/BomList.vue` | 数量 / 损耗率列加 `:formatter="numberFormatter"`；编辑回填去尾 0 |
| `frontend/src/views/planning/RoutingList.vue` | 标准工时列（详情抽屉 + 快照抽屉）加 `:formatter="numberFormatter"`；编辑回填去尾 0；placeholder 改为「小时，如 0.50」 |
| `frontend/src/views/planning/MrpRunList.vue`、`MrpSuggestionList.vue` | 需求 / 供给 / 建议数量列与明细统一 2 位 |
| `frontend/src/views/procurement/{PurchaseOrderList,GoodsReceiptList,RequisitionList}.vue` | 订单量 / 未收 / 单价 / 金额 / 收货量 / 申请量统一 2 位；编辑回填去尾 0 |
| `frontend/src/views/sales/{SalesOrderList,SalesShipmentList,SalesReturnList}.vue` | 订单量 / 未发货 / 发货量 / 退货量 / 价税合计统一 2 位；备注与税率回填去尾 0 |
| `frontend/src/views/wms/InventoryDocumentList.vue` | 输入 placeholder 改为 2 位示例 |
| `frontend/src/views/workflow/TemplateList.vue` | 金额区间改用 `formatNumber` |
| 各视图 | 删除 16 处多余精度参数（`formatAmount(x, 6/4/3)` → `formatAmount(x)`）；保留 `WorkshopList` 产能与工作台计数的 `, 0`（整数计数不显示小数） |

### 21.5 展示层为什么统一改在公共组件里

`ProTable`（列表）与 `EntityListPage`（通用增删改查页）是两个渲染入口，
把口径放在这两处 + `numberFormatter`（原生 `el-table` 列），
新增页面**默认**就是 2 位小数，不需要每个视图各写一次格式化函数。

### 21.6 本轮执行的检查（真实输出）

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| Django 检查 | `manage.py check` | `System check identified no issues (0 silenced).` |
| 迁移漂移 | `manage.py makemigrations --check --dry-run` | `No changes detected` |
| Ruff | `ruff check --no-cache apps config tests ..\scripts\build_user_guide.py` | `All checks passed!` |
| 后端测试 | `pytest tests -q --reuse-db -p no:logging` | `319 passed, 1 warning in 116.99s`（本轮无后端改动，基线不变） |
| 前端测试 | `vitest run` | `Test Files 11 passed (11)` / `Tests 154 passed (154)`（本轮前 138） |
| 前端类型检查 | `vue-tsc --build --force` | 退出码 `0` |
| 前端构建 | `vite build` | `✓ built in 12.13s` |
| 开发库扫描 | 直连 MySQL 遍历 58 个 `DecimalField` 列 | 仅 **2 处**存在 >2 位有效小数（见 21.2） |

### 21.7 未完成事项

1. **浏览器截图级 UI 核对未执行**——本机浏览器自动化被安全策略拒绝。请人工打开
   「采购管理 → 采购订单」「生产管理 → BOM」「销售管理 → 销售订单」确认列表显示为 2 位小数。
2. **后端 Excel 导出未同步**：`openpyxl` 导出的单元格格式仍是后端原始精度（6 位），
   原因是导出属于「数据交付」而非「界面显示」，改成 2 位会造成导出值与页面值不一致且丢失精度。
   若业务上要求导出也按 2 位呈现，应作为**独立需求**评审（需要明确是否允许丢精度）。
3. **打印 / 标签模板未接入**：标签与单据打印尚未实现，届时需复用同一口径。
4. **费率类字段（税率、损耗率）显示为小数而非百分数**：当前按 2 位小数显示
   （`0.1300000000` → `0.13`），未做 `13%` 形式的百分比换算；换算属于业务口径变更，需单独确认。

### 21.8 下一阶段依赖

- 阶段 3 剩余部分（MES 工单报工、QMS 检验单）新增页面的数值列会自动走本轮的公共口径；
- 若后续新增时序或聚合类看板（EMS 能源、OEE），需要先确定「显示 2 位」与
  「统计口径小数位」是否一致，避免把估算值显示得比实际更精确。

## 二十二、权限一级分组显示中文名（本轮增量）

> 用户要求：权限 / 菜单与角色权限界面的**一级分组**不能只有英文模块名，
> 要显示成 `core（中文名称）`。
> 本轮**无迁移**；后端只增加「模块中文名」这一份注册表数据 + 一个启动检查，
> 权限编码、授权逻辑、数据范围判定**均未改动**。

### 22.1 问题

权限编码的第一段是模块（`core.user.view` → `core`），它是英文的。
界面上两个地方把模块名当作一级分组标题直接显示：

| 位置 | 改动前 | 改动后 |
| --- | --- | --- |
| 「系统管理 → 权限与菜单」→ 权限点选项卡（折叠面板标题） | `core（12）` | `core（公共基础）· 12 项` |
| 「系统管理 → 角色权限」→ 分配操作权限（复选框树一级节点） | `core（12）` | `core（公共基础）· 12 项` |

业务人员配置角色时看到 `core`、`identity`、`srm` 这类英文分组，无法判断该勾哪一组。

### 22.2 中文名放在后端，而不是前端硬编码

中文名定义在权限注册表（`backend/apps/identity/permissions_registry.py`）：

```python
MODULE_LABELS: dict[str, str] = {
    "analytics": "工作台与看板", "core": "公共基础", "crm": "客户管理",
    "factory": "工厂与排班", "identity": "用户与权限", "integration": "内部协同",
    "masterdata": "基础资料", "planning": "计划管理", "procurement": "采购管理",
    "sales": "销售管理", "srm": "供应商管理", "wms": "仓储管理", "workflow": "审批中心",
}
```

理由：权限注册表已经是「后端与前端共同依赖的契约」的唯一来源，
`bootstrap_system` 按它写入 `identity.Permission`，`yishang.E001` 按它校验视图声明。
中文名放在同一处，新增模块时**一处登记、两处界面同时生效**，
不会出现前端映射表漏更新导致中文名缺失。

命名尽量与左侧**一级菜单**一致（基础资料 / 工厂与排班 / 客户管理 …），便于对照；
`core` 是不直接对应菜单的基础能力（字典、编码规则、附件、审计、通知），
单独命名为「公共基础」，避免与 `identity` 的「用户与权限」重复。

### 22.3 改动清单

| 文件 | 改动 |
| --- | --- |
| `backend/apps/identity/permissions_registry.py` | 新增 `MODULE_LABELS`（13 个模块）与 `module_label()` |
| `backend/apps/identity/selectors.py` | `permission_groups()` 每个分组增加 `module_name` 字段 |
| `backend/apps/core/checks.py` | 新增启动检查 `yishang.E002`：模块缺中文名时报错 |
| `frontend/src/utils/permissionLabels.ts` | **新增**：`moduleDisplayName()`、`permissionModuleNodeLabel()` 统一文案 |
| `frontend/src/types/models.ts` | `PermissionGroup` 增加 `module_name` |
| `frontend/src/views/system/PermissionList.vue` | 折叠标题显示中文名；**并修掉一个真实缺陷**（见 22.4） |
| `frontend/src/views/system/RoleList.vue` | 权限树一级节点改用统一的 `permissionModuleNodeLabel()` |

### 22.4 顺带修掉的一个真实缺陷

`PermissionList.vue` 的 `filteredGroups` 在按关键字过滤时**重建了分组对象**，
只保留了 `module` 与 `permissions` 两个字段：

```ts
.map((group) => ({ module: group.module, permissions: [...] }))
```

如果只加中文名而不改这里，用户**一输入关键字**中文名就会消失，退回纯英文分组。
本轮已补上 `module_name: group.module_name`，并有对应用例锁定
（`按关键字过滤后中文名仍然保留`）。

### 22.5 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| `manage.py check` | `System check identified no issues (0 silenced).`（新检查 E002 通过） |
| `makemigrations --check --dry-run` | `No changes detected`（**无迁移**） |
| `ruff check` | `All checks passed!` |
| 后端测试 | `322 passed, 1 warning in 120.49s`（本轮前 319，新增 3 条） |
| 前端测试 | `Test Files 12 passed (12)` / `Tests 159 passed (159)`（本轮前 154，新增 5 条） |
| `vue-tsc --build --force` | 退出码 `0` |
| `vite build` | `✓ built in 13.23s` |
| 开发库实际数据 | `permission_groups()` 返回 13 个分组，全部带中文名，权限点合计 **173** 项，与注册表一致 |

开发库实测（直连 `config.settings.dev`，非测试夹具）：

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

### 22.6 新增测试

| 文件 | 用例 |
| --- | --- |
| `backend/tests/test_permissions.py` | `test_every_permission_module_has_chinese_label`（注册表覆盖全部模块） |
| 同上 | `test_module_label_check_reports_missing_module`（E002 真的会报错，可 monkeypatch 验证） |
| 同上 | `test_permission_groups_api_returns_module_chinese_name`（接口返回 `module_name`，且权限点总数与注册表一致） |
| `frontend/tests/permission-module-label.spec.ts` | 文案函数 3 条 + 页面渲染 2 条（含过滤后中文名保留） |

### 22.7 未完成事项

1. **浏览器截图级 UI 核对未执行**——本机浏览器自动化被安全策略拒绝。
   请人工打开「系统管理 → 权限与菜单」与「系统管理 → 角色权限 → 分配操作权限」确认显示为 `core（公共基础）`。
2. **模块中文名未进入 `docs/permission-matrix.md`**：该文档由注册表生成，
   目前只列权限编码，不含模块中文名；如需一并展示属于文档增强，不影响功能。
3. **二级权限点名称未中文化治理**：权限点的中文名来自注册表 `PermissionDef` 的第二个参数，
   已全部是中文，无需处理；但 `resource` / `action` 两列仍是英文，属技术标识，未改。

### 22.8 下一阶段依赖

- 后续新增权限模块（如 `mes`、`qms`、`eam`、`ems`、`ehs`、`logistics`、`endpoint_security`）
  时，**必须**在 `MODULE_LABELS` 登记中文名，否则 `manage.py check` 会以 `yishang.E002` 报错——
  这是刻意的，避免界面又出现纯英文分组。

## 二十三、登录页改版为商用双栏布局（本轮增量）

> 用户要求：登录页「看起来太一般了」，希望更符合商用应用观感。
> 本轮**只改前端视觉与结构**：后端、接口、会话 / CSRF / 登录逻辑、权限判定**均未改动**，
> **无迁移**。

### 23.1 改了什么

| 维度 | 改前 | 改后 |
| --- | --- | --- |
| 布局 | 单张 400px 卡片居中 | **左侧品牌区 + 右侧登录卡**的双栏（`grid`，`min(1080px, 100%)`） |
| 品牌 | 卡片内居中的两行文字 | 渐变色「意」字标识 + 中英文品牌名；左侧另有主标题与平台定位文案 |
| 信息量 | 只有标题、表单、一行提示 | 左侧补 4 条**已实现能力**要点（统一账号与四层权限 / 统一主数据 / 单据与审批留痕 / 关键操作后端校验） |
| 背景 | 单层径向渐变 | 深蓝渐变 + 细网格 + 两处光斑（**纯 CSS，无外链资源**） |
| 输入框 | Element Plus 默认 | 圆角 10px、hover / focus 双态描边 + 4px 主色光晕 |
| 登录按钮 | 默认主色 | 品牌渐变、44px 高、字距 0.22em、悬浮加深 + 阴影 |
| 收尾 | 一行提示 | 安全提示 + 分隔线 + 版权行（年份动态） |
| 交互 | 无 | 打开即聚焦账号输入框；卡片入场动效受 `prefers-reduced-motion` 保护 |
| 响应式 | 无 | ≤960px 隐藏左栏并在卡片内显示紧凑品牌；≤480px 收紧内边距与圆角 |

文案刻意只列**已实现**能力，未实施模块（MES / WMS / QMS 等）不出现，避免登录页变成虚假宣传；
测试里有对应用例（`展示平台能力要点时只陈述已具备的能力`）。

### 23.2 样式搬了家（顺带修掉「两处定义」隐患）

改前登录页样式定义在**全局样式表** `frontend/src/styles/index.css` 的「7. 登录页」小节里，
而页面结构在 `frontend/src/views/LoginView.vue`——改登录页要来回跳两个文件，
且很容易出现「组件里改了、全局那条还在生效」。

本轮把登录页样式**全部移入组件**（`<style scoped>`），并删除全局里的小节，
全局样式表只保留设计令牌与跨页面共享的业务类（小节重新编号为 1–8）。
`frontend/tests/login-view.spec.ts` 用 postcss 断言
`globalCss` 中**不再包含** `.ys-login`，防止以后又长出第二处定义。

### 23.3 保留的行为（未改动）

- 提交顺序仍是 **先 `GET /auth/csrf/` 再 `POST /auth/login/`**（登录接口自身也做 CSRF 校验）；
- 会话登录 + 退出使服务端会话失效，未引入任何新认证方式；
- 账号两侧空格仍会 `trim` 后提交；
- 登录成功仍 `tabs.reset()` 后跳 `redirect` 参数指定地址，默认 `/`；
- 失败仍是把 `ApiError.message` 显示在表单上方的 `el-alert`；
- 账号 / 密码输入框保留 `autocomplete="username"` / `"current-password"`。

### 23.4 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| 前端测试 | `Test Files 13 passed (13)` / `Tests 170 passed (170)`（本轮前 159，新增 11 条） |
| `vue-tsc --build --force` | 退出码 `0` |
| `vite build` | `✓ built in 12.83s` |
| `ruff check` | `All checks passed!` |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| 迁移 | **无迁移**（只改前端 + 全局样式表） |
| 后端测试 | 本轮无后端改动，基线 `322 passed` 不变 |

### 23.5 一条重要的测试边界（必须知道）

**表单必填校验在自动化测试里无法验证**。排查发现：Element Plus 的 `el-form-item`
在 jsdom 下不会注册进 `el-form` 的 `fields`，`validate()` 会走
`fields.length === 0 → return true` 的分支直接放行。
用一个**最小复现**（一个 `el-form` + 一个带 `required` 规则的 `el-form-item` + 按钮调用
`formRef.validate()`）确认：空值下 `validate()` 返回 `true`、错误文案也不渲染。

结论：**这是 jsdom 环境限制，不是本页缺陷**——真实浏览器不受影响，
而且本项目所有页面（含 `EntityListPage`）都用同一套 Element Plus 表单写法。

因此 `frontend/tests/login-view.spec.ts` **不断言校验行为**，只在文件头写明该限制；
「必填校验 / 错误文案」列入「未执行」清单，需人工在浏览器确认。
这里刻意不写成「校验通过」，避免用一条恒真的断言冒充测试覆盖。

### 23.6 未完成事项

1. **浏览器截图级 UI 核对未执行**——本机浏览器自动化被安全策略拒绝。
   请人工打开 `http://127.0.0.1:5173/login` 确认双栏布局、渐变按钮与窄屏折叠（把窗口拖到 960px 以下）。
2. **表单必填校验未由自动化覆盖**（原因见 23.5），需人工点一次「登录」确认出现「请输入账号 / 请输入密码」。
3. **未加登录页专属的 favicon / 品牌图**：当前标识是 CSS 渐变方块 + 文字，没有引入任何图片资源；
   若要换成企业 logo 需要提供素材（并注意不要把版权不明的图片放进仓库）。
4. **未加「记住我 / 忘记密码」入口**：任务书未要求，且平台没有自助改密流程（由管理员重置），
   加了会造成「点了没用」的假入口。

### 23.7 与既有文档的关系

本节**取代** `docs/progress.md` §11.4 中「`styles/index.css` 重写为 8 个小节：… / 登录页 / 辅助类」
对**当前**文件结构的描述：登录页小节已移入组件，全局样式表现有 8 个小节但不含登录页。
§11 与 §9 的历史记录本身不改写（它们记录的是当时的事实）。


## 二十四、登录页左栏文案改为面向使用者的业务描述（本轮增量）

> 用户反馈：「左侧的描述有的不太合适，应该采用面向用户的描述，而不是面向开发者的描述，
> 描述的应该是这个系统的功能、优势」。
> 本轮**只改文案与 `features` 图标**：布局、样式、登录 / 会话 / CSRF 逻辑、后端**均未改动**，
> **无迁移**。

### 24.1 问题：左栏写成了技术说明

`§23` 改版时左栏 4 条要点是按**开发视角**写的，用的是「四层权限 / 菜单·操作·接口·数据范围 /
SKU / BOM / 后端校验 / 服务端判定」这类实现词汇。业务用户（车间、仓库、业务员）看不懂，
也没说明平台对他们有什么用。

### 24.2 改了什么

| 位置 | 改前（开发视角） | 改后（使用者视角） |
| --- | --- | --- |
| 主标题 | 服饰企业统一业务平台 | 服饰企业一体化经营管理平台 |
| 定位文案 | 一个统一平台、一套账号权限、统一主数据、多个内置业务模块、跨模块业务流程闭环 | 从面料采购、款式建码到库存出入库与销售发货，日常业务都在同一个平台上流转，不用在多个系统之间来回切换 |
| 要点 1 | 统一账号与四层权限 / 菜单·操作·接口·数据范围 | **一套账号，权限分明** / 按岗位分配可用功能与数据范围 |
| 要点 2 | 统一主数据 / 物料·款式·颜色尺码·SKU·BOM | **主数据统一维护** / 面料、辅料、款式、颜色尺码一处建档 |
| 要点 3 | 业务单据与审批留痕 / 提交、审批、撤回全程可追溯 | **采购到销售全程贯通** / 到货、入库、出库、发货连续流转 |
| 要点 4 | 关键操作后端校验 / 前端只是入口，权限与状态由服务端判定 | **单据与审批全程留痕** / 谁在何时提交、审批、修改随时可查 |

图标相应从 `Document` 换成 `ShoppingCart`（第 3 条从「单据」改为「业务贯通」），
其余图标（`Key` / `Files` / `CircleCheck`）不变。

**两条约束仍然成立**：

1. 只陈述平台**已具备**的能力——采购、销售、仓储、审批、主数据在本仓库均已实现
   （见 `backend/apps/` 下的 `masterdata` / `procurement` / `sales` / `wms` / `workflow`）；
   未实施的 MES / WMS 术语 / QMS 等模块字样**不得出现**。
2. 不出现开发视角术语（权限分层、数据表字段名、前端/后端职责等）。

### 24.3 测试同步（本轮唯一被改的测试文件）

`frontend/tests/login-view.spec.ts`：

- 用例 `展示平台能力要点时只陈述已具备的能力` → 重命名为
  **`左侧要点用面向使用者的业务描述，不出现开发术语`**；
- 断言新文案 4 条要点全部存在；
- 新增「开发术语黑名单」断言：页面文本不得包含
  `四层权限` / `后端` / `前端` / `接口` / `SKU` / `BOM`；
- 渲染用例补一条主标题断言 `服饰企业一体化经营管理平台`；
- 文件头补写「左栏是给业务用户看的，这类回归肉眼容易漏，所以写进测试」。

用例总数不变（仍 11 条），仅内容调整。

### 24.4 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| 前端测试 | `Test Files 13 passed (13)` / `Tests 170 passed (170)` |
| `vue-tsc --build --force` | 退出码 `0` |
| `vite build` | `✓ built in 11.07s` |
| 迁移 | **无迁移**（只改前端文案） |
| 后端测试 / `ruff` / `manage.py check` | 本轮无后端改动，基线不变（`322 passed`） |

### 24.5 与既有文档的关系

本节**取代** `§23.1` 中「左侧补 4 条已实现能力要点（统一账号与四层权限 / 统一主数据 /
单据与审批留痕 / 关键操作后端校验）」这一行的描述，以及 `§23.1` 末尾提到的旧用例名
`展示平台能力要点时只陈述已具备的能力`（已重命名，见 24.3）。
`§23` 其余内容（双栏布局、样式搬入组件、960px 断点、jsdom 限制）依然有效。

### 24.6 未完成事项

1. **浏览器截图级 UI 核对仍未执行**（浏览器自动化被安全策略拒绝）——
   新文案比原文案长（定位文案由 1 行变 2 行），请人工打开 `http://127.0.0.1:5173/login`
   确认左栏在 1080px 宽度下不溢出、不与右侧登录卡挤压。
2. 若客户希望左栏出现**具体模块名**（如「销售管理 / 仓储管理 / 质量管理」）或
   **客户化宣传语**，需要客户提供措辞——注意 QMS / MES / EAM / EMS / EHS 等模块
   目前**尚未实现**，不能写进登录页。


## 二十五、修复「登录后工作台是空的」+ 全站文案改为面向使用者（本轮增量）

> 用户反馈两件事：
> ①「登录成功进入系统会加载一个工作台，但工作台内容是空的」；
> ②「系统里面的其他文字描述不要采用面向开发者的描述，应该采用面向用户的描述」。
> 本轮**含后端改动（新增只读展示字段）**，**无迁移**。

### 25.1 空白工作台的根因（不是接口没数据）

先排除「接口返回空」：直接以 `admin` 调用 `apps.analytics.services.dashboard()`，11 张卡片
（物料 65、SKU 50、款式 6、仓库 6、储位 228、在职员工 15、启用账号 11、部门 13、工厂 2、
车间 6、线体 6）与 10 条最近操作都有数据。**接口是好的，问题在前端落点。**

真实原因：登录成功后 `LoginView` 执行 `router.replace('/')`，而**站点根路径 `/` 只是布局外壳**
（`BasicLayout` + 动态子路由），它**没有自己的页面组件**。于是：

- 侧边栏、顶部、标签页都渲染了（面包屑当时还**写死**「工作台」，标签页标题默认值也是「工作台」）；
- `<router-view>` 里没有任何页面 → 内容区空白。

用户看到的就是「加载了个工作台，但里面是空的」。

### 25.2 修法

| 位置 | 改动 |
| --- | --- |
| `frontend/src/router/index.ts` | 新增 `resolveHomePath(menus)`：取**该账号菜单里的第一个页面**；路由守卫里 `to.path === '/'` 时重定向过去（`replace: true`） |
| 同上 | 新增 `menuTrail(menus, path)`：返回地址在菜单树里的层级链路，供面包屑使用 |
| `frontend/src/layouts/BasicLayout.vue` | 面包屑由写死的「工作台」改为按 `menuTrail` 渲染真实层级（如「基础资料 / 物料档案」） |

要点：落地页**不是硬编码 `/workspace`**，而是「该账号第一个可访问页面」。这样没有
`analytics.dashboard.view` 权限的账号也不会被扔到一个 403/404 页面上。

### 25.3 审计与工作台不再显示内部英文标识

排查文案时发现一个真实问题：审计日志的「对象类型」、工作台「最近操作记录」直接渲染
`object_type`，值是 `app_label.ModelName`（`masterdata.Material`、`identity.Role`…），
变更摘要是整块 `{字段: {before, after}}` 原始 JSON，键是英文字段名。业务用户看不懂。

修法（**展示名由后端算好，前端只渲染**，避免前端再维护一份翻译表）：

| 后端新增 | 位置 | 说明 |
| --- | --- | --- |
| `object_type_label(value)` | `backend/apps/core/services.py` | `app_label.ModelName` → 模型 `verbose_name`（中文）；解析不到**原样返回**，不猜名字 |
| `display_value(value)` | 同上 | `None`/空串 → 「空」；布尔 → 是/否；列表 → 「、」拼接 |
| `describe_changes(object_type, changes)` | 同上 | 字段名 → 中文名；非模型字段的键由 `AUDIT_CHANGE_LABELS` 显式登记（`grants` → 数据范围、`line_count` → 明细行数…），两边都查不到则保留原键名 |
| `object_type_display` / `changes_display` | `backend/apps/core/serializers.py` | 只读序列化字段，**不改表结构、无需迁移** |
| `action_display` / `object_type_display` | `backend/apps/analytics/services.py` | 工作台 `recent_activity` 一并返回中文名 |

前端对应渲染：

- 工作台时间线由「操作人 + 英文模型名 + 对象」改为 `activityText()` 生成的一句话，
  例如「系统管理员 新增 角色「审计测试角色」」；
- 审计日志列表「对象类型」列改用 `object_type_display`，「请求编号」列标题中文化；
- 审计详情抽屉的变更摘要由 `<pre>` 原始 JSON 改为三列表格（字段 / 变更前 / 变更后）。

### 25.4 全站文案：从开发视角改为使用者视角

`frontend/src/views/**` 里 40 余处页面说明、空状态、表单提示、弹窗文案统一改写，原则是
「讲使用者能做什么」，而不是「系统内部怎么实现」。代表性改写：

| 位置 | 改前（开发视角） | 改后（使用者视角） |
| --- | --- | --- |
| 工作台说明 | 卡片数值全部实时计算…无权限的卡片后端不会返回 | 这里汇总与您当前工作直接相关的信息…数字全部由业务数据实时统计 |
| 工作台横幅 | 当前阶段说明 / 本平台当前处于阶段 1（登录、权限、组织…） | 当前可用的业务范围 / 现在可以办理：基础资料、工厂与排班、客户与供应商、采购、销售、仓储、生产计划、审批与内部协同 |
| 工作台区块 | 主数据规模（按数据范围统计） | 基础资料与组织概览 |
| 卡片悬浮提示 | 来源：masterdata.Material ｜ 时间字段：created_at ｜ 口径…｜ 权限… | 统计口径：… ｜ 统计时间：… |
| 仓储 | 阶段 1 只交付仓库、库区、储位主数据…属阶段 2 | 维护仓库、库区与储位结构。库存数量与出入库记录请在「库存余额」「库存流水」页面查看 |
| 计量单位 | 数量按 20 位整数、6 位小数存储；不改变后端计算精度 | 计量单位用于统一数量口径…小数位只影响页面显示的小数位数，不改变系统内部的计算精度 |
| 角色 | 权限分四层：菜单、操作、接口、数据范围…（fail-closed）处理 | 角色决定「能用哪些功能」和「能看到哪些数据」：先勾选菜单与操作权限，再设置数据范围…宁可少看不可多看 |
| 用户 | 用户负责登录与权限…平台不提供用户物理删除 | 用户用于登录与权限分配；账号不再使用后请停用而不是删除，历史操作记录需要保留 |
| 计划 | BOM 是版本化工程数据…已下达工单引用的快照不会被改写 | BOM（用料清单）是版本化资料…已下达的生产工单仍按当时的用料清单执行 |
| MRP | MRP 按「销售需求 → 净算 → BOM 展开 → 缺料建议」同步计算 | 物料需求运算按「销售需求 → 净需求计算 → 用料清单展开 → 缺料建议」一次算完 |
| 审批待办 | 审批通过与库存过账是两个动作 | 审批与出入库是两个独立动作，通过审批不会直接改变库存 |
| 采购订单 | 金额由后端按行重算…具备 override 权限，例外会写入审计 | 金额由系统按明细自动计算…必须填写例外原因并拥有相应权限，例外会记入操作日志 |
| 销售发货 | 重复点击按幂等键只扣一次 | 重复提交只会扣减一次 |
| 质量判定提示 | 未接入真实检测设备接口：此处为人工判定… | 本判定为人工填写，系统未接入检测设备；结论与判定人会一并记录 |
| 通用错误提示 | 无法连接服务器，请检查网络或后端服务状态 | 无法连接服务器，请检查网络后重试 |
| 列表错误提示 | 请把页面提示与后端日志中的 request_id 一起反馈给系统管理员 | 请把这条提示和发生时间一并反馈给系统管理员 |
| 实施进度页 | 实时计数（来自当前环境的后端接口）/ 阶段实施状态（文档镜像）/ **尚未实施** 的模块… | 当前环境的实时计数 / 各阶段实施状态 / 尚未实现的模块不会出现在菜单里 |

另外修掉一个**显示缺陷**：实施进度页横幅原本写的是 `**尚未实施**`（Markdown 语法），
会原样显示两个星号，已改为普通文字。

**保留**：代码注释、日志、管理命令输出等面向维护者的文本不变；实施进度页仍保留「阶段 / 验收
状态 / 未完成事项」这类管理员需要的信息（该页的用途就是回答「现在能用哪些模块」）。

### 25.5 本轮新增/调整的测试

| 文件 | 用例 | 锁住什么 |
| --- | --- | --- |
| `frontend/tests/menu-home.spec.ts`（新增 7 条） | 落地页解析 3 条 + 面包屑 3 条 + 守卫 1 条 | `/` 必须跳到菜单第一个页面；面包屑取真实层级；守卫用真实 router 验证「不再停在空白布局」 |
| `backend/tests/test_audit_display.py`（新增 9 条） | 翻译 / 兜底 / 接口字段 / 工作台字段 | 模型能翻成中文；查不到原样返回；**全库模型不得出现非中文展示名**（白名单仅 `SKU`）；接口确实返回 `object_type_display` 与 `changes_display` |
| `frontend/tests/login-view.spec.ts` | 1 条断言更新 | 登录页要点标题改为「基础资料统一维护」 |
| `frontend/tests/styles.spec.ts` | 1 条夹具更新 | `ys-code-block` 共享类的代表页面由审计日志改为 `BomList`（审计详情已改用表格） |

### 25.6 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| 后端测试 | `331 passed in 130.91s`（本轮前 322，新增 9，无回归） |
| `ruff check` | `All checks passed!` |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `makemigrations --check --dry-run` | `No changes detected`（**无迁移**：新增字段都是只读 SerializerMethodField） |
| 前端测试 | `Test Files 14 passed (14)` / `Tests 177 passed (177)`（本轮前 13/170，新增 7） |
| `vue-tsc --build --force` | 退出码 `0` |
| `vite build` | `✓ built in 14.84s` |
| `pytest tests/test_docs_sync.py` | `7 passed`（使用说明已重建） |

> 说明：本节记录的是当时的结果，其中 `scripts/smoke_check.ps1` **当时会偶发失败**（vitest 报 1 条 unhandled error，断言全通过）。原因与修法见 §26，最终结果以 §26.5 为准。

### 25.7 未完成事项

1. **浏览器观感未人工确认**（本机未安装 Playwright，浏览器自动化被安全策略拒绝）：
   请登录后确认①不再出现空白内容区、②面包屑显示「基础资料 / 物料档案」这类层级、
   ③工作台时间线是中文句子、④审计日志「对象类型」是中文。
2. `identity.Role` 的 `company_id` 中文名是模型自带的「归属公司」，审计界面沿用，
   未做人工润色（保持与模型 `verbose_name` 一致，避免两处叫法不同）。
3. 权限类型枚举里的「接口权限」是平台四层权限的既有术语（`models.py`、`docs/permission-matrix.md`、
   用户手册都在用），本轮未改名；若要改成更面向业务的叫法，需要同时改枚举、文档与测试。
4. 审计详情里的「客户端」仍显示原始 User-Agent 字符串（这是原始数据，不做美化）。

### 25.8 与既有文档的关系

本节**不影响** §24（登录页文案）与 §23（登录页改版）；§24.6 提到的「浏览器观感未确认」
在本轮同样适用。实施进度页的文案已在上一轮（`§24` 之外的本轮改动）一并调整，页面内容
（阶段清单）不改写。
## 二十六、冒烟脚本偶发失败的真实原因（测试环境拆除竞态）与剩余开发视角文案（本轮增量）

> 起因：上一轮（§二十五）收尾时 `scripts/smoke_check.ps1` 会**偶发**失败，报 1 条 vitest
> unhandled error；同时全站文案仍有少数开发视角写法没清掉。本轮把这两件事做完。
> **无迁移**；接口只多了一个只读展示字段（内部协同事件的中文业务对象名）。

### 26.1 失败原因：不是用例失败，是「迟到回调」

先复现、再下结论，避免把「跑不过」当成「代码坏了」：

- `npm run test` 与 `node node_modules/vitest/vitest.mjs run` 都输出
  `Test Files 14 passed (14)` / `Tests 177 passed (177)`，**断言全部通过**；
- 失败的那几次额外打印 1 条 `Unhandled Errors`：
  `ReferenceError: requestAnimationFrame is not defined`，
  栈是 `Object.doLayout (table/src/table/style-helper.ts:83) ← trailingEdge (lodash-es/debounce.js:144)`，
  并注明 `This error was caught after test environment was torn down.`；
- 探针脚本抓到确切机制：Element Plus 表格把重排包成 `debounce(doLayout, 50)`
  （`table.mjs:104`），而 `doLayout()` 结尾必然调用全局 `requestAnimationFrame`
  （`style-helper.mjs:83`）。用例结束后组件仍留在内存里，这个 50ms 定时器就在 jsdom
  环境拆除**之后**才触发，此时 `requestAnimationFrame` 已随环境消失 → 报错。
- 实测衰减窗口：卸载组件后，迟到重排**只在 50ms 内出现 1 次，之后归零**。

结论：这是「定时器生命周期」问题，**不是业务用例失败**，也不该靠重跑掩盖。

### 26.2 修法：统一卸载 + 文件结束前静默期（`frontend/tests/setup.ts`）

| 措施 | 作用 |
| --- | --- |
| `enableAutoUnmount(afterEach)` | 每个用例结束后卸载组件；表格的 `onBeforeUnmount` 会 `cancel()` 待触发的重排 |
| `afterAll` 等待 120ms | 文件结束前留静默期，让「卸载本身重新排出的那一次重排」在环境还活着时跑完 |
| 补 `requestAnimationFrame` / `cancelAnimationFrame` 兜底桩 | 环境不提供时也不会静默失败 |

两个要点：**只卸载不够**（卸载动作本身会再排一次重排，探针实测迟到 1 次），必须配合静默期；
改动只在测试基建里，不动业务代码，也不改变任何断言。

### 26.3 剩余开发视角文案（本轮清零）

| 位置 | 改前 | 改后 |
| --- | --- | --- |
| 采购申请 / 销售订单详情 | 审批实例 | 审批单号（未提交时显示「未提交审批」） |
| 角色 → 数据范围明细 | 对象 ID | 对象编号 |
| 我的通知 | 业务 ID | 关联业务编号 |
| 内部协同（列表与详情） | 对象 ID、事件 ID、原始 `sales.SalesOrder` | 对象编号、事件编号、中文业务对象名 |
| 角色 → 数据范围弹窗提示 | 「不能通过其他方式越权」 | 「其他途径同样无法超出该范围」 |
| 实施进度（阶段 0 说明、未完成清单） | 后端与前端、容器化部署脚本、C 编译工具链 | 服务与界面、容器化部署配置、本机缺少编译工具链 |

配套后端改动（本轮唯一一处）：`apps/integration/serializers.py` 增加只读字段
`aggregate_type_display`，复用 §二十五 的 `object_type_label()` 把 `sales.SalesOrder`
翻成「销售订单」；**原始值照旧返回**，排查问题不受影响。

### 26.4 本轮新增测试

| 文件 | 用例 | 锁住什么 |
| --- | --- | --- |
| `frontend/tests/copy-tone.spec.ts`（新增 4 条） | 列标题 / 内部协同 / 审计 / 工作台 | 可见文案不出现「对象 ID / 业务 ID / 事件 ID / 审批实例」；内部协同、审计、工作台必须渲染后端算好的中文展示字段 |
| `backend/tests/test_audit_display.py`（新增 1 条） | 内部协同事件带中文业务对象名 | `aggregate_type` 原值保留、`aggregate_type_display` 为「销售订单」 |

### 26.5 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| `powershell -File scripts/smoke_check.ps1` | **`全部检查通过。`（退出码 0）** |
| 后端测试 | `332 passed in 126.38s (0:02:06)` |
| `ruff check --no-cache apps config tests` | `All checks passed!` |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `makemigrations --check --dry-run` | `No changes detected` |
| 前端测试 | `Test Files 15 passed (15) / Tests 181 passed (181)`，连跑 3 次均无 unhandled error |
| `vue-tsc --build --force` | 退出码 `0` |
| `vite build` | `✓ built in 12.62s` |
| 真实 HTTP 抽查（只读） | `GET /api/v1/analytics/dashboard/` = 200，11 张卡片 + 10 条中文动态；`GET /api/v1/audit-logs/` = 200，`object_type_display="用户"`、`action_display="登录"` |

### 26.6 未完成事项

1. **浏览器观感仍需人工确认**（本机未安装 Playwright，浏览器自动化被安全策略拒绝）：
   请登录后确认①不再出现空白内容区、②面包屑显示层级、③工作台时间线是中文句子、
   ④审计「对象类型」是中文、⑤内部协同「业务对象」显示「销售订单」这类中文名。
2. 权限四层术语里的「接口权限」按任务书保留（`docs/permission-matrix.md` 同名），未改名。
3. 内部协同页的 `event_type`（如 `sales.order.approved`）仍显示原始标识：
   它是管理员定位失败原因用的事件编码，**不做翻译**。

## 二十七、个人中心移除「接口文档」入口 + 使用说明改为面向客户（本轮增量）

> 起因：用户反馈 ①登录后个人中心下拉里的「接口文档」不该出现；②`docs/user-guide.md` 是给客户看的，
> 却混入了启动命令、环境变量、测试命令、文档同步规则等开发内容。
> 本轮去掉入口，并把使用说明改写为**纯客户使用手册**。**无迁移、无接口变化**。

### 27.1 界面：个人中心不再出现「接口文档」

| 改动 | 文件 | 说明 |
| --- | --- | --- |
| 删除下拉项「接口文档」 | `frontend/src/layouts/BasicLayout.vue` | 个人中心下拉只剩「修改密码 / 使用说明 / 退出登录」 |
| 删除 `openDocs()` | 同上 | 不再从界面跳转 `/api/v1/docs/` |

- 后端 OpenAPI 端点（`/api/v1/docs/`、`/api/v1/schema/`）**保留**，只是界面不再提供入口，
  开发者仍可直接访问（地址见 `docs/deployment.md` §二 7）。
- 顶部工具栏与个人中心的「使用说明」入口**保留**。

### 27.2 文档：`docs/user-guide.md` 改写为面向客户

改写前该文件同时承载两类内容：客户怎么用（登录、菜单、按模块操作、报错处理）与
开发怎么跑（启动命令、环境变量、测试命令、文档同步规则、未执行清单）。
本轮按「客户手册」重写，开发内容**迁移而非删除**。

| 原章节 | 处理 |
| --- | --- |
| §一 这份文档怎么用 | 保留，改为客户视角（去掉「开发人员，改了代码」一行） |
| §二 能力边界 | 保留，去掉技术规模计数（权限点 / 模型 / 迁移 / `.vue` 数量）；「两条最容易误会的规则」改为表格 |
| §三 环境准备与启动 | **移出** → `docs/deployment.md` §二 5~8（启动脚本、命令开关、访问地址、数据库与文件位置） |
| §四 账号与权限 | 保留可用部分（四层权限、内置角色、分配步骤）；**删除演示账号表与角色的权限点计数** |
| §五 界面导航与通用操作 | 保留；菜单清单由「路由 + 权限编码」改为「目录 + 页面 + 用途」 |
| §六 按模块操作指南 | 保留并去开发化（如幂等键、接口路径、快照接口） |
| §七 跟着做一遍 | 保留；演示账号名换成角色名，演示单号仍作示例 |
| §八 测试与自检 | **移出** → `AGENTS.md` §四/§五、`docs/test-report.md` |
| §九 常见问题与错误码 | 保留错误码表；「环境类问题」（后端未启动 / Vite 端口 / 驱动编译 / CSRF）改为面向客户的「界面与其他问题」 |
| §十 未执行 / 未验证 | **移出** → `docs/test-report.md` |
| §十一 代码更新后同步 | **移出** → `AGENTS.md` §九（含机器可读事实行与网页版生成规则） |

配套改动：

| 文件 | 改动 |
| --- | --- |
| `AGENTS.md` | 新增 §九「面向客户的使用说明与文档同步」：定位约束、网页版生成命令、事实行与键说明；§五 收尾清单加第 6 条；§六 文档地图加 `docs/user-guide.md` |
| `backend/tests/test_docs_sync.py` | 事实行改从 `AGENTS.md` 读取（`SYNC_DOC_PATH`），用例名与提示同步更新；网页版新鲜度校验不变 |
| `scripts/build_user_guide.py` | 日期标记改为「最后更新：YYYY-MM-DD」；标题 / 横幅 / 页脚改为面向客户的文案（不再出现 `docs/*.md` 路径） |
| `docs/deployment.md` | 顶部交叉引用改写；补齐原属使用说明的开发内容（日常启动、命令开关、访问地址、数据库与文件位置） |
| `docs/acceptance.md` | 「现在的数字」指向 `AGENTS.md` §九 事实行（原指向已移除的 `user-guide.md` §2.3） |
| `README.md` | 文档地图与访问地址表更新；文档同步要求指向 `AGENTS.md` §九 |

### 27.3 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| `pytest tests/test_docs_sync.py -q --reuse-db` | `7 passed in 0.12s` |
| `python scripts/build_user_guide.py` | 生成 `docs/user-guide.html`（49950 字符）与 `frontend/public/guide.html` |
| `ruff check --no-cache apps config tests ../scripts/build_user_guide.py` | `All checks passed!` |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `makemigrations --check --dry-run` | `No changes detected` |
| 前端 `vue-tsc --build --force` | 退出码 `0` |
| 前端 `npm run test` | `Test Files 15 passed (15) / Tests 181 passed (181)` |
| 前端 `vite build` | `✓ built in 12.68s` |
| HTML 静态校验 | 17 张表格、36 个标题（8 个一级 / 28 个二级）、0 处未渲染的 `**`、0 行表格语法泄漏 |

### 27.4 未完成事项

1. **浏览器观感未人工确认**：本轮尝试用浏览器打开页面被安全策略拒绝
   （`file://` 与 `http://127.0.0.1:5173` 均被 Browser use 策略拦截），
   因此只做了 HTML 静态校验与源码级检查。请登录后确认：
   ①个人中心下拉里不再有「接口文档」；②顶部与个人中心的「使用说明」仍能打开 `/guide.html`。
2. 使用说明正文的描述性内容（菜单名称、操作步骤、错误码解释）仍只能人工维护，
   自动校验只覆盖「网页版是否与 Markdown 一致」与 `AGENTS.md` 的事实行数量。


## 二十八、设备管理 / 能源管理 / 生产物流 / 安全环保四大模块落地（本轮增量）

> 起因：用户给出约 60 个页面的功能清单（设备管理、能源管理、客户管理、生产物流管理、安全环保管理），
> 要求「加一下这些功能」。本轮落地**设备管理 / 能源管理 / 生产物流管理 / 安全环保管理**四块，
> 共新增 4 个后端 App、41 个数据模型、5 个迁移、137 个权限点、69 项菜单、4 个内置角色；
> **客户管理深化（客户投诉、产品评价）与设备数采硬件接入明确不在本轮**（理由见 28.8）。

### 28.1 需求清单逐项对照

| 用户清单 | 落地情况 | 页面 / 接口 |
| --- | --- | --- |
| 设备基础信息管理：设备信息管理、设备类型管理、设备零部件管理、设备台账 | **已实现** | `/equipment/equipments`、`/equipment/types`、`/equipment/parts`、`/equipment/ledger` |
| 备品备件、配件管理、故障保修 | **已实现** | `/equipment/spare-parts`、`/equipment/accessories`（配件视角复用备件台账）、`/equipment/fault-reports` |
| 库存台账（备件现存量与寿命） | **已实现（只读）** | `/equipment/spare-part-stock`，数字来自仓储统一库存余额，不新建库存表 |
| 采购申请（备件，兼容计划 / 紧急采购） | **已实现** | 菜单指向 `/procurement/requisitions`（`procurement.Requisition` 已有 `plan` / `urgent` 类型） |
| 设备保养管理：项目 / 计划 / 任务 / 日历 / 记录 | **已实现** | `/equipment/maintenance-items`、`maintenance-plans`（可一键生成到期任务）、`maintenance-tasks`、`maintenance-calendar`、`maintenance-records` |
| 设备维修管理：维修任务、维修记录 | **已实现** | `/equipment/repair-tasks`、`/equipment/repair-records` |
| 点巡检管理：项目 / 任务 / 记录 | **已实现** | `/equipment/inspection-items`、`inspection-tasks`、`inspection-records` |
| 设备异常上报：异常类型 / 任务 / 记录 | **已实现** | `/equipment/abnormal-types`、`abnormal-tasks`、`abnormal-records` |
| 设备数采和监控（设备数据采集展示） | **未实现** | 需要采集网关 / 协议接入，属硬件接入阶段，见 `docs/hardware-integration.md` |
| 能源管理：首页 / 设备监控 / 运行记录 / 报警 / 看板 / 报表 / 统计 | **已实现** | `/ems/home`、`/ems/monitor`、`/ems/run-records`、`/ems/alarms`、`/ems/kanban`、`/ems/report`、`/ems/statistics` |
| 用水 / 用电 / 用气 / 用液统计 | **已实现** | 四条菜单共用 `/api/v1/ems/statistics/`，只固定 `medium` 参数 |
| 基础管理：水价 / 电价 / 气价 / 液价 / 阈值 / 区域 / 设备 | **已实现** | `/ems/base/*`（价格按介质分页，阈值支持读数上下限、日用量、单耗、离线时长） |
| 客户管理：客户投诉、产品评价 | **未实现** | 属 CRM 深化（阶段 6），见 28.8 |
| 生产物流管理：自动化设备 / 任务管理 / 操作日志 | **已实现** | `/logistics/devices`、`/logistics/tasks`、`/logistics/logs` |
| 安全环保管理：安全管理 / 环保管理 / 消防管理 / 设备设施安全 / 操作日志 | **已实现** | `/ehs/safety/*`、`/ehs/environment/*`、`/ehs/fire/*`、`/ehs/equipment-safety/*`、`/ehs/logs` |

### 28.2 后端新增（4 个 App、41 个模型、5 个迁移）

| App | 模型数 | 迁移 | 说明 |
| --- | --- | --- | --- |
| `apps/equipment` | 17 | `0001_initial`、`0002_...` | 设备类型 / 设备 / 零部件 / 备品备件、保养项目计划任务记录、报修单、维修任务记录、点巡检项目任务记录、异常类型任务记录 |
| `apps/ems` | 7 | `0001_initial` | 计量区域、计量设备、能源价格、能源阈值、抄表读数、设备运行记录、能源报警 |
| `apps/logistics` | 3 | `0001_initial` | 自动化设备、物流任务、操作日志 |
| `apps/ehs` | 14 | `0001_initial` | 安全制度 / 培训 / 隐患 / 应急预案 / 事故、排污监测 / 固废危废 / 环保合规、消防设施 / 演练 / 作业许可、安全检查 / 特种设备检验、操作日志 |

编码规则新增 30 条（`EQ` / `SP` / `MP` / `MT` / `MR` / `FR` / `RT` / `RR` / `IT` / `IR` / `AT` / `AR`、
`EM` / `EAL` / `ERN`、`AD` / `LT`、`SRG` / `TRN` / `HZD` / `EPL` / `ACR` / `ENV` / `WST` / `CMP` / `FDR` / `FFC` / `WPR` / `SCH` / `SPI`），
`CODE_RULES` 由 15 条增至 **45 条**。

### 28.3 分层与业务规则的落实方式

1. **状态只由服务层推进。** 保养 / 维修 / 点巡检任务、报修单、异常任务、能源报警、运行记录、
   物流任务、隐患、事故、作业许可、环保合规检查的 `status` 在序列化器里一律 `read_only`，
   前端点 PATCH 改不动；流转只能走动作接口（如 `.../dispatch/`、`.../finish/`、`.../verify/`）。
   **本轮为 3 个序列化器补上了这个漏洞**（见 28.4）。
2. **公司由服务端推导。** 设备 / 能源 / 物流 / EHS 的单据都挂在当前用户的公司下，
   前端不传 `company_id`；越权写入由 `assert_in_scope` 拦截并返回 `OUT_OF_DATA_SCOPE`。
3. **不碰库存表。** 备件现存量（库存台账）是只读汇总，数据来自 `wms` 的统一库存余额，
   设备模块不写任何库存表；备件采购走既有 `procurement` 申请流程，不另建申请单。
4. **环保达标由服务层判定。** 排污监测保存后由 `apply_monitor_compliance` 按「实测值 vs 排放限值」
   自动写入 `is_compliant`，该字段只读，客户端改不动。
5. **操作日志只读。** 物流与安全环保的操作日志由服务层在业务事务内写入，接口只提供列表 / 详情。

### 28.4 本轮修复的两个真实缺陷（都会让页面直接不可用）

| 缺陷 | 现象 | 根因 | 修法 |
| --- | --- | --- | --- |
| `dispatch` 覆盖 `APIView.dispatch` | 报修单与物流任务**整个视图集**所有请求 500（`WSGIRequest has no attribute query_params`） | DRF `@action(..., url_path="dispatch")` 会把方法装成实例属性，与 `APIView.dispatch` 同名即覆盖 | 方法改名 `dispatch_repair` / `dispatch_task`，URL 仍是 `.../dispatch/`，权限键同步改名 |
| DRF `UniqueTogetherValidator` 强制必填 | 保养计划 / 任务 / 记录、报修单、维修、点巡检、异常的新增全部 400「该字段是必填项」 | 模型上 `UniqueConstraint(company, xxx_no)` 被 DRF 转成唯一性校验器后，把服务端推导的 `company` 变成必填 | 新增 `DerivedCompanySerializerMixin.get_unique_together_validators()` 返回 `[]`，10 个「公司由服务端推导」的序列化器继承它；编号字段改 `allow_blank=True, default=""` |

### 28.5 前端

新增 58 个 `.vue` 页面（设备 20、能源 18、物流 3、安全环保 17）与 3 个共享组件
（`EnergyChart.vue`、`EnergyStatisticsPanel.vue`、`WorkPermitPanel.vue`），
新增 `frontend/src/api/energy.ts`。菜单仍由后端下发（`identity/menus/mine/`），
前端没有硬编码业务菜单权限；`EMPTY_META` / `MetaPayload` / `MetaView` 三处枚举键同步扩充。

### 28.6 测试（本轮新增）

| 文件 | 用例数 | 覆盖重点 |
| --- | --- | --- |
| `backend/tests/test_equipment_api.py` | 12 | 公司范围、取号、保养到期任务幂等、任务完成生成记录并关闭报修单、点检异常转报修、状态不可 PATCH、只读库存台账 |
| `backend/tests/test_ems_api.py` | 15 | 取号、倍率与上次读数算用量、读数回退拒绝、越限报警去重、离线扫描、运行记录单耗与报警、报表价格折算与 xlsx 导出、只读抄表 |
| `backend/tests/test_logistics_api.py` | 11 | 取号、状态机跳步拒绝、故障设备不可下发、设备忙冲突、取消需理由、设备状态动作写日志、日志只读 |
| `backend/tests/test_ehs_api.py` | 11 | 取号、隐患整改验收闭环（不通过退回）、事故调查整改关闭、动火作业必须监护人、许可驳回需理由、排污达标服务端判定、日志只读 |

### 28.7 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `manage.py makemigrations --check --dry-run` | `No changes detected` |
| `ruff check apps config tests` | `All checks passed!` |
| `pytest tests -q --reuse-db`（全量） | `381 passed in 201.53s` |
| `pytest tests/test_equipment_api.py` | `12 passed` |
| `pytest tests/test_ems_api.py` | `15 passed` |
| `pytest tests/test_logistics_api.py` | `11 passed` |
| `pytest tests/test_ehs_api.py` | `11 passed` |
| `pytest tests/test_docs_sync.py` | `7 passed` |
| `manage.py bootstrap_system`（开发库，幂等重跑） | `权限点：新增 0，更新 310，注册表共 310 条。` / `菜单：新增 0，更新 125，注册表共 125 条。` / `编码规则：新增 0，共计 45 条。` |
| 前端 `npm run typecheck` | 退出码 `0`（vue-tsc） |
| 前端 `npm run test` | `Test Files 15 passed (15) / Tests 241 passed (241)` |
| 前端 `npm run build` | `✓ built in 16.91s` |

### 28.8 未完成事项（不要按「能用」去承诺）

1. ~~**设备数据采集与实时监控**未实现~~ —— **已于 §二十九补齐首版**（HTTP 上报入口 + 内置模拟器；
   MQTT / Modbus 与真实设备联调仍未做）。能源数据的「在线 / 离线」在 `ems` 侧仍是抄表超时推断，
   数采设备另有基于 `last_seen_at` 的在线状态。
2. ~~**客户投诉与产品评价**未实现~~ —— **已于 §二十九补齐**（`apps/crm` 的 `CustomerComplaint` /
   `ProductReview` 与两个页面）。
3. **浏览器观感未人工确认**：沙箱内无法启动 `runserver` / 浏览器，本轮只做源码级与接口级验证。
   请登录后确认：①左侧出现「设备管理 / 能源管理 / 生产物流管理 / 安全环保管理」四个目录；
   ②设备保养计划能否生成到期任务；③抄表后报警是否按阈值生成。
4. **EHS 与设备台账是两套表**：特种设备检验、本质安全检查引用设备台账但**不写设备表**，
   安全检查发现问题也**不会自动生成隐患单**（需要人工在「隐患排查」登记），避免跨模块隐式副作用。
5. **能源报表导出未做权限细分**：导出动作记审计日志（`EXPORT`），但与查看报表共用 `ems.report.view`。

### 28.9 与既有文档的关系

| 文档 | 变动 |
| --- | --- |
| `AGENTS.md` | 事实行更新为 `permissions=310 menus=125 models=127 migrations=24 builtin_roles=17` |
| `docs/permission-matrix.md` | §三 / §四 按注册表**重新生成**（310 条权限 / 125 项菜单） |
| `docs/requirements-matrix.md` | 新增 §一之十八 逐条对照 |
| `docs/data-model.md` | 新增 §九 equipment / ems / logistics / ehs 表清单 |
| `docs/test-report.md` | 新增 §二十七 本轮复验记录 |
| `docs/assumptions.md` | 新增 §四之七 本轮实现假设与偏差 |
| `docs/energy-calculation.md` | 补阶段 5 的计量、计价与报警口径 |
| `docs/business-flows.md` | 新增 §13 设备保养与维修闭环、§14 隐患整改闭环 |
| `docs/architecture.md` | §二 分层说明补四个新 App |
| `docs/deployment.md` | 补 `manage.py ems_offline_check` 定时任务说明 |
| `docs/user-guide.md` + `docs/user-guide.html` + `frontend/public/guide.html` | 能力表、菜单清单（125 项）、内置角色表同步并重新生成网页版 |

> 上表是 §二十八 当时的记录。本轮（§二十九）已把 `AGENTS.md` 事实行更新为
> `permissions=333 menus=134 models=134 migrations=27 builtin_roles=18`，
> 并按注册表重新生成 `docs/permission-matrix.md` §三 / §四 与网页版说明（菜单 134 项）。

## 二十九、客户投诉 / 产品评价 + 设备数采首版（本轮增量）

> 起因：用户确认「客户管理：客户投诉、产品评价」与「设备管理：设备数采和监控」两项要补做
> （上一轮 §二十八 明确标注为未实现）。本轮新增 `apps/iot`（5 个模型、1 个迁移）、
> 扩展 `apps/crm`（+2 个模型、1 个迁移）、`apps/ems` 增 `source_ref`（1 个迁移）；
> 新增 24 个权限点、9 项菜单、1 个内置角色、31 个后端用例。

### 29.1 需求清单逐项对照

| 用户清单 | 落地情况 | 页面 / 接口 |
| --- | --- | --- |
| 客户管理：客户投诉 | **已实现** | `/crm/complaints`（`accept` / `resolve` / `close` 动作接口） |
| 客户管理：产品评价 | **已实现** | `/crm/product-reviews`（`reply` / `close` 动作接口） |
| 设备管理：设备数采和监控 | **已实现（首版）** | 「设备数采和监控」目录：连接配置 / 数采设备 / 采集测点 / 设备监控 / 采集读数 / 采集日志 |

### 29.2 后端新增

| App | 模型数 | 迁移 | 说明 |
| --- | --- | --- | --- |
| `apps/crm` | +2（合计 4） | `0002_customercomplaint_productreview` | 客户投诉（`CMPL` 取号，`satisfaction` 约束 0~5）、产品评价（`PRV` 取号，`score` 约束 1~5） |
| `apps/iot` | 5（新建） | `0001_initial` | 连接配置（`IOTCN`）、数采设备（`IOTGW`，含令牌摘要）、测点（`IOTPT`）、采集报文、标准化读数 |
| `apps/ems` | 0（字段） | `0002_energyalarm_source_ref` | 报警增 `source_ref`，让数采报警按来源去重 |

编码规则新增 5 条（`CMPL` / `PRV` / `IOTCN` / `IOTGW` / `IOTPT`），`CODE_RULES` 由 45 条增至 **50 条**。

### 29.3 分层与业务规则的落实方式

1. **状态只由服务层推进。** 投诉的「受理 → 处理 → 关闭」与评价的「回复 → 关闭」都是 Service 动作，
   跳步抛 `StateConflict`（409），关闭前必须写处理措施（空措施 400）；`status` 与各时间戳字段在序列化器里只读，
   每次流转写审计日志（`record_audit`），**不另建业务日志表**。
2. **设备独立凭证，不复用员工会话。** `POST /api/v1/iot/ingest/` 显式 `authentication_classes = []`，
   只认 `X-Device-Token`（或 `Authorization: Device <token>`）；库里只存 SHA-256 摘要，
   明文令牌仅在生成 / 轮换响应里返回一次，轮换后旧令牌立即失效。
3. **采集读数不写能源抄表。** 测点上的 `meter` 只是对照线索；越限与离线统一调用
   `apps/ems/services.py::raise_alarm` 写入能源报警台账（`source_ref` = `iot:<设备编码>:<测点编码>`），
   **没有**在 iot 模块直接写 EMS 的表。
4. **模拟数据必须可辨识。** `is_simulated` 从连接 → 设备 → 报文 → 读数逐级传递；模拟设备**不参与离线判定**；
   模拟器走真实采集链路（`services.ingest_report`），不绕过校验直接写库。
5. **公司范围由服务端推导。** 测点的公司取自所属设备，序列化器不接受 `company_id`；
   跨公司引用（如把 A 公司客户挂到 B 公司投诉）在 `validate()` 与 `assert_object_in_scope` 两处拒绝。

### 29.4 本轮发现并修复的问题

| 问题 | 现象 | 根因 | 修法 |
| --- | --- | --- | --- |
| 数采报警互相顶掉 | 数采侧同一天多个测点越限时只留得下一条报警 | `raise_alarm` 的去重条件是「公司 + 类型 + 当日窗口 + 仪表」，而数采报警没有仪表（`meter` 为空），同类型的都被压成一条 | `EnergyAlarm` 增 `source_ref` 并纳入去重条件；EMS 自身报警 `source_ref` 留空，原口径不变（`test_over_limit_alarm_is_raised_once_per_day` 仍通过） |
| 新增代码未过 ruff | `ruff check` 报 5 项（未使用的导入、导入未排序、嵌套 `if`） | 新模块编写时未跑 ruff | 清理未用导入、合并嵌套判断；`All checks passed!` |

### 29.5 前端

新增 5 个 `.vue` 页面（`iot/GatewayList`、`iot/PointList`、`iot/DeviceMonitor`、`iot/ReadingList`、
`iot/MessageList`）与 `frontend/src/api/iot.ts`（设备监控聚合接口 + 令牌轮换动作）；
`views/iot/ConnectionList.vue`、`views/crm/ComplaintList.vue`、`views/crm/ProductReviewList.vue` 为前序增量。
菜单仍由后端下发（`identity/menus/mine/`）；`EMPTY_META` / `MetaPayload` / `MetaView` 三处枚举键同步扩充
（投诉 / 评价 5 个 + 数采 7 个）。设备令牌明文只在弹出窗口里展示一次，并提示「关闭后只能重新轮换」。

### 29.6 测试（本轮新增）

| 文件 | 用例数 | 覆盖重点 |
| --- | --- | --- |
| `backend/tests/test_crm_api.py` | 28（+11） | 投诉取号、完整生命周期与审计、跳步 409、未填处理措施 400、状态不可 PATCH、跨公司客户拒绝、公司范围、权限 403、评价取号与评分校验、回复 / 关闭生命周期、元数据枚举 |
| `backend/tests/test_iot_api.py` | 20（新建） | 未登录拒绝、无令牌 / 用员工会话上报被拒、令牌只存摘要、读数入库与双重去重、模拟标识、失败留痕、超批次与非法协议 400、按设备限流 429、越限报警每测点一条、离线扫描跳过模拟设备与最近上报设备、令牌轮换使旧令牌失效、测点公司由设备推导、取号、公司范围、权限 403、监控聚合、模拟器命令、元数据枚举 |

### 29.7 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `manage.py makemigrations --check --dry-run` | `No changes detected` |
| `ruff check apps config tests` | `All checks passed!` |
| `pytest tests/test_crm_api.py -q --reuse-db` | `28 passed in 15.43s` |
| `pytest tests/test_iot_api.py -q --reuse-db` | `20 passed in 5.88s` |
| `pytest tests -q --reuse-db`（全量） | `412 passed in 203.42s (0:03:23)` |
| `pytest tests/test_docs_sync.py -q --reuse-db` | `7 passed in 0.13s` |
| `manage.py bootstrap_system`（开发库，幂等重跑） | `权限点：新增 0，更新 333，注册表共 333 条。` / `菜单：新增 0，更新 134，注册表共 134 条。` / `编码规则：新增 0，共计 50 条。` / `角色 iot_admin（设备数采管理员）：新增，权限 21 个。` |
| 前端 `npm run typecheck` | 退出码 `0`（vue-tsc） |
| 前端 `npm run test` | `Test Files 15 passed (15)` / `Tests 249 passed (249)` |
| 前端 `npm run build` | `✓ built in 12.31s` |
| `python scripts/build_user_guide.py --check` | `使用说明网页版是最新的。` |

### 29.8 未完成事项（不要按「能用」去承诺）

1. **只实现了 HTTP 上报与内置模拟器**：连接配置可以登记 `mqtt` / `modbus`，但采集入口对未实现的协议
   返回 `PROTOCOL_NOT_IMPLEMENTED`（409）——**协议适配与真实设备联调未做**（待现场确认协议）。
2. **没有采集数据的小时 / 日汇总表与原始数据归档清理**：监控页按原始读数实时聚合，数据量增长后需要补汇总与归档。
3. **平台没有内置调度器**：数采离线扫描要由部署侧配置 `manage.py iot_offline_check`
   （能源侧同理是 `ems_offline_check`），当前只在开发机手工执行过。
4. **投诉不含外部渠道自动接入、自动分派与统计报表**；投诉与订单 / 批次的一键追溯仍是文字登记（`related_no`）。
5. **浏览器观感未人工确认**：沙箱内无法启动 `runserver` / `vite dev` / 浏览器，
   四个新页面只做了源码级（`vue-tsc`、`views-compile.spec.ts`、`styles.spec.ts`）与接口级验证。
   请登录后确认：①左侧出现「设备数采和监控」目录与 6 个页面；②「数采设备」里能生成令牌并只显示一次；
   ③用 `python manage.py iot_simulate --seed-demo --company <ID> --rounds 2 --out-of-range` 造数据后，
   「设备监控 / 采集读数 / 采集日志」有数据且带「模拟」标签，能源报警台账里出现越限报警。
6. **客户投诉 / 产品评价的统计报表**未做（本轮只做登记与处理闭环）。

### 29.9 与既有文档的关系

| 文档 | 变动 |
| --- | --- |
| `AGENTS.md` | 事实行更新为 `permissions=333 menus=134 models=134 migrations=27 builtin_roles=18`；§八 阶段边界改「设备数采首版 + 客户投诉与产品评价已完成」 |
| `README.md` | 当前状态、模块表（+2 行）、未开始清单、测试结果数字同步 |
| `docs/permission-matrix.md` | §三 / §四 按注册表**重新生成**（333 条权限 / 134 项菜单） |
| `docs/requirements-matrix.md` | 新增 §一之十九；REQ-11.3-01~09 由「未开始」改为「已完成」；REQ-12.2 / 12.3 / 12.4 闭环状态更新 |
| `docs/data-model.md` | `ems_energyalarm` 补 `source_ref`；新增 §十 crm / iot 表清单 |
| `docs/test-report.md` | 新增 §二十八 本轮复验记录 |
| `docs/assumptions.md` | §四之七 补 13~18 条实现假设；§六 未做清单同步 |
| `docs/hardware-integration.md` | 状态改为「首版已实现」；§六 未完成清单勾掉已做项，保留 MQTT / Modbus 等 |
| `docs/business-flows.md` | §12.2 / 12.3 / 12.4 状态更新；新增 §十五 设备数采闭环 |
| `docs/architecture.md` | §三 目录树与「已创建 / 未创建」清单同步（18 个 App） |
| `docs/user-guide.md` + `docs/user-guide.html` + `frontend/public/guide.html` | 能力表、菜单清单（134 项）、内置角色表同步，新增 §6.10 / §6.11 操作说明并重新生成网页版 |
| `frontend/src/views/system/ProgressView.vue` | 实施进度页的阶段说明与「已完成 / 未完成」清单同步 |

## 三十、采集统计与客户服务统计 + 两处实测缺陷修复（本轮增量）

> 起因：上一轮 §29.8 列出的未做项里，「数采采集数据的汇总与归档」与「客户投诉 / 产品评价的统计报表」
> 是**本方能自行完成**的部分。本轮 **不新增模型、不新增迁移、不新增权限点、不新增菜单**
> （事实行仍为 `permissions=333 menus=134 models=134 migrations=27 builtin_roles=18`），
> 只新增 3 个**只读统计接口**与前端统计区块，并修掉 3 个实测问题；后端用例 412 → **424**。

### 30.1 本增量内容

| 能力 | 落地情况 | 页面 / 接口 |
| --- | --- | --- |
| 设备数采：采集统计 | **已实现** | `GET /api/v1/iot/statistics/`；「设备数采和监控 → 设备监控」下方「采集统计」区块 |
| 客户投诉：统计 | **已实现** | `GET /api/v1/crm/complaints/statistics/`；「客户管理 → 客户投诉」顶部统计卡片与分布表 |
| 产品评价：统计 | **已实现** | `GET /api/v1/crm/product-reviews/statistics/`；「客户管理 → 产品评价」顶部统计卡片与评分分布 |

三个接口都是**只读**：不新增写路由，也不复用「列表」接口做客户端聚合（避免把整表拉到浏览器）。

### 30.2 后端新增

| 文件 | 内容 |
| --- | --- |
| `apps/iot/selectors.py`（新建） | `reading_statistics(user, *, granularity, since, until, company_id, gateway_id, point_id, is_simulated, limit)`：按「测点 × 时间桶」聚合采集读数，返回 `rows` / `buckets` / `totals` / `truncated` / `row_limit` |
| `apps/crm/selectors.py`（新建） | `complaint_statistics(...)` 与 `product_review_statistics(...)`：总量、未关闭 / 待回复、状态 / 类型 / 级别 / 来源分布、满意度平均分、评分分布与好评率 |
| `apps/iot/views.py` + `apps/iot/urls.py` | 新增 `IoTStatisticsView`（权限 `iot.reading.view`）与 `statistics/` 路由 |
| `apps/crm/views.py` | 两个 ViewSet 各加一个 `@action(url_path="statistics")`，权限复用 `crm.complaint.view` / `crm.product_review.view` |
| `apps/core/services.py` | 新增 `parse_business_moment(value, *, field, end_of_day)`：把查询串里的日期 / 日期时间按**业务时区**解析成 UTC 时刻 |

**统计口径（刻意如此，不要改成汇总表）**：

1. **一律按明细实时聚合，不落汇总表**——与 `apps/ems/selectors.py` 同一口径。设备会补发、会重传，
   任何「小时 / 日汇总表」在一次补发之后就会与明细对不上；实时聚合保证页面上的数字永远能回到
   「采集读数 / 投诉 / 评价」列表逐条核对。
2. **分桶按业务时区**（`YISHANG['BUSINESS_TIME_ZONE']`，默认 Asia/Shanghai）。按 UTC 截断会把北京时间
   08:00 之前的读数算进前一天。
3. **超限只做标记、不生成报警**：报警的判定与去重只发生在采集入库路径（`services.evaluate_point_limits`）
   与离线扫描上，避免同一份数据两处报警。
4. **不粉饰的空样本**：窗口内没有已回访样本时，平均满意度返回 `null`（前端显示「未回访」），
   而不是拿 0 分拉低平均值；未评价条数单独返回 `unrated_total`。好评 = 4 分及以上，`good_rate` 按百分比返回。
5. **时间窗上限是为了保护接口**：按小时默认近 48 小时、最多 31 天；按天默认近 30 天、最多 1096 天（约 3 年）；
   明细行默认 500 行、最多 2000 行，超出只标记 `truncated`，趋势桶最多 200 个。

### 30.3 前端

| 文件 | 内容 |
| --- | --- |
| `frontend/src/components/EntityListPage.vue` | 新增 `#summary` 插槽（位于页头与表格之间）与 `@refresh` 事件；`refresh()` = 重新拉列表 + 抛出 `refresh` 事件，供列表页在「刷新」时同步刷新统计 |
| `frontend/src/views/crm/ComplaintList.vue` | 顶部 3 张统计卡片（总数 / 未关闭 / 平均满意度，未回访时显示「未回访」）+ 分布表（处理状态 / 投诉类型 / 投诉级别 / 投诉来源） |
| `frontend/src/views/crm/ProductReviewList.vue` | 顶部 4 张统计卡片（总数 / 待回复 / 平均评分 / 好评率）+ 评分分布表（含各分数占比） |
| `frontend/src/views/iot/DeviceMonitor.vue` | 新增「采集统计」区块：按小时 / 按天切换、统计区间提示、4 张卡片（样本数 / 覆盖测点 / 超限时间桶 / 读数合计）+ 明细表（时间桶 / 设备 / 测点 / 样本数 / 最小 / 最大 / 平均 / 单位 / 越限 / 数据标识） |
| `frontend/src/api/crm.ts`（新建）、`frontend/src/api/iot.ts`、`frontend/src/types/models.ts` | 三个统计接口的封装与类型定义 |

统计请求失败时**静默降级**（不打断列表与页面），页面主体功能不受影响。
前端未新增 scoped 样式，仍只用共享原语（`ys-stat-cards` / `ys-ml-4` / `ys-muted` 等），
`frontend/tests/styles.spec.ts` 与 `views-compile.spec.ts` 继续通过。

### 30.4 本轮发现并修复的三个问题

| 问题 | 现象 | 根因 | 修法 |
| --- | --- | --- | --- |
| 日期型 `until` 被静默当成当天 00:00 | 统计接口传 `until=今天` 时，**当天全部数据被排除** | Python 3.11+ 的 `datetime.fromisoformat` 也接受纯日期串，先走它则 `end_of_day=True` 永远不生效 | `parse_business_moment` 先 `date.fromisoformat` 判纯日期，再回退到 `datetime.fromisoformat`，并加注释说明原因 |
| 设备监控接口 N+1 查询 | 测点多时，设备监控页对**每个测点**单独查一次最新读数 | 逐点查询 | 改为「每测点取最新 id」子查询（`Subquery(latest_ids.values("id")[:1])`）一次性取回再按 `point_id` 映射；无读数的测点仍会显示（`latest_value=null`） |
| 新增用例未过 ruff | `ruff check apps config tests` 报 5 项：`tests/test_iot_api.py` 的导入块未排序（`I001`）、4 处 `datetime(tzinfo=timezone.utc)` 应使用 `datetime.UTC`（`UP017`） | 新增用例时未跑 ruff（写入在测试之后） | 改为 `from datetime import UTC, datetime, timedelta`，4 处改用 `tzinfo=UTC`；`ruff check --no-cache apps config tests` → `All checks passed!` |

### 30.5 测试（本轮新增）

后端新增 12 个用例（`tests/test_iot_api.py` +6、`tests/test_crm_api.py` +6）：

- 数采统计：权限 403；**按业务时区分桶**（并验证「删掉明细后统计跟着变」，证明不是汇总表）；
  筛选（设备 / 测点 / 模拟标识）与 `is_simulated` 判定；非法粒度与超宽区间被拒；
  公司范围收敛；设备监控每测点取最新读数。
- 客户服务统计：投诉总量与分布；无评分样本时平均满意度为 `null` 且 `unrated_total` 正确；
  统计接口权限 403；公司范围收敛；评价平均分与好评率；评价统计的日期筛选（含 `until` 含当天）。

### 30.6 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `ruff check --no-cache apps config tests` | `All checks passed!` |
| `pytest tests/test_iot_api.py -q --reuse-db` | `26 passed` |
| `pytest tests/test_crm_api.py -q --reuse-db` | `34 passed` |
| `pytest tests -q --reuse-db`（全量） | **`424 passed in 209.98s (0:03:29)`** |
| `pytest tests/test_docs_sync.py -q --reuse-db` | `7 passed` |
| 前端 `vue-tsc`（等价执行） | 退出码 `0`（两个 project 均无输出） |
| 前端 `npm run test`（等价执行） | `Test Files 15 passed (15)` / `Tests 249 passed (249)` |
| 前端 `npm run build`（等价执行） | `✓ built in 12.87s` |
| `python scripts/build_user_guide.py --check` | `使用说明网页版是最新的。` |

> 说明：本轮没有新增模型 / 迁移 / 权限点 / 菜单，因此 `makemigrations --check` 预期仍为
> `No changes detected`；沙箱内该命令因写入 `.tmp` 受限未能执行，已按「未执行」处理（见 `docs/test-report.md` §二十九）。

### 30.7 未完成事项（不要按「能用」去承诺）

1. **协议适配与真实设备联调仍未做**：`mqtt` / `modbus` 依旧是「待协议确认」的选项，
   采集入口对未实现协议返回 `PROTOCOL_NOT_IMPLEMENTED`（409）。
2. **没有汇总表，也没有原始数据归档 / 清理任务**：数据量继续增长后仍需补归档策略；
   本轮只把「按天」区间上限放宽到 1096 天，用来替代「查历史报表」的部分诉求。
3. **投诉 / 评价仍未做外部渠道自动接入与自动分派**；统计只做「按明细现算」，没有定时快照与趋势同环比。
4. **数采统计没有做超大数据量的性能压测**：按明细聚合在测点 × 时间桶量级上成本可控，
   但单公司读数达到千万级时的响应时间**未测量**。
5. **浏览器观感未人工确认**：沙箱内无法启动 `runserver` / `vite dev` / 浏览器，
   本轮前端改动只做了源码级（`vue-tsc`、`views-compile.spec.ts`、`styles.spec.ts`）与构建级验证。
   请登录后核对：①「客户管理 → 客户投诉 / 产品评价」列表顶部的统计卡片与分布；
   ②「设备数采和监控 → 设备监控」的「采集统计」区块（先跑
   `python manage.py iot_simulate --seed-demo --company <ID> --rounds 2 --out-of-range` 造数据）。

### 30.8 与既有文档的关系

| 文档 | 变动 |
| --- | --- |
| `AGENTS.md` | 事实行**数字不变**（本轮无模型 / 迁移 / 权限点 / 菜单变化）；§八 阶段边界补「采集统计与客户服务统计已实现」 |
| `README.md` | 当前状态与模块表补统计能力；测试结果数字 **412 → 424**；下一步清单勾掉已做项 |
| `docs/requirements-matrix.md` | 新增 §一之二十；数采「监控与数据查看」与投诉 / 评价条目补统计能力与用例名 |
| `docs/test-report.md` | 新增 §二十九 本轮复验记录 |
| `docs/data-model.md` | §十 补「统计按明细实时聚合、不新增汇总表」 |
| `docs/api-conventions.md` | §一 补设备 / 能源 / 安全环保 / 物流 / 数采模块前缀，并列出本条新增的三个只读统计接口 |
| `docs/architecture.md` | §三 「未创建模块 → 已创建」清单里 `iot` 的说明补「只读采集统计」 |
| `docs/hardware-integration.md` | §六 未完成清单同步（勾掉「实时聚合查询」，保留归档清理，注明按天已支持 ~3 年） |
| `docs/assumptions.md` | §四之七 追加 19~20 条实现假设 |
| `docs/user-guide.md` + `docs/user-guide.html` + `frontend/public/guide.html` | 能力表、§6.10 / §6.11 统计说明、§8.5 新增错误码，并重新生成网页版 |
| `frontend/src/views/system/ProgressView.vue` | 「已完成 / 未完成」清单同步 |

## 三十一、质量管理（QMS）

> 来源：任务书 §10.9 QMS 质量（阶段 3），以及「已有但功能不足」清单中对制造执行系统（MES）的补充项
> 「质量在线检测与分析、产品质量知识库」。本轮新增应用 `apps/qms`，
> 事实行由 `permissions=333 menus=134 models=134 migrations=27` 变为
> `permissions=350 menus=139 models=139 migrations=28`（`builtin_roles=18` 不变）。

### 31.1 后端

| 文件 | 内容 |
| --- | --- |
| `apps/qms/models.py`（新建） | 5 个模型：`QualityInspectionItem`（检验项目，定量 / 定性、上下限含端点）、`QualityInspectionOrder`（检验单，`source_no` 引用来源单据）、`QualityInspectionResult`（结果明细，**不挂 `company`**，归属由单据确定）、`QualityAlert`（质量报警）、`QualityIssue`（质量问题知识库） |
| `apps/qms/services.py`（新建） | `judge_measured_value` / `_row_judgement`（定量按上下限判定）、`record_results`（`update_or_create` 覆盖，判定后拒改）、`submit_order`（无结果不许提交）、`judge_order`（结论不得与结果矛盾；让步接收必须有说明；不合格自动建报警且**同单只建一条**）、`close_order`（报警未闭环拒绝）、`handle_alert` / `close_alert`（必须写说明）、`publish_issue` / `archive_issue` / `create_issue_from_alert`、`next_*_code` |
| `apps/qms/selectors.py`（新建） | `inspection_statistics`：单据量、**合格率（分母只含已判定单据）**、判定分布、不合格项 TOP10、未关闭报警与级别分布；**按明细实时聚合、不落汇总表** |
| `apps/qms/serializers.py`、`views.py`、`urls.py`（新建） | 4 个 ViewSet + 动作端点 `results/`（GET 查看 / POST 录入）、`submit/`、`judge/`、`close/`、报警 `handle/` / `close/` / `create-issue/`、知识库 `publish/` / `archive/`、只读 `statistics/` |
| `apps/qms/migrations/0001_initial.py`（新建） | 5 张表 + 唯一约束 / 检查约束 / 索引 |
| `config/settings/base.py`、`config/urls.py` | 注册 `apps.qms`，挂载 `/api/v1/qms/` |
| `apps/identity/permissions_registry.py` | 17 个 `qms.*` 权限点；菜单目录「质量管理」+ 4 个页面（`sort_order` 80~89 区间，排在「仓储管理」之后、「设备管理」之前）；`MODULE_LABELS` 登记 `qms` |
| `apps/core/management/commands/bootstrap_system.py` | `CODE_RULES` 新增 `QIT` / `QC` / `QAL` / `KI`；内置角色「质检员」并入 `qms.` 权限 |
| `apps/core/views.py::MetaView` | 下发 9 个质量枚举，前端不硬编码中文标签 |

**一条铁律：检验结论不允许粉饰。** 定量项目（有上下限）的 `is_qualified` **只由服务层按标准区间计算**，
请求里携带的结论被忽略；定性项目必须由检验员给出结论。判定时再校验一次：
存在不合格项不能判「合格」，全部合格不能判「不合格」，判「让步接收」必须写清原因。
判定不合格自动生成一条质量报警，**同一检验单重复判定不会重复报警**；
报警未闭环时检验单**关不掉**，避免「点一下就算处理完」。

### 31.2 本轮发现并修复的两个问题

| 问题 | 现象 | 根因 | 修法 |
| --- | --- | --- | --- |
| 录入结果后接口返回旧数据 | `POST /qms/inspections/{id}/results/` 返回的 `results` 为空，页面看不到刚录入的行 | `get_object()` 的 `prefetch_related("results__item")` 缓存已过期，`record_results` 新建的明细不在缓存里 | 写入后重新取一次对象（`self.get_queryset().get(pk=...)`）再序列化 |
| 一个 action 两种权限，写路径被放行 | 只有查看权限的「只读用户」也能录入检验结果 | 权限按 `self.action` 解析，`results` 一个 action 只能声明一份编码，`required_permissions["record_results"]` 是**死代码** | 写路径在方法内部用 `require_codes(request.user, "qms.inspection.update")` 做二次校验，并加用例锁定 |

> 另外修正了一处**平台约定冲突**：`apps/core/viewsets.py` 把视图允许的方法限定为
> `get / post / patch`，而 `results/` 最初设计为 `GET + PUT`，导致写操作直接 405。
> 已改为 `GET + POST`（动作接口一律 POST），与全平台一致。

### 31.3 前端

| 文件 | 内容 |
| --- | --- |
| `frontend/src/views/qms/InspectionItemList.vue`（新建） | 检验项目台账；列表里直接显示标准区间与判定方式 |
| `frontend/src/views/qms/InspectionOrderList.vue`（新建） | 检验单：结果录入弹窗（选项目、填实测值 / 定性结论，实时显示标准区间与系统判定说明）、提交 / 判定 / 关闭 |
| `frontend/src/views/qms/QualityAlertList.vue`（新建） | 质量报警：开始处理 / 关闭（必须写说明）/ 沉淀知识库 |
| `frontend/src/views/qms/QualityIssueList.vue`（新建） | 质量问题知识库：发布 / 归档 |
| `frontend/src/api/endpoints.ts`、`frontend/src/types/models.ts`、`frontend/src/stores/meta.ts` | 4 个接口封装、5 个类型定义、9 个枚举键 |
| `frontend/tests/fixtures/menu-components.json` | 从注册表按运行顺序**整体重新导出**（139 项），顺带消除此前累积的顺序漂移 |
| `frontend/src/views/system/ProgressView.vue` | 「已完成 / 未完成」清单同步 |

前端未新增 scoped 样式，只使用共享原语（`ys-mono` / `ys-ml-4` / `ys-muted` / `ys-form-error`），
`frontend/tests/styles.spec.ts` 与 `views-compile.spec.ts` 继续通过。

### 31.4 测试（本轮新增）

后端新增 14 个用例（`tests/test_qms_api.py`）：检验项目取号与公司范围（越界写入 403 `OUT_OF_DATA_SCOPE`）；
定量项目必须给出一侧界限；**定量结果由服务层判定（客户端谎报「合格」被忽略）**；
定性项目必须给出结论；无结果不许提交、`status` 不能用 PATCH 推进、跳步 409；
结论不得与结果矛盾；**判定不合格生成唯一报警且报警未闭环时单据关不掉**；
让步接收必须写说明且不生成报警；报警转知识库保留来源链路；知识库发布 / 归档；
**合格率分母只含已判定单据**（草稿不计入，让步接收单列）；
公司范围在报警与知识库上生效；只读角色不能写入；受检物料必须与单据同公司。

### 31.5 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `manage.py migrate` | `Applying qms.0001_initial... OK` |
| `makemigrations --check --dry-run` | `No changes detected` |
| `ruff check --no-cache apps config tests` | `All checks passed!` |
| `pytest tests/test_qms_api.py -q --reuse-db` | `14 passed` |
| `pytest tests -q --reuse-db`（全量） | **`438 passed in 242.34s (0:04:02)`** |
| `pytest tests/test_docs_sync.py -q --reuse-db` | 随全量通过（事实行已同步为 `permissions=350 menus=139 models=139 migrations=28 builtin_roles=18`） |
| 前端 `npm run typecheck` | 通过（退出码 `0`） |
| 前端 `npm run test` | `Test Files 15 passed (15)` / `Tests 253 passed (253)` |
| 前端 `npm run build` | `✓ built in 15.70s` |
| `python scripts/build_user_guide.py --check` | `使用说明网页版是最新的。` |

> 顺带修掉一个**与时钟相关的用例缺陷**：`test_iot_api.py::test_device_monitor_picks_latest_reading_per_point`
> 用「本地日期字符串前缀」比对接口返回的 **UTC** 时间戳，在北京时间 00:00~09:00 之间跑必然失败。
> 已改为比对**时刻**（`datetime.fromisoformat(...) == 期望时刻.astimezone(UTC)`），与运行时间无关。

### 31.6 未完成事项（不要按「能用」去承诺）

1. **检验标准的版本快照未做**：检验单保存受检对象与来源单据，但标准改动不会回写历史单据；
   面向物料的「检验标准集 / 版本」还没有建模。
2. **返工 / 退货 / 报废的处置工单未做**：本轮落地的是「合格 / 不合格 / 让步接收 + 报警闭环」。
3. **检测仪器直连未做**：结果全部人工录入，没有在线检测分析设备的采集接口。
4. **与既有流程尚未接线**：`procurement.receipt.inspect`（收货单人工判定）与 `wms` 的质量放行仍是独立路径，
   QMS 检验单没有取代它们；按工艺路线 `is_quality_gate` 决定质检点需要 MES 落地后一并做。
5. **MES 仍未开始**：生产工单与报工是本轮清单里最大的一块，尚未实现。
6. **浏览器观感未人工确认**：沙箱内无法启动 `runserver` / `vite dev` / 浏览器，
   本轮前端改动只做了源码级（`vue-tsc`、`views-compile.spec.ts`、`styles.spec.ts`）与构建级验证。
   请登录后核对：「质量管理 → 检验项目 / 检验单 / 质量报警 / 质量问题知识库」四个页面，
   以及检验单的「录入结果」弹窗（定量项应显示「系统判定」，定性项才出现结论下拉）。

### 31.7 与既有文档的关系

| 文档 | 变动 |
| --- | --- |
| `AGENTS.md` | 事实行改为 `permissions=350 menus=139 models=139 migrations=28 builtin_roles=18`；§八 阶段边界补 QMS，并明确 MES、销售计划 / 分销商 / 市场预测、供应商寻源与量化评价、跨系统数据交换、工业终端安全、OEE、职业健康、能源调度仍未实现 |
| `README.md` | 权限 / 菜单数字、当前状态、模块表新增「质量管理（阶段 7 首块）」、下一步清单勾掉 QMS 并列出未做项 |
| `docs/requirements-matrix.md` | 新增 §一之二十一（质量逐条追踪）；§10.9 QMS 逐条状态由「未开始」改为实际状态；§十六 阶段计划表按实际进度重写 |
| `docs/architecture.md` | §三 App 清单加 `qms`，「已创建」改为 19 个，「未创建」只剩 `mes / endpoint_security` |
| `docs/data-model.md` | 新增 §十一 质量管理表清单（5 张表 + 跨模块引用边界 + 统计口径） |
| `docs/api-conventions.md` | §一 模块前缀补 `qms`，并说明检验单动作端点、`results/` 的 GET/POST 与二次权限校验 |
| `docs/permission-matrix.md` | §三 / §四 按注册表整体重新生成（350 条权限 / 139 项菜单） |
| `docs/test-report.md` | 新增 §三十 本轮复验记录 |
| `docs/assumptions.md` | 新增 §四之八（检验结论不接受客户端指定、结果覆盖口径、不合格唯一报警、报警未闭环不可关单、标准快照缺口、与既有质量路径并行、结果人工录入、统计口径） |
| `docs/acceptance.md` | §七 未通过 / 未执行项补质量条目；§八 验收结论补「阶段 3 第四步首块：通过（含未实现项声明）」并更新「不声称已完成」；新增 §五之五 验收明细 |
| `docs/user-guide.md` + `docs/user-guide.html` + `frontend/public/guide.html` | 能力表新增质量管理、§2.2 未实现项收窄、菜单清单更新为 139 项、新增 §6.12 质量管理与 §8.6 错误码，并重新生成网页版 |
| `frontend/src/views/system/ProgressView.vue` | 阶段 3 说明与「已完成 / 未完成」清单同步 |


## 三十二、生产执行（MES）

> 用户要求「继续帮我做」。本轮交付「订单到交付」闭环的最后一块：**生产执行（MES）**，
> 并把 MRP 的**在制供给**与**生产建议转单**真正接入。
> 新增 `apps/mes`（**4 个模型 / 1 个迁移 / 10 个权限点 / 3 项菜单**），
> 事实行由 `permissions=350 menus=139 models=139 migrations=28 builtin_roles=18` 变为
> `permissions=360 menus=142 models=143 migrations=29 builtin_roles=19`。

### 32.1 交付内容

| 能力 | 实现位置 | 页面 / API |
| --- | --- | --- |
| 生产工单（草稿 / 下达 / 生产中 / 已完工 / 已关闭 / 已取消） | `apps/mes/models.py::ProductionOrder` | 「生产执行 → 生产工单」；`/api/v1/mes/orders/` |
| 工单下达（冻结 BOM / 工艺快照、展开用料与工序） | `apps/mes/services.py::release_order` | `POST /api/v1/mes/orders/{id}/release/` |
| 生产领料（经统一库存服务过账） | `apps/mes/services.py::issue_materials` → `apps/wms/services/stock.py` | `POST /api/v1/mes/orders/{id}/issue-materials/` |
| 报工（数量 / 工时 / 不良，守恒校验） | `apps/mes/services.py::report_production` | `POST /api/v1/mes/orders/{id}/report/`；`/api/v1/mes/reports/`（只读台账） |
| 完工（工序完成 + 质检点判定）与完工入库 | `apps/mes/services.py::complete_order` / `receipt_finished_goods` | `POST …/complete/`、`…/receipt/` |
| 关闭 / 取消（必填原因） | `apps/mes/services.py::close_order` / `cancel_order` | `POST …/close/`、`…/cancel/` |
| 质检点自动开 QMS 检验单 | `apps/mes/services.py::_ensure_gate_inspection` → `apps/qms/services.py` | 报工时内部触发（校验 `qms.inspection.create`） |
| 生产统计 | `apps/mes/selectors.py::production_statistics` | `GET /api/v1/mes/orders/statistics/` |

关键设计：

- **工单下达即冻结快照**：`bom_snapshot` / `routing_snapshot`（JSON）随工单落库，
  不单独建快照表（ADR-08）；之后工程数据出新版本**不影响已下达工单**。
- **完工数量取末道工序合格数**（按工单汇总所有工序会重复计数），
  `scrap_quantity` 取全工序报废之和。
- **报工只追加、不可回改**：报工台账无修改接口，填错补一条返工报工。
- **质检点是完工硬门**：工序报满自动开检验单，未判定 / 不合格均不放行。

### 32.2 两处跨模块接线（本轮关键）

1. **MRP 在制供给**（`apps/planning/mrp.py`）：新增 `_in_progress_supplies()`，
   取**已下达 / 生产中**工单的未完工数量。**这里修了一个真实缺陷**：
   原实现把在制写进 `supplies`，但净算只认 `ON_ORDER`，导致**在制供给从未参与净算**。
   现已把 `_net_item` 的 `on_order_by_bucket` 改为 `inbound_by_bucket`，同时纳入两者。
2. **MRP 生产建议转单**：`convert_suggestion()` 的生产分支改为
   `_convert_production_suggestion()`，生成**草稿 MES 工单**（`source_type=mrp_suggestion` + `source_no` + `DocumentLink`）。
   **不自动下达**：下达会冻结快照并生成工序与用料，是独立动作，
   由计划员确认后触发——转单不等于承诺产能。旧错码 `PRODUCTION_ORDER_NOT_IMPLEMENTED` 随之废弃。

### 32.3 本轮修复的四个缺陷（均已复验）

| 缺陷 | 现象 | 修正 |
| --- | --- | --- |
| `progress_rate` 输出 `0E+6` | Serializer 直接输出 `Decimal`，零值被序列化为科学计数法 | 改为 `_percent()`：Decimal×100 后保留 2 位，输出 `"0.00"` |
| 非草稿工单表头未冻结 | PATCH 能改已下达工单的数量 / 排期 | `perform_update()` 新增状态校验，报 **409 `STATE_CONFLICT`** |
| MRP 在制供给不参与净算 | 供给行写入了，但净算只认采购在途 | `_net_item` 改用 `inbound_by_bucket`（同纳 `ON_ORDER` 与 `IN_PROGRESS`） |
| `mrp.convert_suggestion` docstring 过期 | 仍写着「生产建议不在此转单」 | 同步为「按类型分流」，与代码一致 |

### 32.4 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `makemigrations --check --dry-run` | `No changes detected` |
| `ruff check --no-cache apps config tests` | `All checks passed!` |
| `pytest tests/test_mes_api.py -q --reuse-db` | `32 passed` |
| `pytest tests/test_mrp.py -q --reuse-db` | `34 passed` |
| `pytest tests -q --reuse-db`（全量） | **`472 passed in 354.92s (0:05:54)`** |
| 前端 `npm run typecheck` | 通过（退出码 `0`） |
| 前端 `npm run test` | `Test Files 15 passed (15)` / `Tests 255 passed (255)` |
| 前端 `npm run build` | `✓ built in 16.95s` |

### 32.5 未完成事项（不要按「能用」去承诺）

1. **线体排产**：工单可指定厂区 / 车间 / 线体，但没有排产优化与产能冲突检查。
2. **裁剪任务 / 裁片批次**、**工位派工与接单**未建模。
3. **在制品转移与独立返工工单**：返工只以报工类型与数量留痕，
   也没有「返工报工必须引用原不良行」的强约束。
4. **扫码 / RFID 与硬件控制**：无协议不伪造，报工全部人工。
5. **工序级良率与 OEE**：需设备运行时长，本轮未算；工单成本也未算。
6. **并发报工 / 并发领料的多连接压测未执行**（幂等与锁已用例覆盖）。
7. **浏览器截图级观感未人工确认**：沙箱内无法启动 `runserver` / `vite dev` / 浏览器，
   本轮前端只做了源码级（`vue-tsc`、`views-compile.spec.ts`、`styles.spec.ts`）与构建级验证。
   请登录后核对「生产执行 → 生产工单 / 生产报工」两个页面与工单详情抽屉、「报工」弹窗。

### 32.6 与既有文档的关系

| 文档 | 变动 |
| --- | --- |
| `AGENTS.md` | 事实行改为 `permissions=360 menus=142 models=143 migrations=29 builtin_roles=19` |
| `README.md` | 权限 / 菜单 / 模型数字、当前状态、模块表新增「生产执行（MES）」、下一步清单 |
| `docs/requirements-matrix.md` | 新增 §一之二十二（MES 逐条追踪）；§10.7 MES 逐条状态由「未开始」改为实际状态；§12.1 / 案例 21 / §十六阶段表同步 |
| `docs/data-model.md` | 新增 §十二 生产执行表清单（4 张表 + 快照不单独建表） |
| `docs/architecture.md` | §三 App 清单加 `mes`（已创建 20 个，未创建只剩 `endpoint_security`）；ADR-08 / ADR-11 改为已落地 |
| `docs/api-conventions.md` | §一 模块前缀补 `mes`，并新增「生产执行（mes）约定」（动作端点、幂等、表头冻结） |
| `docs/permission-matrix.md` | §三 / §四 按注册表重新生成（360 权限 / 142 菜单） |
| `docs/business-flows.md` | §12.1 改为已打通；新增 §十六 生产执行闭环 |
| `docs/assumptions.md` | A-33 / A-37 过期条目改正；新增 §四之九 生产执行实现假设 |
| `docs/acceptance.md` | 新增 §五之六 MES 验收；§七 / §八 / §九 同步 |
| `docs/test-report.md` | 新增 §三十一 本轮复验记录 |
| `docs/user-guide.md` + 网页版 | 能力表、未实现清单、菜单清单（142）与新增 §6.13 生产执行 |
| `frontend/src/views/system/ProgressView.vue` | 已完成 / 未完成清单补 MES |

## 三十三、供应商五维量化评价（SRM）

> 用户要求「仍未实现 帮我完成」。本轮把上一轮总结里遗留清单中的
> **「供应商寻源与五维量化评价（质量 / 技术 / 响应 / 交付 / 成本）」** 做出可用闭环：
> 该口径在 `docs/assumptions.md` A-10~A-12 中**事先约定**，此前「只有文档约定、
> 不落任何评分数据、界面也不展示评分」，本轮按约定真正落地。
> 事实行由 `permissions=360 menus=142 models=143 migrations=29 builtin_roles=19` 变为
> `permissions=368 menus=144 models=146 migrations=30 builtin_roles=19`。

### 33.1 交付内容

| 能力 | 实现位置 | 页面 / API |
| --- | --- | --- |
| 五维权重配置（合计必须 100%） | `apps/srm/models.py::SupplierEvaluationWeight`、`services.create_weight_config` | 「供应商管理 → 评价权重配置」；`/api/v1/srm/supplier-evaluation-weights/` |
| 权重版本留痕（改权重 = 派生新版本） | `apps/srm/services.py::derive_weight_config` | `PATCH /api/v1/srm/supplier-evaluation-weights/{id}/` |
| 评价单（建单即冻结权重快照） | `apps/srm/models.py::SupplierEvaluation`、`services.create_evaluation` | 「供应商管理 → 供应商评价」；`/api/v1/srm/supplier-evaluations/` |
| 五维明细录入与重算（缺数据两种口径） | `apps/srm/services.py::set_evaluation_lines` / `recalculate` / `_redistributed_weights` | `GET|POST /api/v1/srm/supplier-evaluations/{id}/lines/` |
| 生效 / 归档状态机 | `apps/srm/services.py::publish_evaluation` / `archive_evaluation` | `POST …/publish/`、`…/archive/` |
| 评价统计 | `apps/srm/selectors.py::evaluation_statistics` | `GET /api/v1/srm/supplier-evaluations/statistics/` |

关键设计：

- **总分只能由服务层算**：请求里带 `total_score` 会被忽略；界面也填不了总分。
- **权重只增不改**：`PATCH` 派生新版本（响应体是新那条），旧版本原样保留；
  评价单保存 `weight_snapshot`，**改权重不回头改历史分**。
- **「没有数据」≠「0 分」**：五个维度各一行，缺数据维度 `is_missing=True`、
  有效权重 0、加权得分 `NULL`；「标注缺失」不给等级，「重新分配有效权重」合计仍精确 100% 并给等级。
- **生效后不可改**：只能归档后重新发起，历史始终可核对。

### 33.2 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `makemigrations --check --dry-run` | `No changes detected` |
| `ruff check --no-cache apps config tests` | `All checks passed!` |
| `pytest tests/test_srm_api.py -q --reuse-db` | **`29 passed`**（本轮新增 18 例） |
| 前端 `npm run typecheck` | 通过（退出码 `0`） |
| 前端 `npm run test` | `Test Files 15 passed (15)` / `Tests 257 passed (257)` |

全量复验结果见 `docs/test-report.md` §三十二。

### 33.3 未完成事项（不要按「能用」去承诺）

1. **供应商寻源与候选供应商**（REQ-10.4-01 的寻源部分）未开始。
2. **准入审批接入 `workflow`**（REQ-10.4-02）未做，`admission_status` 仍只是档案字段。
3. **可供物料、报价及有效期**（REQ-10.4-03）未开始，与采购价的联动因此也没有。
4. **评分数据仍需人工录入**：评价明细由界面手填，**没有**检测仪器 / ERP 直连数据源。
5. **评价不会自动改写供应商等级**：`Supplier.grade` 仍是人工维护字段，
   本轮刻意不做「评价生效就覆盖主数据等级」的隐式副作用（见 §33.4）。
6. **浏览器截图级观感未人工确认**：沙箱内无法启动 `runserver` / `vite dev` / 浏览器，
   新增两个页面只做了源码级与构建级验证。请登录后核对
   「供应商管理 → 评价权重配置 / 供应商评价」两个页面与「录入评分」弹窗。

### 33.4 一处刻意的设计取舍

**评价生效时不回写 `Supplier.grade`。** 一次评价直接改写供应商主数据等级是隐式的跨实体副作用，
且等级还被其他流程（采购例外授权等）当作判断依据；本轮只把等级留在评价单上，
由人工决定是否更新档案等级。若项目方要求自动评级，需要先确认「用哪一次评价、多久一次」的口径。

### 33.5 与既有文档的关系

| 文档 | 变动 |
| --- | --- |
| `AGENTS.md` | 事实行改为 `permissions=368 menus=144 models=146 migrations=30 builtin_roles=19`；§八 阶段边界补五维评价 |
| `README.md` | 权限 / 菜单 / 模型数字与当前状态、下一步清单 |
| `docs/requirements-matrix.md` | 新增 §一之二十三（逐条追踪）；§10.4 的 REQ-10.4-05~08 由「未开始 / 仅文档约定」改为实际状态 |
| `docs/data-model.md` | 新增 §十三 供应商五维评价表清单（3 张表） |
| `docs/permission-matrix.md` | §三 / §四 按注册表重新生成（368 权限 / 144 菜单） |
| `docs/assumptions.md` | 第 9 / 13 条过期表述改正；新增 §四之十 评价实现假设（36~42） |
| `docs/test-report.md` | 新增 §三十二 本轮复验记录 |
| `docs/user-guide.md` + 网页版 | 能力表、未实现清单、菜单清单（144）与新增 §6.14 供应商评价 |
| `frontend/src/views/system/ProgressView.vue` | 已完成 / 未完成清单补五维评价 |


## 三十四、新疆意尚智造（XJYS）专项演示数据

> 用户反馈「很多页面都是空的数据」，要求：为**新疆意尚智造科技有限公司**造一套演示数据，
> 记录起始时间自 **2026 年 1 月** 起，并结合该公司自身情况（新疆作息、棉纺/成衣产线、两个生产基地）。
> 本轮**不新增页面、接口与权限点**，只增加一条管理命令与数据。

### 34.1 交付内容

| 项目 | 内容 |
| --- | --- |
| 命令 | `python manage.py seed_demo_xjys`（`--yes` 非开发环境确认、`--skip-heavy` 跳过读数类大表） |
| 实现位置 | `backend/apps/core/management/commands/seed_demo_xjys.py` |
| 作用公司 | 新建 `XJYS`「新疆意尚智造科技有限公司」；**不触碰**既有 `YS` 公司数据 |
| 时间口径 | 所有业务日期落在 `2026-01-01` ~ 执行当天（业务时区 UTC+8，落库 UTC） |
| 幂等 | 重复执行「新建 0 条」；已存在的记录只回读不重建 |
| 安全 | `DJANGO_ENV=production` 直接拒绝；非 development/test 需 `--yes`；不写真实个人信息 |

命令自身口径：

- **业务状态只由 Service 层推进**：保养/维修/点巡检/异常、能源报警、库存过账、采购审批、
  销售发货、MES 下达与报工、QMS 判定、SRM 评价生效、EHS 整改与作业许可，全部调用
  `apps.*/services.py`，没有直接改状态字段。`_stamp()` 只用于把时间字段对齐到 2026 区间。
- **库存只能经统一库存服务**：期初、待检放行、移库、盘点、采购收货、销售发货、生产领料与完工入库
  一律走 `apps.wms.services.stock.create_document → post_document → release_quality`。
- **金额数量使用 Decimal**，不经 float。
- 所有对象 `remark` 带 `演示数据（新疆意尚智造）` 前缀，便于与真实数据区分、便于整体清理。

### 34.2 覆盖范围（实测行数，按公司 `XJYS` 统计）

| 模块 | 主要数据 |
| --- | --- |
| 组织与主数据 | 公司 1、部门 14、工厂 2、车间 13、线体 13、工位 104、班次 3、班组 12、员工 20、物料 63、SKU 46、款式 4、颜色/尺码各 8、计量单位 15 |
| 设备管理 | 设备类型 10、设备 22、备件 8、零部件 18、保养项目 10、点巡检项目 10、异常类型 6；保养计划 8 / 任务 59 / 记录 46、报修 11 / 维修任务 6 / 维修记录 4、点巡检任务 18 / 记录 70、异常任务 8 / 记录 5 |
| 能源管理 | 区域 11、表计 14、价格 7、阈值 5、抄表 742、运行记录 23、报警 31 |
| 设备数采 | 连接 3、网关 8、测点 16、报文 69、读数 158 |
| 仓储（WMS） | 仓库 5、库存单据 23、库存流水 62、库存余额 36、占用 2 |
| 采购 | 采购申请 3（含紧急采购）、采购订单 2、收货 2 |
| 销售 | 订单 4、发货 2、退货 1 |
| 计划与 MRP | BOM 4、工艺路线 4、MRP 运算 1（含建议转单） |
| MES | 生产工单 6（草稿/已下达/生产中/完工/关闭/取消）、报工 11、领料与完工入库 |
| 质量（QMS） | 检验项目 10、检验单 10、质量报警 2、质量问题知识库 1 |
| 供应商（SRM） | 供应商 5、五维评价权重 1、评价单 5 |
| 客户（CRM） | 客户 5、客户投诉 5、产品评价 6 |
| 安全环保（EHS） | 制度 5、培训 6、隐患 6、应急预案 2、演练 3、事故 3、排污监测 6、固废/危废 5、合规检查 4、消防设施 9、作业许可 5、安全检查 4、特种设备检验 3、操作日志 33 |
| 厂内物流 | 自动化设备 5（AGV / 穿梭车 / 堆垛机 / 码垛机器人）、任务 7、操作日志 32 |
| 审批与审计 | 审批模板 6、审批实例 15、审计日志 223 |
| 合计 | **2108 行**（该公司的全部业务表均非空） |

### 34.3 本轮修复的三个真实缺陷

1. **演示账号权限缓存陈旧**：命令在同一事务里反复 `bump_permission_version()`，
   事务回滚时版本号不前进，`identity:user_perms:<pk>:<version>` 会一直命中旧值，
   服务层 `require_codes` 误判「没有权限」。现在写入演示账号后主动清除该用户的权限缓存
   （`_forget_permission_cache`）。
2. **质检点检验单必须回读工序**：`mes.services.report_production` 内部重新取工序行，
   质检单挂在那一份对象上；调用方持有的旧对象 `inspection_order_id` 为空，
   导致完工时校验「质检点尚未判定合格」。现在报工后 `refresh_from_db` 再判定。
3. **环保合规检查关闭前不能已是「已关闭」**：原先把演示数据直接建成「已关闭」再调
   `close_compliance_check`，被状态机拒绝。现在先落「已整改」再由服务层关闭，状态推进与操作日志走同一路径。

另外，`_demo_roles()` 只在缺失时补建 `demo_dept_manager` / `demo_gm` / `demo_finance`，
避免把 `seed_demo` 建好的（属于另一家公司的）同名角色改到本公司。

### 34.4 本轮执行的检查（真实输出）

| 检查 | 结果 |
| --- | --- |
| `manage.py seed_demo_xjys` | 首次：各模块新建并打印清单；二次：**「新建 0 条」** |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `makemigrations --check --dry-run` | `No changes detected` |
| `ruff check --no-cache apps config tests` | `All checks passed!` |
| `pytest tests -q --reuse-db` | **`493 passed`**（含新增 3 例：拒绝生产环境 / 非开发环境需 `--yes` / 各模块都有数据且幂等） |

### 34.5 未完成事项（不要按「已实现」去承诺）

1. **不新增任何页面与接口**：本轮只造数据；`docs/requirements-matrix.md` 中标注「未开始」的能力
   （销售计划、分销商、市场预测、供应商寻源、跨系统数据交换中间件、工业终端安全、OEE、
   职业健康、能源调度等）**不因本轮而有任何变化**。
2. **设备数采仍是 HTTP 上报 + 内置模拟器**，没有真实设备 / MQTT / Modbus 联调，
   演示读数与报文全部是构造数据。
3. **演示账号口令**：优先取 `YISHANG_DEMO_PASSWORD`，未设置时随机生成并**只打印一次**；
   重复执行不会重置已存在账号的口令。
4. **浏览器观感未人工核对**：沙箱内不能启动 `runserver` / `vite dev` 与浏览器自动化，
   数据只做了数据库层与自动化测试层验证。

## 三十五、界面数值显示口径修复（最多 2 位小数）

> 用户反馈：部分页面的数字小数点后超过 2 位，举例是**能源首页 → 本月各介质用量与费用**表的
> 「用量」列显示成 `35497.730000`。本轮**只改显示口径**：接口精度、数据库精度、
> 导出单元格里保存的数值一律不变。

### 35.1 根因

1. **渲染绕过统一格式化工具。** 统一口径在 `frontend/src/utils/decimal.ts`
   （`formatNumber` / `formatDecimal` / `formatAmount` / `numberFormatter`，四舍五入到 2 位 + 千分位），
   但若干页面把接口返回的字符串**直接插值**或直接放进 `el-table-column`，没走这些函数，
   于是 `MeterReading.consumption`（`DecimalField(max_digits=20, decimal_places=6)`）
   的原值 `35497.730000` 被原样打印。`ProTable` 默认列会自动格式化，
   但**自定义 `#column-*` 插槽会绕过它**，这类列是排查重点。
2. **数据本身没问题。** `ems.MeterReading.consumption` 写入时已 `quantize(Decimal("0.01"))`，
   实测 742 条读数**全部 ≤ 2 位小数**；用户看到的多位小数是显示问题，不是数据问题。
3. **Excel 导出单元格没有显示格式。** `apps/ems/views.py::_xlsx_response` 用 `float()` 写入
   且未设 `number_format`，费用这类 4 位小数的值在 Excel 里会显示成 `356574.3758`。

### 35.2 改动清单

| 文件 | 改动 |
| --- | --- |
| `frontend/src/views/ems/EnergyHome.vue` | 介质表「用量 / 费用」走 `formatDecimal` / `formatAmount`；计量点「用量 / 费用」列补格式化；趋势图 tooltip 加 `valueFormatter` |
| `frontend/src/views/ems/EnergyKanban.vue` | 饼图 / 柱状图 / 趋势图 tooltip 加 `valueFormatter` |
| `frontend/src/views/ems/EnergyReport.vue` | 尖峰平谷图 tooltip 加 `valueFormatter` |
| `frontend/src/components/EnergyStatisticsPanel.vue` | 同上（占比饼图 / 对比柱状图 / 趋势图） |
| `frontend/src/views/iot/DeviceMonitor.vue` | 「报警下限 / 报警上限」列补 `numberFormatter` |
| `frontend/src/views/procurement/PurchaseOrderList.vue` | 「已收」列补 `numberFormatter` |
| `frontend/src/views/procurement/RequisitionList.vue` | 「已转数量」列补 `numberFormatter` |
| `frontend/src/views/sales/SalesOrderList.vue` | 「已发货 / 已退货」列补 `numberFormatter` |
| `frontend/src/views/sales/SalesReturnList.vue` | 「可退货」列补 `numberFormatter` |
| `frontend/src/views/planning/MrpSuggestionList.vue` | MRP 分段净算「期初 / 供给 / 需求 / 净需求 / 期末」5 列补 `numberFormatter` |
| `frontend/src/views/mes/ProductionOrderList.vue` | 数量、报工 / 合格、应领 / 已领改走 `formatDecimal` |
| `frontend/src/views/equipment/InspectionItemList.vue` | 合格范围上下限走 `formatDecimal`（原来直接 `String(...)`） |
| `frontend/src/views/qms/InspectionItemList.vue` | 标准上下限走 `formatDecimal` |
| `frontend/src/views/qms/InspectionOrderList.vue` | 检验单明细「标准范围」走 `formatDecimal` |
| `backend/apps/ems/views.py` | 能耗报表 Excel 导出：「用量 / 费用」两列设 `number_format = "0.00"` |
| `frontend/tests/decimal.spec.ts` | 新增用例，把用户反馈的两个原值（`35497.730000` / `21724.6108`）锁进回归 |

### 35.3 刻意不改的位置（避免过度格式化）

- `srm/SupplierEvaluationList.vue` 的各分值列：模型是 `max_digits=5, decimal_places=2`，
  接口实测返回 `"84.10"`、`"10.80"` 这类 2 位值，本身合规。
- `factory/ShiftList.vue` 的 `duration_hours`：`ShiftSerializer.get_duration_hours`
  已 `f"{worked / 60:.2f}"`。
- `iot/PointList.vue` 的 `quantity`：是物理量枚举（`CharField`），不是数值。
- `integration/OutboxList.vue`、`system/ProgressView.vue` 的计数：都是整数。
- 统计类接口的 `avg_satisfaction` / `avg_score` / `good_rate` / `avg_total_score` / `missing_rate`：
  接口实测已经是 `4.67` / `3.83` / `66.67` / `84.10` / `8.00`。
- `formatNumber` 的**刻意例外**：非零值四舍五入后为 0 时保留真实精度（如 BOM 用量 `0.004`），
  避免把「有」显示成「没有」。这不是缺陷。

### 35.4 验证（实测结果）

| 项目 | 结果 |
| --- | --- |
| `npm run typecheck`（vue-tsc） | 通过（无输出） |
| `npm run test`（vitest） | **`258 passed`**（较上一轮 +1，新增显示口径回归用例） |
| `npm run build`（vue-tsc + vite） | 通过（`built in 18.28s`） |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `makemigrations --check --dry-run` | `No changes detected` |
| `ruff check --no-cache apps config tests` | `All checks passed!` |
| `pytest tests -q --reuse-db` | **`493 passed in 305.75s`** |

### 35.5 未执行 / 未验证

1. **浏览器内人工核对显示效果未执行**：本轮只跑了 `typecheck` / `vitest` / `build`，
   并用 `django.test.Client` 实测了接口返回值与导出 xlsx 的单元格格式，没有在真实浏览器里逐页看图。
2. **Playwright 端到端、性能压测、备份恢复、Docker Compose 验证**仍与 §三十四 一致，未执行。
3. `docs/progress.md` §一 的「当前规模」数字（310 权限点 / 125 菜单 / 127 模型 / 24 迁移 / 17 角色）
   与当前实际值（368 / 144 / 146 / 30 / 19，见 `AGENTS.md` 事实行）不一致，
   属于**历史遗留的文档过期**，本轮未改，待后续统一以事实行为准刷新。

## 三十六、能耗报表 / 能耗统计：时间维度按介质分行

> 用户确认要修的问题：能耗报表在「全部介质」（默认）状态下数字会误导 ——
> 同一段时间里水 / 电 / 气 / 液被合并成一行，「介质」列只标其中一种、单位列空着，
> 用量却是各介质之和。**数字算对了，口径是错的。**

### 36.1 根因

`apps/ems/selectors.py::_period_rows` 的合并键只有时间桶（`merged.setdefault(row["bucket"], …)`）。
`values(...)` 里虽然取了 `meter__medium` / `meter__unit`，但只用来当**首行**标签，
同桶里其它介质的行全被加进同一个 bucket。于是：

- 「介质」列显示的是该桶第一行的介质（取决于数据库返回顺序，看起来像随机的）；
- 「单位」列是写死的空串；
- 「用量」是该桶全部介质之和（kWh + m³ + t 相加）。

实测（XJYS 演示数据，`period=month`）：2026-04 只有 1 行、标成「电」、单位空、用量 `149236.20`；
而该月实际有电 / 气 / 液 / 水四种介质。

### 36.2 改动

| 文件 | 改动 |
| --- | --- |
| `backend/apps/ems/selectors.py` | `_period_rows` 合并键改为 `(时间桶, 介质, 单位)`；`unit` 取 `meter__unit`；补 docstring 说明为什么不能只按时间合并 |
| `frontend/src/components/EnergyStatisticsPanel.vue` | 时间维度趋势图改为**每个介质一条线**（带单位后缀与图例），不再把多介质行铺在同一个 x 轴上 |
| `backend/tests/test_ems_api.py` | 新增 `test_period_rows_split_by_medium` 回归用例 |

每种介质一行之后，「单位」列不再为空，导出 Excel 的「介质 / 单位」两列也随之正确。
「按介质过滤」的结果与改动前完全一致（不变）。

### 36.3 验证（实测结果）

| 项目 | 结果 |
| --- | --- |
| 回归用例反向验证 | 把合并键临时改回「仅时间桶」后 `test_period_rows_split_by_medium` **失败**（断言只剩 `('electricity', '')` 一行），改回后通过 —— 证明用例确实锁住了这个缺陷 |
| 接口实测 `period=month`（XJYS） | 9 个月 × 4 介质 = **36 行**，单位分别为 kWh / m³ / t / t；2026-01 电 `182351.77` 与「按介质过滤」的结果一致（四介质相加 `201210.31` = 旧的合并值） |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `makemigrations --check --dry-run` | `No changes detected` |
| `ruff check --no-cache apps config tests` | `All checks passed!` |
| `pytest tests -q --reuse-db` | **`494 passed in 324.79s`** |
| `npm run typecheck` / `npm run test` / `npm run build` | 通过 / **`258 passed`** / 通过 |

### 36.4 未执行 / 未验证

1. **浏览器内人工核对未执行**：趋势图改成多介质多条线后，只过了 `vue-tsc` / `vitest` / `vite build`
   三关以及接口实测，没有在浏览器里逐页看图。
2. 多介质共用一条 y 轴（kWh 与 t 量级相差很大）时曲线可读性一般，属于可视化折中，
   不是数据口径问题；需要分开看时把「介质」筛成一种即可。
3. **「合计用量」卡片仍是跨介质相加**：`totals.consumption` 把 kWh / m³ / t 加在一起，
   物理含义不成立（改动前也一样）。要做成按介质分别合计需要产品决策，本轮未动，已在客户说明中提示。

## 三十七、单公司合并：下线旧演示公司，全平台只保留「新疆意尚智造科技有限公司」

**背景。** 平台早期由 `seed_demo` 建了第二家演示公司（`YS`），
与 `seed_demo_xjys` 建的「新疆意尚智造科技有限公司（`XJYS`）」并存；两套组织架构
（部门 / 工厂 / 车间 / 工位 / 班次 / 员工）同名不同值，谁后执行谁覆盖谁。
本平台只服务新疆意尚智造一家公司，因此旧公司及其演示数据整体下线。

**数据清理（开发库实做，2026-09-22）。**

- 先改挂权限与账号：16 个角色的 `company_id`、11 个账号的 `company_id` 由 `YS` 改为 `XJYS`；
  10 个账号的 `department_id` 按部门编码改挂到 `XJYS` 同名部门，避免随旧部门一起被删。
- 旧公司数据按依赖逆序清理，共删除 **808 行、覆盖 54 张表**：工厂 / 部门 / 员工 / 班组 /
  物料 / 款式 / SKU / 条码 / 仓库 / 库位 / 库存单据与余额 / 客户 / 供应商 / 采购 /
  销售 / BOM / 工艺路线 / MRP / 审批模板与实例 / 审计日志。
- 清理后 `factory.Company` 只剩 1 行（`XJYS`）；`XJYS` 名下数据行数与清理前一致
  （2137 → 2137），跨公司引用为 0；5 处非法枚举值（`SalesOrder.priority` 的 `low`/`high`、
  `Equipment.status` 的 `fault`、`Warehouse.warehouse_type` 的 `accessory`/`spare_part`）
  在**数据与种子代码**里一并改写为合法值（否则界面显示英文）。
- 清理前用 `mysqldump` 备份开发库到 `.tmp/backup/`（本地临时文件，不提交）。

**命令合并。** `seed_demo` 不再有独立实现：保留命令名作为**兼容入口**，实际调用
`seed_demo_xjys`（生产环境仍被拒绝，非开发环境仍需 `--yes`）。演示角色定义 `DEMO_ROLES`
与口令生成 `_generate_password` 随实现迁入 `seed_demo_xjys.py`。
实测 `manage.py seed_demo` 重跑输出 `新疆意尚智造演示数据：新建 0 条。` 与
`公司：新疆意尚智造科技有限公司（XJYS）`——幂等且只写一家公司。

**回归。** `tests/test_management_commands.py` 的 `seed_demo` 用例收紧为
「公司数 == 1 且 `code == "XJYS"`」；`tests/test_enum_labels.py`
（执行 `seed_demo` 后全库扫非法枚举值）现在跑的是 XJYS 全套演示数据，
上面 5 处非法枚举值正是它发现的。

文档侧同步：`README.md`、`backend/README.md`、`docs/deployment.md`、
`docs/user-guide.md`（客户手册）与 `docs/assumptions.md`。
## 三十八、数据库版本基线调整：MySQL 8.4 LTS → MySQL 8.0 系列

**背景。** 任务书要求 MySQL 8.4 LTS，而开发机实际是 MySQL 8.0.17，库里长期挂着这条版本偏差。
项目方 2026-09-23 确认：把**部署版本与开发库统一到 MySQL 8.0 系列**，
避免「开发能跑、上线报版本错」的差异。

**改动。**

- `compose.yaml` 的 mysql 服务镜像由 `mysql:8.4` 改为 `mysql:8.0`
  （8.0 系列最新补丁，**不钉死小版本**）。`deploy/mysql/my.cnf` 与 compose 的 `command`
  参数未改：`utf8mb4` / `utf8mb4_0900_ai_ci` / 严格 `sql_mode` / UTC 在 8.0 与 8.4 上写法一致。
- **代码与迁移未改动**：检索确认没有使用 8.0.17 之后才具备的特性
  （`JSON_VALUE` / `JSON_TABLE` / `INTERSECT` / `EXCEPT` / `LATERAL` / `NOWAIT` / `SKIP LOCKED`
  均无使用），实际能力下限是 `utf8mb4_0900_ai_ci`（8.0.0+）与 CHECK 约束（8.0.16+）。
- 版本口径同步更新：`PROJECT_SPEC.md`、`README.md`（环境要求 / 未执行清单 / 已知环境偏差）、
  `docs/deployment.md`、`docs/requirements-matrix.md`（REQ-3.1-05、REQ-5.1-01）、
  `docs/test-report.md`、`docs/acceptance.md`、`docs/assumptions.md` §一与第 46 条，
  以及前端「进度说明」页（`frontend/src/views/system/ProgressView.vue`）的版本描述。

**两条必须留意的运维约束（已写入 `docs/assumptions.md` 第 46 条）。**

1. **不能降级复用数据目录**：已有 8.4 实例的数据文件无法直接给 8.0 启动，
   必须 `mysqldump` 逻辑导出后重新导入（见 `docs/backup-restore.md`）。
2. **8.0 系列的官方支持窗口到 2026-04 结束**，因此取 8.0 系列**最新补丁**而非 8.0.17。

**回归。** `manage.py check` 无问题、`makemigrations --check --dry-run` 无变更、`ruff` 全过、
`pytest tests/test_docs_sync.py` 7 passed、前端 `vue-tsc` 通过 / `vitest` 258 passed / `vite build` 通过。
**未执行**：`docker compose build` 与 `mysql:8.0` 容器镜像的实际启动验证（本机 Docker 守护进程不可达）。
## 三十九、跨平台开发：`.gitignore` 与 `.gitattributes`

**背景。** 开发会在 Windows 与 macOS 两台机器上进行。本机 `core.autocrlf=true`，
而仓库之前**没有 `.gitattributes`**：同一个文件在 Windows 检出是 CRLF、macOS 是 LF，
两边各改一行就会互相看到「整个文件都被改了」的假差异；
`deploy/docker/entrypoint.sh` 这类进入 Linux 容器的脚本更会在 Windows 检出后带 CRLF，
容器内直接报 `bad interpreter: /bin/sh^M`。

**改动。**

- 新增 `.gitattributes`：`* text=auto` + 明确文本类型；`*.sh` / `Dockerfile*` /
  `deploy/docker/*` / `compose.yaml` / `deploy/nginx/nginx.conf` / `deploy/mysql/my.cnf` /
  两个锁文件固定 **LF**；`*.ps1` / `*.psm1` / `*.bat` / `*.cmd` 固定 **CRLF**；
  图片、字体、压缩包、表格等按 `binary` 处理，不做换行转换。
  `scripts/*.ps1` 的 **UTF-8 BOM 属于内容字节，不受换行转换影响**（AGENTS.md §七 的约束仍然成立）。
- 重写 `.gitignore`（保留原有全部规则并补全）：Python 增加 `.tox/` / `.hypothesis/` /
  `.coverage.*`；前端增加 `*.tsbuildinfo` / `.eslintcache` / `.stylelintcache` / 各类
  `*-debug.log*`；编辑器增加 `.history/` / `*.swp` / `*.swo` / `*~` / `*.orig` / `*.rej`；
  Windows 增加 `ehthumbs.db` / `ehthumbs_vista.db` / `Desktop.ini` / `$RECYCLE.BIN/` /
  `*.lnk` / `*.stackdump`；macOS 增加 `._*` / `.AppleDouble/` / `.LSOverride` /
  `.Spotlight-V100/` / `.Trashes/` / `.fseventsd/` / `.DocumentRevisions-V100/` /
  `.VolumeIcon.icns` / `.com.apple.timemachine.donotpresent`。
- 同时更新 `AGENTS.md` §七 的「已知陷阱」，把换行与文件属性的口径写进开发约定。

**验证（实执行）。**

| 检查 | 结果 |
| --- | --- |
| `git status --short` | 仅 `.gitignore`（改）与 `.gitattributes`（新增），**已跟踪文件无一被属性变更弄脏** |
| `git check-attr text eol -- deploy/docker/entrypoint.sh` | `text: set` / `eol: lf` |
| `git check-attr text eol -- scripts/dev_backend.ps1` | `text: set` / `eol: crlf` |
| `git check-ignore -v`（`.DS_Store` / `._*` / `Thumbs.db` / `Desktop.ini` / `$RECYCLE.BIN/` / `node_modules` / `*.tsbuildinfo` / `.eslintcache` / `__pycache__` / `.tmp` / `*.swp` / `*.orig`） | 全部命中预期规则 |
| 反向确认 `.env.example`、`scripts/*.ps1`、`deploy/docker/entrypoint.sh`、`frontend/public/guide.html`、`docs/user-guide.html` | **未被忽略**（这两个 HTML 是随发布交付的产物，必须继续入库） |

**未执行：** 未在 macOS 上做真实检出验证（本机只有 Windows），
因此「macOS 检出后换行符合预期」是按 `.gitattributes` 语义推断，**未实测**。
