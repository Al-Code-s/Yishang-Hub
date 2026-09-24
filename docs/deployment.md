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
object-storage S3 兼容对象存储（**默认不启动**，见下）
```

> **`object-storage`（MinIO）默认不启动。** 附件默认落在本机文件系统（`backend-media` 卷），
> `OBJECT_STORAGE_BUCKET` 留空即代表「不用对象存储」，此时 `docker compose up -d` **不会去拉
> `minio/minio` 镜像**。确实要用 S3 兼容对象存储时才执行
> `docker compose --profile object-storage up -d`（`compose.yaml` 里该服务已加
> `profiles: ["object-storage"]`），并在 `.env` 里填好 `OBJECT_STORAGE_*`。
> 早前版本没有这个 profile，容器每次 `up` 都会被拉起；国内网络下拉取失败会让整个 `up` 直接报错退出。

### 启动流程

```bash
# 根目录 .env 已随仓库提交并填好 6 个强制项，正常情况不需要再动它。
# ⚠️ 不要再用 `cp .env.example .env` 覆盖：示例文件里这些键是空值，
#    覆盖后会立刻回到 `required variable ... is missing a value` 而构建失败。
# 构建 nginx + backend 两个镜像；migrate / worker / beat 复用 backend 的镜像，不重复构建
docker compose build
docker compose run --rm migrate      # 迁移作为独立发布步骤，单独执行
docker compose up -d
docker compose ps
# 访问入口：HTTP_PORT 是 80 时用 http://localhost/，否则要带端口（如 http://localhost:8080/）
curl -f http://localhost/healthz
```

> `.env` 必填项（缺任一项 Compose 直接拒绝启动）：`DJANGO_SECRET_KEY`、`DJANGO_ALLOWED_HOSTS`、
> `DJANGO_CSRF_TRUSTED_ORIGINS`、`DB_PASSWORD`、`MYSQL_ROOT_PASSWORD`、`OBJECT_STORAGE_SECRET_KEY`；
> 空库首次安装还要提供 `YISHANG_ADMIN_PASSWORD`（见下一节）。

> **根目录 `.env` 已随仓库提交**（含随机生成的口令，与 `backend/.env` 同属「单人私有仓库」的取舍，
> 见 `docs/assumptions.md` 第 47 条），所以 clone 之后可以直接 `docker compose build`。
> **换环境时必须检查这几项**：`DJANGO_ALLOWED_HOSTS`、`DJANGO_CSRF_TRUSTED_ORIGINS`
> （要与实际访问方式完全一致，如内网 IP）、`HTTP_PORT`、
> 以及下面两个 HTTPS/Cookie 开关。
>
> 早前 `.env.example` 里**漏了 `MYSQL_ROOT_PASSWORD`**，直接复制会得到
> `required variable MYSQL_ROOT_PASSWORD is missing a value` 并使 `docker compose build` 直接失败
> （compose 在解析阶段就会校验这些变量，所以连构建都过不去）。该变量已在示例中补上。

> **构建期网络：国内环境必看。** `docker compose build` 会在容器里跑 `apt-get`，默认走官方源
> `deb.debian.org`；实测国内直连会间歇性返回 `502 Bad Gateway`，报错形如
> `E: The repository 'http://deb.debian.org/debian trixie-updates InRelease' is no longer signed.`，
> 最后以 `target backend: failed to solve ... exit code: 100` 结束（连构建都过不去）。
> 处理：在根目录 `.env` 里把 `APT_MIRROR` 改成国内镜像（**本仓库当前值 `mirrors.aliyun.com`**，
> 也可用 `mirrors.tuna.tsinghua.edu.cn` / `mirrors.ustc.edu.cn`），再重新 `docker compose build`。
> 换到别的网络后如果直连正常，把该值改回 `deb.debian.org` 即可。
> 同理，前端镜像构建里的 `npm ci` 若因网络失败，可在 `.env` 里设
> `NPM_REGISTRY=https://registry.npmmirror.com`（默认空 = npm 官方源，行为不变）。
>
> **镜像加速器同理。** 如果 Docker Desktop 里配了 `registry.docker-cn.com` 这类**已下线**的加速器，
> `docker compose up -d` 会把本地镜像 `yishang-platform-nginx:local` 也当成远端去拉，报
> `failed to resolve reference "docker.io/library/yishang-platform-nginx:local" ... EOF`。
> 该设置在 Docker Desktop → Settings → Docker Engine（配置文件见 `%APPDATA%\Docker\settings-store.json`），
> 仓库改不了，**必须由使用者删除该 mirror 后重试**。

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
# 1) 先只起数据库，并【等健康检查通过】再加数据（MySQL/Redis 不对宿主发布端口，只能经 compose 操作）
docker compose up -d --wait mysql      # --wait：等到 mysql 的 healthcheck 变成 healthy 才返回
docker compose ps mysql                # 必须看到 (healthy)；只显示 Up / Created 还不够

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
# 1) 起数据库，并等健康检查通过：显示 (healthy) 才算就绪
docker compose up -d --wait mysql
docker compose ps mysql

# 2) 拷进容器再导入（PowerShell 不支持 `<` 重定向，管道传中文有二次编码风险）
docker compose cp db\yishang_platform_2026-09-24.sql mysql:/tmp/snapshot.sql
docker compose exec mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot yishang_platform < /tmp/snapshot.sql'

# 3) 清掉临时文件，再起其余服务并收静态资源
docker compose exec mysql rm -f /tmp/snapshot.sql
docker compose up -d
docker compose exec backend python manage.py collectstatic --noinput
docker compose ps
```

> **先等 `(healthy)` 再导入，这一步不能省。** 实测在 `docker compose up -d mysql` 之后立刻导入会得到
> `ERROR 2002 (HY000): Can't connect to local MySQL server through socket '/var/run/mysqld/mysqld.sock' (2)`
> —— 容器虽然已经是 `Created` / `Up`，但 `mysqld` 还在初始化，socket 文件尚未创建，
> **与快照、口令、配置都无关**。用 `docker compose up -d --wait mysql`，或先 `docker compose ps mysql`
> 确认显示 `(healthy)` 再执行导入即可；已经报了 2002 也没关系，等健康后把导入那条命令重跑一次就行。

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
| `DJANGO_ALLOWED_HOSTS` | 必须是客户机**实际访问地址**，如 `192.168.1.50,localhost`（写 IP，不带端口） |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 带协议的完整来源，如 `http://192.168.1.50`；不一致会导致登录报 CSRF 失败 |
| `HTTP_PORT` | 前端对外端口，默认 `80`；被同一台机器上**其他 Docker 服务**占用时改成别的（如 `HTTP_PORT=8080`），改完 `docker compose up -d` 重建 nginx 容器才生效 |
| 定时任务 | 平台**没有内置调度器**，`ems_offline_check` / `iot_offline_check` 需用 Windows 计划任务或 Compose 的 `beat` 服务（见 §三之三、§三之四） |
| HTTPS / Cookie | 走 HTTPS：`DJANGO_SECURE_SSL_REDIRECT=true` + `DJANGO_COOKIE_SECURE=true`（默认值，推荐）。纯内网 HTTP（无证书）：两项都要设 `false`——只关 `DJANGO_SECURE_SSL_REDIRECT` 的话页面能打开，但浏览器不会在 HTTP 下回传会话 Cookie，**登录后会被立刻踢回登录页**（见 `docs/assumptions.md` 第 45 条） |
| `APT_MIRROR` | 构建后端镜像时的 Debian 软件源。国内网络直连 `deb.debian.org` 报 `502 Bad Gateway`、构建以 `exit code: 100` 失败时，改成 `mirrors.aliyun.com`（见 `docs/assumptions.md` 第 48 条） |
| `NPM_REGISTRY` | 前端镜像构建用的 npm 源；默认空 = npm 官方源，国内网络不稳时设 `https://registry.npmmirror.com` |
| Docker 镜像加速器 | Docker Desktop 里若配了 `registry.docker-cn.com` 等**已下线**的加速器必须删除，否则本地镜像 `yishang-platform-*:local` 会被当成远端拉取并报 `EOF`；**仓库无法代改** |
| 对象存储 | `object-storage`（MinIO）默认不启动，附件走本地卷；要用 S3 兼容存储才 `docker compose --profile object-storage up -d` |
| 端口与局域网 | 见下一小节「改端口 / 让局域网其他电脑访问」：`HTTP_PORT` / `HTTP_BIND` 与两项主机白名单必须一致 |

### 改端口 / 让局域网其他电脑访问 【未执行 ⚠️】

平台对外**只有一个端口**（Nginx；容器内固定 8080），宿主端口由 `.env` 的 `HTTP_PORT` 决定；
MySQL / Redis / MinIO **都不发布宿主端口**，不用为它们的端口冲突担心。

**一键配置（推荐）**：在仓库根目录执行，脚本会自动挑一个空闲端口、识别本机局域网 IP，
并把这 4 项写进 `.env`：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\docker_network.ps1               # 自动选空闲端口 + 自动识别本机 IP
powershell -ExecutionPolicy Bypass -File scripts\docker_network.ps1 -Port 18080   # 指定端口（被占用会直接报错）
powershell -ExecutionPolicy Bypass -File scripts\docker_network.ps1 -Ip 192.168.1.50
docker compose up -d      # 重建 nginx 容器，端口映射才会生效
```

| `.env` 项 | 作用 | 写错的后果 |
| --- | --- | --- |
| `HTTP_PORT` | 宿主端口（`HTTP_PORT=8080` → 访问 `http://<IP>:8080/`） | 端口被占用时 `docker compose up -d` 报 `port is already allocated` |
| `HTTP_BIND` | `0.0.0.0`（默认）= 本机与局域网都能访问；`127.0.0.1` = 只有本机能访问 | 只能本机访问，或对外暴露过多 |
| `DJANGO_ALLOWED_HOSTS` | 必须含**本机局域网 IP（不含端口）** | 局域网访问报 `400 Bad Request (DisallowedHost)` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 必须含 `http://<本机IP>:<HTTP_PORT>` | 页面能打开，但**登录报 CSRF 失败** |

**手工改法**：直接编辑根目录 `.env` 的这 4 项 → `docker compose up -d`。

**Windows 防火墙**：首次发布端口时 Docker Desktop 会弹窗，选「允许访问」；若局域网电脑仍打不开，
用**管理员** PowerShell 放行（端口换成 `HTTP_PORT`）：

```powershell
New-NetFirewallRule -DisplayName "Yishang Platform HTTP" -Direction Inbound -Protocol TCP -LocalPort 8080 -Action Allow
```

**排查用**：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8080     # 有输出 = 该端口已被别的程序占用
curl.exe -f http://127.0.0.1:8080/healthz              # 本机自测，能返回即服务正常
```

> **改端口 / 换地址后登录报「CSRF 校验未通过」？** 两个原因，通常一起出现：
> ① `.env` 的 `DJANGO_CSRF_TRUSTED_ORIGINS` 没写全——浏览器地址栏里的那个地址必须**原样**在列表里
> （如用 `http://localhost:8080` 访问就要有这一条）；② 反向代理把 Host 里的端口丢了。
> 本仓库的 `deploy/nginx/nginx.conf` 已用 `$http_host`（保留端口），所以一般只需把 ① 写全；
> 注意 `nginx.conf` 是**打进镜像**的，改它之后要 `docker compose build nginx` 才生效。
>
> 局域网其他电脑用 `http://<本机IP>:<HTTP_PORT>/` 打开即可，**不需要装任何客户端**。
> 本机 IP 由路由器 DHCP 分配、换网络会变；变了就重跑一次上面的脚本。
> 仓库当前 `.env`：`HTTP_PORT=8080`、`HTTP_BIND=0.0.0.0`，本机局域网 IP 已写入白名单。

### 设计约束（已写入 `compose.yaml`）

- **同一后端镜像**承担 Web / Worker / Beat 三种角色，仅启动命令不同。
- **同一个镜像 tag 只允许一个 `build` 目标**：`backend` 负责构建 `yishang-platform-backend:local`，
  `migrate` / `worker` / `beat` 只声明 `image` 复用；若两个服务都写 `build`，buildx bake 会并发导出
  同名镜像并报 `failed to solve: image "docker.io/library/yishang-platform-backend:local": already exists`。
- **如果仍报同名镜像已存在**（例如手工改回了两个 `build` 块），按顺序试：
  ① 只构建这两个镜像：`docker compose build backend nginx`；
  ② 关掉 buildx bake，改用经典构建器：`$env:COMPOSE_BAKE='false'; docker compose build`；
  ③ 删掉旧 tag 再重来：`docker image rm yishang-platform-backend:local yishang-platform-nginx:local`。
- **反向代理必须透传带端口的 Host**（`proxy_set_header Host $http_host`）：nginx 的 `$host` 会丢掉端口，
  而浏览器发来的 `Origin` 带端口，Django 的 CSRF 同源校验会因此判为跨站，
  表现为「页面能打开，但登录报 `CSRF 校验未通过`」（见 `docs/progress.md` 第 47 节）。
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

**2026-09-24 项目方在本机（Windows + Docker Desktop）实际执行的记录**（由使用者执行，属真实执行结果）：

| 实测项 | 结果 |
| --- | --- |
| `docker compose build` | ❌ 失败：`runtime` 阶段 `apt-get update` 对 `deb.debian.org` 返回 `502 Bad Gateway`，`target backend: failed to solve ... exit code: 100` → 已改为 `APT_MIRROR` 可配置（本轮改动，**未复测**） |
| `docker compose up -d mysql` | ✅ 成功：`mysql:8.0` 拉取完成，容器 `Up (healthy)` |
| `docker compose cp db\...sql mysql:/tmp/snapshot.sql` | ✅ 成功 |
| 在 `(healthy)` 之前就 `docker compose exec mysql ... < /tmp/snapshot.sql` | ❌ `ERROR 2002 (HY000): Can't connect to local MySQL server through socket '/var/run/mysqld/mysqld.sock' (2)` → 已补「先等 `(healthy)`」步骤 |
| `docker compose up -d` | ❌ 失败：Docker Desktop 内配的加速器 `registry.docker-cn.com` 已下线，本地镜像 `yishang-platform-nginx:local` 被当远端拉取报 `EOF`；同时无谓拉取 `minio/minio:latest` 也失败 → 前者需使用者自行删除加速器，后者已改为默认不启动 |
| `collectstatic` | ⛔ 未执行：`service "backend" is not running`（因构建失败，容器未起） |
| `docker compose build`（修完 apt/npm 源后重跑） | ❌ 走到了 `exporting to image`（`backend` 310.0s / `nginx` 303.1s），但报 `target backend: failed to solve: image "docker.io/library/yishang-platform-backend:local": already exists` → `migrate` 与 `backend` 两个 build 目标导出同一个 tag，已让 `migrate` 只声明 `image` 复用（本轮改，**未复测**） |

因此**仍未验证**的是：去掉重复 build 目标后 `build` 能否成功、镜像能否启动、`migrate`、Nginx 配置、
`mysqlclient` 驱动、数据导入与「表数 = 154」的核对；端口映射与局域网访问同样未验证。

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
