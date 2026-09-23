# AGENTS.md —— 意尚智造集成平台开发约定

本文件面向在本仓库工作的开发者与 AI 编码代理。**先读 `PROJECT_SPEC.md` 再动手。**

## 一、项目性质（不要搞错方向）

本平台**直接内置**采购、销售、生产、仓储、质量、设备、能源等业务，
**不是**对接外部 ERP/MES/WMS 的接口平台。

- ❌ 不要把业务功能"留给外部系统通过接口对接"。
- ❌ 不要创建 `platform.py` 顶层模块（与标准库同名）。
- ❌ 不要为了"看起来完整"批量创建空壳 App 或伪可用页面。

## 二、仓库结构

```text
backend/    Django 5.2 + DRF（config/ 工程配置，apps/ 业务模块，tests/ 集成测试）
frontend/   Vue 3 + TS + Vite（src/{api,components,layouts,router,stores,views,types,utils}）
deploy/     nginx/ docker/ mysql/
scripts/    本地开发与运维脚本
docs/       全部设计与过程文档（见下）
compose.yaml  Docker Compose 编排
.env.example  环境变量示例（只放示例，禁止真实密钥）
```

## 三、必须遵守的硬性规则

1. **不覆盖已有有效代码。** 修改前先读文件；不确定就跑测试确认现状。
2. **不提交生产密钥、密码、真实个人资料。** 密码只从环境变量读取；
   本地开发密码放 `.tmp/`（已在 `.gitignore` 中忽略）。
3. **不伪造结果。** 未执行的测试写"未执行"，不写"通过"；
   不伪造构建、部署、设备接入结果。
4. **业务状态只能由 Service 层修改。** View 只做鉴权 + 参数装配 + 调用服务；
   Serializer 不做跨模块副作用；不使用 signals 连锁创建关键单据；
   不跨模块直接改他人业务表。
5. **库存只能经统一库存服务**（阶段 2 起）。禁止任何模块直接写库存余额。
6. **权限编码是统一契约。** 新增页面/接口必须先到
   `backend/apps/identity/permissions_registry.py` 注册权限点与菜单，
   否则后端启动自检（`apps/core/checks.py`）会失败。这是刻意的设计。
7. **金额与数量禁用 float**，Decimal 在 API 中以字符串输出，前端用 `decimal.js`。
8. **前端菜单由后端下发**（`identity/menus/mine/`），不要在 `router` 里硬编码业务菜单权限。

## 四、常用命令

### 后端（Windows 本地开发使用 `backend/.venv`）

```powershell
cd backend
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run   # 应无变更
.\.venv\Scripts\python.exe -m ruff check apps config tests
.\.venv\Scripts\python.exe -m pytest tests -q --reuse-db

开发更新代码运行
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

### 前端

```powershell
cd frontend
$env:npm_config_cache='E:\github\Yishang-Hub\.tmp\npm-cache'   # 或使用 scripts/dev_frontend.ps1
npm run typecheck
npm run test
npm run build

开发更新代码运行
npm run dev -- --port 5173
```

### 一键冒烟

```powershell
powershell -ExecutionPolicy Bypass -File scripts\smoke_check.ps1
```

## 五、每完成一个可运行增量必须做

1. 运行与改动相关的**最窄测试**，再跑更广的测试。
2. `manage.py check` + `makemigrations --check`（确保迁移已提交）。
3. Ruff / vue-tsc 通过。
4. 更新 `docs/progress.md` 与 `docs/requirements-matrix.md`。
5. 新增能力时同步更新对应专项文档（`architecture.md`、`data-model.md`、
   `permission-matrix.md`、`api-conventions.md` 等）。
6. 若改动影响**使用者能看到的行为**（菜单、操作步骤、错误提示、业务口径），
   同步更新面向客户的 `docs/user-guide.md`，并重新生成网页版（见 §九）。

## 六、文档地图

| 文档 | 用途 |
| --- | --- |
| `docs/requirements.md` | 范围基线（含排除项） |
| `docs/requirements-matrix.md` | 逐条需求追踪（**必须保持更新**） |
| `docs/architecture.md` | 架构与分层、ADR |
| `docs/data-model.md` | 表结构、数值口径、NULL 唯一索引方案 |
| `docs/business-flows.md` | 五条业务闭环设计 |
| `docs/permission-matrix.md` | 四层权限、权限编码清单、菜单树（表格由注册表生成） |
| `docs/api-conventions.md` | 接口/错误/分页/幂等/异步契约 |
| `docs/inventory-rules.md` | 库存规则（阶段 2 强制契约） |
| `docs/energy-calculation.md` | 能源计量规则（阶段 5） |
| `docs/assumptions.md` | 假设与偏差（**新增不确定项写这里**） |
| `docs/progress.md` | 阶段进度报告 |
| `docs/test-report.md` | 测试实际执行结果（含未执行清单） |
| `docs/acceptance.md` | 阶段验收结论 |
| `docs/deployment.md` | 部署与运行（含未验证项） |
| `docs/backup-restore.md` | 备份恢复方案 |
| `docs/hardware-integration.md` | 硬件接入方案与边界 |
| `docs/user-guide.md` | **面向客户的使用说明**（业务操作手册：登录、菜单、按模块操作、错误处理）。只写使用者能看到的行为，不写实现细节；网页版见 §九 |

## 七、已知陷阱（本仓库踩过）

- **前端 `.vue` 文件缺少 `</script>` 等标签时，`vue-tsc` 可能通过但 `vite build` 失败。**
  `frontend/tests/views-compile.spec.ts` 专门拦截这类问题，不要删除它。
- **权限/菜单表在 `docs/permission-matrix.md` 中是由注册表生成的**，
  改动注册表后需重新生成本节，避免文档与代码不一致。
- **测试内登录限流**：`backend/tests/conftest.py` 有 autouse fixture 复位限流计数，
  否则连续登录用例会互相干扰。
- **Windows 上 `Get-Content` 可能错误显示中文**；读取中文文件请用
  `python -c "import io;print(io.open(path, encoding='utf-8').read())"`。
- **`scripts/*.ps1` 必须保存为带 BOM 的 UTF-8**（`utf-8-sig`）。
  Windows PowerShell 5.1 会按 ANSI/GBK 解析无 BOM 的脚本，中文注释与中文字符串会导致
  `TerminatorExpectedAtEndOfString` 之类的语法错误（本仓库实际踩过这个坑）。
- **换行与文件属性统一由 `.gitattributes` 决定**：仓库内按 LF 存储，`*.sh` / `Dockerfile*` / `deploy/*` / `compose.yaml` / 锁文件固定 **LF**，`*.ps1` / `*.bat` / `*.cmd` 固定 **CRLF**。
  Windows 上 `core.autocrlf=true` 会把文本按 CRLF 检出，**不要手工整文件转换换行**（会造成「整个文件都被改了」的假差异）；
  新增脚本类文件后先跑 `git check-attr text eol -- <路径>` 确认属性命中。
  路径级忽略规则见 `.gitignore`（Windows 与 macOS 的系统文件、编辑器临时文件、构建产物均已覆盖）。
- **`.tmp/` 下是本地临时脚本与开发密码**，不要提交，也不要删除他人的临时文件。

## 八、阶段边界

当前已完成：阶段 0~1（工程基座 + 登录/权限/组织/主数据/审批/审计）、阶段 2
（客户/供应商/采购/销售/WMS 统一库存）、阶段 3（BOM/工艺/MRP/**MES 生产工单与报工**）、**阶段 4 设备管理**、
**阶段 5 能源管理 + 设备数采首版（HTTP 上报入口与内置模拟器）**、
阶段 6 的**安全环保管理**与**厂内物流**、客户管理的**客户投诉与产品评价**，
以及**质量管理（QMS）**：检验项目、检验单与结果判定、质量报警、质量问题知识库，
以及供应商管理的**五维量化评价**（权重配置与只增不改的版本派生、缺数据两种口径、按明细聚合的评价统计）。
按明细实时聚合的**只读统计**（设备数采采集统计、投诉 / 评价统计、质量信息动态监测、MES 生产统计）也已实现，**不建汇总表**。

**明确未实现、不要声称已完成**：销售计划 / 分销商 / 市场预测、
供应商寻源与报价、跨系统数据交换中间件、MQTT / Modbus 等工业协议解析与真实设备接入
（现只有 HTTP 上报入口与内置模拟器，且未与真实设备联调）、采集原始数据的归档 / 清理任务、
工业终端安全（防病毒与补丁管理）、OEE 统计、职业健康管理、能源调度、
MES 的线体排产 / 裁剪任务 / 工位派工 / 在制品转移 / 扫码硬件控制、
综合报表 / 成本 / 运维演练。
新增能力时，先更新 `docs/requirements-matrix.md` 再写代码。

## 九、面向客户的使用说明与文档同步

`docs/user-guide.md` 是**发给客户看的使用说明**（业务操作手册），
因此：**启动命令、环境变量、测试命令、代码路径、文档同步规则等开发内容不写进该文件**，
它们属于本文件与 `docs/deployment.md`、`docs/test-report.md`。

同一份说明还有**自动生成的单文件网页版**，供系统内「使用说明」入口与客户直接打开：

| 产物 | 位置 | 用途 |
| --- | --- | --- |
| `docs/user-guide.html` | 仓库内 | 单文件、离线可用：双击打开，或作为附件发给客户 |
| `frontend/public/guide.html` | 随前端发布 | 浏览器访问 `/guide.html`（Nginx 作为静态资源发布） |

```powershell
cd backend
.\.venv\Scripts\python.exe ..\scripts\build_user_guide.py           # 生成 / 覆盖两份产物
.\.venv\Scripts\python.exe ..\scripts\build_user_guide.py --check   # 只校验是否最新
```

**不要直接编辑 HTML**（生成物，改了会被覆盖）。改了 Markdown 不重新生成，
`pytest tests/test_docs_sync.py` 会失败。

该用例还校验下面这条**机器可读事实行**，它与注册表 / 模型 / 迁移文件逐项比对，
**改了代码就按实际值更新这一行**：

<!-- yishang-doc-sync: permissions=368 menus=144 models=146 migrations=30 builtin_roles=19 -->

| 键 | 含义 | 权威来源 |
| --- | --- | --- |
| `permissions` | 权限点总数 | `apps/identity/permissions_registry.PERMISSIONS` |
| `menus` | 菜单项总数（含目录） | `apps/identity/permissions_registry.MENUS` |
| `models` | 受管数据模型总数 | Django `apps.get_models()`（排除自动生成模型） |
| `migrations` | 迁移文件总数 | `backend/apps/*/migrations/0*.py` |
| `builtin_roles` | 内置角色数（**不含** `seed_demo_xjys` 建的演示角色） | `bootstrap_system.BUILTIN_ROLES` |
