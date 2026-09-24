# 意尚智造集成平台 —— 后端

Django 5.2 LTS + Django REST Framework + MySQL 8 + Redis/Celery。

## 目录

```text
config/            工程配置
  settings/        base.py / dev.py / test.py / prod.py
  urls.py          /api/v1 路由与 OpenAPI
  celery.py        Celery 应用
apps/
  core/            公共基础：BaseModel、审计、Outbox、幂等、字典、编码规则、附件、异常、分页
  identity/        用户、角色、权限点、菜单、会话、通知（权限契约在 permissions_registry.py）
  factory/         公司、部门、工厂、车间、线体、工位、员工、班次、班组
  masterdata/      物料、分类、面料属性、款式、颜色、尺码、SKU、计量单位与换算、标识
  wms/             仓库、库区、储位（阶段 2 增加库存余额与流水）
  workflow/        审批模板、实例、节点、日志
  integration/     Outbox 事件与单据关系（内部协同）
  analytics/       看板与报表聚合
tests/             跨模块集成测试（pytest + pytest-django，运行在 MySQL 上）
```

## 常用命令

```powershell
$env:PYTHONIOENCODING='utf-8'

.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe -m ruff check apps config tests
.\.venv\Scripts\python.exe -m pytest tests -q --reuse-db
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

管理命令：

```powershell
.\.venv\Scripts\python.exe manage.py bootstrap_system   # 权限点/菜单/角色/管理员（幂等）
.\.venv\Scripts\python.exe manage.py seed_demo          # 演示数据：兼容入口，等价于 seed_demo_xjys
.\.venv\Scripts\python.exe manage.py seed_demo_xjys     # 演示数据：新疆意尚智造（XJYS，2026-01 起，幂等）
```

## 环境变量

本地开发读 `backend/.env`（已随仓库入库）；要重建时键的清单见 `docs/deployment.md` §二，
Compose 用的示例见仓库根目录 `.env.example`。关键项：

- `DJANGO_ENV`（development/test/staging/production）、`DJANGO_SECRET_KEY`
- `DB_DRIVER`（`mysqlclient` 生产 / `pymysql` Windows 本地）、`DB_*`
- `REDIS_URL`、`CELERY_BROKER_URL`
- `YISHANG_*` 业务参数（分页上限、登录限流、附件限制、CSP 等）

## 约定

- **业务状态只由 Service 层修改**；View 只做鉴权与参数装配。
- **库存只能经统一库存服务**（阶段 2 起）。
- 新增权限点/菜单必须登记到 `apps/identity/permissions_registry.py`，
  否则启动自检 `apps/core/checks.py` 会失败。
- 金额与数量使用 Decimal（禁用 float），API 以字符串输出。
- 详细规则见仓库根目录 `PROJECT_SPEC.md` 与 `AGENTS.md`。