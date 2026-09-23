# 阶段验收记录（docs/acceptance.md）

> 验收依据：任务书 19.3「完成标准」。**「页面已存在」不等于「已通过阶段验收」。**
> 所有数字来自本轮**实际执行**的命令输出，原始记录见 `docs/test-report.md`。
>
> **最新核对（2026-09-21）**：权限点 **333** / 菜单 **134**（113 个页面 + 21 个目录）/
> 数据模型 **134** / 迁移文件 **27**；自动化测试 **后端 412 + 前端 249** 通过。
> 下面各小节里的数字是**该阶段验收当时的快照**，不回改；要「现在是多少」请看
> `AGENTS.md` §九 的文档同步事实行与 `docs/test-report.md` §16。

## 一、阶段 0 验收

| 任务书条目 | 交付物 | 证据 | 结论 |
| --- | --- | --- | --- |
| 20.1.1 检查仓库 | 仓库检查结论 | 仓库为单次 `Initial commit`，无既有业务代码，未覆盖任何内容 | ✅ |
| 20.1.3 需求追踪矩阵 | `docs/requirements-matrix.md` | 覆盖任务书全部章节，含实施边界标注 | ✅ |
| 20.1.4 架构/数据模型/权限文档 | `architecture.md`、`data-model.md`、`permission-matrix.md` | 文档存在且与代码一致（权限表由注册表生成） | ✅ |
| 20.1.5 初始化工程 | Vue 3 + TS + Vite 6；Django 5.2 + DRF | `npm run build` 成功；`manage.py check` 无问题 | ✅ |
| 20.1.6 配置 MySQL/Redis/对象存储/Compose | 配置与 `compose.yaml` | MySQL 8.0.17 连通（阶段 0 快照 62 张表；**最新核对 92 张**，utf8mb4_0900_ai_ci，严格模式）；Redis 3.2.100 连通。**Compose 未启动验证** | ⚠️ 部分 |
| 20.1.7 自定义 User 模型 | `identity.User` | `AUTH_USER_MODEL=identity.User`，首次迁移即启用 | ✅ |
| 20.1.15 初始化与演示命令 | `bootstrap_system`、`seed_demo` | 幂等（重复执行不重复建）、`seed_demo` 拒绝生产环境 | ✅ |
| 20.1.16 迁移/测试/检查/构建 | 见 `test-report.md` | 后端 112 通过；前端 60 通过（**该阶段当时快照**，最新为后端 307 / 前端 129，见上方「最新核对」）；Ruff 通过；类型检查通过；构建成功 | ✅ |
| 20.1.17 更新进度文档 | `docs/progress.md` | 已更新 | ✅ |
| 20.1.18 输出启动/验证步骤 | `README.md`、`deployment.md` | 含访问地址、启动命令、验证步骤、未完成项 | ✅ |

## 二、阶段 1 验收

| 能力 | 实现位置 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| 会话登录 / CSRF / 退出 / 改密 | `identity/auth/*` | `test_auth_api.py` 12 项 + HTTP 验证（登录→会话→退出→退出后 403） | ✅ |
| 登录限流与失败锁定 | `User.failed_login_count`、`locked_until`、`LoginAttempt` | `test_auth_api.py`；测试内 autouse fixture 复位限流 | ✅ |
| 角色 / 权限点 / 菜单 | `identity` + `permissions_registry`（**当前 124 权限 / 43 菜单**） | `test_permissions.py` 17 项；启动自检校验编码存在 | ✅ |
| 四层权限与数据范围 | `apps/core/selectors.py::resolve_data_scope` | `test_permissions.py`（含 fail-closed 断言） | ✅ |
| 组织（公司/部门/工厂/车间/线体/工位） | `factory` | `test_factory_api.py` | ✅ |
| 员工 / 班次 / 班组 | `factory` | `test_factory_api.py`；`ShiftSerializer.validate()` 跨夜校验 | ✅ |
| 物料 / 分类 / 面料属性 | `masterdata` | `test_smoke_api.py`；HTTP 验证（列表 count=65、新建 201、重复编码 400） | ✅ |
| 款式 / 颜色 / 尺码 / SKU | `masterdata` | `test_smoke_api.py::test_sku_generate_endpoint`；`uq_sku_style_color_size` | ✅ |
| 计量单位与换算 | `masterdata` | `ck_uom_conversion_distinct` / `factor_positive` | ✅ |
| 标识分型 | `masterdata.Identifier` | `uq_identifier_type_value` | ✅ |
| 仓库 / 库区 / 储位 | `wms` | `test_smoke_api.py::test_warehouse_zone_location_tree` | ✅ |
| 基础审批（模板/顺序/条件/撤回/快照） | `workflow` | `test_workflow_api.py` 10 项 | ✅ |
| 审计日志 | `core.AuditLog` | HTTP 验证：新建物料后审计行可查；审计无写入路由 | ✅ |
| 通知 / 字典 / 编码规则 / 附件 | `core` | `test_core_services.py` | ✅ |
| 后台布局 / 菜单 / 工作台 | `frontend/src/layouts`、`views/workspace/Index.vue` | `router.spec.ts` 菜单组件一致性；HTTP 验证 dashboard 11 张卡片 | ✅ |
| 实施进度页 | `views/system/ProgressView.vue` | 管理员可见菜单含「实施进度」 | ✅ |

## 三、阶段 2 第一步验收（客户与供应商主数据）

任务书 10.2 与 10.4 中**属于主数据**的部分。寻源、报价、评分评价、准入审批流程
**不在本轮范围**，界面与文档均未声称完成。

| 能力 | 实现位置 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| 客户档案（分类/等级/状态/信用额度/业务员） | `crm.Customer` | `test_crm_api.py`；HTTP 验证 count=3 | ✅ |
| 客户联系人 + 唯一主联系人 | `crm.CustomerContact`、`core.services.ensure_single_primary` | `test_crm_api.py`（切换主联系人后原标记被取消，DB 仅一行 primary） | ✅ |
| 客户编码公司内唯一 | `uq_customer_company_code` | 接口 400/409 + 绕过接口直写触发 `IntegrityError` | ✅ |
| 供应商档案（类别/等级/准入状态/采购员） | `srm.Supplier` | `test_srm_api.py`；HTTP 验证 count=3 | ✅ |
| 供应商联系人 + 唯一主联系人 | `srm.SupplierContact` | `test_srm_api.py` | ✅ |
| 供应商资质与有效期 | `srm.SupplierQualification` | `test_srm_api.py`；HTTP 验证 4 条含过期/未登记/空编号三种情形 | ✅ |
| 到期日不早于发证日 | `ck_supplier_qualification_date_order` | `test_srm_api.py`（400 且字段级报错） | ✅ |
| 证书编号规范化去重 | `dedup_key`（唯一、可空、`editable=False`） | 大小写不同被拒；未填编号可并存多条（`dedup_key IS NULL`） | ✅ |
| 剩余天数 / 是否过期 | 序列化器 `days_to_expiry` / `is_expired` | 后端计算；未登记到期日返回 `null`（**不当作未过期**） | ✅ |
| 数据范围（列表/详情/写入） | `ScopedModelViewSet` + `customer__company_id` / `supplier__company_id` | `test_crm_api.py`、`test_srm_api.py`：跨公司 404、跨公司写入 403 | ✅ |
| 权限点与菜单 | `permissions_registry`（+17 权限 / +7 菜单） | `test_crm_api.py::test_viewer_without_create_permission_is_rejected` 等 | ✅ |
| 枚举字典 | `/api/v1/meta/` 7 个新键 | `test_meta_exposes_crm_and_srm_enums` | ✅ |
| 演示数据 | `seed_demo` | 首次新建 17 条，第二次 0 条（幂等） | ✅ |
| 审计 | `AuditLog` | `test_customer_create_is_audited` | ✅ |

> 「主数据可用」**不等于**「供应商评级可用」：本轮没有任何评分字段写入数据库，
> 界面上也不展示评分，避免用默认值冒充评价结果（任务书 10.4 规则）。

## 四、阶段 2 核心验收（统一库存服务）

任务书 10.8 中**属于库存核心**的部分。采购、销售、生产单据与调拨在途、盘点
**不在本轮范围**，界面、API 与文档均未声称完成。

| 能力 | 实现位置 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| 库存余额与维度唯一 | `wms.InventoryBalance` + `dimension_key` | `test_empty_batch_and_roll_share_one_dimension`、`test_batch_no_is_case_insensitive` | ✅ |
| 四类数量口径 | `on_hand`/`frozen`/`reserved`/`available` + 2 个检查约束 | 已在 MySQL 中创建并由测试间接验证 | ✅ |
| 只追加流水 | `wms.InventoryTransaction` | `test_ledger_is_append_only`（改写抛 `ImmutableLedgerError`） | ✅ |
| 收货入库 | `post_document`（receipt） | `test_receipt_creates_balance_and_ledger` | ✅ |
| 出库与库存不足拒绝 | `_assert_available` | `test_issue_reduces_balance`、`test_insufficient_stock_is_rejected_without_side_effect` | ✅ |
| 待检/不合格不可出库 | `_assert_quality_allowed` | `test_quarantine_stock_cannot_be_issued`、`test_rejected_stock_cannot_be_issued` | ✅ |
| 质量放行 | `release_quality`（QUALITY 单） | `test_release_quality_moves_stock_between_statuses`、`test_api_release_quality` | ✅ |
| 同仓移库守恒 | `post_document`（move） | `test_move_conserves_quantity`、`test_concurrent_transfer_keeps_total` | ✅ |
| 跨仓调拨 | — | `test_move_to_other_warehouse_is_rejected`（**当前拒绝**） | ❌ 未实现 |
| 冲销与下游消耗保护 | `reverse_document` / `_assert_reversible` | `test_reversal_blocked_when_stock_consumed`、`test_reversal_requires_reason`、`test_double_reversal_is_rejected` | ✅ |
| 幂等过账 | `InventoryTransaction.idempotency_key` | `test_same_idempotency_key_posts_once`、`test_api_idempotency_key_deducts_once` | ✅ |
| 死锁重试不重复 | `MAX_LOCK_RETRIES`（仅 1213/1205） | `test_deadlock_retry_does_not_duplicate_ledger`、`test_non_retryable_error_is_not_retried` | ✅ |
| 并发创建余额行不重复（必测 7） | `dimension_key` UNIQUE + 保存点内重试 | `test_concurrent_balance_creation_yields_single_row` | ✅ |
| 并发出库不产生负库存（必测 6） | `行锁 + 锁内复校` | `test_concurrent_issue_never_produces_negative_stock` | ✅ |
| 超量报工/非授权数量 | 单据行检查约束 + 服务校验 | `test_zero_quantity_line_is_rejected`、`test_empty_document_is_rejected` | ✅ |
| 已过账不可编辑 | `update_draft_document` | `test_posted_document_cannot_be_edited` | ✅ |
| 单据编号唯一且创建时分配 | `allocate_document_no` + `uq` 约束 | `test_document_numbers_are_unique_and_allocated_on_create` | ✅ |
| 审计（过账/冲销） | `_record_document_audit` | 过账写 `AuditAction.POST`、冲销写 `REVERSE`，与业务同事务 | ✅ |
| 只读接口无写路由 | 余额/流水 ViewSet | `test_inventory_read_apis_reject_writes`（405） | ✅ |
| 仓库数据范围 | `warehouse__factory_id` / `warehouse_id` + `assert_in_scope` | `test_api_enforces_warehouse_scope` | ✅ |
| 权限点与菜单 | `permissions_registry`（+7 权限 / +3 菜单） | `test_inventory_endpoints_require_permission`、`test_inventory_endpoints_require_login` | ✅ |
| 枚举字典 | `/api/v1/meta/` 5 个新键 | `test_meta_exposes_inventory_enums` | ✅ |
| 演示数据 | `seed_demo._inventory`（仅调服务，不直写表） | 首次新建 6 单 + 1 质量放行，第二次 0 条 | ✅ |
| 盘点与范围冻结 | — | 未实现 | ❌ 未实现 |
| 冻结/解冻、占用/释放业务动作 | 数量桶已建模，无服务入口 | 未实现 | ❌ 未实现 |
| 库位推荐、标签打印、库存成本 | — | 未实现 | ❌ 未实现 |

> 重要：`allow_negative_stock` 字段已建模，但**服务层不考虑该开关**，始终拒绝负库存；
> 数据库检查约束是第二道硬墙。这与 `docs/inventory-rules.md` §八的记录一致。


## 五、阶段 2 采购模块验收（申请 / 订单 / 收货 / 来料检验）

任务书 10.5 的**主体链路**。询价比价、到货差异、退货、应付与付款登记、采购分析报表、单据打印
**不在本轮范围**，界面、API 与文档均未声称完成。

| 能力 | 实现位置 | 验证方式 | 结果 |
| --- | --- | --- | --- |
| 采购申请（类型、行、取号） | `procurement.PurchaseRequisition` | `test_requisition_create_persists_lines_and_generates_no` | ✅ |
| 申请审批与状态回写 | `apps/workflow/registry.py` 显式回调 | `test_requisition_approval_writes_back_status` | ✅ |
| 申请转订单（防重复转单） | `services.create_order_from_requisition` | `test_convert_requisition_to_order_and_block_duplicates`、`test_draft_requisition_cannot_be_converted` | ✅ |
| 订单状态机与关闭 | `submit_order` / `cancel_order` / `close_order` | `test_order_submit_then_approve_writes_back_status`、`test_order_can_be_closed_after_receipt`、`test_order_cannot_be_cancelled_once_receipt_exists` | ✅ |
| 金额由后端计算且字段只读 | `recalculate_order_amounts` + 只读序列化器字段 | `test_order_amount_is_computed_by_backend`、`test_order_tax_rounding_is_half_up` | ✅ |
| 供应商准入 / 停用校验 | `_assert_supplier_usable` | `test_suspended_supplier_cannot_be_used_without_reason`、`test_inactive_supplier_needs_override_permission` | ✅ |
| 例外下单授权与留痕 | `supplier_exception*` + 审计 | `test_override_supplier_requires_reason_and_is_audited` | ✅ |
| 收货不允许超收 | `_assert_receipt_quantities` | `test_receipt_over_order_quantity_is_rejected` | ✅ |
| 草稿收货占用额度 | 同上（草稿一并计入） | `test_draft_receipts_reserve_remaining_quantity` | ✅ |
| 收货行必须属于本订单 | `_order_line_rows` | `test_receipt_line_must_belong_to_the_order` | ✅ |
| 收货过账 → 待检库存 | `stock.create_document` + `post_document` | `test_post_receipt_creates_quarantine_stock_and_blocks_issue` | ✅ |
| 待检库存不可领用 | 库存服务 `_assert_quality_allowed` | 同上（领用被拒绝） | ✅ |
| 来料检验放行 | `stock.release_quality` | `test_inspect_qualified_releases_stock_for_issue` | ✅ |
| 不合格库存仍被拦截 | 同上（`rejected`） | `test_inspect_rejected_keeps_stock_blocked` | ✅ |
| 多行收货逐行放行 | 服务内按行号隔离幂等键 | `test_multi_line_receipt_inspect_releases_every_line_once` | ✅ |
| 状态机约束（未过账不可检验等） | `inspect_receipt` / `cancel_receipt` | `test_inspect_requires_posted_state`、`test_repeated_inspect_is_rejected`、`test_posted_receipt_cannot_be_cancelled` | ✅ |
| 幂等（过账 / 检验） | `Idempotency-Key` + `core.IdempotencyRecord` | `test_receipt_post_is_idempotent_with_header`、`test_inspect_with_idempotency_key_replays_without_second_release` | ✅ |
| 跨模块权限按「与」语义 | `required_permissions` 列表形式 | `test_receipt_permission_is_enforced`、`test_view_only_user_cannot_create_order` | ✅ |
| 数据范围与跨公司隔离 | `scoped_queryset` + `assert_in_scope` | `test_orders_are_company_scoped`、`test_receipts_of_other_company_orders_are_not_visible` | ✅ |
| 枚举字典 | `/api/v1/meta/` 5 个新键 | `test_meta_exposes_procurement_enums` | ✅ |
| 演示数据 | `seed_demo._procurement`（仅调服务层） | 首次建 PR / PO / RC 各 1 张并走完检验放行，第二次 0 条 | ✅ |
| 询价比价 / 报价单 | — | 未实现 | ❌ 未实现 |
| 到货差异处理 | — | 未实现（当前只有「不允许超收」） | ❌ 未实现 |
| 采购退货 | — | 未实现 | ❌ 未实现 |
| 应付与付款登记 | — | 未实现 | ❌ 未实现 |
| 采购价格与交付分析、单据打印 | — | 未实现（分析属阶段 7） | ❌ 未实现 |
| 供应商准入审批流程 | `admission_status` 仍是档案字段 | 未接入 `workflow` | ❌ 未实现 |

> 重要：来料检验是**人工录入判定**，未接入任何检测设备；
> 界面与文档均未把它写成自动检测结果（任务书 10.9 的口径）。
## 五之二、阶段 2 销售模块验收（订单 / 占用 / 发货 / 退货检验）

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| 页面可操作 | ✅ | `SalesOrderList.vue` / `SalesShipmentList.vue` / `SalesReturnList.vue`，`views-compile.spec.ts` 实际编译并加载 |
| API 可访问 | ✅ | `/api/v1/sales/orders/`、`/api/v1/sales/shipments/`、`/api/v1/sales/returns/` 及 `submit` / `reserve` / `release` / `close` / `cancel` / `post` / `inspect` / `chain` 动作；真实数据链路见 `docs/test-report.md` §10.4 |
| 数据持久化 | ✅ | MySQL 真实写入并读回：`SO-DEMO-0001` / `SH-DEMO-0001` / `SR-DEMO-0001` 及库存余额与流水 |
| 权限生效 | ✅ | 未登录被拒；只读用户不能建单；无 `wms.inventory.reserve` 不能占用；**业务员不能判定退货**（`test_sales_clerk_cannot_inspect_returns`）；跨公司不可见 |
| 状态迁移正确 | ✅ | 草稿 → 提交 → 批准 → 部分发货 → 已发货 → 关闭；支持驳回与取消；已过账发货单不可取消（只能冲销/退货） |
| 异常处理明确 | ✅ | 统一错误码：`RESERVATION_REQUIRED`、`INSUFFICIENT_STOCK`、`OVER_RETURN`、`CUSTOMER_INACTIVE`、`ORDER_WAREHOUSE_REQUIRED`、`STOCK_SPLIT_ACROSS_DIMENSIONS` |
| 关键操作可审计 | ✅ | 建单、提交、占用、释放、发货过账、退货过账、检验判定均 `record_audit` 并写 Outbox 事件（同事务） |
| 跨模块结果正确 | ✅（本增量范围内） | 出库、入库、质量放行**只调用** `apps/wms/services/stock.py`；成品批次 `FG-2509-01`：入库 240 → 占用 60 → 发货 60 → 退货 6 待检 → 合格回库 6 → 可用 186，占用归零 |
| 自动化测试实际执行 | ✅ | `tests/test_sales.py` 34 例；全量 `pytest tests -q --reuse-db` → `217 passed` |
| 文档已更新 | ✅ | `docs/progress.md` §十、`docs/requirements-matrix.md` §一之五、`docs/inventory-rules.md` §十、`docs/data-model.md`、`docs/business-flows.md` §12.1、`docs/test-report.md` §十 |
| 未完成内容明确列出 | ✅ | 见下方未实现清单与 `docs/assumptions.md` §四之四（A-19 ~ A-25） |

**本增量明确的未实现项**（不得视为通过）：销售计划、颜色尺码矩阵批量录入、折扣、订单变更版本快照、
分批发货界面细化、分销商、基础预测、应收与收款登记、跨维度自动拆分占用、多批次部分退货的批次分摊。

**未执行的验证**：占用并发（同键并发只成功一次）**未做真实多连接压测**；Docker Compose、
Celery Worker/Beat、Playwright、备份恢复、性能压测仍未执行（与第七节口径一致）。

## 五之三、阶段 3 第一步验收（BOM 与工艺路线版本快照）

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| 页面可操作 | ✅ | `views/planning/BomList.vue` / `RoutingList.vue`，位于「计划管理」目录下；`views-compile.spec.ts` 实际编译并加载；`npm run build` 产物含 `BomList-B_Xq9rdS.js` 与 `RoutingList-BoeDw3JC.js` |
| API 可访问 | ✅ | `/api/v1/planning/boms/`、`/api/v1/planning/routings/` 及 `submit` / `obsolete` / `new-version` / `snapshot` / `set-active`；OpenAPI 共 14 个 planning 路径；真实数据链路见 `docs/test-report.md` §15.5 |
| 数据持久化 | ✅ | MySQL 真实写入并读回：`BOM202609180001` v1（5 行明细，面料含损耗用量 `0.296800`）、`RT202609180001` v1（5 道工序） |
| 权限生效 | ✅ | 匿名 403；只读用户不能新建；`planning.routing.*` **不授予** BOM 写权限；跨公司对象被拒；越权车间被拒 |
| 状态迁移正确 | ✅ | `draft → submitted → approved / rejected`，可 `withdraw` 回草稿；**审核通过时同范围旧生效版本自动转 `obsolete`**；作废必填原因；审核中不许派生新版本或作废 |
| 异常处理明确 | ✅ | `EMPTY_DOCUMENT`、`NORMAL_MATERIAL_DUPLICATED`、`SUBSTITUTE_TARGET_INVALID`、`ROUTING_STEP_REQUIRED`、`APPROVAL_TEMPLATE_NOT_FOUND`、`OPTIMISTIC_LOCK_CONFLICT` |
| 关键操作可审计 | ✅ | 新建、修改、提交、审核回写、作废、派生新版本均 `record_audit`（`test_key_actions_are_audited`） |
| 跨模块结果正确 | ✅（本增量范围内） | 只调用 `workflow` 审批与 `masterdata` / `factory` 主数据，**不触碰库存服务**；`build_bom_snapshot()` 与接口快照逐字段相等 |
| 自动化测试实际执行 | ✅ | `tests/test_planning.py` 50 例；全量 `pytest tests -q --reuse-db` → `267 passed`；前端 `vitest` → `127 passed`；`ruff` / `vue-tsc` / `vite build` 通过 |
| 文档已更新 | ✅ | `docs/progress.md` §十四、`docs/requirements-matrix.md` §一之六、`docs/data-model.md` §三 planning 与 §六 第 10 条、`docs/permission-matrix.md`（重生成 167 权限 / 54 菜单）、`docs/architecture.md` ADR-06~08、`docs/business-flows.md` §12.1、`docs/test-report.md` §15 |
| 未完成内容明确列出 | ✅ | 见下方「未实现项」 |

**本增量明确的未实现项**（不得视为通过）：MRP、MES 工单与报工、QMS 检验单、快照表落库、
BOM / 工艺 Excel 导入导出、BOM 成本卷算、工艺路线与设备 / 工位主数据的外键关联、
`standard_hours` 参与任何计算。

**未执行的验证**：「同一范围唯一生效版本」**未做独立连接的真实并发用例**
（当前靠服务层 `select_for_update` + 服务层校验，MySQL 无部分唯一索引）；Docker Compose、
`mysqlclient` 生产驱动、Celery Worker/Beat、Playwright、MySQL 容器镜像（`mysql:8.0`）、性能压测与备份恢复仍未执行
（与第七节口径一致）。

## 五之四、阶段 3 第二步验收（MRP）

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| 页面可操作 | ✅ | `views/planning/MrpRunList.vue`（运行表单 + 运行列表 + 详情抽屉三页签 + 归档）与 `MrpSuggestionList.vue`（建议列表 + 转采购申请 + 取消 + 净算过程），位于「计划管理」目录下（sort 78 / 79）；`views-compile.spec.ts` 实际编译并加载；`npm run build` 产物含 `MrpRunList-D1oXWkdZ.js`、`MrpSuggestionList-B8mYygLV.js` |
| API 可访问 | ✅ | `/api/v1/planning/mrp-runs/`（`create` / `{id}/demands` / `{id}/supplies` / `{id}/suggestions` / `{id}/archive`）与 `/api/v1/planning/mrp-suggestions/`（`{id}/convert` / `{id}/cancel`）；真实 HTTP 链路 **29 项检查全部通过**（`docs/test-report.md` §16.5） |
| 数据持久化 | ✅ | MySQL 真实写入并读回：`MRP202609180005`（7 需求行 / 3 供给行 / 5 建议）、转出 `PR202609180002`（草稿采购申请）、`DocumentLink` `MRP202609180005#2 → PR202609180002` |
| 权限生效 | ✅ | 匿名 403；只有 `planning.mrp.view` 的用户不能运行；有 `convert` 但无 `procurement.requisition.create` 仍被拒；公司 / 仓库范围生效；`planning.mrp.*` 不授予其它模块权限 |
| 状态迁移正确 | ✅ | 运行 `completed → archived`；建议 `open → converted / cancelled`；重复转单 409、过期建议 409、归档后转单 409、已取消转单 409、生产建议 409（均实测） |
| 异常处理明确 | ✅ | `COMPANY_REQUIRED`、`INVALID_BUCKET`、`INVALID_HORIZON`、`BOM_CYCLE_DETECTED`、`BOM_TOO_DEEP`、`SUGGESTION_ALREADY_CONVERTED`、`SUGGESTION_STALE`、`SUGGESTION_NOT_OPEN`、`MRP_RUN_NOT_ACTIVE`、`MATERIAL_INACTIVE`、`PRODUCTION_ORDER_NOT_IMPLEMENTED`、`REASON_REQUIRED` |
| 关键操作可审计 | ✅ | 运行创建、归档、建议转单、建议取消均写 `AuditLog`（数据库实测 5 条 MRP 相关记录，`reason` 落库） |
| 跨模块结果正确 | ✅（本增量范围内） | 只**读** `wms` 可用库存与 `procurement` 在途（`test_mrp_is_read_only_for_inventory` 断言前后库存零变化）；转单调用 `procurement.services.create_requisition()` 生成**草稿**，并写 `integration.DocumentLink`（`generated_from`）；Outbox 事件与业务同事务（`planning.mrp.completed` / `planning.mrp.suggestion_converted`） |
| 自动化测试实际执行 | ✅ | `tests/test_mrp.py` **32 例**；全量 `pytest backend/tests -q --reuse-db` → `301 passed`；前端 `vitest` → `129 passed`；`ruff` / `vue-tsc` / `vite build` 与 `scripts/smoke_check.ps1` 7 步全过 |
| 文档已更新 | ✅ | `docs/progress.md` §十五、`docs/requirements-matrix.md` §一之七与 REQ-10.6-01~11、`docs/data-model.md` §三 planning（MRP 4 表）与 §八（18 个迁移）、`docs/permission-matrix.md`（重生成 173 权限 / 56 菜单）、`docs/architecture.md` ADR-09~12、`docs/business-flows.md` §12.1、`docs/assumptions.md` §四之六、`docs/test-report.md` §十六 |
| 未完成内容明确列出 | ✅ | 见下方「未实现项」 |

**本增量明确的未实现项**（不得视为通过）：

- 采购提前期与批量规则（当前 `lot_for_lot`，不提前、不合并批量）；安全库存缓冲；
- **在制供给恒为 0**（`in_progress_supply=not_implemented`，等 MES）；替代料不参与展开；
- 需求来源仅销售订单（缺生产计划 / 预测 / 补货需求）；多工厂 / 多仓库独立净算；
- **生产建议转单未实现**（`PRODUCTION_ORDER_NOT_IMPLEMENTED` 是刻意拒绝，不是缺陷）；MRP Excel 导出；
- MRP 定时重算（Celery Beat）；MRP 成本卷算（阶段 7）。

**未执行的验证**：

- 真实多连接的**"同一建议并发转单"压测未执行**（当前靠 `select_for_update` + 状态机 + 行号唯一约束）；
- Outbox 事件仍为 `pending`（Celery Worker / Beat 未启动，**未执行**消费侧验证）；
- Playwright、浏览器截图级校验、高性能压测、备份恢复、MySQL 容器镜像（`mysql:8.0`）与 `mysqlclient` 驱动均未执行（与第七节口径一致）。

## 五之五、阶段 3 第四步验收（质量管理 QMS 首块）

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| 页面可操作 | ✅ | `views/qms/InspectionItemList.vue`、`InspectionOrderList.vue`、`QualityAlertList.vue`、`QualityIssueList.vue`，位于「质量管理」目录下（sort 85~89，排在「仓储管理」之后、「设备管理」之前）；`views-compile.spec.ts` 实际编译并加载；`router.spec.ts` 的菜单契约由 `frontend/tests/fixtures/menu-components.json`（139 项，按注册表运行顺序重新导出）覆盖；`npm run build` 产物含 4 个页面 chunk |
| API 可访问 | ✅ | `/api/v1/qms/inspection-items/`、`/inspections/`（`{id}/results/`、`submit/`、`judge/`、`close/`、`statistics/`）、`/alerts/`（`{id}/handle/`、`close/`、`create-issue/`）、`/issues/`（`{id}/publish/`、`archive/`），全部由 `tests/test_qms_api.py` 走真实 HTTP 验证 |
| 数据持久化 | ✅ | MySQL 真实写入并读回：`qms_qualityinspectionorder` / `qms_qualityinspectionresult` / `qms_qualityalert` / `qms_qualityissue`；`manage.py migrate` → `Applying qms.0001_initial... OK` |
| 权限生效 | ✅ | 匿名 403；只有 `.view` 的只读角色写入 403（**含 `results/` 的 POST 路径**）；跨公司写入 403 `OUT_OF_DATA_SCOPE`；四个台账均按公司收敛 |
| 状态迁移正确 | ✅ | 检验单 `draft → submitted → judged → closed`；报警 `open → handling → closed`；知识库 `draft → published → archived`；`status` / `judgement` 只读（PATCH 推不动）；跳步（草稿直接判定、无结果提交、报警未闭环关单、重复发布）一律 409 |
| 异常处理明确 | ✅ | `ITEM_NOT_QUANTITATIVE`、`MEASURED_VALUE_REQUIRED`、`RESULT_JUDGEMENT_REQUIRED`、`INSPECTION_NO_RESULT`、`INSPECTION_STATUS_INVALID`、`INVALID_JUDGEMENT`、`JUDGEMENT_CONFLICT`、`ALERT_CLOSE_REMARK_REQUIRED`、`QUALITY_ALERT_STATUS_INVALID`、`QUALITY_ISSUE_STATUS_INVALID`、`ITEM_COMPANY_MISMATCH` |
| 关键操作可审计 | ✅ | 结果录入、提交、判定（合格走 `approve`、不合格走 `reject` 并带判定说明）、关闭、报警处理 / 关闭、知识库发布 / 归档均写 `core` 审计 |
| 跨模块结果正确 | ✅（本增量范围内） | 只**引用** `masterdata` / `srm` / `factory` / `equipment` 台账，不修改它们的表；与 `procurement.receipt.inspect`、`wms` 质量放行**并行**，不做隐式联动（`test_material_must_belong_to_same_company` 锁定同公司约束） |
| 自动化测试实际执行 | ✅ | `tests/test_qms_api.py` **14 例**；全量 `pytest tests -q --reuse-db` → `438 passed in 242.34s`；前端 `vitest` → 15 文件 / 253 项；`ruff` / `vue-tsc` / `vite build` 全过 |
| 文档已更新 | ✅ | `docs/progress.md` §三十一、`docs/requirements-matrix.md` §一之二十一与 §10.9 逐条状态、`docs/data-model.md` §十一、`docs/api-conventions.md` §一与质量约定、`docs/permission-matrix.md`（重生成 350 权限 / 139 菜单）、`docs/architecture.md` §三、`docs/assumptions.md` §四之八、`docs/test-report.md` §三十、面向客户的 `docs/user-guide.md`（+ 网页版）、`AGENTS.md` 事实行 |
| 未完成内容明确列出 | ✅ | 见下方「未实现项」 |

**本增量明确的未实现项**（不得视为通过）：

- **检验标准版本快照**：检验单不保存项目标准的历史快照，改标准会影响历史单据的解读；
- **不合格处置工单**：返工 / 退货 / 报废的处置流程未做（本轮只做合格 / 不合格 / 让步接收 + 报警闭环）；
- **检测仪器直连**：结果全部人工录入，没有在线检测分析设备的采集接口；
- **与既有质量路径尚未接线**：`procurement.receipt.inspect`（收货单人工判定）与 `wms` 质量放行仍是独立路径，
  QMS 检验单没有取代它们；按工艺路线 `is_quality_gate` 决定质检点需要 MES 落地后一并做；
- 质量统计的定时快照与同环比、性能压测。

**未执行的验证**：

- **浏览器截图级校验未执行**（沙箱内无法启动 `runserver` / `vite dev`，浏览器自动化被策略拦截）：
  4 个新页面与「录入结果」弹窗只做了源码级与构建级验证；
- 真实检测设备 / 在线检测仪器的联调**未执行**（没有设备可接）；
- 与第七节口径一致：Playwright、高性能压测、备份恢复、容器环境启动验证均未执行。

## 五之六、阶段 3 第三步验收（生产执行 MES）

| 验收项 | 结果 | 证据 |
| --- | --- | --- |
| 页面可操作 | ✅ | `views/mes/ProductionOrderList.vue`、`ProductionReportList.vue`，位于「生产执行」目录下（sort 79，排在「计划管理」之后、「仓储管理」之前）；`views-compile.spec.ts` 实际编译并加载；`router.spec.ts` 菜单契约由 `frontend/tests/fixtures/menu-components.json`（142 项）覆盖；`npm run build` 产物含 2 个页面 chunk |
| API 可访问 | ✅ | `/api/v1/mes/orders/`（`{id}/materials/`、`steps/`、`statistics/`、`release/`、`issue-materials/`、`report/`、`complete/`、`receipt/`、`close/`、`cancel/`）、`/api/v1/mes/reports/`，全部由 `tests/test_mes_api.py` 走真实 HTTP 验证 |
| 数据持久化 | ✅ | MySQL 真实写入并读回：`mes_productionorder` / `mes_productionordermaterial` / `mes_productionorderstep` / `mes_productionreport`；`manage.py migrate` → `Applying mes.0001_initial... OK` |
| 权限生效 | ✅ | 匿名 403；只有 `.view` 的只读角色写入 403；跨公司写入 403 `OUT_OF_DATA_SCOPE`；四张表均按公司收敛（`test_company_scope_hides_other_company_orders`）；质检点自动开单内部校验 `qms.inspection.create`（缺权整笔回滚） |
| 状态迁移正确 | ✅ | 工单 `draft → released → in_progress → completed → closed`，`draft / released → cancelled`；非草稿 `PATCH` 报 **409 `STATE_CONFLICT`**；未下达就领料 / 报工、工序未完就完工、质检点未判定就完工均 409 |
| 快照冻结正确 | ✅ | 下达即写入 `bom_snapshot` / `routing_snapshot`；BOM 展开用量按含损耗计算（2.8×1.06×10 = 29.68）；工程数据派生新版本后已下达工单的用料与工序不变（`test_release_freezes_snapshot_and_expands_bom`） |
| 报工守恒 | ✅ | 合格 + 返工 + 报废 ≠ 报工量 → `QUANTITY_MISMATCH`；同一工序累计超计划 → `OVER_PRODUCTION`；报工台账**只读、不可回改**（无 PATCH 路由） |
| 库存经统一服务 | ✅ | 领料与完工入库均调 `apps/wms/services/stock.py` 生成并过账库存单（`issue_document` / `receipt_document`），MES 不写库存余额；幂等重放返回首次结果，重复请求报 `MATERIAL_ALREADY_ISSUED` / `RECEIPT_ALREADY_POSTED` |
| 异常处理明确 | ✅ | `ROUTING_REQUIRED`、`ROUTING_EMPTY`、`BOM_REQUIRED`、`BOM_EMPTY`、`INVALID_QUANTITY`、`QUANTITY_MISMATCH`、`OVER_PRODUCTION`、`QUALITY_GATE_NOT_PASSED`、`STEPS_NOT_FINISHED`、`STEP_ALREADY_COMPLETED`、`STEP_ORDER_MISMATCH`、`MATERIAL_ALREADY_ISSUED`、`NOTHING_TO_ISSUE`、`RECEIPT_ALREADY_POSTED`、`NOTHING_TO_RECEIPT`、`STATE_CONFLICT`、`REASON_REQUIRED`、`WAREHOUSE_REQUIRED`、`STYLE_INACTIVE`、`COMPANY_STYLE_MISMATCH`、`SKU_STYLE_MISMATCH`、`DUPLICATE_MATERIAL` |
| 关键操作可审计 | ✅ | 建单、修改、下达、领料、报工、完工、入库、关闭、取消均写 `core` 审计，并写 `integration.Outbox`（`ORDER_RELEASED` / `ORDER_COMPLETED`） |
| 跨模块结果正确 | ✅ | MRP 生产建议转单 → 草稿工单 + `DocumentLink`；MRP 在制供给取已下达 / 生产中工单未完工量；质检点报满自动开 QMS 检验单；入库走 `wms` 库存服务 |
| 自动化测试实际执行 | ✅ | `tests/test_mes_api.py` **32 例**；全量 `pytest tests -q --reuse-db` 见 `docs/test-report.md` §三十一；前端 `vitest` → 15 文件 / 255 项；`ruff` / `vue-tsc` / `vite build` 全过 |
| 文档已更新 | ✅ | `docs/progress.md` §三十二、`docs/requirements-matrix.md` §一之二十二与 §10.7 逐条状态、`docs/data-model.md` §十二、`docs/api-conventions.md` §一与生产执行约定、`docs/permission-matrix.md`（重生成 360 权限 / 142 菜单）、`docs/architecture.md` §三与 ADR-08 / ADR-11、`docs/assumptions.md` §四之九、`docs/business-flows.md` §十六、`docs/test-report.md` §三十一、面向客户的 `docs/user-guide.md`（+ 网页版）、`AGENTS.md` 事实行 |
| 未完成内容明确列出 | ✅ | 见下方「未实现项」 |

**本增量明确的未实现项**（不得视为通过）：

- **线体排产**：工单可指定厂区 / 车间 / 线体，但没有排产优化与产能冲突检查；
- **裁剪任务 / 裁片批次**：未建模；
- **工位派工**：工序不指定工位，没有派工与接单动作；
- **在制品转移与返工工单**：返工以报工类型体现，没有独立的返工工单；
- **扫码 / RFID 与硬件控制**：无协议不伪造，报工全部人工；
- **工序级良率与 OEE**：需设备运行时长，本轮未算；
- **工单成本与实际工时汇总**：报工记录实际工时，但不计算成本。

**未执行的验证**：

- **浏览器截图级校验未执行**（沙箱内无法启动 `runserver` / `vite dev`，浏览器自动化被策略拦截）：
  2 个新页面与「报工」弹窗只做了源码级与构建级验证；
- **并发报工 / 并发领料的多连接压测未执行**（幂等与锁已用例覆盖，但未做真实多连接竞争）；
- 与第七节口径一致：Playwright、高性能压测、备份恢复、容器环境启动验证均未执行。

## 六、逐条对照 19.3 完成标准

| 标准 | 阶段 0/1 情况 |
| --- | --- |
| 页面可操作 | ✅ 41 个业务页面 + 登录/403/404；`views-compile.spec.ts` 保证可编译 |
| API 可访问 | ✅ 19/19 HTTP 端到端验证通过 |
| 数据持久化 | ✅ MySQL 实际写入并读回（新建物料 id=66，读回一致） |
| 权限生效 | ✅ 未登录 403；跨角色 403；缺 CSRF 写操作 403 |
| 状态迁移正确 | ✅ 审批状态机（提交/通过/驳回/撤回）有测试 |
| 异常处理明确 | ✅ 统一错误结构；重复编码 400、分页超限 400、幂等冲突 409 |
| 关键操作可审计 | ✅ 审计与业务同事务写入，且有实际断言 |
| 跨模块结果正确 | ⚠️ 采购侧「申请 → 订单 → 收货 → 待检 → 放行 → 合格库存」、销售侧「订单 → 占用 → 发货 → 退货 → 检验」、**MRP 侧「销售订单 → 净算 → 采购建议 → 草稿采购申请」均已打通、幂等、可审计**；但 MES 与生产领料/报工/成品入库未实现，因此「订单到交付」整条闭环**仍未打通**（阶段 3 第三步） |
| 自动化测试实际执行 | ✅ 后端 **307** + 前端 **129** + 真实 HTTP 链路 **29**（MRP）/ 19（阶段 0/1），均为真实输出 |
| 文档已更新 | ✅ 16 份文档，含未执行清单 |
| 未完成内容明确列出 | ✅ 见下节 |

## 七、本轮未通过 / 未执行项（不得视为通过）

| 项 | 状态 | 原因 |
| --- | --- | --- |
| Docker Compose 构建与启动 | **未执行** | 本机 Docker 守护进程不可达 |
| `mysqlclient` 生产驱动验证 | **未执行** | 本地 Windows 无 C 工具链，开发用 PyMySQL |
| Celery Worker / Beat 实际运行 | **未执行** | 未启动进程验证任务执行与调度 |
| Playwright 端到端测试 | **未执行** | 仅配置就绪 |
| 硬件采集 / 模拟器 | **未执行** | 阶段 5 |
| 备份恢复演练 | **未执行** | 阶段 7 |
| 性能压测 | **未执行** | 阶段 7（需先确定部署资源） |
| 供应商五维量化评价（权重配置 / 评价单 / 缺数据口径 / 只读统计） | **已通过阶段验收** | 阶段 2 深化（本轮），详见 `docs/progress.md` §三十三；**寻源与报价仍未开始** |
| 寻源 / 报价 / 准入审批流程 | **未开始** | 阶段 2 剩余增量 |
| 采购：询价比价、到货差异、退货、应付与付款登记、采购分析报表、单据打印 | **未开始** | 阶段 2 采购模块剩余增量（主体链路已完成） |
| 销售发货、退货与库存占用 | **已通过阶段验收** | 阶段 2 第四步，详见 §五之二 |
| 销售计划、折扣、订单变更版本快照、分销商、基础预测、应收与收款登记、跨维度拆分占用 | **未开始** | 阶段 2 销售模块剩余增量 |
| MRP 净算、缺料建议与建议转单 | **已通过阶段验收** | 阶段 3 第二步，详见 §五之四；**提前期与批量规则、安全库存未实现**；**在制供给与生产建议转 MES 工单已随 MES 落地**（§五之六） |
| 生产领料、工序报工、生产工单与完工入库 | **已通过阶段验收** | 阶段 3 第三步，详见 §五之六；**线体排产、裁剪任务、工位派工、在制品转移、扫码 / 硬件控制、工序良率 / OEE 未实现** |
| 跨仓调拨与盘点 | **未开始** | 阶段 3 剩余增量（统一库存服务、采购、销售、MRP、MES 已完成） |
| 质量管理（QMS）检验项目 / 检验单与判定 / 质量报警 / 质量问题知识库 | **已通过阶段验收** | 阶段 3 第四步首块，详见 §五之五；**检验标准版本快照、返工 / 报废处置工单、检测仪器直连、与采购收货放行的接线未实现** |
| MES 剩余的线体排产 / 裁剪任务 / 工位派工 / 在制品转移 | **未开始** | 阶段 3 剩余增量（工单与报工已完成） |
| EAM / EMS / EHS / 厂内物流 / 设备数采 / 客户服务深化 | **已通过阶段验收** | 阶段 4–6，详见 §五之三 |

## 八、验收结论

- **阶段 0：通过（含 1 项部分完成）** —— 唯一部分完成项是 Docker Compose 未实际启动验证，
  已在 `docs/progress.md` 与本文档中明确标注，未虚假声明完成。
- **阶段 1：通过（本地开发环境）** —— 登录到主数据维护闭环可用、有权限、可审计、有测试。
- **阶段 2 第一步：通过** —— 客户与供应商主数据可用、有权限、有审计、有 22 条真实用例。
- **阶段 2 核心（库存）：通过（含未实现项声明）** —— 统一库存服务与质量放行可用、幂等、并发安全、可审计，36 条新用例；
  **跨仓调拨、盘点、冻结/占用动作与库存成本未实现**，不得视为通过。
- **阶段 2 采购模块：通过（含未实现项声明）** —— 采购申请、订单、收货、来料检验放行链路可用、有权限、可审计，
  35 条新用例（含多行逐行放行、幂等重放与枚举字典）；**询价比价、到货差异、退货、应付与付款登记、
  采购分析报表、单据打印、供应商准入审批流程未实现**，不得视为通过。
- **阶段 2 销售模块：通过（含未实现项声明）** —— 销售订单、库存占用、发货出库、退货入库与检验判定链路可用、有权限、可审计，34 条新用例；
  **销售计划、颜色尺码矩阵批量录入、折扣、订单变更版本快照、分销商、基础预测、应收与收款登记、
  跨维度自动拆分占用、多批次部分退货的批次分摊未实现**，不得视为通过。
- **阶段 3 第一步（BOM 与工艺路线版本快照）：通过（含未实现项声明）** —— 版本化工程数据、
  审批后冻结、派生新版本不覆盖已审核版本、作废留痕、快照输出可用，有权限、可审计，50 条新用例；
  **（本增量当期）MES 工单与报工、QMS 检验单、快照落库、BOM 成本卷算未实现**，不得视为通过；
  其中**MES 工单与报工、快照落库已在阶段 3 第三步交付**（§五之六）。
- **阶段 3 第二步（MRP）：通过（含未实现项声明）** —— 时间分段净算、多层 BOM 展开与损耗、
  循环 BOM 检查、缺料清单、采购 / 生产建议、供需追溯、计算快照、采购建议转**草稿**采购申请可用，
  有权限、可审计、对库存只读，32 条新用例 + 29 项真实 HTTP 链路检查；
  **（本增量当期）在制供给、提前期与批量规则、替代料展开、生产建议转工单未实现**，不得视为通过；
  其中**在制供给与生产建议转草稿工单已在阶段 3 第三步交付**（§五之六），提前期 / 批量规则与替代料展开仍未做。
- **阶段 3 第四步（质量管理 QMS）首块：通过（含未实现项声明）** —— 检验项目、检验单与结果录入、
  **定量项由服务层按标准上下限自动判定**、判定不合格**自动生成唯一质量报警**、报警未闭环时单据关不掉、
  质量问题知识库（发布 / 归档、来源链路）、按明细实时聚合的质量动态监测可用，有权限、可审计，14 条新用例；
  **检验标准版本快照、返工 / 退货 / 报废处置工单、检测仪器直连、与 `procurement.receipt.inspect`
  及 `wms` 质量放行的接线未实现**，不得视为通过；
  其中**按 `is_quality_gate` 决定质检点已随 MES 落地**（工序报满自动开 QMS 检验单，§五之六）。
- **阶段 3 第三步（生产执行 MES）：通过（含未实现项声明）** —— 生产工单（下达冻结 BOM / 工艺快照、BOM 展开用料、工艺生成工序）、
  领料与完工入库经统一库存服务、报工守恒与超产拦截、质检点自动开检验单并作为完工硬门、状态机与数据范围可用，
  有权限、可审计，32 条新用例；**线体排产、裁剪任务 / 裁片批次、工位派工、在制品转移与返工工单、扫码 / RFID 与硬件控制、工序良率与 OEE、工单成本未实现**，不得视为通过。
- **供应商五维量化评价（阶段 2 深化）：通过（含未实现项声明）** —— 权重配置（合计必须正好 100%、只增不改的版本派生）、
  评价单（草稿 → 已生效 → 已归档，五维各一行，总分与等级只由服务层按权重快照计算）、
  缺数据的两种口径（`mark_missing` 不给等级 / `redistribute` 合计精确 100%）与按明细实时聚合的评价统计可用，
  有权限、可审计、有数据范围，**18 条新用例**；**评价不自动回写** `Supplier.grade`（刻意设计），
  **供应商寻源与报价未实现**，不得视为通过。
- **不声称**已完成全部平台。阶段 2 的销售计划与预测、供应商寻源与报价，
  以及阶段 3 剩余部分（跨仓调拨与盘点、线体排产、裁剪任务与工位派工、在制品转移）尚未开始；
  跨系统数据交换中间件、工业终端安全（防病毒与补丁管理）、
  EMS 能源调度、EAM 的 OEE 统计、EHS 职业健康同样未开始。
- **界面样式增量：通过（含未执行项声明）** —— 左侧导航一级目录与二级页面按层级区分，
  各视图重复手写的面板/区块标题/统计卡/代码块下沉为共享样式类（视图内重名定义 4 → 0），
  新增 `side-menu.spec.ts`（10 项）与 `styles.spec.ts`（31 项）契约测试；
  **浏览器截图级像素校验与暗色主题未执行**，不得视为通过。
- **窄屏响应式增量：通过（含未执行项声明）** —— 侧边栏 ≤1200px 自动折叠（手动偏好优先、跨断点重置），表格改为容器内横向滚动，统计卡由固定 `:span` 栅格改为共享 flex 栅格，新增 `responsive.spec.ts` 15 条；
  **≤768px 手机布局、触摸手势与真机观感未经人工确认**，不得视为通过。

## 九、下一阶段依赖（阶段 2 剩余部分）

1. 库存口径与「冻结/占用」互斥方案**已按「互斥数量桶 + 检查约束」实现并测试**（`docs/inventory-rules.md` 第三、八节）；
   若业务上需要「同一数量同时冻结与占用」，属口径变更，需重新评估。
2. 需要确认是否启用对象存储（附件在阶段 1 使用本地文件系统）。
3. 建议先在有 Docker 的环境验证 Compose，再进入阶段 2，避免基座问题被业务代码放大。
4. **已完成**：收货可直接入待检库（`quality_status=quarantine`），只有经质量放行
   才能变为可动用的合格库存；待检/不合格库存出库被拒绝（任务书第十七章补充说明）。
5. **已完成**：供应商五维评价的权重模型（质量 / 技术 / 响应 / 交付 / 成本，**合计必须正好 100%**）与「无数据不记零分」口径（`mark_missing` / `redistribute` 两种策略）已按任务书 10.4 落地并有用例覆盖（`docs/progress.md` §三十三）。**仍未做**：供应商寻源与报价。
6. **已完成**：`dimension_key` 单列 UNIQUE 规范化键 + 并发测试（必测案例 6、7、8）。
   **采购单据与销售单据均已接入该服务**（收货过账 → 待检 / 检验放行 → 合格；销售发货出库、退货入库、检验放行）；
   下一步：
   实现跨仓调拨在途与盘点范围冻结。
7. **已完成**：采购侧「实物到货 / 库存记账 / 质量放行」三者分离（`docs/business-flows.md` §12.1）。
   阶段 3 QMS 检验单落地后，`receipt.inspect` 的人工判定应升级为引用检验单结果，并保留人工录入兜底。
8. **已完成**：阶段 3 第二步（MRP）已按「按日 / 按周两种分段 + 销售订单为唯一需求来源」实现，
   派生需求按低层码只净算一次（必测案例 12 已覆盖）。**仍未处理**：采购提前期与批量规则、
   安全库存、在制供给、替代料展开——这些依赖 MES 工单与供应商交期数据。
   **开工前需确认**：是否需要多工厂 / 多仓库维度的独立净算（当前按公司 + 可选单仓过滤）。
9. **已完成**：阶段 3 第三步（MES 工单）已在 `apps/mes` 落地，下达时保存
   `build_bom_snapshot()` / `build_routing_snapshot()` 到工单的 JSON 快照字段（`bom_snapshot` / `routing_snapshot`，
   不单独建快照表，见 ADR-08）；`docs/data-model.md` §十二已与工单快照字段对齐。
10. **已完成（接线部分）**：MES 工单下达时把 `is_quality_gate` 工序标记为质检点，
    报满自动开 QMS 检验单，并作为工单完工的硬门。
    **仍待做**：与 `procurement.receipt.inspect` 的升级路径共用同一检验单实体。
