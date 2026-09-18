# 项目使用说明（docs/user-guide.md）

> **本文档面向「使用者与实施人员」**：怎么把平台跑起来、用哪个账号登录、每个菜单能做什么、
> 怎么完整走通一条业务链、出错怎么排查，以及**代码更新后本文档必须同步修改的规则**。
>
> 与其它文档的分工：`README.md` 是项目入口概览；`docs/deployment.md` 是部署与发布；
> `docs/progress.md` 是每轮实施记录；**本文档是「怎么用」的操作手册**。
>
> **最后与代码核对：2026-09-18（对应阶段 3 第二步 MRP 完成后的代码）**。
> 文档与代码不一致时，**以代码为准**，并立即按 §十一 的规则同步本文档。

## 一、这份文档怎么用

| 你是 | 建议阅读顺序 |
| --- | --- |
| 第一次接触项目，想跑起来看看 | §三 环境准备与启动 → §四 账号与权限 → §七 跟着做一遍 |
| 想知道某个菜单是干什么的 | §五 界面导航与通用操作 → §六 按模块操作指南 |
| 想知道现在哪些功能能用、哪些不能用 | §二 平台能力边界 |
| 报错了要定位 | §九 常见问题与错误码 |
| 开发人员，改了代码 | §十一 文档与代码同步规则（**必读**） |
| 想把这份说明直接发给客户 | §11.7 网页版使用说明（单文件 HTML，可直接打开或发送） |

## 二、平台能力边界

> 任务书要求「不创建大量空壳模块冒充完成」。**未实施的模块不出现在左侧菜单里，也没有可访问路由**，
> 因此你在界面上看不到 MES、QMS、设备、能源、EHS、终端安全等模块是正常的、刻意的。

### 2.1 已经可以用的（截至最后核对日期）

| 模块 | 能做什么 | 入口 |
| --- | --- | --- |
| 登录与权限 | 会话登录、CSRF、退出、改密、角色/权限点/菜单/数据范围、登录限流与失败锁定 | 「系统管理」 |
| 组织与工厂 | 公司、部门（树）、工厂、车间、线体、工位、员工、班组、班次 | 「工厂与排班」 |
| 服饰主数据 | 物料分类、物料（含面料属性）、款式、颜色、尺码、SKU、计量单位与换算、标识分型 | 「基础资料」 |
| 仓储基础 | 仓库、库区、储位（含仓储树） | 「仓储管理 → 仓库与储位」 |
| 统一库存服务 | 库存余额（实存/冻结/占用/可用）、只追加流水、库存单据（收货/出库/同仓移库/调整/质量）、过账与冲销、质量放行、占用与释放、幂等与并发安全 | 「仓储管理」 |
| 客户与供应商 | 客户档案与联系人；供应商档案、联系人、资质与有效期 | 「客户管理」「供应商管理」 |
| 采购 | 采购申请（常规/计划/紧急）→ 审批 → 转采购订单 → 到货收货 → 待检库存 → 来料检验放行 | 「采购管理」 |
| 销售 | 销售订单 → 审批 → 库存占用 → 发货出库 → 销售退货 → 检验判定 → 订单链路查询 | 「销售管理」 |
| 计划 / 工程数据 | BOM（款式通用与 SKU 差异版本、替代料、含损耗用量、生效区间、审批后冻结、只能派生新版本）与工艺路线（工序、标准工时、设备要求、工序质检点） | 「计划管理」 |
| MRP | 运行 MRP（按日/按周分段净算）→ 需求行 / 供给行 / 缺料建议 → 采购建议转草稿采购申请、建议取消、运行归档 | 「计划管理 → MRP 运算 / 缺料与建议」 |
| 审批与治理 | 审批模板与实例、顺序多级、条件路由、模板快照、审批轨迹、待办/我的申请 | 「审批中心」 |
| 内部协同 | Outbox 事件状态、失败与人工重放、单据关系 | 「内部协同」 |
| 通知与审计 | 我的通知；审计与登录日志（只读） | 「系统管理」 |
| 工作台 | 指标看板与快捷入口 | 「工作台」 |

### 2.2 还没有的（不要按"能用"去承诺）

- **MES**：工单、线体排产、裁剪任务、派工、报工、在制转移、返工报废、完工入库。
- **QMS**：检验项目/标准/版本、首件/过程/成品/出货检验、不合格处置与质量知识库。
  → 目前采购的「来料检验」是**人工录入判定**，不是自动检测设备结果。
- **设备（EAM/CMMS）**、**能源（EMS）与采集**、**EHS**、**厂内物流**、**工业终端安全**。
- 销售计划与预测、供应商寻源/报价/评分、应收应付与收付款登记、跨仓调拨在途、盘点范围冻结、库存成本。
- **MRP 未包含**：采购提前期与批量规则、安全库存、在制供给（依赖 MES）、替代料展开、
  生产计划/预测等其它需求来源、生产建议转工单（当前明确拒绝）、MRP 导出与定时重算。
- 审批通过 ≠ 库存变动；**转采购申请 ≠ 采购承诺**（MRP 转单只生成**草稿**采购申请）。

### 2.3 当前规模（实测）

权限点 **173** 个 / 菜单 **56** 项（45 个业务页面 + 11 个目录）/ 数据模型 **86** 个 /
数据库表 **92** 张 / 已提交迁移 **19** 个 / 前端视图 **48** 个 `.vue` / 内置角色 **16** 个。

## 三、环境准备与启动

### 3.1 前置依赖

| 组件 | 版本要求 | 本项目实测 |
| --- | --- | --- |
| Python | 3.12 | 3.12 |
| Node.js | ≥ 20.19 | 22.17.1 / npm 10.9.2 |
| MySQL | 8（规范要求 8.4 LTS） | 8.0.17（**版本偏差已在 `docs/assumptions.md` 记录**） |
| Redis | 与 Django/Celery 兼容即可 | 3.2.100（**版本偏差同上**） |

Windows 本地开发若没有 C 编译工具链，用 `DB_DRIVER=pymysql`；Docker/Linux 用 `mysqlclient`。

### 3.2 环境变量

```powershell
Copy-Item .env.example backend\.env   # 再按需修改；不要提交真实密码
```

必须设置（见 `.env.example` 全部项）：

```text
DJANGO_ENV=development
DJANGO_SECRET_KEY=<随机值>
DB_DRIVER=pymysql            # Windows 本地；Docker/Linux 用 mysqlclient
DB_NAME=yishang_platform
DB_USER=yishang_app          # 应用账号，不要用 root
DB_PASSWORD=<应用账号密码>
REDIS_URL=redis://127.0.0.1:6379/0
YISHANG_ADMIN_PASSWORD=<初始管理员口令>
YISHANG_DEMO_PASSWORD=<演示账号口令>
```

**口令来源约定**：`bootstrap_system` 读 `YISHANG_ADMIN_PASSWORD`，`seed_demo` 读
`YISHANG_DEMO_PASSWORD`；**未设置时随机生成并打印一次**，代码里没有任何硬编码默认口令。
生产环境必须通过安全初始化流程注入，且 `seed_demo` 在 `DJANGO_ENV=production` 时**直接拒绝执行**。

### 3.3 首次启动（按顺序执行）

```powershell
# 1) 后端：迁移 → 系统初始化 → 演示数据 → 启动
cd E:\github\Yishang-Hub\backend
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py bootstrap_system    # 权限点/菜单/编码规则/角色/管理员
.\.venv\Scripts\python.exe manage.py seed_demo           # 仅开发环境；可重复执行
.\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000

# 2) 前端（另开一个终端）
cd E:\github\Yishang-Hub\frontend
npm install
$env:VITE_DEV_BACKEND='http://127.0.0.1:8000'
npm run dev
```

初始化命令的常用开关：

| 命令 | 说明 |
| --- | --- |
| `manage.py bootstrap_system --dry-run` | 只展示将执行的动作，不写库 |
| `manage.py bootstrap_system --admin-username X --admin-password Y` | 指定管理员账号与口令 |
| `manage.py bootstrap_system --skip-admin` | 不创建/更新管理员账号 |
| `manage.py bootstrap_system --reset-admin-password` | 重置管理员口令（需提供口令来源，不随机覆盖） |
| `manage.py seed_demo --skip-users` | 造演示业务数据但不建演示账号 |
| `manage.py seed_demo --yes` | 在非 development/test 环境确认写入（生产仍被硬拒） |

两个命令都**幂等**：重复执行只同步固定字段，不重复建记录，也不重置已有账号口令。

### 3.4 日常启动与停止

也可以用仓库自带的脚本（会自动做 check + 迁移，前端会自动装依赖）：

```powershell
cd E:\github\Yishang-Hub
powershell -ExecutionPolicy Bypass -File scripts\dev_backend.ps1        # 默认 8000
powershell -ExecutionPolicy Bypass -File scripts\dev_frontend.ps1       # 默认 5173
# 换端口： scripts\dev_backend.ps1 -Port 8001 / scripts\dev_frontend.ps1 -Port 5174
```

- 启动：只需 3.3 的最后两条（`runserver` 与 `npm run dev`）；无需重复迁移与初始化。
- 停止：在各自终端按 `Ctrl + C`。
- 改了后端代码：Django 开发服务器会自动重载；**改了模型**要重新
  `manage.py makemigrations <app>` + `migrate`。
- **不要用 `runserver` 对外提供生产服务**（生产用 Gunicorn + Nginx，见 `docs/deployment.md`）。

### 3.5 访问地址

| 地址 | 用途 |
| --- | --- |
| http://127.0.0.1:5173/ | 前端界面（日常使用入口） |
| http://127.0.0.1:5173/guide.html | **项目使用说明（网页版）**，可直接给客户看；也可在系统内点顶部「使用说明」打开 |
| http://127.0.0.1:8000/api/v1/ | 后端 API 根 |
| http://127.0.0.1:8000/api/v1/docs/ | OpenAPI（Swagger UI） |
| http://127.0.0.1:8000/api/v1/schema/ | OpenAPI 原始 schema |
| http://127.0.0.1:8000/healthz | 存活检查 |
| http://127.0.0.1:8000/readyz | 就绪检查（数据库 + 缓存） |
| http://127.0.0.1:8000/admin/ | Django Admin（运维兜底，**不是业务前端**） |

### 3.6 数据库在哪里、怎么连接

- **业务数据存在 MySQL 里，不存在项目目录里的文件数据库**。项目目录下没有 `.sqlite3`、
  也没有 `.mdf`/`.ibd` 之类的数据文件；`DB_*` 环境变量指向的就是数据实际所在地。
- 本机 MySQL 默认数据目录在 `C:\ProgramData\MySQL\MySQL Server 8.0\Data\`
  （该目录属系统目录，日常不要手动改动里面的文件）。
- 库的划分：

| 库名 | 作用 |
| --- | --- |
| `yishang_platform` | **开发/运行库**，业务数据都在这里 |
| `test_yishang_platform` | **测试库**，`pytest` 自动创建/复用（`--reuse-db`），跑测试会**重建**它 |
| `information_schema` | MySQL 自带的**元数据视图**（表结构、权限等），只读，不是业务数据 |

- 连接方式（本地）：

```powershell
# 用应用账号连（与后端同一个账号，权限更小，更接近真实情况）
mysql -h 127.0.0.1 -P 3306 -u yishang_app -p yishang_platform
# 或用图形化工具（Navicat / DBeaver / MySQL Workbench）填同样的主机、端口、账号、库名
```

- 连接串等价表示：`mysql://yishang_app:<密码>@127.0.0.1:3306/yishang_platform?charset=utf8mb4`。
- **不要用 root 连接应用**；生产环境数据库端口不对外发布（见 `docs/deployment.md` §四）。
- 备份与恢复步骤见 `docs/backup-restore.md`（当前**未做过真实恢复演练**）。

### 3.7 上传文件与日志

- 开发环境下附件默认落在本地 `MEDIA_ROOT`（项目内 `backend/media/`），配置了 S3 兼容对象存储时改为远端；生产要求「上传文件与代码分离」。
- 日志按 `LOG_LEVEL` 输出到控制台；生产要求日志轮转与 `request_id` 贯穿（见 `docs/deployment.md` §五）。

## 四、账号与权限

### 4.1 管理员账号

| 项 | 值 |
| --- | --- |
| 账号 | `admin`（默认；可用 `bootstrap_system --admin-username` 改） |
| 口令 | `backend/.env` 的 `YISHANG_ADMIN_PASSWORD`；未设置时命令会**随机生成并打印一次** |
| 标识 | `is_superuser=true` → **不受数据范围限制**，拥有全部权限 |
| 归属公司 | **为空**（超级管理员不隶属任何公司） |

> ⚠️ 因为超管没有归属公司，**新建需要公司维度的数据时要显式选择「公司」**
> （例如「MRP 运算」页面的公司下拉框）；服务端在缺少公司时返回 `400 COMPANY_REQUIRED`，
> 这是刻意设计，不是缺陷。用有归属公司的业务账号则无需选择。

使用 `--reset-admin-password` 重置口令时，命令会把 `must_change_password` 置为真，
下次登录后按提示修改即可；**正常重复执行 `bootstrap_system` 不会改动已有口令**。

### 4.2 演示账号（`seed_demo` 创建，仅开发环境）

口令统一来自 `backend/.env` 的 `YISHANG_DEMO_PASSWORD`（未设置则随机生成并打印一次）。

| 账号 | 姓名 | 角色 | 适合用来验证 |
| --- | --- | --- | --- |
| `admin` | 系统管理员 | 超级管理员 | 全部功能、系统管理 |
| `md_admin` | 主数据管理员 | `masterdata_admin` | 基础资料维护 |
| `fac_admin` | 工厂管理员 | `factory_admin` | 组织、工厂、排班 |
| `wh_admin` | 仓储主管 | `warehouse_admin` | 仓库、库存单据与过账 |
| `prc_admin` | 采购专员 | `procurement_admin` | 采购申请/订单/收货（含 MRP 缺料只读） |
| `qc_inspect` | 来料检验员 | `quality_inspector` | 来料检验放行 |
| `dept_mgr` | 生产计划主管 | `approver` + `demo_dept_manager` | 审批（部门主管节点）与 BOM/工艺/MRP |
| `gm` | 总经理 | `approver` + `demo_gm` | 金额较大单据的第二级审批 |
| `finance` | 财务复核 | `approver` + `demo_finance` | 财务节点审批 |
| `qc01` | 质量工程师 | `viewer` | 只读浏览与"无写权限"验证 |
| `sales01` | 销售主管 | `viewer` | 只读浏览销售单据 |

### 4.3 内置角色与权限点数量（实测）

| 角色编码 | 名称 | 权限点数 | 说明 |
| --- | --- | --- | --- |
| `super_admin` | 超级管理员 | 173 | 全部权限 |
| `platform_admin` | 平台管理员 | 65 | 用户/角色/菜单/字典/编码规则/审计/协同 |
| `viewer` | 只读用户 | 51 | 各模块只读 |
| `masterdata_admin` | 主数据管理员 | 38 | 物料、款式、SKU、单位、标识 |
| `factory_admin` | 工厂与组织管理员 | 34 | 公司/部门/工厂/车间/线体/员工/班次 |
| `sales_admin` | 销售管理员 | 27 | 销售订单/发货/退货 + 库存查看 |
| `planning_admin` | 计划管理员 | 27 | BOM/工艺/MRP + 采购申请查看与新建（转单必需） |
| `procurement_admin` | 采购管理员 | 25 | 采购申请/订单/收货/检验 + MRP 缺料只读 |
| `warehouse_admin` | 仓储管理员 | 24 | 仓库/库存/库存单据 |
| `srm_admin` | 供应商管理员 | 16 | 供应商档案/联系人/资质 |
| `crm_admin` | 客户管理员 | 13 | 客户档案/联系人 |
| `quality_inspector` | 质检员 | 11 | 来料检验判定 |
| `approver` | 审批人 | 5 | 待办与审批动作 |
| `demo_dept_manager` / `demo_gm` / `demo_finance` | 演示审批角色 | 5 / 6 / 5 | 仅供演示审批模板使用，限定公司 |

### 4.4 权限模型：四层

| 层 | 作用 | 表现 |
| --- | --- | --- |
| 菜单权限 | 决定左侧是否出现该页面 | 无权限 → **菜单不显示、路由也不注册**（不是"点进去报错"） |
| 操作权限 | 决定按钮/动作能否执行 | 例如没有 `planning.mrp.run` 时"运行 MRP"会被后端拒绝 |
| 接口权限 | 每个 API 独立校验 | 前端隐藏按钮**不等于**后端放行；后端始终重新校验 |
| 数据范围 | 限制"能看哪些数据" | 公司 / 指定工厂 / 指定部门 / 指定仓库 / 本人 / 自定义范围 |

- 多角色合并规则：操作权限取**并集**，数据范围取**最宽**一档，但**始终先受公司边界限制**；
  单一维度范围配置不完整时按**最小范围**处理（fail-closed）。详见 `docs/permission-matrix.md` §五。
- 超级管理员不受数据范围限制；`factory_id` 等参数由前端传入时**不会**被信任，后端会重新校验。

### 4.5 新增用户 / 调整权限的步骤

1. 「系统管理 → 用户管理」→ 新建用户（用户名、姓名、所属公司/部门、初始口令）。
2. 「系统管理 → 角色权限」→ 选角色 → 勾选权限点；如需限制范围，配置「数据范围」。
3. 把角色分配给用户（用户管理里的角色多选）。
4. 让该用户重新登录（权限与菜单在登录/会话刷新时下发）。
5. 验证：用该账号登录，确认**菜单可见性**与**按钮可用性**都符合预期，且越权调用被拒。

> 用户与员工档案是分开的：用户负责登录与权限，员工负责组织/岗位/排班，两者可一对一关联，
> 但不是所有员工都需要登录账号。

## 五、界面导航与通用操作

### 5.1 界面结构

- **左侧导航**：一级是**目录**（工作台、基础资料、工厂与排班、客户管理、销售管理、供应商管理、
  采购管理、计划管理、仓储管理、审批中心、内部协同、系统管理），二级是**具体页面**；
  一级与二级在样式上有明显层级区分（缩进、字号、分组底色）。
- **顶部工具栏**：折叠侧边栏、面包屑、**使用说明**、通知/待办入口、个人中心
  （个人中心下拉里还有「使用说明」与「接口文档」）。
- **窄屏自适应**：窗口宽度 ≤1200px 时侧边栏自动折叠（手动偏好优先），表格在容器内横向滚动。
- 菜单由**后端按当前用户权限下发**；没有权限的页面不会出现在菜单里，也没有对应路由。

### 5.2 通用交互约定

| 能力 | 怎么用 |
| --- | --- |
| 查询 / 分页 / 排序 | 列表页顶部筛选栏；分页有**最大页大小限制**（`YISHANG_PAGE_SIZE_MAX=200`）；排序字段是白名单 |
| 新增 / 编辑 | 抽屉或对话框表单；提交前做字段校验，服务端再次校验 |
| 启停 | 主数据被使用后**停用**而不是删除（列表页「启用/停用」按钮） |
| 详情 | 多数列表提供详情抽屉，含关联单据、审批轨迹、操作历史 |
| 审批 | 单据「提交」后进入「审批中心 → 我的待办」；支持通过/驳回/撤回与审批意见 |
| 附件 | 上传前校验类型/大小/扩展名与**真实内容**（魔数），下载走**权限校验**，不能猜地址绕过 |
| 导入导出 | 上传 → 校验 → 错误预览（**逐行错误**）→ 确认导入；Excel 导出为大任务时走后台 |
| 状态标签 | 单据状态用彩色标签展示（草稿/审批中/已批准/已发货/已转单…） |
| 枚举 / 状态显示 | 列表与详情**优先显示中文**（后端返回的 `<field>_display`，如「成品仓」「职能部门」「面积」）；接口筛选与写入仍用英文键（如 `?warehouse_type=finished`），不要把中文当查询参数 |
| 防重复提交 | 提交按钮有加载态；库存过账、扫码报工、设备上报等支持**幂等键**，重复提交不会产生第二笔业务 |
| 未保存提示 | 离开有改动的表单时会提示确认 |
| 空 / 加载 / 异常 | 列表有空状态、加载态与错误提示（含 `request_id`，便于对日志） |

### 5.3 菜单清单（共 56 项：45 个页面 + 11 个目录）

| 一级目录 | 二级页面 | 路由 | 所需权限（查看） |
| --- | --- | --- | --- |
| （工作台） | 工作台 | `/workspace` | `analytics.dashboard.view` |
| 基础资料 | 物料档案 / 物料分类 / 款式档案 / SKU 档案 / 颜色与尺码 / 计量单位 | `/masterdata/materials`、`/material-categories`、`/styles`、`/skus`、`/color-size`、`/uoms` | `masterdata.*.view` |
| 工厂与排班 | 公司 / 部门 / 工厂 / 车间与线体 / 员工档案 / 班组 / 班次 | `/factory/companies`、`/departments`、`/factories`、`/workshops`、`/employees`、`/teams`、`/shifts` | `factory.*.view` |
| 客户管理 | 客户档案 / 客户联系人 | `/crm/customers`、`/crm/customer-contacts` | `crm.customer.view`、`crm.customer_contact.view` |
| 销售管理 | 销售订单 / 销售发货 / 销售退货 | `/sales/orders`、`/sales/shipments`、`/sales/returns` | `sales.*.view` |
| 供应商管理 | 供应商档案 / 联系人 / 资质 | `/srm/suppliers`、`/srm/supplier-contacts`、`/srm/supplier-qualifications` | `srm.*.view` |
| 采购管理 | 采购申请 / 采购订单 / 采购收货 | `/procurement/requisitions`、`/orders`、`/receipts` | `procurement.*.view` |
| 计划管理 | 物料清单（BOM）/ 工艺路线 / MRP 运算 / 缺料与建议 | `/planning/boms`、`/routings`、`/mrp-runs`、`/mrp-suggestions` | `planning.*.view` |
| 仓储管理 | 仓库与储位 / 库存余额 / 库存流水 / 库存单据 | `/wms/warehouses`、`/inventory-balances`、`/inventory-transactions`、`/inventory-documents` | `wms.*.view` |
| 审批中心 | 我的待办 / 我的申请 / 审批模板 | `/workflow/todo`、`/my-requests`、`/templates` | `workflow.instance.view`、`workflow.template.view` |
| 内部协同 | 事件与协同 | `/integration/outbox` | `integration.outbox.view` |
| 系统管理 | 用户管理 / 角色权限 / 权限与菜单 / 数据字典 / 编码规则 / 审计与登录日志 / 我的通知 / 实施进度 | `/system/users`、`/roles`、`/permissions`、`/dictionaries`、`/code-rules`、`/audit-logs`、`/notifications`、`/progress` | `identity.*.view`、`core.*.view` |

> 完整的权限编码清单（173 条）与菜单树以 `docs/permission-matrix.md` 为准（该文件由
> `apps/identity/permissions_registry.py` 生成）。

## 六、按模块操作指南

> 每个模块都遵循同一套约定：**列表页 → 新建/详情 → 提交 → 审批 → 后续动作**。
> 关键规则在服务端执行，前端只是入口。

### 6.1 基础资料（物料 / 款式 / 颜色 / 尺码 / SKU / 单位）

1. 先建**物料分类**（面料 / 辅料 / 半成品 / 成品 / 包装物 / 备品备件 / 消耗品）。
2. 建**计量单位**与换算规则（如 米 ↔ 公斤、打 ↔ 件）；**面料"米"与"公斤"不无条件换算**，
   若因卷而异，按实际计量值与该卷换算依据保存。
3. 建**物料**：编码、名称、规格、基本单位、采购/销售辅助单位、是否批次管理、安全库存、
   采购价与参考成本、启停状态；面料物料另填成分、幅宽、克重、色号等。
4. 建**颜色**与**尺码**，再建**款式（SPU）**，最后按「款式 + 颜色 + 尺码」生成 **SKU**。
   成品 SKU 与库存物料是**一对一**的，不存在两套库存编码。
5. **标识分型**要区分清楚：SKU 条码（识别物料种类）、批次码、卷号、箱码、RFID EPC、载具码
   ——它们不能混用一个字段。

### 6.2 工厂与排班

- 公司 → 部门（树形）→ 工厂 → 车间 → 线体 → 工位；员工、班组、班次、排班日历。
- 已使用的组织**只能停用不能删除**；层级关系不合法会被拒绝。
- 班次支持跨夜、休息、节假日与调班；排班展开为人员执行记录时会**保留成员快照**。

### 6.3 仓储与库存

| 页面 | 能做什么 | 关键规则 |
| --- | --- | --- |
| 仓库与储位 | 仓库 → 库区 → 储位（含仓储树） | 储位必须属于同一仓库；编码唯一 |
| 库存余额 | 查看每个维度（公司+物料/SKU+仓库+储位+批次/卷号+质量状态）的 **实存 / 冻结 / 占用 / 可用** | 可用量 = 实存 − 冻结 − 占用；**默认禁止负库存** |
| 库存流水 | 只追加的账实记录 | **不能修改或删除**（模型层直接拒绝） |
| 库存单据 | 收货 / 出库 / 同仓移库 / 调整 / 质量 五类单据；草稿 → 过账 → （必要时）冲销 | 过账才改余额并写流水；**冲销不能忽略下游已消耗事实**，不满足会拒绝并提示走退货/更正 |

- 所有库存变更都必须经过**统一库存服务**，业务模块（采购/销售/MRP）不允许直接改余额。
- 质量状态：待检（quarantine）/ 合格（qualified）/ 不合格（rejected）；**待检与不合格库存不能领用或销售**。
- 过账支持**幂等键**：同一键重复提交只生效一次；同键但内容不同会被拒绝。

### 6.4 采购

```text
采购申请(draft) → 提交 → 审批 → approved → 转采购订单(draft) → 提交 → 审批 → approved
   → 收货单(draft) → 过账 → 库存进入「待检」 → 来料检验(合格/不合格) → 合格库存
```

- **不允许超收**：可收上限 = 订单行数量 − 已收 − 草稿占用；订单状态随收货推进
  `approved → partially_received → received`，未收完可「关闭」。
- **实物到货、库存记账、质量放行是三件事**：到货 ≠ 可入库，入库 ≠ 可放行。
- 来料检验目前是**人工录入判定**（未接入检测设备），判定人、结论、说明与依据单据一并留痕。
- 供应商被停用后不能建正常采购订单；例外需要显式授权。

### 6.5 销售

```text
销售订单(draft) → 提交 → 审批 → approved → 库存占用(reserve)
   → 发货单(draft) → 过账 → 合格库存出库 → 订单行已发数量
   → 销售退货(draft) → 过账 → 库存进入「待检」 → 检验判定 → 合格 / 不合格
```

- **必须先占用才能发货**（未占用直接发货返回 `RESERVATION_REQUIRED`），且不能挪用其他订单的占用。
- 发货上限 = 订单行数量 − 已发货；可退数量 = 已发货 − 已退货，超出返回 `OVER_RETURN`。
- 退货行未填储位/批次/卷号时，**继承原发货单据的维度**并写回退货行，保证批次追溯不断链。
- 订单详情提供**链路查询**：从订单查看关联的占用、发货、退货与库存单据。
- 收款登记不等于完整财务记账（应收/收付款属后续增量）。

### 6.6 计划：BOM 与工艺路线

- **BOM**：一个「款式 + SKU 范围」可以有多个版本，但同一时间**只有一个已审核版本生效**；
  审核新版本时旧版本自动转「已作废」。明细含标准用量、损耗率（后端算出**含损耗用量**）、
  替代料（必须指向同一 BOM 的正常用料行）、使用部位、是否关键用料。
- **工艺路线**：工序顺序、工作中心/线体、设备要求、标准工时、**是否工序质检点**；
  新建时默认给出「裁剪 → 缝制 → 整烫 → 检验 → 包装」。
- 改动方式：**只能「派生新版本」**，已审核版本不可就地修改（工单引用的内容必须不变）；
  作废需填写原因。
- 接口 `/snapshot/` 输出**不可变快照**，供后续 MES 工单下达时固化。

### 6.7 MRP（计划管理 → MRP 运算 / 缺料与建议）

**操作顺序**

1. 「MRP 运算」→ 选公司（超管必须选）→ 填需求区间（默认今天起 **90 天**）→ 选按日/按周 →
   可选限定仓库 → 「运行 MRP」。系统**同步计算**并立刻返回结果与摘要。
2. 打开该运行的详情，看三个页签：**需求行**（含来源路径与分段）、**供给行**（可用库存 / 采购在途）、
   **缺料建议**。
3. 「缺料与建议」→ 对**采购建议**点「转采购申请」（填需求日期）→ 生成**草稿**采购申请并显示单号；
   对**生产建议**点转单会被明确拒绝（MES 未实现）。
4. 不需要的建议可以「取消」（**必填原因**）；历史运行可以「归档」（归档后其建议不能再转单）。

**口径（很重要）**

| 项 | 当前口径 |
| --- | --- |
| 需求来源 | **只有销售订单**（已批准、未发货的剩余数量） |
| 供给 | **可用库存**（实存 − 冻结 − 占用，且只认**合格**质量状态）+ **采购未收货在途** |
| 在制供给 | **恒为 0**（MES 未实现，刻意不伪造） |
| 展开用量 | 取 BOM 的**含损耗用量**；只展正常用料行，**替代料不参与** |
| 批量规则 | **lot-for-lot**（净需求多少建议多少），无提前期、无安全库存缓冲 |
| 净算方式 | 低层码分层，**同一物料只净算一次**；父件按**净需求**展开子件 |
| 生产建议 | **不生成工单**，返回 `PRODUCTION_ORDER_NOT_IMPLEMENTED` |
| 转单结果 | 只生成**草稿**采购申请（仍走采购审批），并写单据关联 |

**运行结果示例（开发库真实数据）**：历史运行 `MRP202609180004` 的摘要为
`item_count=7 / level_count=2 / bucket_count=3 / demand_quantity=1422.300000 /
supply_quantity=1866.000000 / suggestion_count=5`（1 条生产建议 + 4 条采购建议），
其中 `SO-MRP-0001`（成品 300 件）展开出 5 条子件需求。

### 6.8 审批中心

- 「我的待办」处理需要自己审批的节点；「我的申请」看自己提交的单据与进度；「审批模板」维护流程。
- 模板支持**顺序多级**与**条件路由**（按金额区间、部门匹配审批人）；实例保存**模板版本快照**，
  模板后续修改不影响在途单据。
- 动作：提交 / 通过 / 驳回（必填意见）/ 撤回；每次动作写审批轨迹（只写不改）。
- 可限制「申请人审批自己的单据」（模板开关 `allow_self_approval`）。
- **审批通过与库存过账是两个不同动作**，互不代表。

### 6.9 内部协同与系统管理

| 页面 | 用途 |
| --- | --- |
| 事件与协同 | 查看 Outbox 事件状态（pending/failed/dead）、失败原因与**人工重放**；单据关系追溯 |
| 用户管理 / 角色权限 / 权限与菜单 | 账号、角色、权限点、菜单与数据范围 |
| 数据字典 / 编码规则 | 枚举值与单号规则（支持编号预演） |
| 审计与登录日志 | 操作审计（只读，不可修改）与登录尝试记录 |
| 我的通知 | 审批、告警等通知 |
| 实施进度 | 当前实施到哪一步、已登记权限/菜单计数、未完成事项 |

> **Outbox 事件在本地开发时可能长期停在 `pending`**：Celery Worker 未启动时不会消费，
> 这是环境限制（见 §九），不代表业务失败。

## 七、跟着做一遍（三条端到端）

### 7.1 采购：从申请到合格入库

演示库里已经有一条完整链路，先看结果，再自己走一遍：

| 单据 | 单号 | 状态 |
| --- | --- | --- |
| 采购申请 | `PR-DEMO-0001` | 已批准 |
| 采购订单 | `PO-DEMO-0001` | 部分到货 |
| 采购收货 | `RC-DEMO-0001` | 已检验 |

自己走一遍（用 `prc_admin` 采购专员 + `qc_inspect` 检验员）：

1. 「采购管理 → 采购申请」新建（选物料、数量、需求日期）→ 提交 → 用 `dept_mgr` 在
   「审批中心 → 我的待办」通过。
2. 回到采购申请 → 「转采购订单」→ 提交 → 审批通过。
3. 「采购收货」新建（引用订单行，**不能超过可收上限**）→ 过账 → 到「仓储管理 → 库存余额」，
   该物料质量状态为**待检**。
4. `qc_inspect` 在收货单上「检验」→ 合格 → 库存变为**合格**（此时才能被领用/销售）。

### 7.2 销售：订单 → 占用 → 发货 → 退货

演示链路：`SO-DEMO-0001`（已发货）→ `SH-DEMO-0001`（已过账）→ `SR-DEMO-0001`（已检验）。

1. 「销售管理 → 销售订单」新建 → 填订单行（SKU、数量、单价）→ 提交 → 审批。
2. 订单详情「占用库存」→ 到「仓储管理 → 库存余额」查看该维度**可用量减少、实存量不变**。
3. 「销售发货」新建（引用订单行，**数量必须被占用覆盖**）→ 过账 → 库存实存减少并写流水。
4. 「销售退货」新建 → 过账 → 库存进入**待检** → 检验判定 → 合格可再销售。

### 7.3 MRP：净算与建议转单

1. 用 `admin` 登录（或 `dept_mgr`）。
2. 「计划管理 → MRP 运算」→ 公司选「意尚智造服饰有限公司」→ 区间取默认 → 「运行 MRP」。
3. 打开运行详情：需求行应能看到 `SO-MRP-0001` 的成品需求被展开成多条子件需求；
   供给行能看到面料库存与采购在途；缺料建议里应有采购建议与生产建议。
4. 「缺料与建议」→ 选一条采购建议「转采购申请」→ 记下生成的申请号 →
   到「采购管理 → 采购申请」确认它是**草稿**（未提交、未审批）。
5. 再点一次「转单」→ 应提示已转单；点生产建议转单 → 应提示 MES 未实现（**这是预期行为**）。


## 八、测试与自检

> 本章只写「怎么自己验证」。最近一次真实输出见 `docs/test-report.md` §16。

### 8.1 一键冒烟（推荐先跑这个）

```powershell
cd E:\github\Yishang-Hub
powershell -ExecutionPolicy Bypass -File scripts\smoke_check.ps1
```

脚本按顺序跑 7 步，任一步失败会汇总失败项并以非零退出码结束：

| 步骤 | 内容 |
| --- | --- |
| 1 | `manage.py check` |
| 2 | `manage.py makemigrations --check --dry-run`（迁移无漂移） |
| 3 | `ruff check apps config tests`（后端静态检查） |
| 4 | `pytest tests -q --reuse-db` |
| 5 | `npm run typecheck`（vue-tsc） |
| 6 | `npm run test`（vitest） |
| 7 | `npm run build` |

> ⚠️ 不要与手动 `pytest` 同时跑：两者共用 `test_yishang_platform` 测试库，并发会互相干扰。

### 8.2 分步命令与最近一次真实结果

后端（工作目录 `backend`，用 `backend\.venv\Scripts\python.exe`）：

| 命令 | 最近一次结果（2026-09-18） |
| --- | --- |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `manage.py makemigrations --check --dry-run` | `No changes detected` |
| `python -m ruff check apps config tests` | `All checks passed!`（沙箱内缓存目录不可写时用 `--no-cache`，规则相同） |
| `python -m pytest tests -q --reuse-db` | `312 passed in 115.05s`（含 `tests/test_docs_sync.py` 7 条文档同步用例、`tests/test_enum_labels.py` 4 条枚举标签用例） |

前端（工作目录 `frontend`）：

| 命令 | 最近一次结果 |
| --- | --- |
| `npm run typecheck` | 退出码 `0`（`vue-tsc` 无错误） |
| `npm run test` | `9 个测试文件 / 131 项通过` |
| `npm run build` | `✓ built in 12.90s` |

另有**不依赖测试框架**的真实链路验证：对运行中的开发服务器直接发 HTTP 请求 **29 项全过**，
经 Vite 开发代理（含 `Origin` / `Referer`，即浏览器真实路径与 CSRF 校验）**5 项全过**，
明细见 `docs/test-report.md` §16.5 / §16.5b。

### 8.3 数据库侧自检

```powershell
# 在 backend 目录执行
.\.venv\Scripts\python.exe manage.py migrate --plan     # 应输出：No planned migration operations.
.\.venv\Scripts\python.exe manage.py showmigrations      # 检查哪些迁移尚未应用（未打 [X]）
```

### 8.4 怎么确认「我的改动没破坏权限与菜单」

| 场景 | 兜底检查 |
| --- | --- |
| 新增/修改权限点、菜单 | `manage.py check`（内置 `yishang.E001` 校验注册表）；前端 `npm run test` 的菜单契约用例 |
| 改了菜单组件路径或改名 | 前端 `router.spec.ts` / `views-compile.spec.ts` 会捕获「登记了组件但文件不存在」 |
| 改了模型 | `makemigrations --check --dry-run` 必须为 `No changes detected` |
| 改了接口契约 | 后端 `pytest`；必要时更新 `docs/api-conventions.md` 与 OpenAPI（`/api/v1/docs/`） |
| 改了本文档 | 重新生成网页版并核对：`python scripts/build_user_guide.py`（`--check` 只校验不写文件）；忘了生成会被 `pytest` 拦下 |

## 九、常见问题与错误码

统一错误结构（详见 `docs/api-conventions.md` §三）：

```json
{
  "code": "INSUFFICIENT_STOCK",
  "message": "可用库存不足",
  "details": { "required": "12.000000", "available": "8.000000" },
  "request_id": "请求追踪标识"
}
```

排查顺序：**先看 `code`**（稳定、可搜索、可写进工单），再看 `message`（面向人的中文说明），
`request_id` 用来在服务端日志里定位同一次请求。

### 9.1 登录、认证与权限

| 错误码 | 现象 | 原因与处理 |
| --- | --- | --- |
| `NOT_AUTHENTICATED` | 401 | 未登录或会话已过期。重新登录；前端遇到 401 会跳转登录页 |
| `PERMISSION_DENIED` | 403，提示缺少操作权限 | 当前账号没有该操作权限点。由管理员在「系统管理 → 角色管理」授予，见 §4.5 |
| `OUT_OF_DATA_SCOPE` | 403 | 有操作权限，但目标对象不在数据范围内（别的公司/工厂/仓库）。这是**数据范围**问题，不是授权问题 |
| `CSRF_FAILED` | 403，「CSRF 校验未通过，请刷新页面后重试」 | 写操作前没有先取 CSRF Cookie。浏览器正常使用不会遇到；用 curl / Postman 手测最容易踩，需先 `GET /api/v1/auth/csrf/` 再带 `X-CSRFToken` |
| `CREDENTIALS_REQUIRED` | 400 | 登录请求没带账号或口令 |
| `INVALID_CREDENTIALS` | 401 | 账号或口令错误（服务端不区分「用户不存在」，避免账号探测） |
| `ACCOUNT_LOCKED` | 403 | 连续失败触发锁定。等待解锁窗口，或由管理员解锁 |
| `ACCOUNT_DISABLED` | 403 | 账号已停用，联系管理员 |
| `LOGIN_RATE_LIMITED` | 429 | 同源登录尝试过于频繁，稍后再试 |

> 会话 Cookie 为 `HttpOnly`，生产环境加 `Secure`；退出登录会使服务端会话失效。

### 9.2 单据与库存

| 错误码 | 现象 | 原因与处理 |
| --- | --- | --- |
| `QUALITY_NOT_RELEASED` | 「只能占用/出库合格库存」 | 待检、不合格库存不能领用或发货。先在收货单 / 退货单上完成检验判定 |
| `RESERVATION_REQUIRED` | 发货时提示「发货数量未被库存占用覆盖」 | 本平台是**先占用、后发货**。到销售订单详情执行「占用库存」，或让发货数量不超过已占用量 |
| `STOCK_SPLIT_ACROSS_DIMENSIONS` | 占用失败 | 合格库存分散在多个储位/批次，单个维度不足以完成占用。先移库合并，或显式指定储位与批次 |
| `OVER_RECEIPT` / `OVER_SHIPMENT` / `OVER_RETURN` | 「超过订单未收 / 未发 / 未退数量」 | 数量超过订单行剩余可执行量。核对该行累计已执行数量；确需增量请走变更流程 |
| `REVERSAL_BLOCKED` | 「原单据增加的库存已被下游消耗，不能直接冲销」 | 冲销不能忽略下游已发生的事实。改走退货 / 更正流程，不要强行冲销 |
| `IDEMPOTENCY_KEY_REQUIRED` | 「该操作必须提供 Idempotency-Key 请求头」 | 过账、冲销等幂等接口必须带幂等键。前端已自动携带，手测需自己加 |
| `IDEMPOTENCY_KEY_CONFLICT` | 同一个幂等键换了请求体 | 幂等键对应的内容不一致会被拒绝，换一个新键重发 |
| `IDEMPOTENCY_IN_PROGRESS` | 同一幂等键的请求还在处理中 | 上一次尚未结束。稍后重试，不要并发复用同一个键 |
| `LOCK_RETRY_EXHAUSTED` | 「库存过账重试次数已用尽」 | 并发锁冲突重试到上限。稍后重试；过账是幂等的，重复提交不会重复扣减 |
| `STATE_CONFLICT` | 状态不允许当前动作 | 例如已过账单据再次过账、已归档运行继续操作。刷新查看当前状态 |
| `HAS_DOWNSTREAM` / `HAS_SHIPMENT` | 不能删除 / 修改 | 单据已有下游引用或已发货。任务书规定**已过账单据不物理删除** |
| `PAGE_SIZE_EXCEEDED` | 400 | 分页大小超过上限，调小 `page_size`（排序、过滤字段为白名单） |

### 9.3 计划与 MRP

| 错误码 | 现象 | 原因与处理 |
| --- | --- | --- |
| `COMPANY_REQUIRED` | 「缺少公司标识」 | 超级管理员等账号没有归属公司，运行 MRP 等接口必须显式传 `company_id`（界面上就是「公司」下拉） |
| `INVALID_BUCKET` | 「时间分段只支持按日或按周」 | 分段参数写错，只有按日 / 按周 |
| `INVALID_HORIZON` | 「需求区间结束日期不能早于开始日期」 | 起止日期填反了 |
| `BOM_CYCLE_DETECTED` | 「检测到循环 BOM」 | BOM 结构成环。先修数据再重算 |
| `BOM_TOO_DEEP` | 「BOM 层级超过 N 层」 | 层级异常（多为数据错误，如自引用）。检查该物料的 BOM 结构 |
| `SUGGESTION_NOT_OPEN` | 建议不可转单 | 建议已被取消或已转单。刷新列表看最新状态 |
| `SUGGESTION_ALREADY_CONVERTED` | 「建议已转单」 | 同一建议不得重复转单（任务书要求）。**这是预期行为** |
| `SUGGESTION_STALE` | 「所属 MRP 运行已被更新的运行取代」 | 期间重新算过 MRP，旧建议已过期。用最新运行的算结果转单 |
| `MRP_RUN_NOT_ACTIVE` | 「只有已完成的运行可以转单」 | 运行仍在计算中或已归档 |
| `MATERIAL_INACTIVE` | 「建议物料已停用，不能转单」 | 物料被停用。先恢复物料，或取消该建议 |
| `PRODUCTION_ORDER_NOT_IMPLEMENTED` | 生产建议转单提示未实现 | **预期行为**：MES 工单属阶段 3 第三步，当前只开放采购建议转单 |

### 9.4 环境类问题（没有错误码）

| 现象 | 原因与处理 |
| --- | --- |
| 前端能打开但接口无响应 / 502 | 后端没启动。跑 `scripts\dev_backend.ps1`，先访问 `/healthz` |
| `/readyz` 不是 200 | 数据库或 Redis 不通。看返回体里哪一项失败，检查 `.env` 的 `DB_*` / `REDIS_URL` |
| Vite 报端口被占用 | 换端口：`npm run dev -- --port 5174`，或 `scripts\dev_frontend.ps1 -Port 5174` |
| 本地连 MySQL 报驱动编译错误 | 本地用 `DB_DRIVER=pymysql`（纯 Python，免编译）；生产按技术方案用 `mysqlclient` |
| 写操作 403 且提示 CSRF | 见 §9.1。开发期确有需要时可把前端来源加入 `DJANGO_CSRF_TRUSTED_ORIGINS`，**不要在生产放宽** |
| Outbox 一直停在 `pending` | Celery Worker 未启动（当前环境未运行 Worker）。属环境限制，不影响单据状态与业务结果 |
| `manage.py check` 报 `yishang.E001` | 权限点 / 菜单注册表不自洽（如菜单引用了不存在的权限点）。按提示修 `apps/identity/permissions_registry.py` |
| 某个类型列显示英文（如 `finished`） | 正常应显示中文标签（后端字段 `<字段>_display`）。若仍是英文：先刷新页面；仍异常请记录**页面 + 列名**反馈。历史非法枚举值已在本轮修复并加了回归用例（`tests/test_enum_labels.py`） |

## 十、未执行 / 未验证事项（不得视为通过）

截至 2026-09-18，以下内容**没有实际执行，或没有实测数据**：

| 事项 | 状态 |
| --- | --- |
| Docker Compose 编排启动 | **未执行**（本机 Docker 不可用，`compose.yaml` 只做过静态检查） |
| `mysqlclient` 生产驱动 | **未验证**（本地走 `pymysql`） |
| Celery Worker / Beat 运行 | **未运行**；任务与调度配置就绪，无运行时验证 |
| Playwright 端到端测试 | **未执行**（本轮未编写用例） |
| 真实硬件采集 | **未执行**（无设备；模拟采集属阶段 5） |
| 备份 / 恢复演练 | **未执行**（脚本存在，见 `docs/backup-restore.md`） |
| 性能压测（百万级流水、并发过账、大文件导出） | **未执行**；阶段 0 未确定性能目标数值 |
| MySQL 8.4 LTS 验证 | **未执行**（本机为 8.0.17，已知偏差，见 `docs/assumptions.md`） |
| 「同一建议并发转单」多连接压测 | **未执行**（逻辑有唯一约束保障，但无真实多连接验证） |
| 浏览器截图级 UI 校验、≤768px 手机布局 | **未执行** |
| 后台管理命令 `reconcile_inventory` / `rebuild_energy_summary` | **未实现**（随阶段 2 / 阶段 5 交付） |

> 真实采集、真实硬件控制、完整财务核算等能力边界，见 `docs/hardware-integration.md`
> 与 `docs/requirements.md`；偏差与假设见 `docs/assumptions.md`。

## 十一、代码更新后，本文档必须同步

> 本节回应一个明确要求：**代码变了，使用说明也要跟着变**。
> 这里定义「什么变了必须改本文档、怎么改、靠什么兜底」。

### 11.1 本文档的定位与口径来源

- 本文档**只描述使用者能看到的行为**：怎么启动、有哪些菜单、每个模块怎么操作、遇到错误怎么办。
- 它**不复制代码细节**。业务口径的唯一来源是：服务层实现、`apps/identity/permissions_registry.py`
  注册表、以及数据库迁移文件。三者与本文档冲突时**以代码为准**，并回来修本文档。
- 文档顶部标注「最后与代码核对：YYYY-MM-DD」。**只改代码不改文档时这个日期就不会更新**，
  它是最直观的失同步信号。
- 文档内嵌一条机器可校验的事实行（见 §11.5），`pytest` 会拿它和注册表比对。

### 11.2 触发同步的变更清单

| 代码变更 | 必须同步的小节 |
| --- | --- |
| 新增 / 删除 / 改名权限点或菜单 | §五 菜单清单、§四 内置角色权限点数、§二 能力边界 |
| 菜单路径、前端组件改名或移动 | §五 菜单清单 |
| 新增业务动作、状态机变化 | 对应 §六 操作指南、§七 端到端步骤 |
| 新增 / 改名错误码、修改错误文案 | §九 常见问题与错误码 |
| 初始化命令、命令参数变化 | §三 启动步骤与命令开关表 |
| 环境变量新增 / 改名 / 默认值变化 | §三 环境准备（并同步 `.env.example`） |
| 业务口径变化（如 MRP 分段、库存数量桶定义） | §六 对应模块、§二 能力边界 |
| 演示数据单号 / 账号变化 | §四 演示账号、§七 端到端 |
| 阶段状态推进（某模块从「未实现」变「可用」） | §二 能力边界、§十 未执行事项 |
| 访问地址、启动方式、端口变化 | §三 全章 |
| 前端交互约定变化（新增批量操作等） | §五 通用交互约定 |

### 11.3 每轮增量的收尾清单（照做）

1. 跑通检查（§8.1 一键冒烟，或等价的分步命令），记录**真实输出**。
2. 更新 `docs/progress.md`：追加本轮小节，写明已实现 / 未实现。
3. 更新 `docs/requirements-matrix.md`：受影响需求行的状态与实现位置。
4. 更新 `docs/test-report.md`：**追加**本轮真实输出（历史小节不改写）。
5. **回头修改本文档**：按 §11.2 对照表修改受影响小节，更新顶部「最后与代码核对」日期，
   并在数量变化时同步 §11.5 的事实行。
5b. **重新生成网页版**：`python scripts/build_user_guide.py`（产出 `docs/user-guide.html`
    与 `frontend/public/guide.html`）；漏做会被 `pytest` 的文档同步用例发现。
6. 若权限点 / 菜单数量变化，重生成 `docs/permission-matrix.md`。
7. 更新根目录 `README.md` 的「当前状态 / 下一步」与文档地图。

### 11.4 怎么核对（不靠印象）

| 想确认 | 怎么做 |
| --- | --- |
| 权限点、菜单的真实数量与清单 | `manage.py bootstrap_system --dry-run`；`docs/permission-matrix.md` 由注册表生成 |
| 枚举字典（各种 status、类型） | `GET /api/v1/meta/` |
| 命令是否还存在、参数是否变了 | `manage.py help <command>` |
| 迁移是否与代码一致 | `manage.py makemigrations --check --dry-run` |
| 菜单登记的组件是否真实存在 | `npm run test`（`router.spec.ts` / `views-compile.spec.ts`） |
| 权限点与菜单是否自洽 | `manage.py check`（`yishang.E001`） |
| 权限点 / 菜单 / 模型数量是否与本文档一致 | `pytest tests/test_docs_sync.py` |

### 11.5 机器可校验事实行（改了代码就同步这一行）

`pytest` 里的 `tests/test_docs_sync.py` 会读取下面这条注释，并与注册表、模型、迁移文件比对；
**不一致就会测试失败**，从而强制文档同步：

<!-- yishang-doc-sync: permissions=173 menus=56 models=86 migrations=19 builtin_roles=13 -->

| 键 | 含义 | 权威来源 |
| --- | --- | --- |
| `permissions` | 权限点总数 | `apps/identity/permissions_registry.PERMISSIONS` |
| `menus` | 菜单项总数（含目录） | `apps/identity/permissions_registry.MENUS` |
| `models` | 受管数据模型总数 | Django `apps.get_models()`（排除自动生成模型） |
| `migrations` | 迁移文件总数 | `backend/apps/*/migrations/0*.py` |
| `builtin_roles` | 内置角色数（**不含** `seed_demo` 建的 `demo_*` 演示角色） | `bootstrap_system.BUILTIN_ROLES` |

改完代码后同步动作：跑一次 `pytest tests/test_docs_sync.py`，按失败信息给出的实际值更新上面这一行。

### 11.6 兜底机制（自动发现失同步）

- 后端：`apps/core/checks.py` 的 `yishang.E001` 在 `manage.py check` 时校验权限点 / 菜单注册表一致性。
- 前端：`npm run test` 的菜单契约与视图编译用例，会在「菜单登记了组件但文件不存在」时失败。
- 文档：`tests/test_docs_sync.py` 校验 §11.5 事实行与代码一致（数量层面）。
- 文档网页版：`tests/test_docs_sync.py` 会执行 `scripts/build_user_guide.py --check`，
  比对 `docs/user-guide.html` / `frontend/public/guide.html` 是否与 Markdown 源一致，
  **忘了重新生成就会失败**。
- **仍有缺口**：文档正文里的描述性内容（菜单名称、操作步骤、错误码解释）**没有自动校验**，
  只能靠 §11.3 的收尾清单手动维护。这一点已在 §十 明确列出。

### 11.7 网页版使用说明（给客户直接看）

本文档除了 Markdown 源文件，还有一份**自动生成的单文件网页**，适合直接给客户：

| 产物 | 位置 | 用途 |
| --- | --- | --- |
| `docs/user-guide.html` | 仓库内 | **单文件、离线可用**：双击打开，或作为附件发给客户 |
| `frontend/public/guide.html` | 随前端发布 | 浏览器访问 `/guide.html`（开发 `http://127.0.0.1:5173/guide.html`） |

生成方式（只在改了 `docs/user-guide.md` 之后需要执行）：

```powershell
cd E:\github\Yishang-Hub
backend\.venv\Scripts\python.exe scripts\build_user_guide.py           # 生成 / 覆盖两份产物
backend\.venv\Scripts\python.exe scripts\build_user_guide.py --check   # 只校验是否最新
```

网页版特性：左侧**可搜索目录**（含滚动定位）、表格与代码块按平台配色排版、
右上角「**打印 / 导出 PDF**」、窄屏自适应；**CSS/JS 全部内联，无外链、无 CDN**，
断网或内网环境同样能正常显示。

> ⚠️ 两点注意：
> 1. **不要直接编辑 HTML**——它是生成物，改了会被下一次生成覆盖，且 `pytest` 会失败。
> 2. `frontend/public/` 下的文件由 Nginx **作为静态资源直接发布，不校验登录**。
>    如果这份说明包含你不希望外部访问的内容（如内网地址、库名），请只把
>    `docs/user-guide.html` 发给客户，或在 Nginx 上为 `/guide.html` 单独加访问控制。
