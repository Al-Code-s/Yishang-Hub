# 部署与运行（docs/deployment.md）

> **重要**：本文件中标记 **【未执行】** 的步骤在本轮开发环境中**没有实际运行过**。
> 未执行的内容一律不写作通过（任务书 2.4）。真实执行结果见 `docs/test-report.md`。
>
> **面向客户的使用说明（登录、菜单、按模块操作、错误处理）见 `docs/user-guide.md`**：
> 该文件只写使用者能看到的行为，**启动命令、环境变量、测试命令等开发内容写在本文件**。
> 命令或环境变量变化时，除本文件外还需按 `AGENTS.md` §九 的规则同步文档与网页版说明。
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
- MySQL 8.0 系列（本轮实测 8.0.17；部署镜像 `mysql:8.0`）、Redis（本轮实测 3.2.100）

### 双平台（Windows / macOS）环境对照

开发会在 Windows 与 macOS 两台机器上进行。**代码与数据都不再手工拷贝**：
`backend/.env`（开发库口令与配置）与开发库快照 `db/*.sql` 已随仓库入库，
新机器只要 `git clone` 就有这些文件，换机步骤见 `docs/backup-restore.md` §8.5。
两平台的差异如下：

| 组件 | Windows | macOS |
| --- | --- | --- |
| Python 3.12 | 官方安装包（`py -3.12`） | `brew install python@3.12` |
| Node.js 22 | 官方安装包 | `brew install node@22` |
| MySQL | 本机服务名 `MySQL80`，实测 8.0.17 | **`brew install mysql@8.0`**（brew 的 `mysql` 公式当前指向 9.x，不是 8.0），再 `brew services start mysql@8.0` |
| Redis | 本机已装（实测 3.2.100） | `brew install redis`，再 `brew services start redis` |
| 数据库驱动 | `DB_DRIVER=pymysql` + `pip install ".[pymysql]"` | 同左：用 `pymysql` 可以省掉 `mysqlclient` 的编译依赖，与 Windows 保持一致 |
| 虚拟环境路径 | `.\.venv\Scripts\python.exe` | `.venv/bin/python` |
| 启动脚本 | `scripts/*.ps1`（`dev_backend.ps1` / `dev_frontend.ps1` / `smoke_check.ps1`） | **PowerShell 脚本不能直接运行**，用原生命令 `manage.py runserver` + `npm run dev`；`scripts/*.sh`（备份 / 恢复）是 bash，可在 Mac 使用 |
| 换行 | 由 `.gitattributes` 统一（仓库内 LF，`*.ps1` 固定 CRLF） | 同左，Mac 检出为 LF，不会带 `\r` |

两平台一致的部分：

- 表结构由 `manage.py migrate` 建，数据从 `db/yishang_platform_<日期>.sql` 导入。
  MySQL 的 `lower_case_table_names` 默认值各平台不同，但本平台表名全小写，**跨平台导入不受影响**；
  快照在 `.gitattributes` 中标记为 `-text`（保持原样，不做换行转换），`mysql < 文件` 两平台都能直接导入。
- Apple Silicon 上 `mysql@8.0` / `python@3.12` / `node@22` 均有 arm64 包；
  若安装不顺，可退回官方 dmg，或直接用 `compose.yaml` 只起 MySQL / Redis 容器、后端跑在宿主。
- 前端依赖用 `npm install` 在新机器上重装（`node_modules/` 不要跨平台拷贝）。

> **未执行**：上面 macOS 路径**未在真实 Mac 上实测**（本机只有 Windows），
> 属按 `.gitattributes` 与 brew 包语义推断；Windows 路径见本节其余各处（已实测）。

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
.\.venv\Scripts\python.exe manage.py seed_demo          # 兼容入口，等价于 seed_demo_xjys
.\.venv\Scripts\python.exe manage.py seed_demo_xjys     # 仅开发环境，演示数据（新疆意尚智造 XJYS，2026-01 起）
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

> 初始化命令的密码来源：`bootstrap_system` 读取 `YISHANG_ADMIN_PASSWORD`，
> `seed_demo` 读取 `YISHANG_DEMO_PASSWORD`。**未设置时会生成随机密码并打印一次**，
> 不硬编码任何公开默认密码。生产环境必须通过安全初始化流程设置。
>
> 平台只服务「新疆意尚智造科技有限公司」一家公司；`seed_demo` 是 `seed_demo_xjys`
> 的兼容入口（两者等价，旧演示公司已合并删除），
> 覆盖设备、能源、数采、库存、采购、销售、MES、MRP、质量、供应商评价、客户投诉/评价、
> 安全环保与厂内物流，所有业务日期落在 2026-01-01 至执行当天；重复执行只补齐缺失记录。

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

### 5. 日常启动与停止

也可以用仓库自带的脚本（会自动做 `check` + 迁移，前端会自动装依赖）：

```powershell
cd E:\github\Yishang-Hub
powershell -ExecutionPolicy Bypass -File scripts\dev_backend.ps1        # 默认 8000
powershell -ExecutionPolicy Bypass -File scripts\dev_frontend.ps1       # 默认 5173
# 换端口： scripts\dev_backend.ps1 -Port 8001 / scripts\dev_frontend.ps1 -Port 5174
```

- 日常启动只需上面第 2、3 步的最后两条（`runserver` 与 `npm run dev`），无需重复迁移与初始化。
- 停止：在各自终端按 `Ctrl + C`。
- 改了后端代码：开发服务器会自动重载；**改了模型**要重新
  `manage.py makemigrations <app>` + `migrate`。
- **不要用 `runserver` 对外提供生产服务**（生产用 Gunicorn + Nginx，见 §三、§四）。

### 6. 初始化命令常用开关

| 命令 | 说明 |
| --- | --- |
| `manage.py bootstrap_system --dry-run` | 只展示将执行的动作，不写库 |
| `manage.py bootstrap_system --admin-username X --admin-password Y` | 指定管理员账号与口令 |
| `manage.py bootstrap_system --skip-admin` | 不创建 / 更新管理员账号 |
| `manage.py bootstrap_system --reset-admin-password` | 重置管理员口令（需提供口令来源，不随机覆盖） |
| `manage.py seed_demo` | 兼容入口，等价于 `seed_demo_xjys` |
| `manage.py seed_demo --yes` | 在非 development/test 环境确认写入（生产仍被硬拒） |

两个命令都**幂等**：重复执行只同步固定字段，不重复建记录，也不重置已有账号口令。

### 7. 访问地址一览（本地开发）

| 地址 | 用途 |
| --- | --- |
| http://127.0.0.1:5173/ | 前端界面（日常使用入口） |
| http://127.0.0.1:5173/login | 登录页；未登录访问任何页面都会跳到这里 |
| http://127.0.0.1:5173/guide.html | **平台使用说明（网页版）**，也可在系统内点「使用说明」打开 |
| http://127.0.0.1:8000/api/v1/ | 后端 API 根 |
| http://127.0.0.1:8000/api/v1/docs/ | OpenAPI（Swagger UI）；**界面不提供入口，仅供开发者使用** |
| http://127.0.0.1:8000/api/v1/schema/ | OpenAPI 原始 schema |
| http://127.0.0.1:8000/healthz | 存活检查 |
| http://127.0.0.1:8000/readyz | 就绪检查（数据库 + 缓存） |
| http://127.0.0.1:8000/admin/ | Django Admin（运维兜底，**不是业务前端**） |

### 8. 数据库与文件位置

- **业务数据存在 MySQL 里**，不在项目目录内。项目目录下没有 `.sqlite3`，
  `DB_*` 环境变量指向的就是数据实际所在地。
- 本机 MySQL 默认数据目录在 `C:\ProgramData\MySQL\MySQL Server 8.0\Data\`
  （系统目录，日常不要手动改动其中的文件）。

| 库名 | 作用 |
| --- | --- |
| `yishang_platform` | **开发 / 运行库**，业务数据都在这里 |
| `test_yishang_platform` | **测试库**，`pytest` 自动创建 / 复用（`--reuse-db`），跑测试会**重建**它 |
| `information_schema` | MySQL 自带的**元数据视图**（表结构、权限等），只读，不是业务数据 |

```powershell
# 用应用账号连接（与后端同一个账号，权限更小，更接近真实情况）
mysql -h 127.0.0.1 -P 3306 -u yishang_app -p yishang_platform
```

- 连接串等价表示：`mysql://yishang_app:<密码>@127.0.0.1:3306/yishang_platform?charset=utf8mb4`。
- **不要用 root 连接应用**；生产环境数据库端口不对外发布（见 §四）。
- 附件默认落在本地 `MEDIA_ROOT`（项目内 `backend/media/`），配置 S3 兼容对象存储时改为远端；
  生产要求「上传文件与代码分离」。日志按 `LOG_LEVEL` 输出到控制台，生产要求日志轮转与
  `request_id` 贯穿（见 §五）。
- 备份与恢复步骤见 `docs/backup-restore.md`（当前**未做过真实恢复演练**）。

## 三、Docker Compose 部署 【未执行 ⚠️】

### 服务清单

```text
nginx          反向代理 + 静态资源 + 安全响应头
backend        Gunicorn 应用（非 root）
worker         Celery Worker
beat           Celery Beat（默认单实例）
migrate        一次性发布步骤（不常驻）
mysql          MySQL 8.0 系列（镜像 `mysql:8.0`，不发布端口）
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

> `.env` 必填项（缺任一项 Compose 直接拒绝启动）：`DJANGO_SECRET_KEY`、`DJANGO_ALLOWED_HOSTS`、
> `DJANGO_CSRF_TRUSTED_ORIGINS`、`DB_PASSWORD`、`MYSQL_ROOT_PASSWORD`、`OBJECT_STORAGE_SECRET_KEY`；
> 空库首次安装还要提供 `YISHANG_ADMIN_PASSWORD`（见下一节）。

### 首次安装（空库）必做步骤 【未执行 ⚠️】

上面的 `migrate` 只建出**空表结构**。空库还必须补下面两步，否则**登录不进去、`/admin/` 样式 404**：

```bash
# 1) 权限点 / 菜单 / 内置角色 / 管理员账号（幂等，可重复执行）
#    production 环境必须提供管理员口令，缺失时直接报错退出（不允许猜口令）
docker compose run --rm -e YISHANG_ADMIN_PASSWORD='<强口令>' backend python manage.py bootstrap_system

# 2) 把 Django Admin / DRF 的静态资源收集到 backend-static 卷（Nginx 的 /static/ 从该卷读取）
#    前端页面是打进 Nginx 镜像的构建产物，不受这一步影响
docker compose run --rm backend python manage.py collectstatic --noinput

# 3) 重启一次，让新写入的菜单 / 权限生效
docker compose up -d
```

- **客户机不要执行演示数据命令**：`seed_demo` 与 `seed_demo_xjys` 在 `DJANGO_ENV=production`
  下**直接拒绝执行**，演示数据只用于本地开发。
- 客户机是**全新空库**时，从零到能登录只需 `migrate` + `bootstrap_system`；
  把已有数据搬到新机器请改用 `docs/backup-restore.md` §八 的导入流程，不要重新初始化。

### 把数据带进容器（开发库快照）【未执行 ⚠️】

仓库里的 `db/yishang_platform_<日期>.sql` 是开发库的逻辑快照（154 张表，含业务数据），
按下面的顺序灌进容器 MySQL 即完成「代码 + 数据」一起部署。

```bash
# 1) 先只起数据库，等健康检查通过（MySQL/Redis 不对宿主发布端口，只能经 compose 操作）
docker compose up -d mysql
docker compose ps mysql

# 2) 导入快照（Linux / macOS / CI 的 bash 可直接重定向）
docker compose exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot yishang_platform' \
    < db/yishang_platform_2026-09-24.sql

# 3) 再起其余服务：migrate 自动执行，随后 backend / worker / beat / nginx
docker compose up -d

# 4) 静态资源进卷（Nginx 的 /static/ 从该卷读取），然后看健康状态
docker compose exec backend python manage.py collectstatic --noinput
docker compose ps
curl -f http://localhost/healthz
```

**Windows PowerShell 不支持 `<` 重定向**，且用管道传中文有二次编码风险，改成「先拷进容器再导入」：

```powershell
docker compose up -d mysql
docker compose cp db\yishang_platform_2026-09-24.sql mysql:/tmp/snapshot.sql
docker compose exec mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot yishang_platform < /tmp/snapshot.sql'
docker compose exec mysql rm -f /tmp/snapshot.sql
docker compose up -d
docker compose exec backend python manage.py collectstatic --noinput
```

**关于快照与初始化的四点事实：**

- 快照**不含 `CREATE DATABASE`**（导入不需要建库权限）；库由容器启动时的 `MYSQL_DATABASE`
  自动建好，用户由 `MYSQL_USER` / `MYSQL_PASSWORD` 建好，所以上面直接指定库名即可导入。
- 快照自带 `DROP TABLE IF EXISTS`，**重复导入会覆盖同名表的数据**，可放心重跑，但会丢掉导入后新录的数据。
- **用快照导入时，`bootstrap_system` 是可选的**：快照里已含权限点、菜单、内置角色与管理员账号，
  重复执行只会补齐缺失项；已存在的管理员**保留原口令**（只有显式加 `--reset-admin-password` 才会改）。
  只有**空库**首次安装才必须跑它并提供 `YISHANG_ADMIN_PASSWORD`。
- 导入后 `docker compose run --rm migrate` / `migrate` 服务应显示**没有需要应用的迁移**；
  若有新迁移，正常执行即可（不会动已有数据）。

**核对导入结果**（期望 `154`）：

```bash
docker compose exec mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot yishang_platform -N \
    -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()"'
```

**想让「首次启动自动带数据」**（可选）：在 `compose.yaml` 的 `mysql` 服务里加一行挂载，
MySQL 官方镜像会在**数据卷为空时**自动执行 `/docker-entrypoint-initdb.d/` 下的 `.sql`：

```yaml
    volumes:
      - mysql-data:/var/lib/mysql
      - ./db/yishang_platform_2026-09-24.sql:/docker-entrypoint-initdb.d/10-snapshot.sql:ro
```

> 注意：该机制**只在数据卷为空的首次启动执行**，已有卷不会重跑（想重来要 `docker compose down -v`，
> 那会**删掉全部数据**）；而且它会把演示数据带进该环境，客户机生产库建议仍用上面的手工导入，便于确认。

### 客户机（内网）落地注意事项 【未执行 ⚠️】

| 项目 | 要求 |
| --- | --- |
| `DJANGO_ALLOWED_HOSTS` | 必须是客户机**实际访问地址**，如 `192.168.1.50,localhost` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 带协议的完整来源，如 `http://192.168.1.50`；不一致会导致登录报 CSRF 失败 |
| `HTTP_PORT` | 前端对外端口，默认 `80`；被占用时改 `.env`（如 `HTTP_PORT=8080`） |
| 定时任务 | 平台**没有内置调度器**，`ems_offline_check` / `iot_offline_check` 需用 Windows 计划任务或 Compose 的 `beat` 服务（见 §三之三、§三之四） |
| HTTPS | `prod.py` 默认 `SECURE_SSL_REDIRECT=true`，纯 HTTP 访问会被 301 跳 https；内网无证书时设 `DJANGO_SECURE_SSL_REDIRECT=false`，但**纯 HTTP 下登录仍会失败**（详见 `docs/assumptions.md` 第 45 条） |

### 设计约束（已写入 `compose.yaml`）

- **同一后端镜像**承担 Web / Worker / Beat 三种角色，仅启动命令不同。
- **Beat 默认只运行一个调度实例**，避免重复生成业务单据。
- **MySQL、Redis 不发布端口到宿主机**，只在内部网络可达。
- 所有服务配置**健康检查**；数据使用**持久化卷**。
- **数据库迁移作为独立发布步骤执行**，不由多个 Web 实例同时执行。
- 容器**非 root 用户**运行；上传文件与代码分离。
- 生产使用 **Gunicorn**，不使用 `runserver` 对外提供服务。
- 构建上下文由根目录 `.dockerignore` 收窄：排除 `.git`、`**/node_modules`、`**/.venv`、`.tmp/`、`db/`、
  `backend/.env`、`backend/media`、`docs/` 等（本机实测这些目录合计约 620 MB），
  既避免把宿主机依赖复制进 Linux 镜像，也避免开发库口令进镜像。
- **镜像内不含 `backend/.env`**：容器配置只来自编排注入。Django 侧 `load_dotenv(BASE_DIR / ".env")`
  默认 `override=False`，即便镜像里存在 `.env`，**编排注入的环境变量优先**。

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

## 三之三、能源离线报警定时任务（本轮新增）

能源模块的「设备离线」报警依赖**抄表超时扫描**，平台**没有内置调度器**，需要在部署侧配置计划任务：

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py ems_offline_check            # 扫描全部公司
.\.venv\Scripts\python.exe manage.py ems_offline_check --company-id 1
```

- 建议频率：**每 5~15 分钟一次**（阈值 `EnergyThreshold.offline_minutes` 决定多久算离线）。
- 幂等：同一公司 / 仪表 / 类型在**同一天内**只报一次警，重跑不会刷屏。
- 手动触发等价入口：`POST /api/v1/ems/alarms/scan-offline/`（需要 `ems.alarm.handle` 权限）。
- 只扫描配置了 `offline_minutes` 的介质 / 仪表；没有配置阈值的仪表不参与检测（避免「全表报警」）。
- **Windows 计划任务 / Linux cron / 容器定时**均可，命令本身不依赖 Celery。

## 三之四、设备数采离线报警与令牌（本轮新增）

数采侧同样**没有内置调度器**，设备离线报警需要在部署侧配置计划任务：

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py iot_offline_check                 # 扫描全部公司
.\.venv\Scripts\python.exe manage.py iot_offline_check --company 1     # 只扫描指定公司
```

- 建议频率：**每 5~15 分钟一次**（判定阈值是每台数采设备上的 `offline_minutes`，默认 30 分钟）。
- 幂等：同一公司 / 设备 / 类型在**同一天内**只报一次警；**模拟设备（`is_simulated=True`）不参与扫描**。
- 手动造数与验证：`manage.py iot_simulate --seed-demo --company 1 --rounds 2 [--out-of-range]`
  （数据全程标注「模拟」，`--dry-run` 只打印报文不入库）。

**设备令牌的运维注意**：

- 令牌明文**只在生成 / 轮换的响应里返回一次**，平台只保存 SHA-256 摘要，无法从数据库反查明文；
  设备侧丢失令牌只能重新轮换（旧令牌立即失效）。
- 设备上报入口是 `POST /api/v1/iot/ingest/`，只认 `X-Device-Token`（或 `Authorization: Device <token>`）头，
  **不接受员工登录会话**；建议把采集网段与办公网段隔离，并只放通该接口。
- 上线 MQTT / Modbus 之前必须先确认设备协议：连接配置可以登记这两种协议，但采集入口会返回
  `PROTOCOL_NOT_IMPLEMENTED`（409），**不会静默吞掉数据**。

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
