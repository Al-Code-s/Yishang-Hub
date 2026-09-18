# 架构设计（docs/architecture.md）

## 一、总体形态：模块化单体

```text
Vue 3 前端（Vite 构建）
    ↓  HTTPS，同域部署
Nginx（静态资源 + /api 反向代理 + 安全响应头）
    ↓
Django / DRF（模块化单体）
    ├── 业务模块（identity / factory / masterdata / wms / workflow ...）
    ├── 权限与审批（identity.permissions_registry + workflow）
    ├── 仓储服务（阶段 2：唯一库存过账入口）
    ├── 审计与通知（core.audit / identity.notification）
    └── 采集接收（阶段 5：iot）
         ↓
      MySQL 8（业务事实唯一来源）

Celery Worker（报表 / 导入导出 / 汇总 / 告警 / Outbox 消费）
Celery Beat（调度，默认单实例）
Redis（缓存 + 任务消息辅助，不是业务状态唯一存储）
S3 兼容对象存储（附件，默认私有）
```

**为什么不是微服务**：第一版数据强一致要求集中在库存、审批、单据状态上，
拆分会把事务边界变成分布式事务，得不偿失。任务书 2.3.7 也明确第一版不采用微服务与 Kubernetes。

## 二、技术选型与理由

| 层 | 选型 | 理由 |
| --- | --- | --- |
| 后端 | Django 5.2 LTS + DRF | 大量主数据、单据、权限、审批、后台任务、事务与报表，Django 可减少基础设施重复开发 |
| 数据库 | MySQL 8 InnoDB / utf8mb4 | 事务、行锁、外键与成熟运维生态 |
| 缓存/队列 | Redis + Celery | 缓存与异步任务；不承担业务事实 |
| 前端 | Vue 3 + TS + Element Plus + Pinia | 企业级管理后台组件完备，类型安全 |

**明确的边界（任务书 3.2）**：
- Django 自带权限**不能替代**业务数据权限 → 实现四层权限与数据范围（`docs/permission-matrix.md`）。
- Django Admin **不替代**正式业务前端 → 业务前端为独立 Vue 应用，Admin 仅作运维兜底。
- Django signals **不承载**库存过账等隐式关键流程 → 关键链路一律走显式服务层调用。

## 三、后端目录结构

```text
backend/
├── config/                 Django 工程配置
│   ├── settings/{base,dev,test,prod}.py
│   ├── urls.py  wsgi.py  asgi.py  celery.py
├── apps/
│   ├── core/               公共基础：BaseModel、审计、字典、编码规则、附件、幂等、Outbox、异常
│   ├── identity/           用户、角色、权限点、菜单、登录会话、通知
│   ├── factory/            公司、部门、工厂、车间、线体、工位、员工、班次、班组
│   ├── masterdata/         物料、分类、款式、颜色、尺码、SKU、计量单位、标识
│   ├── crm/                客户档案与联系人（阶段 6 扩展服务工单、投诉、满意度）
│   ├── srm/                供应商、联系人、资质（寻源/报价/评分在阶段 2 后续增量）
│   ├── wms/                仓库、库区、储位、库存余额与流水、库存单据（统一库存服务）
│   ├── procurement/        采购申请、采购订单、采购收货（收货过账与放行调用 wms 库存服务）
│   ├── sales/              销售订单、库存占用、发货出库、销售退货（库存变更全部调用 wms 库存服务）
│   ├── planning/           BOM / 工艺路线（版本化工程数据）+ MRP（净算 / 建议 / 建议转单）
│   ├── workflow/           审批模板、实例、节点、待办
│   ├── integration/        Outbox 事件、单据关系（内部协同中心）
│   └── analytics/          看板与报表聚合
├── tests/                  跨模块集成测试
├── manage.py  pyproject.toml  uv.lock
```

**已创建**：`core / identity / factory / masterdata / crm / srm / wms / procurement / sales / planning / workflow / integration / analytics`。

**未创建的模块**：`mes / qms / eam / ems / ehs / logistics / iot /
endpoint_security` 当前**不创建目录**。任务书 20.3 要求「不创建大量空壳模块冒充完成」，
因此这些模块在阶段 3–6 按需建立（`crm`、`srm` 于阶段 2 第一步，`procurement` 于阶段 2 第三步，
`sales` 于阶段 2 第四步，`planning` 于阶段 3 第一步（BOM 与工艺路线）、阶段 3 第二步（MRP），均按此原则建立）。

**命名约定**：顶层不创建 `platform.py`（与标准库同名），平台级能力归属 `core`。

## 四、单模块分层职责

```text
View/ViewSet  请求接收、认证授权、调用服务、返回响应
Serializer    输入输出格式、字段级校验
Service       业务规则、事务、状态迁移        ← 唯一允许修改业务状态的地方
Selector      查询、权限范围过滤、查询优化
Model         数据结构、约束、简单实体行为
Task          异步执行**已定义**的业务服务
```

强制约束（任务书 4.3 禁止项，已在本轮代码中遵守）：

- View 中不写库存/MRP 逻辑；View 只做参数装配与权限校验后调用 Service。
- Serializer 不隐藏跨模块副作用，不自动创建下游单据。
- 不使用 signals 连锁创建关键业务单据。
- 不跨模块直接修改他人业务表（跨模块协作只经由对方 Service）。
- 前端传入的计算结果不决定库存扣减。

## 五、模块协作与一致性

- **强一致**（必须同事务）：库存过账、单据状态迁移、审批推进、审计落库 → 同步 Service 调用 + `transaction.atomic()`。
- **最终一致**（允许延迟）：通知、汇总、报表 → 业务事务内写 Outbox，Worker 轮询分发。
- 不把所有操作异步化；不把 Celery 任务结果当正式业务记录（数据库是唯一依据）。

**已落地（阶段 2 库存核心）**：过账与冲销在同一事务内完成
「余额 + 流水 + 单据状态 + 审计 + Outbox」，并使用「按 `dimension_key` 升序上锁」与
「保存点内重试创建余额行」降低死锁与并发重复风险。

### Outbox 时序

```text
1. 业务事务内：写业务数据 + 写 OutboxEvent(status=PENDING)   ← 同一事务，原子
2. Worker 轮询：取 PENDING/FETCH 到期的行，attempts+1
3. 分发到消费者；消费者按 dedup_key 幂等
4. 成功 → PROCESSED；失败 → 记录 last_error，按 next_retry_at 退避重试
5. 超过上限 → FAILED，进入人工处理，可按权限重放
```

`transaction.on_commit()` 仅用于**加速唤醒**，不能替代持久化 Outbox。

## 六、权限执行链路

```text
请求 → 认证（Session）→ CSRF 校验 → 权限点校验（操作/接口层）
     → Selector 数据范围过滤（列表/详情/导出/汇总）
     → Service 内二次校验（关联对象、跨组织写入）
     → 审计落库（与业务同事务）
```

数据范围**始终以后端解析结果为准**，前端传 `factory_id` 仅作为过滤条件，不作为授权依据。

## 七、前端架构

```text
src/
├── api/          按模块封装的请求方法（统一 http 客户端，含 CSRF 与错误归一化）
├── components/   EntityListPage、ProTable、字典/枚举选择器等通用件
├── layouts/      侧边导航 + 顶部工具栏 + 标签页
├── router/       静态路由 + 按后端菜单动态注册（无权限不注册）
├── stores/       Pinia：会话、菜单权限、字典缓存
├── views/        业务页面
├── types/        API 类型（Decimal 一律 string）
└── utils/        decimal.js 封装、时间与枚举格式化
```

**菜单由后端下发**：`identity/menus/mine/` 返回当前用户可见菜单树，前端据此注册路由。
这样「菜单权限」与「接口权限」共用一份契约，避免前端硬编码菜单导致的越权显示。

## 八、部署拓扑

```text
nginx ──┬─→ 静态资源（前端 dist）
        └─→ backend:8000（Gunicorn）
backend / worker / beat  ← 同一镜像，不同启动命令
mysql（不发布端口）/ redis（不发布端口）/ object-storage
migrate ← 一次性发布步骤，由单个实例执行
```

要求：非 root 容器运行、服务健康检查、数据持久化卷、MySQL/Redis 不暴露到公网、
不使用 `runserver` 对外提供服务。详见 `docs/deployment.md`。

## 九、关键设计决策记录（ADR 摘要）

| 编号 | 决策 | 备选 | 结论理由 |
| --- | --- | --- | --- |
| ADR-01 | 首次迁移即使用自定义 `identity.User` | 先 `auth.User` 后迁移 | 后期更换代价极高；用户与员工档案分离（任务书 6.2） |
| ADR-02 | 权限点用集中注册表 `permissions_registry` | 各 App 分散 declare | 单一契约便于后端启动自检、前端菜单与文档同步 |
| ADR-03 | 库存维度使用显式规范化键而非多可空列唯一索引 | 多列联合唯一 | MySQL 唯一索引对 NULL 不去重，会导致重复余额行 |
| ADR-03b | 库存变更全部走 `apps/wms/services/stock.py` 单一服务 | 各模块直写表 / Django signals | 任务书 3.2、4.3：signals 不能承载库存过账等隐式关键流程；已实现并通过 36 条用例（含并发）。**采购收货过账与来料放行是首个接入的调用方**（`apps/procurement/services.py`），只调用服务、不写库存表 |
| ADR-03c | 审批终态回写业务单据采用**显式注册回调**（`apps/workflow/registry.py`） | Django signals / 在审批服务里硬编码各模块分支 | 任务书 4.3：禁止用 signals 自动连锁创建关键业务单据；显式注册让依赖方向保持单向（业务模块注册，工作流模块调用），采购申请与订单是首批使用者 |
| ADR-03c | 库存流水为**只追加**（模型层拒绝 update/delete） | 普通 CRUD 模型 | 账实一致与审计要求；模型 `save()`/`delete()` 抛 `ImmutableLedgerError` |
| ADR-04 | 看板默认轮询，不引入 WebSocket | ASGI + Channels | 任务书 3.1 要求第一版避免过早引入复杂实时基础设施 |
| ADR-05 | 阶段 0/1 不创建未实施模块目录 | 预建空壳 | 任务书 20.3：不以空壳模块冒充完成 |
| ADR-06 | 工程数据（BOM / 工艺路线）**版本化 + 审批后冻结**，变更只能派生新版本 | 就地修改已审核版本 / 只留审计快照 | 已下达工单引用的版本内容必须不变（任务书 9.5、14.2 案例 13）；「同一范围唯一生效版本」由服务层 `select_for_update` 保证（MySQL 无部分唯一索引） |
| ADR-07 | 工程版本范围唯一键用 `scope_key` 规范化字符串 | 直接对 `(company, style, sku, version_no)` 建唯一索引 | 同 ADR-03：MySQL 唯一索引不约束 NULL，「款式通用」多版本会冲突不到 |
| ADR-08 | 快照由 `build_*_snapshot()` 输出 dict，**不预先建快照表** | 现在就建空的工单快照表 | 任务书 20.3：不建空壳；快照归属方是 MES 工单，阶段 3 后续增量落库 |
| ADR-09 | MRP 采用**同步计算 + 落库快照**（不投 Celery） | 异步任务 + 轮询结果 | 任务书 4.4「不将所有操作都异步化」、7.4「数据库是任务业务结果的最终依据」；演示规模下单次净算为毫秒级，同步执行让"运算—结果—转单"在同一个请求-响应周期内可解释、可复验；数据量增长后可再评估异步化 |
| ADR-10 | MRP 内核拆分为**纯计算 `_compute()` + 落库 `_persist()`** | 边算边写表 | 计算逻辑可被测试直接调用（无副作用），落库集中在单一事务内完成；`MrpRun.parameters` / `summary` 固化本次口径，重算只产生新运行，不覆盖历史 |
| ADR-11 | 生产建议**不伪造 MES 工单**，`convert_suggestion` 直接拒绝（`PRODUCTION_ORDER_NOT_IMPLEMENTED`） | 先建一个"占位工单" | 任务书 20.3「不创建大量空壳模块冒充完成」「不用模拟结果冒充真实」；错误码让前端能给出明确提示，MES 落地后再打开该分支 |
| ADR-12 | MRP 对库存 / 采购**只读**，转单只产出**草稿**单据 | MRP 直接生成采购订单 / 工单 | 任务书 10.6「转单前重新检查建议有效性」「不得重复转单」，以及任务书 4.3「禁止在 View 中编写库存逻辑」；草稿单据仍走采购审批，审批与过账是不同动作 |