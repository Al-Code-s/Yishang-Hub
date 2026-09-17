# 阶段验收记录（docs/acceptance.md）

> 验收依据：任务书 19.3「完成标准」。**「页面已存在」不等于「已通过阶段验收」。**
> 所有数字来自本轮**实际执行**的命令输出，原始记录见 `docs/test-report.md`。

## 一、阶段 0 验收

| 任务书条目 | 交付物 | 证据 | 结论 |
| --- | --- | --- | --- |
| 20.1.1 检查仓库 | 仓库检查结论 | 仓库为单次 `Initial commit`，无既有业务代码，未覆盖任何内容 | ✅ |
| 20.1.3 需求追踪矩阵 | `docs/requirements-matrix.md` | 覆盖任务书全部章节，含实施边界标注 | ✅ |
| 20.1.4 架构/数据模型/权限文档 | `architecture.md`、`data-model.md`、`permission-matrix.md` | 文档存在且与代码一致（权限表由注册表生成） | ✅ |
| 20.1.5 初始化工程 | Vue 3 + TS + Vite 6；Django 5.2 + DRF | `npm run build` 成功；`manage.py check` 无问题 | ✅ |
| 20.1.6 配置 MySQL/Redis/对象存储/Compose | 配置与 `compose.yaml` | MySQL 8.0.17 连通（阶段 0 快照 62 张表；**当前 71 张**，utf8mb4_0900_ai_ci，严格模式）；Redis 3.2.100 连通。**Compose 未启动验证** | ⚠️ 部分 |
| 20.1.7 自定义 User 模型 | `identity.User` | `AUTH_USER_MODEL=identity.User`，首次迁移即启用 | ✅ |
| 20.1.15 初始化与演示命令 | `bootstrap_system`、`seed_demo` | 幂等（重复执行不重复建）、`seed_demo` 拒绝生产环境 | ✅ |
| 20.1.16 迁移/测试/检查/构建 | 见 `test-report.md` | 后端 112 通过；前端 60 通过；Ruff 通过；类型检查通过；构建成功 | ✅ |
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
## 六、逐条对照 19.3 完成标准

| 标准 | 阶段 0/1 情况 |
| --- | --- |
| 页面可操作 | ✅ 38 个业务页面 + 登录/403/404；`views-compile.spec.ts` 保证可编译 |
| API 可访问 | ✅ 19/19 HTTP 端到端验证通过 |
| 数据持久化 | ✅ MySQL 实际写入并读回（新建物料 id=66，读回一致） |
| 权限生效 | ✅ 未登录 403；跨角色 403；缺 CSRF 写操作 403 |
| 状态迁移正确 | ✅ 审批状态机（提交/通过/驳回/撤回）有测试 |
| 异常处理明确 | ✅ 统一错误结构；重复编码 400、分页超限 400、幂等冲突 409 |
| 关键操作可审计 | ✅ 审计与业务同事务写入，且有实际断言 |
| 跨模块结果正确 | ⚠️ 采购侧「申请 → 订单 → 收货 → 待检 → 放行 → 合格库存」已打通且幂等、可审计；但销售订单、MRP、MES 与销售发货未实现，因此「订单到交付」整条闭环**仍未打通** |
| 自动化测试实际执行 | ✅ 后端 183 + 前端 66 + HTTP 19，均为真实输出 |
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
| 寻源 / 报价 / 供应商评分 / 准入审批流程 | **未开始** | 阶段 2 剩余增量 |
| 采购：询价比价、到货差异、退货、应付与付款登记、采购分析报表、单据打印 | **未开始** | 阶段 2 采购模块剩余增量（主体链路已完成） |
| 销售单据、MRP、跨仓调拨与盘点 | **未开始** | 阶段 2 主体剩余（**统一库存服务与采购模块已完成**） |
| 库存 / MRP / MES / QMS / EAM / EMS / EHS 等 | **未开始** | 阶段 2–6 |

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
- **不声称**已完成全部平台。阶段 2 的销售与供应商评价等能力尚未开始。

## 九、下一阶段依赖（阶段 2 剩余部分）

1. 库存口径与「冻结/占用」互斥方案**已按「互斥数量桶 + 检查约束」实现并测试**（`docs/inventory-rules.md` 第三、八节）；
   若业务上需要「同一数量同时冻结与占用」，属口径变更，需重新评估。
2. 需要确认是否启用对象存储（附件在阶段 1 使用本地文件系统）。
3. 建议先在有 Docker 的环境验证 Compose，再进入阶段 2，避免基座问题被业务代码放大。
4. **已完成**：收货可直接入待检库（`quality_status=quarantine`），只有经质量放行
   才能变为可动用的合格库存；待检/不合格库存出库被拒绝（任务书第十七章补充说明）。
5. 供应商寻源/报价/评分需先确认权重模型与「无数据不记零分」的实现口径（任务书 10.4）。
6. **已完成**：`dimension_key` 单列 UNIQUE 规范化键 + 并发测试（必测案例 6、7、8）。
   **采购单据已接入该服务**（收货过账 → 待检，检验放行 → 合格）；下一步：销售单据接入，
   并实现跨仓调拨在途与盘点范围冻结。
7. **已完成**：采购侧「实物到货 / 库存记账 / 质量放行」三者分离（`docs/business-flows.md` §12.1）。
   阶段 3 QMS 检验单落地后，`receipt.inspect` 的人工判定应升级为引用检验单结果，并保留人工录入兜底。