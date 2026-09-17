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
```

### 前端

```powershell
cd frontend
$env:npm_config_cache='E:\github\Yishang-Hub\.tmp\npm-cache'   # 或使用 scripts/dev_frontend.ps1
npm run typecheck
npm run test
npm run build
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
- **`.tmp/` 下是本地临时脚本与开发密码**，不要提交，也不要删除他人的临时文件。

## 八、阶段边界

当前完成的是**阶段 0 与阶段 1**（工程基座 + 登录/权限/组织/主数据/审批/审计）。
阶段 2 起（客户、供应商、采购、销售、WMS 库存等）尚未实现，**不要声称已完成**。
新增阶段时，先更新 `docs/requirements-matrix.md` 再写代码。