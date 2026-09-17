# 意尚智造集成平台（Yishang Platform）

面向服饰、服装制造及相关经营企业的**统一业务平台**。

一个平台、一套账号权限、统一主数据、多个内置业务模块、跨模块流程闭环。

> **重要**：采购、销售、生产、仓储、质量、设备、能源等功能**在本平台内部实现**，
> 本平台**不是**对接外部 ERP / MES / WMS 的接口平台。

- 技术栈：Python 3.12 + Django 5.2 LTS + DRF + MySQL 8 + Redis/Celery ＋ Vue 3 + TypeScript + Element Plus
- 架构形态：**模块化单体**（第一版不使用微服务/Kubernetes）
- 完整规格：`PROJECT_SPEC.md` ｜ 开发约定：`AGENTS.md`

## 当前状态

**已完成：阶段 0（工程基座）、阶段 1（登录 → 主数据维护闭环）、阶段 2 第一步（客户与供应商主数据）、
阶段 2 核心（**统一库存服务：余额 / 流水 / 单据 / 质量放行 / 幂等过账 / 并发安全**）、
阶段 2 第三步（**采购模块：采购申请 → 订单 → 收货 → 来料检验放行**）。**

| 已交付 | 说明 |
| --- | --- |
| 工程与部署 | Django + DRF 后端、Vue 3 + TS 前端、MySQL/Redis 配置、`compose.yaml` |
| 认证与会话 | 会话登录、CSRF、退出、改密、个人中心、登录限流与失败锁定 |
| 权限体系 | 四层权限（菜单/操作/接口/数据范围）、139 个权限点、47 项菜单 |
| 组织与排班主数据 | 公司、部门、工厂、车间、线体、工位、员工、班次、班组 |
| 服饰主数据 | 物料、分类、面料属性、款式、颜色、尺码、SKU、计量单位与换算、标识分型 |
| 仓储基础 | 仓库、库区、储位 |
| 统一库存服务 | 库存余额（四类数量口径）与**只追加**流水、库存单据（收货/出库/同仓移库/调整/质量）、过账与冲销、质量放行、幂等与并发安全（**不含跨仓调拨在途、盘点、冻结/占用动作入口**） |
| 客户与供应商主数据 | 客户档案与联系人、供应商档案与联系人、供应商资质与有效期（**不含寻源、报价、评分评价与准入审批流程**） |
| 采购模块 | 采购申请（常规/计划/紧急）与审批、申请转订单、采购订单（金额后端计算、审批、关闭）、供应商准入校验与例外授权、收货（**不允许超收**、草稿占额度）、收货过账 → 待检库存、来料检验放行（**人工判定**，多行逐行放行）；**不含**询价比价、到货差异、退货、应付与付款登记、单据打印 |
| 审批与治理 | 审批模板与实例、顺序多级、条件路由、快照与轨迹；审计、通知、字典、编码规则、附件 |
| 界面 | 后台布局、按权限下发的动态菜单、工作台看板、实施进度页 |

**尚未开始**：销售单据、**跨仓调拨在途与盘点**、生产（MRP/MES/QMS）、设备（EAM）、
能源（EMS）、EHS、物流、终端安全，以及供应商寻源/报价/评分评价与客户服务工单
—— 见 `docs/requirements-matrix.md` 的阶段标注与 §一之二 / §一之三 / §一之四增量清单。

> ⚠️ **Docker Compose 未实际启动验证**（开发机 Docker 守护进程不可达）。
> 相关文件已编写，但**不声称"已验证可部署"**。详见 `docs/assumptions.md`。

## 环境要求

| 组件 | 版本 | 备注 |
| --- | --- | --- |
| Python | 3.12 | 本项目在 3.12.14 上验证 |
| Node.js | ≥ 20.19 | 本项目在 22.17.1 / npm 10.9.2 上验证 |
| MySQL | 8.4 LTS（目标） | 本地开发验证于 8.0.17，见偏差说明 |
| Redis | 7.x（目标） | 本地开发验证于 3.2.100 |

## 快速开始

### 1. 配置环境变量

```powershell
Copy-Item .env.example backend\.env
```

至少填写：`DJANGO_SECRET_KEY`、`DB_NAME`、`DB_USER`、`DB_PASSWORD`。
Windows 本地开发请设 `DB_DRIVER=pymysql`（无 C 编译工具链）；Docker/Linux 使用 `mysqlclient`。

> 数据库请使用**专用应用账号**，不要用 `root` 连接应用。
> 密码不要写进代码或提交到仓库。

### 2. 启动后端

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py bootstrap_system   # 权限点/菜单/角色/管理员
.\.venv\Scripts\python.exe manage.py seed_demo          # 仅开发环境演示数据
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

初始化命令的密码来自环境变量（`YISHANG_ADMIN_PASSWORD` / `YISHANG_DEMO_PASSWORD`）；
**未设置时会生成随机密码并打印一次**，代码中不硬编码任何公开默认密码。
`seed_demo` 在 `production` 环境会被直接拒绝。

也可使用脚本：`powershell -ExecutionPolicy Bypass -File scripts\dev_backend.ps1`

### 3. 启动前端

```powershell
cd frontend
npm install
$env:VITE_DEV_BACKEND='http://127.0.0.1:8000'
npm run dev
```

也可使用脚本：`powershell -ExecutionPolicy Bypass -File scripts\dev_frontend.ps1`

前端通过 Vite 代理把 `/api`、`/admin`、`/static`、`/media`、`/healthz`、`/readyz`
转发到 Django，保持与生产（Nginx 同域）一致的会话与 CSRF 行为。

## 访问地址

| 地址 | 说明 |
| --- | --- |
| http://127.0.0.1:5173/ | 前端界面 |
| http://127.0.0.1:8000/api/v1/ | 后端 API |
| http://127.0.0.1:8000/api/v1/docs/ | OpenAPI（Swagger UI） |
| http://127.0.0.1:8000/healthz | 存活检查 |
| http://127.0.0.1:8000/readyz | 就绪检查（含数据库） |
| http://127.0.0.1:8000/admin/ | Django Admin（运维兜底，非业务前端） |

登录账号：`bootstrap_system` 创建的管理员（默认用户名 `admin`，密码见初始化时设置或输出的随机值）。

## 验证步骤

```powershell
# 一键冒烟：后端 check / 迁移检查 / ruff / pytest + 前端 typecheck / vitest / build
powershell -ExecutionPolicy Bypass -File scripts\smoke_check.ps1
```

或分别执行：

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m ruff check apps config tests
.\.venv\Scripts\python.exe -m pytest tests -q --reuse-db

cd ..\frontend
npm run typecheck
npm run test
npm run build
```

手工验证要点：

1. 未登录访问 `/api/v1/identity/users/` → 403。
2. 登录后能拿到会话、权限与菜单；工作台显示看板卡片。
3. 在「基础资料 → 物料档案」新建物料 → 列表可见 → 用重复编码再建 → 400 且提示明确。
4. 「系统管理 → 审计与登录日志」能看到上面的新增操作记录。
5. 退出后再次访问受保护接口 → 403。
6. 「仓储管理 → 库存余额」看到演示余额（`available = on_hand - frozen - reserved`）；
   「库存流水」**没有编辑/删除按钮**。
7. 「库存单据」新建一张 `issue` 单，数量大于可用量 → 过账被拒并提示可用量不足；
   改为可满足的数量 → 过账成功、余额与流水同步变化 → 冲销（填原因）后库存回滚、状态为 `reversed`。
8. 「采购管理 → 采购申请」新建申请 → 提交 → 审批通过 → 「转订单」→ 采购订单金额由后端算出 →
   提交并审批 → 「采购收货」从订单带出明细（数量不得超过未收量）→ 过账 →
   「库存余额」出现该批次 `quarantine` 库存 → 用质检账号执行「来料检验」判定合格 →
   余额转为 `qualified`，此后可被 `issue` 单领用。

## 测试结果（实际执行）

| 项目 | 命令 | 结果 |
| --- | --- | --- |
| 后端测试 | `pytest tests -q --reuse-db` | **183 passed**（MySQL 上运行） |
| 后端检查 | `manage.py check` | 无问题 |
| 迁移一致性 | `makemigrations --check --dry-run` | No changes detected |
| 代码风格 | `ruff check apps config tests` | All checks passed |
| 前端类型 | `npm run typecheck` | 通过（退出码 0） |
| 前端测试 | `npm run test` | **6 文件 / 66 项 passed** |
| 前端构建 | `npm run build` | 构建成功 |

**未执行**（不得视为通过）：Docker Compose 构建与启动、`mysqlclient` 生产驱动验证、
Celery Worker/Beat 实际运行、Playwright 端到端测试、硬件采集、备份恢复演练、性能压测。
详见 `docs/test-report.md`。

## 文档地图

| 文档 | 内容 |
| --- | --- |
| `docs/requirements.md` | 范围基线与排除项 |
| `docs/requirements-matrix.md` | 逐条需求追踪矩阵 |
| `docs/architecture.md` | 架构、分层、ADR |
| `docs/data-model.md` | 数据模型与口径（含 NULL 唯一索引方案） |
| `docs/business-flows.md` | 五条业务闭环 |
| `docs/permission-matrix.md` | 权限矩阵与菜单树 |
| `docs/api-conventions.md` | 接口契约 |
| `docs/inventory-rules.md` | 库存规则（已实现，见 §八） |
| `docs/energy-calculation.md` | 能源计量（阶段 5） |
| `docs/hardware-integration.md` | 硬件接入边界 |
| `docs/assumptions.md` | 假设与偏差 |
| `docs/progress.md` | 阶段进度报告 |
| `docs/test-report.md` | 测试实际结果 |
| `docs/acceptance.md` | 阶段验收结论 |
| `docs/deployment.md` | 部署与运行 |
| `docs/backup-restore.md` | 备份与恢复 |

## 已知环境偏差

| 项 | 目标 | 实际 | 处理 |
| --- | --- | --- | --- |
| MySQL | 8.4 LTS | 8.0.17 | 不使用 8.4 专属语法；部署镜像固定 `mysql:8.4` |
| Redis | 7.x | 3.2.100 | 仅作缓存与 Broker，不使用新版本专属命令 |
| 数据库驱动 | mysqlclient | 开发用 PyMySQL | Docker/Linux 使用 mysqlclient（**未验证**） |
| Docker | Compose 部署 | 守护进程不可达 | 文件已编写，**未启动验证** |

详见 `docs/assumptions.md`。

## 下一步（阶段 2）

1. ~~客户、供应商主数据与 SRM/CRM 基础能力~~ —— **已完成**（见 `docs/progress.md` §六）。
2. ~~采购申请 → 审批 → 采购订单 → 到货 → 待检收货 → 检验放行 → 合格入库~~
   —— **本轮已完成**（见 `docs/progress.md` §八）。剩余：询价比价、到货差异、退货、应付与付款登记、单据打印。
3. ~~统一库存服务：库存余额与流水、四类数量口径、禁止负库存、幂等过账、并发安全~~
   —— **已完成**（见 `docs/progress.md` §七）。剩余：跨仓调拨在途、盘点范围冻结、冻结/占用动作入口。
4. 销售订单、库存占用、发货与退货（发货接入统一库存服务，**不新建库存体系**）。
5. 采购模块的后续增量：询价比价、到货差异处理、采购退货、应付与付款登记、单据打印、
   供应商准入审批流程接入 `workflow`。
6. 前提：建议先在有 Docker 的环境验证 `compose.yaml`。