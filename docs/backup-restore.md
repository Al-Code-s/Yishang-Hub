# 备份与恢复（docs/backup-restore.md）

> **状态：方案已完成，恢复演练未执行（阶段 7）。** 本文件描述目标方案与必须遵守的边界；
> 标注为「待演练」的步骤在本轮**没有实际执行**，不得写作通过。

## 一、备份对象

| 对象 | 方式 | 说明 |
| --- | --- | --- |
| MySQL 数据 | 定时逻辑备份（`mysqldump` / `mysqlsh`） | 业务事实的唯一来源 |
| 二进制日志 | 按 `binlog` 配置 | 支持时间点恢复（PITR），按恢复目标设定保留期 |
| 附件对象存储 | 存储侧版本化 + 跨区复制 | 附件默认私有 |
| 配置与密钥 | 独立密钥管理，**不进备份归档** | 备份不得包含明文生产密钥 |

## 二、关键指标（必须由项目方确认）

| 指标 | 含义 | 当前状态 |
| --- | --- | --- |
| RPO（可接受数据丢失时间） | 最长可容忍的数据丢失窗口 | **待项目方确认** |
| RTO（可接受恢复时长） | 从故障到恢复服务的时长 | **待项目方确认** |

未确认前不对外承诺具体恢复能力。

## 三、备份要求

- 备份**加密**并设置**访问控制**（备份文件含业务数据）。
- 明确**保留周期**（建议：日备保留 30 天，周备保留 12 周，月备保留 12 个月，按项目方要求调整）。
- 记录**备份状态**并纳入监控（任务书 16.3）。
- 对象存储备份与数据库备份**时间对齐**，便于一致性恢复。

## 四、恢复步骤

```text
1. 停止写入（停止应用与 Worker/Beat，避免恢复期间产生新数据）
2. 恢复数据库（全量备份 → 按需回放 binlog 到目标时间点）
3. 恢复附件对象存储
4. 核对【数据库引用】与【实际附件】的一致性：
   - 数据库中存在记录但附件缺失 → 记录缺失清单
   - 附件存在但数据库无记录 → 记录孤儿清单
5. 执行 Django 迁移到目标版本（如备份早于当前代码版本）
6. 启动应用，健康检查 + 关键业务抽查
7. 记录本次恢复的实际 RTO 与丢失数据区间
```

## 五、迁移与 DDL 的重要边界（任务书 5.7）

> **MySQL 部分 DDL 不能像业务事务一样完整回滚。**

- `ALTER TABLE` 等 DDL 在 MySQL 8 中虽然支持原子 DDL（单条语句失败可回滚），
  **但跨多条语句的迁移整体失败时，数据库不会自动回到迁移前状态**。
- 因此**不虚假保证「迁移失败后自动恢复」**：
  - 发布前**必须备份**；
  - 必须编写并演练**恢复步骤**；
  - 数据迁移必须**分批、可恢复**（可从中断点继续，而不是整体重来）。
- 大表变更需评估**锁表时间与执行时长**，必要时使用在线 DDL 或分阶段迁移。

## 六、一致性核对（必须执行）

数据库与附件恢复后，**必须核对引用一致性**：

- 附件表记录 → 对象存储文件是否存在；
- 对象存储文件 → 是否存在对应业务记录（孤儿文件清理需审计）；
- 库存类数据恢复后执行 `reconcile_inventory`（阶段 2 提供）核对余额与流水一致性；
- 能源汇总恢复后执行 `rebuild_energy_summary`（阶段 5 提供）重算汇总。

## 七、待演练清单（阶段 7）

| 编号 | 项目 | 状态 |
| --- | --- | --- |
| B-01 | 空库恢复演练（从备份恢复到可用） | 待演练 |
| B-02 | 已有数据升级 + 回滚验证 | 待演练 |
| B-03 | 附件与数据库引用一致性核对 | 待演练 |
| B-04 | 实际 RTO 测量与记录 | 待演练 |
| B-05 | 备份加密与访问控制验证 | 待演练 |

对应必测案例第 22 项「备份可以恢复」——**当前为未执行**。

## 八、本机数据在哪里（开发机）与换电脑迁移

> 本节面向**本地开发机**（Windows + 本机 MySQL / Redis）。生产备份与容灾见第一至七节。
> **已执行**：旧机导出与导出文件的结构校验（2026-09-23）。**未执行**：新机完整恢复演练（见 §七）。

### 8.1 数据分布（本机实测）

| 内容 | 位置 | 换机是否必须带走 |
| --- | --- | --- |
| 业务数据（唯一事实来源） | MySQL 库 `yishang_platform`；物理文件在 `\<MySQL 安装目录>\data\yishang_platform\`（本机约 20 MB、154 张表） | **必须**，用 `mysqldump` 导出 |
| 测试库 | `test_yishang_platform`（pytest 用，可自动重建） | 不需要 |
| 附件上传 | `backend/media/`（当前为空，说明还没上传过附件；将来有附件则必须一起拷） | 有则必须 |
| 配置与密钥 | `backend/.env`（DB 口令、`DJANGO_SECRET_KEY`、初始化口令） | **必须**（未纳入 Git） |
| 本地脚本与备份 | `.tmp/`（含 `mysqldump` 备份、本地口令记录） | 视需要 |
| 代码 | Git 仓库 | `git clone` 或整体复制 |
| Redis | 仅作缓存与队列（`redis://127.0.0.1:6379/0`） | 不需要，重建即可 |

> **不要直接拷贝 MySQL 的 `data\` 目录。** InnoDB 表空间与 MySQL 版本绑定，跨机直接拷贝容易起不来；
> 统一用逻辑备份（`mysqldump`）+ 导入。

### 8.2 旧机器：导出

```powershell
# 不加 --databases：备份里不含 CREATE DATABASE，导入时不会因应用账号没有建库权限而失败
& '<MySQL 安装目录>\bin\mysqldump.exe' -h 127.0.0.1 -P 3306 -u yishang_app '-p<口令>' `
    --single-transaction --default-character-set=utf8mb4 --routines --triggers `
    yishang_platform > yishang_platform.sql
```

- 备份文件含业务数据：**不要**提交 Git、不要放公开网盘。
- 同时把 `backend/.env` 一并带走（口令、`DJANGO_SECRET_KEY` 都在里面）。

### 8.3 新机器：装环境 → 建库 → 导入

1. 安装 MySQL 8（Windows 服务名默认 `MySQL80`，启动类型自动）、Redis、Python 3.12、Node.js 22。
2. 用 **root** 建库与账号（应用账号只有两个库的权限，没有建库权限，实测 `SHOW GRANTS` 已确认）：

```sql
CREATE DATABASE yishang_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'yishang_app'@'localhost' IDENTIFIED BY '<口令>';
GRANT ALL PRIVILEGES ON yishang_platform.* TO 'yishang_app'@'localhost';
GRANT ALL PRIVILEGES ON test_yishang_platform.* TO 'yishang_app'@'localhost';
FLUSH PRIVILEGES;
```

3. 导入：

```powershell
& '<MySQL 安装目录>\bin\mysql.exe' -h 127.0.0.1 -P 3306 -u yishang_app '-p<口令>' `
    --default-character-set=utf8mb4 yishang_platform < yishang_platform.sql
```

4. 代码与后端依赖（Windows 本地用 `pymysql`，生产/Linux 用 `mysqlclient`；测试还需要 dev 依赖）：

```powershell
git clone <仓库地址> ; cd Yishang-Hub\backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install ".[pymysql]"
```

5. 放回 `backend/.env`，然后按顺序确认（`migrate` 应显示无新迁移）：

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

6. 前端：

```powershell
cd frontend
npm install
npm run dev -- --port 5173
```

### 8.4 迁移后核对

- `factory.Company` 只有 1 行：`XJYS` / 新疆意尚智造科技有限公司；
- 表数量为 **154**，与源库一致；
- 抽查设备 / 能源 / 库存等表行数与源库一致（`SELECT COUNT(*)`）；
- 管理员账号与 `xj_*` 账号能登录，菜单与列表有数据；
- 有附件时核对 `core.attachment` 记录与 `backend/media/` 文件是否一一对应（见 §六）。

### 8.5 换机不必手工传文件（本仓库的取舍）

项目方 2026-09-24 确认：本仓库为**单人私有仓库**，开发库配置与数据快照直接随仓库走，
换电脑只需要 `git clone`，不必再手工拷贝任何文件。

| 内容 | 仓库内位置 | 说明 |
| --- | --- | --- |
| 开发库配置与口令 | `backend/.env`（**已入库**） | `.gitignore` 里加了 `!backend/.env` 例外；改动后按普通文件提交即可 |
| 开发库数据快照 | `db/yishang_platform_<日期>.sql`（**已入库**） | `mysqldump` 逻辑导出，154 张表 |

新机器落地顺序：`git clone` → 用 root 建库建账号（§8.3 第 2 步）→ 导入 `db/` 下快照 →
建 venv 装依赖 → `backend/.env` 已在仓库里 → `manage.py migrate`（应显示无新迁移）→
`manage.py check` → 起服务 → `cd frontend && npm install && npm run dev`。

**刷新快照**（数据有变化时，导出成新日期文件并提交）：

```powershell
& '<MySQL 安装目录>\bin\mysqldump.exe' -h 127.0.0.1 -P 3306 -u yishang_app '-p<口令>' `
    --single-transaction --default-character-set=utf8mb4 --routines --triggers `
    yishang_platform > db\yishang_platform_<日期>.sql
```

**两条警告：**

- `db/` 下的是**开发库快照，不是生产备份**：没有加密、没有保留策略、也没有恢复演练记录，
  生产备份一律按本文第一至七节执行。
- 快照**有时效性**：导入前先 `manage.py migrate` 对齐结构；若快照比代码旧，以代码迁移为准，
  不要为了省事把旧快照直接灌进新结构。
