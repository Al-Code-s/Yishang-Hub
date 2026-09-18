# 部署与运行（docs/deployment.md）

> **重要**：本文件中标记 **【未执行】** 的步骤在本轮开发环境中**没有实际运行过**。
> 未执行的内容一律不写作通过（任务书 2.4）。真实执行结果见 `docs/test-report.md`。
>
> **使用者视角的操作手册（启动、账号、菜单、排错）见 `docs/user-guide.md`**；
> 本文档侧重部署与发布。两者的启动命令与初始化参数必须保持一致——
> 命令或环境变量变化时，除本文件外**必须同步 `docs/user-guide.md` §三**（规则见其 §十一）。
>
> 使用说明的**网页版**由 `python scripts/build_user_guide.py` 从 `docs/user-guide.md` 生成，
> 产物 `frontend/public/guide.html` 随前端静态资源一起发布（nginx 直接托管 `/guide.html`，
> **不校验登录**）；单文件副本 `docs/user-guide.html` 可直接发给客户。发布前先跑 `--check`。

## 一、环境区分

| 环境 | 用途 | 配置文件 | 说明 |
| --- | --- | --- | --- |
| `development` | 本地开发 | `config/settings/dev.py` | `DEBUG=True`，宽松 CORS |
| `test` | 自动化测试 | `config/settings/test.py` | pytest 默认使用 |
| `staging` | 预发布 | `config/settings/prod.py` + 独立变量 | 与生产同构，数据脱敏 |
| `production` | 生产 | `config/settings/prod.py` | 强制 `DEBUG=False`、HTTPS、严谨来源校验 |

配置**全部由环境变量注入**，`.env.example` 只放示例，**不含真实密钥**。

## 二、本地开发启动（本轮已实际验证 ✅）

### 前置条件

- Python 3.12、Node.js ≥ 20.19（本项目实测 22.17.1 / npm 10.9.2）
- MySQL 8（本轮实测 8.0.17）、Redis（本轮实测 3.2.100）

### 1. 环境变量

```powershell
Copy-Item .env.example backend\.env   # 然后填写 DB_PASSWORD 等，不要提交
```

必须设置：

```text
DJANGO_ENV=development
DJANGO_SECRET_KEY=<随机值>
DB_DRIVER=pymysql          # Windows 本地开发；Docker/Linux 用 mysqlclient
DB_NAME=yishang_platform
DB_USER=yishang_app
DB_PASSWORD=<应用账号密码，不要用 root>
```

### 2. 后端

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py bootstrap_system   # 权限点/菜单/角色/管理员
.\.venv\Scripts\python.exe manage.py seed_demo          # 仅开发环境，演示数据
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

> 初始化命令的密码来源：`bootstrap_system` 读取 `YISHANG_ADMIN_PASSWORD`，
> `seed_demo` 读取 `YISHANG_DEMO_PASSWORD`。**未设置时会生成随机密码并打印一次**，
> 不硬编码任何公开默认密码。生产环境必须通过安全初始化流程设置。

### 3. 前端

```powershell
cd frontend
npm install
$env:VITE_DEV_BACKEND='http://127.0.0.1:8000'   # 与后端端口保持一致
npm run dev
```

开发期前端通过 Vite 代理把 `/api`、`/admin`、`/static`、`/media`、`/healthz`、`/readyz`
转发到 Django，**保持与生产（Nginx 同域）一致的会话与 CSRF 行为**，不依赖跨域 Cookie。
若默认端口 5173 被占用，可 `npm run dev -- --port 5199`（同时需把该来源加入
`DJANGO_CSRF_TRUSTED_ORIGINS`）。

### 4. 健康检查

```text
GET /healthz    存活检查
GET /readyz     就绪检查（含数据库连通性）
```

## 三、Docker Compose 部署 【未执行 ⚠️】

### 服务清单

```text
nginx          反向代理 + 静态资源 + 安全响应头
backend        Gunicorn 应用（非 root）
worker         Celery Worker
beat           Celery Beat（默认单实例）
migrate        一次性发布步骤（不常驻）
mysql          MySQL 8.4 LTS（不发布端口）
redis          Redis（不发布端口）
object-storage S3 兼容对象存储
```

### 启动流程

```bash
cp .env.example .env      # 填写真实值，不提交
docker compose build
docker compose run --rm migrate      # 迁移作为独立发布步骤，单独执行
docker compose up -d
docker compose ps
curl -f http://localhost/healthz
```

### 设计约束（已写入 `compose.yaml`）

- **同一后端镜像**承担 Web / Worker / Beat 三种角色，仅启动命令不同。
- **Beat 默认只运行一个调度实例**，避免重复生成业务单据。
- **MySQL、Redis 不发布端口到宿主机**，只在内部网络可达。
- 所有服务配置**健康检查**；数据使用**持久化卷**。
- **数据库迁移作为独立发布步骤执行**，不由多个 Web 实例同时执行。
- 容器**非 root 用户**运行；上传文件与代码分离。
- 生产使用 **Gunicorn**，不使用 `runserver` 对外提供服务。

### ⚠️ 本轮未验证的原因与风险

本机 **Docker 守护进程不可达**，因此：

| 未执行项 | 风险 | 建议 |
| --- | --- | --- |
| `docker compose build` | 镜像构建可能失败（如 `mysqlclient` 编译依赖缺失） | 在有 Docker 的机器上先构建 |
| `docker compose up` | 服务编排、健康检查、卷挂载未验证 | 逐服务启动并观察健康状态 |
| `migrate` 一次性任务 | 未验证并发/失败处理 | 空库与已有数据两种场景都跑 |
| Nginx 配置 | 路径、代理头、静态资源未验证 | 用 `nginx -t` 校验后灰度 |
| `mysqlclient` 路径 | 本地用的是 PyMySQL，**生产驱动未验证** | 构建后在容器内跑全量 `pytest` |

在上述项目实际通过前，**不得将 Compose 描述为"已验证可部署"**。

## 四、生产要求（任务书 16.2）

- `DEBUG=False`（`prod.py` 强制）。
- 正确配置域名、`CSRF_TRUSTED_ORIGINS` 与 HTTPS（缺失时 `prod.py` 直接抛
  `ImproperlyConfigured`，**启动即失败**，避免带着开发配置上线）。
- 非 root 容器运行。
- 不公开 MySQL、Redis 管理端口。
- 合理配置数据库连接池或连接寿命（`DB_CONN_MAX_AGE`）。
- 上传文件与代码分离；日志轮转。
- 静态资源正确部署。
- **不使用 `runserver` 对外提供生产服务。**
- 生产安全响应头：`SECURE_HSTS_SECONDS`（默认 30 天）、`SECURE_SSL_REDIRECT`、CSP
  （`YISHANG_CSP_POLICY`，默认 `default-src 'self'`）。
- **仅在可信反向代理已设置 `X-Forwarded-For` 时**才开启 `DJANGO_USE_X_FORWARDED_FOR`。

## 五、监控（任务书 16.3）

至少提供：应用存活检查（`/healthz`）、数据库就绪检查（`/readyz`）、Worker 状态、
任务积压、**Outbox 失败数量**（`integration/outbox-events/health/`）、采集离线、
磁盘与备份状态、接口错误率。

日志带 `request_id`；业务任务带任务 ID 与事件 ID。

## 六、发布与回滚（任务书 16.5）

```text
1. 发布前测试迁移（空库 + 已有数据）
2. 备份
3. 兼容性迁移优先
4. 停止或隔离可能冲突的后台任务
5. 执行迁移
6. 发布应用
7. 健康检查与关键业务抽查
```

**代码回滚不等于数据库自动回滚。** 数据库变更必须有独立的恢复计划
（见 `docs/backup-restore.md`）。