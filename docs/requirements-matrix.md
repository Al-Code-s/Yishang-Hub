# 需求追踪矩阵（docs/requirements-matrix.md）

> 覆盖范围：任务书全部条目。每条需求必须给出「实现位置」「合并到哪个共享功能」或「实施边界」，
> 不允许静默遗漏。原始编号存在重复的，按 `REQ-<章节>-<序号>` 重新编号并保留来源章节映射。
>
> 状态定义（任务书 19.2）：未开始 / 设计中 / 开发中 / 待测试 / 已通过阶段验收 / 受外部条件阻塞。
> **「页面已存在」不等于「已通过阶段验收」**：只有当页面可操作、API 可访问、数据持久化、权限生效、
> 状态迁移正确、异常处理明确、关键操作可审计、跨模块结果正确、自动化测试实际执行、文档已更新时，
> 才可能通过阶段验收。阶段 0/1 的验收结论见 `docs/acceptance.md`。

## 一、阶段 0 与阶段 1 需求（必须完成项）

| 编号 | 来源 | 业务模块 | 页面 | API | 数据实体 | 业务规则 | 测试案例 | 阶段 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| REQ-20-01 | 20.1.1 | 平台 | — | — | — | 先检查仓库再修改，不覆盖已有有效代码 | 人工检查 | 0 | 已完成 | 本轮为首次提交，仓库无既有业务代码 |
| REQ-20-02 | 20.1.2 | 平台 | — | — | — | 输出简要现状与改造计划 | — | 0 | 已完成 | 见 `docs/progress.md` |
| REQ-20-03 | 20.1.3 | 平台 | — | — | — | 建立需求追踪矩阵 | — | 0 | 已完成 | 本文件 |
| REQ-20-04 | 20.1.4 | 平台 | — | — | — | 架构、数据模型、权限文档 | — | 0 | 已完成 | `architecture.md`、`data-model.md`、`permission-matrix.md` |
| REQ-20-05 | 20.1.5 | 平台 | — | — | — | 初始化 Vue 与 Django 工程 | `manage.py check`、`npm run build` | 0 | 已完成 | 前后端均可构建 |
| REQ-20-06 | 20.1.6 | 平台 | — | `/readyz` | — | 配置 MySQL、Redis、对象存储与 Compose | `test_health_ready_checks_database` | 0 | 部分完成 | 本地 MySQL/Redis 已连通；对象存储与 Compose 未启动验证 |
| REQ-20-07 | 20.1.7 | 身份 | 用户管理 | `identity/users/` | `identity.User` | 首次迁移即使用自定义 User | 全套 identity 用例 | 0/1 | 已完成 | `AUTH_USER_MODEL=identity.User` |
| REQ-20-08 | 20.1.8 | 身份 | 登录 / 个人中心 | `identity/auth/*` | Session、LoginAttempt | 会话登录、CSRF（**含登录接口**）、退出、改密 | `test_auth_api.py`（14 项） | 1 | 已完成 | 含登录限流与失败锁定；登录 CSRF 于阶段 3 第二步补齐（`@method_decorator(csrf_protect, name="dispatch")`） |
| REQ-20-09 | 20.1.9 | 身份 | 角色与权限 | `identity/roles/*` | Role、Permission、Menu、RoleScopeGrant | 角色、权限点、数据范围 | `test_permissions.py`（17 项） | 1 | 已完成 | 四层权限 |
| REQ-20-10 | 20.1.10 | 组织 | 公司/部门/工厂/员工 | `factory/*` | Company、Department、Factory、Employee | 组织层级合法、跨公司拒绝 | `test_factory_api.py`、`test_permissions.py` | 1 | 已完成 | 车间/线体/工位/班次/班组同页提供 |
| REQ-20-11 | 20.1.11 | 主数据 | 款式/颜色/尺码/SKU/物料 | `masterdata/*` | Style、Color、Size、Sku、Material | 款式+颜色+尺码 唯一确定 SKU | `test_smoke_api.py::test_sku_generate_endpoint` | 1 | 已完成 | SKU 与成品物料一对一 |
| REQ-20-12 | 20.1.12 | 仓储 | 仓库/库区/储位 | `wms/*` | Warehouse、Zone、Location | 层级归属与唯一编码 | `test_smoke_api.py::test_warehouse_zone_location_tree` | 1 | 已完成 | 阶段 1 不含库存余额与流水 |
| REQ-20-13 | 20.1.13 | 平台 | 后台布局/菜单/首页 | `identity/auth/session/`、`analytics/dashboard/` | Menu | 菜单由后端按权限下发 | `router.spec.ts`（菜单组件一致性） | 1 | 已完成 | 无权限的页面不注册路由 |
| REQ-20-14 | 20.1.14 | 平台 | 待办/我的申请/审批模板 | `workflow/*` | ApprovalTemplate、ApprovalInstance | 顺序多级、条件路由、快照 | `test_workflow_api.py`（10 项） | 1 | 已完成 | 审批与库存过账分离 |
| REQ-20-15 | 20.1.15 | 平台 | — | — | — | 初始化与演示命令 | `test_management_commands.py`（8 项） | 1 | 已完成 | `bootstrap_system`、`seed_demo` 幂等 |
| REQ-20-16 | 20.1.16 | 平台 | — | — | — | 迁移、测试、检查、构建 | 见 `docs/test-report.md` | 0/1 | 已完成 | 后端 **332** + 前端 **181** 项通过；一键冒烟 7 步全过；真实 HTTP 链路 29 项通过（含阶段 2 四步、界面样式 / 视图统一 / 窄屏响应式、阶段 3 第一步 BOM 与工艺版本快照、**阶段 3 第二步 MRP**、**数值显示口径 2 位小数**、**权限一级分组中文名**、**登录页商用化改版**、**登录后落地页与全站文案去开发化**、**内部协同业务对象中文化 + 冒烟脚本拆除竞态修复**） |
| REQ-20-17 | 20.1.17 | 平台 | 实施进度 | — | — | 更新进度文档 | — | 0/1 | 已完成 | `docs/progress.md` |
| REQ-20-18 | 20.1.18 | 平台 | — | — | — | 输出访问地址、启动命令、验证步骤、未完成项 | — | 0/1 | 已完成 | `README.md`、`docs/deployment.md`、`docs/progress.md` |

## 一之二、阶段 2 第一步增量交付清单（本轮实际完成）

任务书 §17 要求「每阶段功能范围以需求追踪矩阵明确，不使用『基础功能』这类模糊词替代交付清单」。
本表即为本轮增量的完整清单；**未列出的能力即未实现**。

| 交付项 | 页面（前端组件） | API | 数据实体 | 权限点 | 自动化用例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 客户档案 | `views/crm/CustomerList.vue` | `/api/v1/crm/customers/` | `crm.Customer` | `crm.customer.view/create/update/deactivate` | `test_crm_api.py`（6 项） | 已通过阶段验收 |
| 客户联系人 | `views/crm/CustomerContactList.vue` | `/api/v1/crm/customer-contacts/` | `crm.CustomerContact` | `crm.customer_contact.view/create/update` | `test_crm_api.py`（4 项） | 已通过阶段验收 |
| 客户枚举字典 | — | `/api/v1/meta/`（`customer_categories/levels/statuses`） | 枚举类 | — | `test_meta_exposes_crm_and_srm_enums` | 已通过阶段验收 |
| 供应商档案 | `views/srm/SupplierList.vue` | `/api/v1/srm/suppliers/` | `srm.Supplier` | `srm.supplier.view/create/update/deactivate` | `test_srm_api.py`（6 项） | 已通过阶段验收 |
| 供应商联系人 | `views/srm/SupplierContactList.vue` | `/api/v1/srm/supplier-contacts/` | `srm.SupplierContact` | `srm.supplier_contact.view/create/update` | `test_srm_api.py`（3 项） | 已通过阶段验收 |
| 供应商资质与有效期 | `views/srm/SupplierQualificationList.vue` | `/api/v1/srm/supplier-qualifications/` | `srm.SupplierQualification` | `srm.supplier_qualification.view/create/update` | `test_srm_api.py`（5 项） | 已通过阶段验收 |
| 供应商枚举字典 | — | `/api/v1/meta/`（`supplier_categories/grades/admission_statuses/qualification_types`） | 枚举类 | — | `test_meta_exposes_crm_and_srm_enums` | 已通过阶段验收 |
| 演示数据 | — | — | 客户/供应商/联系人/资质 | — | `seed_demo` 二次执行新建 0 条 | 已通过阶段验收 |

**明确未包含**：寻源、候选供应商、准入审批流程、可供物料与报价、供应商评分评价、
供应商资质到期提醒定时任务、客户跟进/服务工单/投诉/满意度、采购与销售单据、库存余额与流水。
这些条目在 §10.2、§10.4 中逐条标注为「未开始」或「部分完成」，并给出计划阶段。

## 一之三、阶段 2 核心增量：统一库存服务（本轮实际完成）

| 交付项 | 页面（前端组件） | API | 数据实体 | 权限点 | 自动化用例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 库存余额（只读） | `views/wms/InventoryBalanceList.vue` | `GET /api/v1/wms/inventory-balances/` | `wms.InventoryBalance` | `wms.inventory.view` | `test_wms_inventory.py` | 已通过阶段验收 |
| 库存流水（只读、只追加） | `views/wms/InventoryTransactionList.vue` | `GET /api/v1/wms/inventory-transactions/` | `wms.InventoryTransaction` | `wms.inventory.view` | `test_ledger_is_append_only`、`test_inventory_read_apis_reject_writes` | 已通过阶段验收 |
| 库存单据（草稿/过账/冲销） | `views/wms/InventoryDocumentList.vue` | `/api/v1/wms/inventory-documents/` + `post/`、`reverse/` | `wms.InventoryDocument` / `InventoryDocumentLine` | `wms.document.view/create/update/post/reverse` | `test_document_lifecycle_over_api` 等 | 已通过阶段验收 |
| 质量放行 | 同上（弹窗） | `POST /api/v1/wms/inventory-documents/{id}/release-quality/` | 同上（QUALITY 单） | `wms.quality.release` | `test_api_release_quality`、`test_release_quality_moves_stock_between_statuses` | 已通过阶段验收 |
| 幂等过账 | 同上（`Idempotency-Key` 头） | 同上 | `wms.InventoryTransaction.idempotency_key` | `wms.document.post` | `test_same_idempotency_key_posts_once`、`test_api_idempotency_key_deducts_once` | 已通过阶段验收 |
| 并发安全（余额行创建 / 出库 / 移库） | — | — | `dimension_key` UNIQUE + 行锁 | — | `test_concurrent_balance_creation_yields_single_row`、`test_concurrent_issue_never_produces_negative_stock`、`test_concurrent_transfer_keeps_total` | 已通过阶段验收 |
| 库存枚举字典 | — | `/api/v1/meta/`（5 个新键） | 枚举类 | — | `test_meta_exposes_inventory_enums` | 已通过阶段验收 |
| 演示数据 | — | — | 6 张单据 + 1 张质量放行单 | — | `seed_demo` 二次执行新建 0 条 | 已通过阶段验收 |

**明确未包含**：跨仓调拨与在途状态、盘点与范围冻结、冻结/解冻与占用/释放的业务动作入口、
库位推荐、标签打印、库存成本与移动加权平均、采购与销售单据
（**采购单据已在下一增量完成，见 §一之四**；销售单据仍未开始）。
这些条目在 §10.8 中逐条标注。

## 一之四、阶段 2 第三步增量：采购模块（本轮实际完成）

| 交付项 | 页面（前端组件） | API | 数据实体 | 权限点 | 自动化用例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 采购申请（含行、类型、审批） | `views/procurement/RequisitionList.vue` | `/api/v1/procurement/requisitions/` + `submit/`、`cancel/`、`convert/` | `procurement.PurchaseRequisition` / `PurchaseRequisitionLine` | `procurement.requisition.view/create/update/submit` | `test_procurement.py`（申请相关 5 项） | 已通过阶段验收 |
| 申请转采购订单 | 同上（弹窗） | `POST .../requisitions/{id}/convert/` | 订单头 + `source_line` 追溯 | `procurement.order.create` | `test_convert_requisition_to_order_and_block_duplicates`、`test_draft_requisition_cannot_be_converted` | 已通过阶段验收 |
| 采购订单（金额后端计算、审批、关闭） | `views/procurement/PurchaseOrderList.vue` | `/api/v1/procurement/orders/` + `submit/`、`cancel/`、`close/` | `procurement.PurchaseOrder` / `PurchaseOrderLine` | `procurement.order.view/create/update/submit/close` | `test_order_amount_is_computed_by_backend`、`test_order_tax_rounding_is_half_up`、`test_order_can_be_closed_after_receipt` | 已通过阶段验收 |
| 供应商准入/停用校验与例外授权 | 同上（表单校验提示） | 同上 | `supplier_exception` / `supplier_exception_reason` | `procurement.order.override_supplier` | `test_suspended_supplier_cannot_be_used_without_reason`、`test_inactive_supplier_needs_override_permission`、`test_override_supplier_requires_reason_and_is_audited` | 已通过阶段验收 |
| 采购收货（不允许超收、草稿占用额度） | `views/procurement/GoodsReceiptList.vue` | `/api/v1/procurement/receipts/` + `cancel/` | `procurement.GoodsReceipt` / `GoodsReceiptLine` | `procurement.receipt.view/create/update` | `test_receipt_over_order_quantity_is_rejected`、`test_draft_receipts_reserve_remaining_quantity`、`test_receipt_line_must_belong_to_the_order` | 已通过阶段验收 |
| 收货过账 → 待检库存 | 同上（过账按钮，带 `Idempotency-Key`） | `POST .../receipts/{id}/post/` | `receipt_document_id` → `wms.InventoryDocument` | `procurement.receipt.post` + `wms.document.create/post` | `test_post_receipt_creates_quarantine_stock_and_blocks_issue`、`test_receipt_post_is_idempotent_with_header` | 已通过阶段验收 |
| 来料检验判定 → 质量放行 | 同上（检验弹窗） | `POST .../receipts/{id}/inspect/` | `quality_document_id`、`inspection_result` | `procurement.receipt.inspect` + `wms.quality.release` | `test_inspect_qualified_releases_stock_for_issue`、`test_inspect_rejected_keeps_stock_blocked`、`test_multi_line_receipt_inspect_releases_every_line_once`、`test_inspect_with_idempotency_key_replays_without_second_release` | 已通过阶段验收 |
| 审批终态回写机制 | — | `workflow/instances/{id}/approve` / `reject` / `withdraw` | `apps/workflow/registry.py` 显式回调 | 复用 `workflow.instance.*` | `test_order_submit_then_approve_writes_back_status`、`test_order_approval_rejection_writes_back_rejected`、`test_requisition_approval_writes_back_status` | 已通过阶段验收 |
| 采购枚举字典 | — | `/api/v1/meta/`（5 个新键） | 枚举类 | — | `test_meta_exposes_procurement_enums` | 已通过阶段验收 |
| 数据范围与跨公司隔离 | — | 全部列表/详情 | `factory` / `department` / `warehouse` 范围 | 四层权限 | `test_orders_are_company_scoped`、`test_receipts_of_other_company_orders_are_not_visible`、`test_view_only_user_cannot_create_order`、`test_receipt_permission_is_enforced` | 已通过阶段验收 |
| 演示数据 | — | — | 申请 / 订单 / 收货各 1 张，走真实链路 | — | `seed_demo` 二次执行新建 0 条 | 已通过阶段验收 |

**明确未包含**：询价比价与报价单、到货差异处理、采购退货、应付与付款登记、备件采购、
采购价格与交付分析报表、单据打印、供应商准入审批流程接入 `workflow`。
这些条目在 §10.4、§10.5 中逐条标注并给出计划阶段。

## 一之五、阶段 2 第四步增量：销售模块（本轮实际完成）

| 交付项 | 页面（前端组件） | API | 数据实体 | 权限点 | 自动化用例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 销售订单（含行、SKU、交期、优先级） | `views/sales/SalesOrderList.vue` | `/api/v1/sales/orders/` + `submit/`、`cancel/`、`close/` | `sales.SalesOrder` / `SalesOrderLine` | `sales.order.view/create/update/submit/close` | `test_order_submit_then_approve_writes_back_status`、`test_order_approval_rejection_writes_back_rejected`、`test_suspended_customer_cannot_be_used`、`test_order_without_warehouse_cannot_reserve` | 已通过阶段验收 |
| 金额后端计算 | 同上（行金额只读展示） | 同上 | `total_amount` / `tax_amount` / `amount_with_tax` | — | `test_order_amount_is_computed_by_backend`、`test_order_rejects_non_positive_quantity` | 已通过阶段验收 |
| 库存占用 | 同上（占用/释放按钮） | `POST /sales/orders/{id}/reserve/`、`/release/` | `wms.StockReservation` | `sales.order.reserve/release` + `wms.inventory.reserve/release` | `test_reserve_moves_available_to_reserved_without_touching_on_hand`、`test_reserve_is_idempotent`、`test_reserve_rejects_insufficient_available`、`test_reserve_rejects_quarantine_stock`、`test_release_order_stock_returns_available`、`test_cancel_order_releases_open_reservations` | 已通过阶段验收 |
| 库位/批次推荐与维度对齐 | — | 占用内部调用 `stock.choose_reservation_dimension` | `InventoryBalance.dimension_key` | — | `test_reserve_uses_matching_batch_dimension` | 已通过阶段验收 |
| 销售发货与出库过账 | `views/sales/SalesShipmentList.vue` | `/api/v1/sales/shipments/` + `post/`、`cancel/` | `sales.SalesShipment` / `SalesShipmentLine` → `wms.InventoryDocument` | `sales.shipment.view/create/update/post` + `wms.document.create/post` | `test_shipment_post_consumes_reservation_and_decrements_on_hand`、`test_shipment_post_is_idempotent`、`test_shipment_quantity_cannot_exceed_remaining` | 已通过阶段验收 |
| 先占用后发货（未占用拒绝出库） | 同上（过账前提示） | 同上 | `_assert_reservation_covers` | 同上 | `test_shipment_requires_reservation` | 已通过阶段验收 |
| 销售退货（收货进待检 → 检验判定） | `views/sales/SalesReturnList.vue` | `/api/v1/sales/returns/` + `post/`、`inspect/`、`cancel/` | `sales.SalesReturn` / `SalesReturnLine` | `sales.return.view/create/update/post/inspect` + `wms.quality.release` | `test_return_requires_posted_shipment`、`test_return_quantity_cannot_exceed_shipped`、`test_return_post_lands_in_quarantine`、`test_inspect_qualified_returns_stock_to_qualified`、`test_inspect_rejected_keeps_stock_unusable`、`test_inspect_requires_remark`、`test_repeated_inspect_is_rejected` | 已通过阶段验收 |
| 退货批次追溯 | 同上 | 同上 | `_inherit_return_dimensions` + `stock.document_line_hint` | — | `test_return_inherits_original_batch` | 已通过阶段验收 |
| 职责分离（销售不能做质量判定） | 同上（按钮按权限隐藏） | 同上 | 内置角色 `sales_admin` / `quality_inspector` | 权限分离 | `test_sales_clerk_cannot_inspect_returns`、`test_user_without_reserve_permission_cannot_reserve` | 已通过阶段验收 |
| 订单到交付链路视图 | 同上（详情抽屉） | `GET /sales/orders/{id}/chain/` | 订单/发货/退货/库存单据 | `sales.order.view` | `test_chain_endpoint_lists_related_documents` | 已通过阶段验收 |
| 数据范围与跨公司隔离 | — | 全部列表/详情 | `company` + `warehouse` 范围 | 四层权限 | `test_orders_are_company_scoped`、`test_sales_endpoints_require_authentication`、`test_view_only_user_cannot_create_order` | 已通过阶段验收 |
| 销售枚举字典 | — | `/api/v1/meta/`（6 个新键） | 枚举类 | — | `test_meta_exposes_sales_enums` | 已通过阶段验收 |
| 演示数据 | — | — | `seed_demo._sales()`：订单 → 占用 → 发货 → 退货 → 检验各 1 张 | — | `seed_demo` 二次执行新建 0 条 | 已通过阶段验收 |

**明确未包含**（在 §10.3 中逐条标注）：销售计划、颜色尺码矩阵批量录入、折扣、
订单变更版本快照、分销商、基础预测、应收与收款登记、发货申请单与运单对接、
跨储位/跨批次自动拆分占用、多批次部分退货的批次分摊。

## 一之六、阶段 3 第一步增量：BOM 与工艺路线版本快照（本轮实际完成）

| 交付项 | 页面（前端组件） | API | 数据实体 | 权限点 | 自动化用例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| BOM 版本化（草稿/审核中/已审核/已驳回/已作废） | `views/planning/BomList.vue` | `/api/v1/planning/boms/` + `/{id}/` | `planning.Bom` | `planning.bom.view/create/update` | `test_create_bom_persists_lines_and_computes_gross_quantity`、`test_draft_can_be_updated_but_submitted_cannot` | 已通过阶段验收（阶段 3 第一步） |
| 生效日期与区间校验 | 同上 | 同上 | `effective_from` / `effective_to` + `ck_bom_effective_range` | 同上 | `test_bom_effective_range_must_be_ordered` | 已通过阶段验收 |
| 审核状态（走 `workflow`，无模板即拒绝） | 同上（提交/撤回按钮） | `POST /boms/{id}/submit/` | `status` + `approval_instance_id` + `approved_by/at` | `planning.bom.submit` | `test_submit_requires_approval_template`、`test_approve_activates_version_and_obsoletes_previous`、`test_reject_returns_document_to_rejected_state`、`test_withdraw_returns_document_to_draft` | 已通过阶段验收 |
| 同一范围唯一生效版本 | 同上（状态标签） | 同上 | 服务层 `select_for_update` 切换（MySQL 无部分唯一索引） | 同上 | `test_approve_activates_version_and_obsoletes_previous`、`test_effective_bom_returns_approved_only` | 已通过阶段验收 |
| SKU 差异用料（款式通用 / 单 SKU 版本） | 同上 | 同上 | `Bom.sku` + `scope_key` 规范化键 | 同上 | `test_version_no_increments_within_scope`、`test_sku_must_belong_to_style` | 已通过阶段验收 |
| 标准用量与损耗（后端计算含损耗用量） | 同上（只读展示） | 同上 | `BomLine.quantity` / `loss_rate` / `gross_quantity` | 同上 | `test_client_supplied_gross_quantity_is_ignored`、`test_bom_loss_rate_out_of_range_is_rejected` | 已通过阶段验收 |
| 替代料 | 同上 | 同上 | `BomLine.line_type` + `substitute_for` | 同上 | `test_substitute_line_links_to_normal_line`、`test_substitute_for_unknown_line_is_rejected`、`test_normal_line_cannot_reference_substitute_target` | 已通过阶段验收 |
| 变更只能派生新版本（不覆盖已审核版本） | 同上（派生新版本按钮） | `POST /boms/{id}/new-version/` | 新 `Bom` + 复制明细 | `planning.bom.create` | `test_new_version_from_submitted_is_rejected`、`test_snapshot_matches_version_and_survives_new_version` | 已通过阶段验收 |
| 作废（必填原因，不物理删除） | 同上 | `POST /boms/{id}/obsolete/` | `status=obsolete` + `is_active` | `planning.bom.obsolete` | `test_obsolete_requires_reason`、`test_obsolete_marks_version_inactive`、`test_obsolete_submitted_is_rejected` | 已通过阶段验收 |
| 版本快照（供 MES 工单引用） | 同上 | `GET /boms/{id}/snapshot/` | `services.build_bom_snapshot()` | `planning.bom.view` | `test_bom_snapshot_service_equals_api`、`test_snapshot_matches_version_and_survives_new_version` | 已通过阶段验收 |
| 工艺路线（版本/审批/作废/派生规则同 BOM） | `views/planning/RoutingList.vue` | `/api/v1/planning/routings/` 下 7 个端点 | `planning.Routing` | `planning.routing.view/create/update/submit/obsolete` | `test_routing_submit_and_approve`、`test_routing_new_version_copies_steps_and_obsoletes_previous`、`test_routing_update_locks_after_submit`、`test_routing_obsolete_requires_reason` | 已通过阶段验收 |
| 工序、标准工时、设备要求、工序质检点 | 同上 | 同上 | `planning.RoutingStep`（`sequence` / `standard_hours` / `equipment_requirement` / `is_quality_gate` / `workshop`） | 同上 | `test_create_routing_with_explicit_steps`、`test_duplicate_routing_sequence_is_rejected`、`test_negative_standard_hours_is_rejected`、`test_routing_snapshot_contains_quality_gate`、`test_routing_step_workshop_outside_scope_is_rejected` | 已通过阶段验收 |
| 默认工艺 裁剪→缝制→整烫→检验→包装 | 同上（新建即见默认工序） | 同上 | `DEFAULT_ROUTING_STEPS` | 同上 | `test_create_routing_applies_default_steps`、`test_routing_requires_at_least_one_step`（显式空列表被拒） | 已通过阶段验收 |
| 乐观锁与冻结 | 同上 | `PATCH /boms/{id}/`、`/routings/{id}/` | `version` 字段 | 同上 | `test_optimistic_lock_rejects_stale_version` | 已通过阶段验收 |
| 数据范围与跨公司隔离 | — | 全部列表/详情 | `company` 范围（`scope_fields`） | 四层权限 | `test_cross_company_objects_are_rejected`、`test_planning_endpoints_require_authentication`、`test_view_only_user_cannot_create_bom`、`test_routing_permission_does_not_grant_bom_write` | 已通过阶段验收 |
| 计划枚举字典 | — | `/api/v1/meta/`（3 个新键） | `BomStatus` / `RoutingStatus` / `BomLineType` | — | `test_meta_exposes_planning_enums` | 已通过阶段验收 |
| 演示数据 | — | — | `seed_demo._engineering()`：BOM 1 条（5 行）+ 工艺路线 1 条（5 工序）+ 2 个审批模板 | — | `seed_demo` 二次执行新建 0 条 | 已通过阶段验收 |

**明确未包含**（在 §9.5 / §10.6 / §10.7 / §10.9 逐条标注）：MES 工单与报工、QMS 检验单、
快照表落库、BOM/工艺 Excel 导入导出、BOM 成本卷算、工艺路线与设备/工位的外键关联。
（**MRP 已在本轮之后交付**，见 §一之七；此处仅保留本增量当时的边界。）

## 一之七、阶段 3 第二步增量：MRP（本轮实际完成）

| 交付项 | 页面（前端组件） | API | 数据实体 | 权限点 | 自动化用例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 运行 MRP（同步计算 + 落库快照） | `views/planning/MrpRunList.vue` | `POST /api/v1/planning/mrp-runs/` | `planning.MrpRun`（`parameters` / `summary` / `status`） | `planning.mrp.run` | `test_run_api_creates_run_with_counts_and_detail_endpoints`、`test_audit_and_outbox_event_written_with_business_data` | 已通过阶段验收（阶段 3 第二步） |
| 时间分段净需求（按日 / 按周） | 同上（分段选择 + 详情页签） | `GET /mrp-runs/{id}/demands/` | `MrpDemandLine.bucket_date` + `mrp_bucket_date()` | `planning.mrp.view` | `test_net_requirement_nets_on_hand_and_on_order`、`test_week_bucket_normalises_to_monday`、`test_overdue_demand_lands_in_first_bucket`、`test_demand_outside_horizon_ignored` | 已通过阶段验收 |
| 多层 BOM 展开（低层码只净算一次） | 同上（需求行 `level` / `path`） | 同上 | `MrpDemandLine.level` / `source_type=parent_item` / `path` | 同上 | `test_explosion_uses_parent_net_requirement`、`test_low_level_code_net_calculated_once` | 已通过阶段验收 |
| 损耗计算 | 同上（用量由 BOM 快照带入） | 同上 | 取 `BomLine.gross_quantity`（含损耗） | 同上 | `test_explosion_uses_parent_net_requirement`（按含损耗用量展开） | 已通过阶段验收 |
| 循环 BOM 检查与层级上限 | 同上（失败运行可见） | 同上 | `MrpRun.status=failed` + `error_message` | 同上 | `test_cycle_bom_rejected_and_failed_run_recorded` | 已通过阶段验收 |
| 可用库存作为供给（排除冻结 / 占用、只认合格） | 同上（供给行页签） | `GET /mrp-runs/{id}/supplies/` | `MrpSupplyLine`（`source_type=on_hand`） | 同上 | `test_usable_stock_excludes_frozen_reserved_and_unqualified` | 已通过阶段验收 |
| 采购在途作为供给 | 同上 | 同上 | `MrpSupplyLine`（`source_type=on_order`，引用采购订单） | 同上 | `test_purchase_on_order_reduces_net_requirement` | 已通过阶段验收 |
| 缺料清单 / 采购建议 / 生产建议 | `views/planning/MrpSuggestionList.vue` | `GET /mrp-runs/{id}/suggestions/`、`GET /mrp-suggestions/` | `MrpSuggestion`（`suggestion_type` / `reason` / `detail`） | 同上 | `test_suggestion_type_rules_and_unexploded_materials` | 已通过阶段验收 |
| 供需追溯 | 同上（需求行 `source_no` / `path`、建议 `detail.trace`） | 同上 | `source_type/source_id/source_no/source_line_no`、`detail.demand_sources` | 同上 | `test_run_api_creates_run_with_counts_and_detail_endpoints` | 已通过阶段验收 |
| 计算快照（参数与汇总） | 同上（摘要卡片） | 同上 | `MrpRun.parameters` / `summary` / `started_at` / `finished_at` | 同上 | 同上 | 已通过阶段验收 |
| 建议转单 → **草稿**采购申请（不绕过审批） | 同上（转采购申请按钮） | `POST /mrp-suggestions/{id}/convert/` | `MrpSuggestion.converted_document_*` + `integration.DocumentLink`（`generated_from`） | `planning.mrp.convert` + `procurement.requisition.create` | `test_convert_creates_draft_requisition_with_document_link`、`test_convert_requires_procurement_requisition_create` | 已通过阶段验收 |
| 生产建议**不伪造工单**（MES 未实现即拒绝） | 同上（按钮给出明确提示） | 同上 | — | 同上 | `test_convert_production_suggestion_rejected` | 已通过阶段验收（边界明确） |
| 重复转单 / 过期建议 / 取消 / 归档保护 | 同上（状态标签 + 取消按钮） | `POST /mrp-suggestions/{id}/cancel/`、`POST /mrp-runs/{id}/archive/` | `status`（`open/converted/cancelled`）、`cancel_reason`、`MrpRun.status=archived` | `planning.mrp.cancel` / `archive` | `test_convert_twice_rejected`、`test_convert_stale_suggestion_rejected`、`test_cancel_requires_reason_and_blocks_convert`、`test_archive_run_blocks_conversion_and_repeat_archive_rejected` | 已通过阶段验收 |
| 数据范围（公司 / 仓库）与权限隔离 | — | 全部端点 | `scope_fields`（公司、以 `run__company_id` 作用于建议） | 四层权限 | `test_api_run_scoped_to_company_and_warehouse`、`test_anonymous_access_rejected`、`test_view_only_user_cannot_run_mrp`、`test_user_without_convert_permission_cannot_convert`、`test_mrp_permissions_do_not_grant_other_modules` | 已通过阶段验收 |
| 审计与 Outbox（同事务） | — | — | `AuditLog`、`OutboxEvent`（`planning.mrp.completed` / `suggestion_converted`） | — | `test_audit_and_outbox_event_written_with_business_data`、`test_archive_api_requires_permission_and_is_audited` | 已通过阶段验收 |
| 枚举字典 | — | `/api/v1/meta/`（6 个新键） | `MrpRunStatus` / `MrpBucket` / `MrpDemandSource` / `MrpSupplySource` / `MrpSuggestionType` / `MrpSuggestionStatus` | — | 由 `frontend/tests/views-compile.spec.ts` 与路由用例覆盖 | 已通过阶段验收 |

## 一之八、文档同步与项目使用说明（本轮实际完成）

| 交付项 | 位置 | 校验 | 状态 |
| --- | --- | --- | --- |
| 项目使用说明文档 | `docs/user-guide.md`（§一～§十一：启动 / 账号 / 菜单 / 操作 / 错误码 / 未执行项 / 同步规则） | 与代码逐项核对（权限 173 / 菜单 56 / 模型 86 / 表 92 / 迁移 19 / 角色 16） | 已完成 |
| 机器可校验事实行 | `docs/user-guide.md` §11.5 `<!-- yishang-doc-sync: ... -->` | `tests/test_docs_sync.py`（7 条）与注册表 / 模型 / 迁移 / 内置角色比对，并执行 `build_user_guide.py --check` | 已完成（含反向验证） |
| 使用说明网页版（可直接给客户） | `scripts/build_user_guide.py` → `docs/user-guide.html` + `frontend/public/guide.html`（访问 `/guide.html`） | 单文件自包含（CSS/JS 内联，无 CDN）；结构校验 28 表 / 55 目录项 / 锚点全命中；`--check` 防过期 | 已完成 |
| 系统内入口 | `frontend/src/layouts/BasicLayout.vue` 顶部工具栏 + 个人中心「使用说明」 | `npm run typecheck` / `vitest` / `build` | 已完成 |
| 文档按最新代码修正 | `acceptance.md`、`inventory-rules.md`、`api-conventions.md`、`requirements-matrix.md`、`README.md`、`progress.md` | 逐处修正过时陈述（71 张表→92、占用/释放已落地、MRP 非 Celery 任务、MRP 已打通等） | 已完成 |
| 「代码更新后使用文档同步」规则 | `docs/user-guide.md` §十一（触发清单 / 收尾清单 / 核对方法 / 兜底机制） | 规则成文 + 用例兜底数量层面；正文仍靠人工 | 已完成（缺口已声明） |
| 本轮测试 | `backend/tests` | `307 passed in 111.83s`；`ruff` / `check` / 迁移检查通过 | 已完成 |

## 一之九、枚举值中文化（本轮实际完成）

> 起因：界面把仓库类型、部门类型、计量单位类别等枚举显示为英文原始键。

| 需求条目 | 实现位置 | 页面 / API | 数据实体 | 业务规则 | 测试案例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 枚举字段随响应返回中文标签 | `apps/core/serializers.py::DisplayLabelsMixin`（`ReferenceIdSerializer` 继承，71 个 ModelSerializer 生效）+ `apps/identity/serializers.py` 7 个序列化器 | 全部列表 / 详情 API | 所有带 `choices` 的模型字段（59 个） | 写入与筛选仍用英文键；只读 `<field>_display` 返回中文；已显式声明的同名字段不覆盖；只加只读字段不产生迁移 | `tests/test_enum_labels.py`（4 条，含「任一 choices 字段缺 `_display` 即失败」的全量遍历） | 已通过阶段验收 |
| 前端优先展示中文标签 | `frontend/src/components/ProTable.vue::displayValue()`、`EntityListPage.vue::renderCell()` | 全部列表页与详情抽屉 | — | 后端 `_display` 优先，缺失时退回原值（不显示 `undefined`）；前端 `meta` 字典仅作回退 | `frontend/tests/pro-table.spec.ts`（新增 2 条） | 已通过阶段验收 |
| 历史非法枚举数据修复 | `apps/factory/migrations/0003_alter_department_department_type_and_more.py`（`RunPython` + `AlterField`） | — | `factory.Employee.gender`、`Employee.employment_type`、`ProductionLine.line_type`、`Department.department_type`、`Workshop.workshop_type` | 部门类型补 `procurement/sales/equipment`；车间类型补 `finishing`；按编码映射修正历史值；反向迁移为空操作 | 迁移执行后直连开发库复扫：非法枚举 0 条；`test_enum_labels.py::test_seed_demo_writes_only_valid_enum_values` | 已通过阶段验收 |
| 演示数据源头修正 | `apps/core/management/commands/seed_demo.py` | — | 同上一行 | 部门 `supply→procurement`、`marketing→sales`；性别写英文键；用工性质统一 `full_time`；线体类型改合法值 | 同上 | 已通过阶段验收 |

**本轮真实结果**：后端 **312** 项、前端 **131** 项自动化测试通过；`manage.py check` 无问题；
`makemigrations --check --dry-run` 无漂移；`ruff` 通过；前端 `typecheck` 通过、`vite build` 成功。
**未执行**：浏览器截图级 UI 校验（本机浏览器自动化被安全策略拒绝）——需人工核对页面中文标签。

## 一之十、超级管理员权限与角色绑定（本轮实际完成）

> 起因：用户反馈「超级管理员好像什么也新增不了」。定位为**前端未处理权限通配符**的真实缺陷，
> 并顺带修正了「管理员账号未绑定任何角色」的一致性缺口。

| 需求条目 | 实现位置 | 页面 / API | 业务规则 | 测试案例 | 状态 |
| --- | --- | --- | --- | --- | --- |
| 超级管理员通配符权限 | `frontend/src/stores/auth.ts`（`hasFullAccess` + `hasPermission` / `hasAnyPermission`） | 全部列表页与详情页的操作按钮 | 后端对 `is_superuser` 下发 `permissions=["*"]`；前端必须把 `*` 解释为「全部权限」，否则按钮全部隐藏 | `frontend/tests/auth-store.spec.ts`（4 条） | 已通过阶段验收 |
| 管理员账号绑定内置角色 | `backend/apps/core/management/commands/bootstrap_system.py::_ensure_admin_role` | 系统管理 → 用户管理 / 个人中心 | 创建与已存在两条路径都确保绑定 `super_admin`；幂等、`--dry-run` 只打印 | `backend/tests/test_management_commands.py::test_bootstrap_system_binds_super_admin_role_to_admin_account` | 已通过阶段验收 |
| 权限合并规则文档 | `docs/permission-matrix.md` §五规则 1 | — | 明确「通配符 `*` 必须被客户端解释为全部权限」，与后端 `has_permission_codes()` 语义一致 | 人工核对 + 上述两条用例 | 已完成 |

**真实 HTTP 验证（对运行中的开发服务器，非测试框架）**：以 `admin` 登录后

```text
login 200            → roles=[超级管理员]、permissions=["*"]
POST /api/v1/wms/warehouses/       → 400 VALIDATION_FAILED （权限门通过，仅表单校验失败）
POST /api/v1/identity/roles/       → 400 ROLE_CODE_REQUIRED（同上）
POST /api/v1/factory/departments/  → 400 VALIDATION_FAILED （同上）
```

修复前这些请求在页面上**根本没有入口**（按钮被隐藏）；修复后权限门放行，
返回 400 说明是正常的字段校验，而不是 403 权限不足。

**未执行**：浏览器截图级 UI 核对（本机浏览器自动化被安全策略拒绝）——
请用 `admin` 登录后确认「系统管理 → 用户管理 / 角色管理」的「新增」按钮已出现，
且个人中心显示「角色：超级管理员」。

## 一之十一、客户编码自动生成（本轮实际完成）

> 起因：用户要求「新增客户时不必手工输入客户编码，按规律自动生成」。
> 做法：复用既有编码规则引擎，不新增取号代码、不新增数据表、**不产生迁移**。

| 需求条目 | 实现位置 | 页面 / API | 数据实体 | 业务规则 | 测试案例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 新增客户自动生成编码 | `apps/crm/views.py::CustomerViewSet.perform_create` + `apps/crm/services.py::next_customer_code` | 「客户管理 → 客户档案 → 新增」（表单不含编码字段） | `crm.Customer.code`、`core.CodeRule`（`CUS`）、`core.CodeSequence` | 编码缺失 / 空白 / 空串时按规则 `CUS{YYYY}{SEQ:4}`（按年重置）取号；显式传入的编码原样保留；取号与落库同事务，失败一并回滚 | `tests/test_crm_api.py`（新增 6 条） | 已通过阶段验收 |
| 编码规则可配置且不写死 | `apps/core/management/commands/bootstrap_system.py::CODE_RULES` | 「系统管理 → 编码规则」（含编号预演） | `core.CodeRule.pattern` / `reset_period` | 代码只引用规则编码 `CUS`，格式来自规则表；改规则即改后续新编号，历史编码不变 | `test_customer_code_follows_configured_rule_pattern` | 已通过阶段验收 |
| 编辑时不允许清空编码 | `apps/crm/serializers.py::CustomerSerializer.validate_code` | 客户档案 → 编辑 | `crm.Customer.code` | 仅 `self.instance` 非空（编辑）时拒绝空值；编码是客户身份，清空会破坏同公司内唯一 | `test_customer_code_cannot_be_cleared_on_update` | 已通过阶段验收 |
| 新增表单按模式隐藏系统托管字段 | `frontend/src/components/EntityListPage.vue`（`onlyOnUpdate`）、`views/crm/CustomerList.vue` | 客户档案新增 / 编辑对话框 | — | 与既有 `onlyOnCreate` 对称；被隐藏字段不进入提交载荷 | `frontend/tests/entity-list-form.spec.ts`（3 条） | 已通过阶段验收 |

**本轮真实结果**：开发库 `bootstrap_system` 新增 1 条编码规则（共 15 条）；
开发库 HTTP 冒烟（事务已回滚）`201 CUS20260001` → `201 CUS20260002`，
编辑清空编码 `400`；后端 **319** 项、前端 **138** 项自动化测试通过；
`manage.py check` 无问题、`makemigrations --check` 无漂移、`ruff` 通过、
前端 `vue-tsc` 退出码 0、`vite build` 成功。
**未执行**：浏览器截图级 UI 校验（本机浏览器自动化被安全策略拒绝）。

## 一之十二、数值显示 2 位小数（本轮实际完成）

> 起因：用户要求「涉及到数字的内容，都是小数点后 2 位即可」。
> 做法：只在**前端显示层**统一口径，存储与接口精度不变，**不产生迁移、不改后端**。

| 需求条目 | 实现位置 | 页面 / API | 数据实体 | 业务规则 | 测试案例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 列表 / 详情数值统一 2 位小数 | `frontend/src/utils/decimal.ts::formatNumber`（`DISPLAY_PLACES = 2`）、`components/ProTable.vue::displayValue`、`components/EntityListPage.vue::renderCell` | 全部列表页与详情抽屉 | — | HALF_UP 四舍五入到 2 位 + 千分位；空值显示 `-`；**纯整数文本**（手机号、税号、数字型编码）与 `M-001` 这类编码不参与格式化 | `frontend/tests/decimal.spec.ts`、`frontend/tests/pro-table.spec.ts`、`frontend/tests/entity-list-form.spec.ts` | 已通过阶段验收 |
| 原生 `el-table` 数值列 | 各视图 `:formatter="numberFormatter"`（BOM、采购订单、收货、领料、销售订单 / 发货 / 退货、MRP、工艺标准工时） | 同上 | — | 与 `ProTable` 共用同一函数，避免两套口径漂移 | `frontend/tests/decimal.spec.ts::numberFormatter` | 已通过阶段验收 |
| 非零值不显示成 0 | `decimal.ts::formatNumber` 保护分支 | BOM 用量、极小单价 | `planning.BomLine.quantity`（`0.004`）、`masterdata.UoMConversion.factor`（`0.9144`，页面未展示） | 「四舍五入结果恰好为 0 且真值非 0」时保留真实精度；**会进位的值仍按 2 位**（`0.055` → `0.06`）；极小值（`-0.0000001`）回退 `0.00` | `frontend/tests/decimal.spec.ts`（3 条） | 已通过阶段验收 |
| 编辑表单回填 | `decimal.ts::toEditableText`、`EntityListPage.vue::resetForm` | 各编辑对话框的数值输入框 | — | 只去末尾无意义的 0（`12.000000` → `12`），**不做四舍五入、不加千分位**；避免「打开编辑直接保存」把 `0.055` 改写成 `0.06` | `frontend/tests/decimal.spec.ts`（3 条）、`frontend/tests/entity-list-form.spec.ts`（2 条） | 已通过阶段验收 |
| 整数计数列不显示小数 | 调用处显式传 `places = 0`（`factory/WorkshopList.vue` 日产能、`workspace/Index.vue` 看板计数） | 车间管理、工作台 | — | 计数类数值不出现 `.00` | `frontend/tests/decimal.spec.ts::整数计数列（places = 0）不出现小数点` | 已通过阶段验收 |
| 存储 / 接口精度保持不变 | `decimal.ts::toApiString` / `round` / `DECIMAL_PLACES`（数量 6 位、金额 4 位、费率 10 位）；后端 `DecimalField` 未改 | 所有写接口 | 全部业务表 | 显示口径不回写、不参与提交；任务书 5.3 的 6 位数量精度保持不变 | `frontend/tests/decimal.spec.ts::显示口径不影响提交给后端的精度` | 已通过阶段验收 |

**本轮真实结果**：前端 **154** 项自动化测试通过（本轮前 138，新增 16 条）；后端 **319** 项通过（本轮无后端改动，基线不变）；
直连开发库遍历 **58** 个 `DecimalField` 列，只有 **2 处** 存在 >2 位有效小数（`masterdata.UoMConversion.factor` 1 条、`planning.BomLine.quantity` 1 条）；
`manage.py check` 无问题、`makemigrations --check` 无漂移、`ruff` 通过、前端 `vue-tsc` 退出码 0、`vite build` 成功。
**未执行**：浏览器截图级 UI 校验（本机浏览器自动化被安全策略拒绝）；Excel 导出格式未同步为 2 位（属独立需求，见 `docs/progress.md` §21.7）。

## 一之十三、权限一级分组显示中文名（本轮实际完成）

> 起因：用户反馈权限 / 菜单与角色权限界面的一级分组只有英文模块名（`core`、`identity`），
> 业务人员不知道该怎么勾。要求显示为 `core（公共基础）`。
> 做法：中文名登记在后端权限注册表，界面统一显示「英文模块（中文名）」，**无迁移**。

| 需求条目 | 实现位置 | 页面 / API | 数据实体 | 业务规则 | 测试案例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 一级分组显示英文 + 中文 | `apps/identity/permissions_registry.py::MODULE_LABELS`、`selectors.py::permission_groups` | 「系统管理 → 权限与菜单」权限点选项卡；「系统管理 → 角色权限 → 分配操作权限」 | — | 中文名与权限编码同源登记（注册表是前后端共同契约），新增模块一处登记、两处界面生效 | `backend/tests/test_permissions.py`（3 条）、`frontend/tests/permission-module-label.spec.ts`（5 条） | 已通过阶段验收 |
| 前端不硬编码模块中文名 | `frontend/src/utils/permissionLabels.ts`、`types/models.ts::PermissionGroup.module_name` | 同上 | — | 前端只做 `module（module_name）` 拼接；无中文名时只显示模块编码，不出现空括号 | 同上 | 已通过阶段验收 |
| 模块漏登记中文名要报错 | `apps/core/checks.py::check_permission_module_labels`（`yishang.E002`） | — | 权限注册表 | 启动检查 `manage.py check` 直接报错，避免界面退回纯英文分组 | `test_module_label_check_reports_missing_module` | 已通过阶段验收 |
| 过滤后仍保留中文名 | `frontend/src/views/system/PermissionList.vue::filteredGroups` | 权限与菜单 → 关键字过滤 | — | 过滤重建分组时必须带上 `module_name`（修复真实缺陷：原先一输入关键字中文名即消失） | `permission-module-label.spec.ts::按关键字过滤后中文名仍然保留` | 已通过阶段验收 |

**本轮真实结果**：开发库 `permission_groups()` 返回 **13** 个分组且全部带中文名，权限点合计 **173** 项与注册表一致；
后端 **322** 项测试通过（本轮前 319，新增 3 条）；前端 **159** 项通过（本轮前 154，新增 5 条）；
`manage.py check` 无问题（含新检查 `yishang.E002`）、`makemigrations --check` 无漂移（**无迁移**）、`ruff` 通过、
前端 `vue-tsc` 退出码 0、`vite build` 成功。
**未执行**：浏览器截图级 UI 校验（本机浏览器自动化被安全策略拒绝）。

## 一之十四、登录页商用化改版（本轮实际完成）

> 起因：用户反馈登录页「太一般」，希望更符合商用应用观感。
> 做法：**纯前端视觉与结构改造**，登录 / 会话 / CSRF 逻辑一律不动，**无迁移**。
> 后续还按用户要求把左栏文案从**开发视角**改写为**使用者视角**（见 `docs/progress.md` §24）。

| 需求条目 | 实现位置 | 页面 / API | 数据实体 | 业务规则 | 测试案例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 双栏品牌化布局 | `frontend/src/views/LoginView.vue` | `/login` | — | 左侧品牌区 + 右侧登录卡（`grid`，宽 `min(1080px,100%)`）；≤960px 隐藏左栏并在卡片内显示紧凑品牌 | `frontend/tests/login-view.spec.ts`（样式 5 条） | 已通过阶段验收 |
| 视觉升级（纯 CSS，无外链） | 同上（`<style scoped>`） | 同上 | — | 深蓝渐变背景 + 网格/光斑装饰；输入框双态描边；按钮品牌渐变；版权行年份动态；**不引入任何图片或 CDN** | `login-view.spec.ts::装饰层不拦截鼠标事件，且不引入任何外链资源` | 已通过阶段验收 |
| 样式单一定义处 | `frontend/src/styles/index.css`（删除原「7. 登录页」小节，小节重编号 1–8） | — | — | 登录页样式只在组件内定义，避免两处定义互相覆盖 | `login-view.spec.ts::样式定义在组件内，全局样式表不再重复定义 .ys-login` | 已通过阶段验收 |
| 登录行为不变 | `LoginView.vue::submit` | `GET /auth/csrf/` → `POST /auth/login/` | — | 仍先取 CSRF 再登录；账号 `trim`；成功 `tabs.reset()` 后跳 `redirect`；失败显示 `ApiError.message` | `login-view.spec.ts::先取 CSRF 再调用登录接口`、`::登录成功后跳转`、`::账号两侧空格会被去掉再提交` | 已通过阶段验收 |
| 面向使用者的业务描述 | `LoginView.vue::features` + 左栏主标题 / 定位文案 | `/login` | — | 左栏讲的是「平台能帮岗位做什么」（一套账号权限分明 / 主数据统一维护 / 采购到销售全程贯通 / 单据与审批全程留痕），不出现开发视角术语（权限分层、数据表字段名、前后端职责） | `login-view.spec.ts::左侧要点用面向使用者的业务描述，不出现开发术语` | 已通过阶段验收 |
| 不虚构能力 | `LoginView.vue::features` | `/login` | — | 登录页只列已实现能力，未实施模块（MES / WMS / QMS 等）不得出现 | 同上（同一用例的否定断言） | 已通过阶段验收 |
| 登录页文案可无依赖回归 | `frontend/tests/login-view.spec.ts` | — | — | 文案改动必须同步测试，避免「改了页面、测试还锁旧文案」互相打架 | 全量 `vitest run` 13 files / 170 tests | 已通过阶段验收 |
| 无障碍与可用性 | `LoginView.vue` | 同上 | — | 打开即聚焦账号输入框；`autocomplete` 正确；动效受 `prefers-reduced-motion` 保护 | `login-view.spec.ts`（渲染 2 条 + 样式 1 条） | 已通过阶段验收 |

**本轮真实结果**：前端 **170** 项自动化测试通过（本轮前 159，新增 11 条）；
`vue-tsc` 退出码 0、`vite build` 成功、`ruff` 通过、`manage.py check` 无问题、**无迁移**；后端本轮未改动。
**未执行**：浏览器截图级 UI 校验（浏览器自动化被安全策略拒绝）；表单必填校验（jsdom 无法覆盖，
Element Plus 的 `el-form-item` 在 jsdom 下不注册 field，`validate()` 直接放行——已用最小复现确认是环境限制）。

## 一之十五、登录后落地页修复 + 全站文案面向使用者（本轮实际完成）

> 起因：用户反馈 ①登录后「工作台内容是空的」；②系统内其余文字描述要面向使用者而非开发者。
> 结论：**空白是前端落点问题，不是接口没数据**；文案按时逐处改写。**无迁移**。

| 需求条目 | 实现位置 | 页面 / API | 数据实体 | 业务规则 | 测试案例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 登录后不再落到空白页 | `frontend/src/router/index.ts`（`resolveHomePath` + 守卫） | `/` → 菜单第一个页面 | — | `/` 只是布局外壳、没有页面组件；守卫把它重定向到**当前账号菜单里的第一个页面**（通常是工作台），不硬编码 `/workspace` | `frontend/tests/menu-home.spec.ts::登录后访问根路径` | 已通过阶段验收 |
| 面包屑反映真实层级 | `frontend/src/layouts/BasicLayout.vue` + `menuTrail` | 所有页面 | — | 面包屑按菜单层级生成（如「基础资料 / 物料档案」），不再固定显示「工作台」 | `menu-home.spec.ts::面包屑层级` | 已通过阶段验收 |
| 审计对象类型中文化 | `backend/apps/core/services.py::object_type_label` + `serializers.AuditLogSerializer` | `GET /api/v1/audit-logs/` | `core_audit_log` | `app_label.ModelName` → 模型 `verbose_name`；解析不到**原样返回**不猜名字；原始值同时保留供排查 | `backend/tests/test_audit_display.py`（对象类型 3 条 + 接口 1 条） | 已通过阶段验收 |
| 变更摘要中文化 | `services.describe_changes` / `display_value` / `AUDIT_CHANGE_LABELS` | 同上 | 同上 | 模型字段用中文字段名；非模型字段的键显式登记；空值→「空」、布尔→是/否；未登记的键保留原键名 | `test_audit_display.py::TestDescribeChanges` | 已通过阶段验收 |
| 工作台最近操作用中文句子 | `apps/analytics/services.py::_recent_activity` + `workspace/Index.vue::activityText` | `GET /api/v1/analytics/dashboard/` | 同上 | 接口返回 `action_display` / `object_type_display`，前端拼成「系统管理员 新增 角色「…」」，前端不维护翻译表 | `test_audit_display.py::test_工作台最近动态带中文操作与对象名` | 已通过阶段验收 |
| 全站文案面向使用者 | `frontend/src/views/**`（40 余处） | 全部业务页面 | — | 讲「使用者能做什么」而不是「系统内部怎么实现」：去掉阶段编号、模型名、幂等键、fail-closed、接口路径等表述 | 前端全量 `vitest run`、`views-compile.spec.ts` | 已通过阶段验收 |
| 提示语不出现未替换的 Markdown | `views/system/ProgressView.vue` | `/system/progress` | — | 原横幅中的 `**尚未实施**` 会原样显示星号，已改为普通文字 | 人工确认（本轮未做浏览器核对） | 部分完成（**浏览器观感未人工确认**） |

**本轮真实结果**：后端 **331** 项通过（本轮前 322，新增 9）；前端 **177** 项通过（本轮前 170，新增 7）；
`ruff` / `manage.py check` / `vue-tsc` / `vite build` 全部通过；`makemigrations --check` 无变更。
**未执行**：浏览器观感核对（本机未安装 Playwright，浏览器自动化被安全策略拒绝）。

## 一之十六、冒烟脚本拆除竞态修复 + 剩余文案去开发化（本轮实际完成）

> 起因：上一轮冒烟脚本偶发失败（vitest 报 1 条 unhandled error），且界面仍有少数开发视角文案。
> 结论：**失败原因是测试环境拆除后触发的延迟重排定时器，不是用例失败**；本轮修好并清零剩余文案。**无迁移**。

| 需求条目 | 实现位置 | 页面 / API | 数据实体 | 业务规则 | 测试案例 | 状态 |
| --- | --- | --- | --- | --- | --- | --- |
| 冒烟脚本确定性通过 | `frontend/tests/setup.ts` | —（测试基建） | — | 每个用例结束后卸载组件（表格 `onBeforeUnmount` 取消延迟重排），文件结束前留 120ms 静默期让重新排出的那一次跑完 | `scripts/smoke_check.ps1` 连续通过；前端全量 15 文件 / 181 项 | 已通过阶段验收 |
| 详情页不显示「审批实例」 | `views/procurement/RequisitionList.vue`、`views/sales/SalesOrderList.vue` | 采购申请 / 销售订单详情 | `procurement`、`sales` | 列标题改为「审批单号」，未提交时显示「未提交审批」 | `frontend/tests/copy-tone.spec.ts` | 已通过阶段验收 |
| 内部协同显示中文业务对象名 | `apps/integration/serializers.py::aggregate_type_display` | `GET /api/v1/integration/outbox-events/` | `core_outbox_event` | 复用 `object_type_label` 把 `sales.SalesOrder` 翻成「销售订单」；原始值保留供排查 | `backend/tests/test_audit_display.py::test_内部协同事件带中文业务对象名` | 已通过阶段验收 |
| 界面不出现内部标识式列标题 | `views/integration/OutboxList.vue`、`views/system/RoleList.vue`、`views/system/NotificationList.vue` | 内部协同 / 角色 / 我的通知 | — | 「对象 ID」→「对象编号」、「事件 ID」→「事件编号」、「业务 ID」→「关联业务编号」 | `copy-tone.spec.ts::表格与详情不用内部标识当列标题` | 已通过阶段验收 |
| 数据范围弹窗提示改为业务语言 | `views/system/RoleList.vue` | `/roles` | — | 去掉「越权」等技术表述，改为「其他途径同样无法超出该范围」 | `copy-tone.spec.ts`（源码级） | 已通过阶段验收 |
| 实施进度说明去掉开发表述 | `views/system/ProgressView.vue` | `/system/progress` | — | 「后端与前端」→「服务与界面」；「容器化部署脚本」→「容器化部署配置」；保留事实（未在容器环境实跑） | 人工确认（本轮未做浏览器核对） | 部分完成（**浏览器观感未人工确认**） |

**本轮真实结果**：后端 **332** 项通过（本轮前 331，新增 1）；前端 **181** 项通过（本轮前 177，新增 4）；
`ruff` / `manage.py check` / `vue-tsc` / `vite build` 全部通过；`makemigrations --check` 无变更；
`scripts/smoke_check.ps1` 输出「全部检查通过。」。
**未执行**：浏览器观感核对（本机未安装 Playwright，浏览器自动化被安全策略拒绝）。

## 二、技术方案（任务书 3.1）

| 编号 | 来源 | 需求 | 实现位置 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| REQ-3.1-01 | 3.1 | Vue 3 + TypeScript + Vite | `frontend/`（vue 3.5.13、vite 6.0.7） | 已完成 | `npm run build` 通过 |
| REQ-3.1-02 | 3.1 | Element Plus + Pinia + Vue Router | `frontend/src/{main.ts,stores,router}` | 已完成 | element-plus 2.9.1、pinia 2.3.0、vue-router 4.5.0 |
| REQ-3.1-03 | 3.1 | ECharts | `views/workspace/Index.vue` | 已完成 | 发件箱状态柱状图，数据来自后端接口 |
| REQ-3.1-04 | 3.1 | Python 3.12 + Django 5.2 LTS + DRF | `backend/`（Django 5.2.17） | 已完成 | `manage.py check` 通过 |
| REQ-3.1-05 | 3.1 | MySQL 8.4 LTS + InnoDB + utf8mb4 + 严格模式 | `config/settings/base.py` | 部分完成 | 本机实际为 MySQL 8.0.17；字符集/排序规则/SQL 模式已按目标配置 |
| REQ-3.1-06 | 3.1 | 数据库驱动 mysqlclient（锁定版本） | `pyproject.toml`、`uv.lock` | 部分完成 | 开发机无 C 工具链，开发使用 PyMySQL（`DB_DRIVER`）；Docker 目标为 mysqlclient，未验证 |
| REQ-3.1-07 | 3.1 | Django migrations | `backend/apps/*/migrations/` | 已完成 | `makemigrations --check` 无变更 |
| REQ-3.1-08 | 3.1 | Redis 缓存 + Celery 异步 + Beat 调度 | `config/settings/base.py`、`config/celery.py` | 部分完成 | 配置就绪；worker/beat 未实际运行 |
| REQ-3.1-09 | 3.1 | OpenAPI（drf-spectacular） | `/api/v1/schema/`、`/api/v1/docs/` | 已完成 | 已可访问 |
| REQ-3.1-10 | 3.1 | openpyxl（Excel） | `pyproject.toml`（依赖已锁） | 未开始 | 阶段 1 无业务导入导出；审计页导出为当前页 CSV |
| REQ-3.1-11 | 3.1 | S3 兼容对象存储 | `config/settings/base.py`（django-storages） | 部分完成 | 配置了 `OBJECT_STORAGE_*` 才启用，且默认 `AWS_QUERYSTRING_AUTH=True`（私有）；未连接真实对象存储验证 |
| REQ-3.1-12 | 3.1 | uv 包管理 + 锁定文件 | `backend/pyproject.toml`、`uv.lock` | 已完成 | 锁文件已提交 |
| REQ-3.1-13 | 3.1 | Ruff + 类型检查 | `ruff` 配置、`vue-tsc` | 已完成 | 均通过 |
| REQ-3.1-14 | 3.1 | pytest / Vitest / Playwright | `backend/tests`、`frontend/tests` | 部分完成 | 后端与前端已执行；Playwright 未执行 |
| REQ-3.1-15 | 3.1 | Gunicorn + Nginx + Docker Compose | `deploy/`、`compose.yaml` | 部分完成 | 文件已编写，未启动验证 |
| REQ-3.1-16 | 3.1 | 第一版看板用可配置轮询，不引入复杂实时设施 | `views/workspace/Index.vue` | 已完成 | 手动/定时刷新，未使用 WebSocket |

## 三、架构与代码组织（任务书 3.3、4）

| 编号 | 来源 | 需求 | 实现位置 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| REQ-3.3-01 | 3.3 | 模块化单体：前端 → Nginx → Django/DRF → MySQL | `docs/architecture.md`、`compose.yaml` | 已完成 | 未采用微服务 |
| REQ-3.3-02 | 3.3 | Redis 不作为业务状态唯一存储 | 设计约定 | 已完成 | 仅用于缓存与任务消息；库存/审批/工单状态在 MySQL |
| REQ-3.4-01 | 3.4 | 同一镜像承担 web/worker/beat | `compose.yaml` | 部分完成 | 未启动验证 |
| REQ-3.4-02 | 3.4 | Beat 只运行一个调度实例 | `compose.yaml` | 部分完成 | 未启动验证 |
| REQ-3.4-03 | 3.4 | MySQL/Redis 不暴露公网 | `compose.yaml`（仅 internal 网络，未映射宿主端口） | 部分完成 | 未启动验证 |
| REQ-3.4-04 | 3.4 | 服务健康检查 | `/healthz`、`/readyz`、compose healthcheck | 已完成 | 应用侧已实测 |
| REQ-3.4-05 | 3.4 | 数据持久化卷 | `compose.yaml`（named volumes） | 部分完成 | 未启动验证 |
| REQ-3.4-06 | 3.4 | 迁移作为独立发布步骤，不由多 web 实例并发执行 | `compose.yaml` 的 `migrate` 一次性任务 | 部分完成 | 未启动验证 |
| REQ-4.1-01 | 4.1 | 模块目录划分 | `backend/apps/*` | 部分完成 | 已建：core、identity、factory、masterdata、wms、workflow、integration、analytics；其余模块在对应阶段创建，避免空壳 |
| REQ-4.1-02 | 4.1 | 不创建顶层 `platform.py` | — | 已完成 | 无该文件 |
| REQ-4.2-01 | 4.2 | 模块内分层（models/serializers/views/services/selectors/tasks/tests） | `apps/*` | 已完成 | 简单模块适当合并，未制造无意义目录 |
| REQ-4.3-01 | 4.3 | View 不含业务逻辑 | `apps/*/views.py` | 已完成 | 视图只做鉴权、调用服务/查询、返回响应 |
| REQ-4.3-02 | 4.3 | Serializer 不做跨模块副作用 | `apps/*/serializers.py` | 已完成 | 字段级校验仅在序列化器 |
| REQ-4.3-03 | 4.3 | 关键流程写在 service 并使用事务 | `apps/core/services.py`、`apps/identity/services.py`、`apps/workflow/services.py` | 已完成 | 审批状态迁移与审计同事务 |
| REQ-4.3-04 | 4.3 | 不使用 signals 自动连锁创建关键单据 | 全局 | 已完成 | 未使用 post_save 等信号创建业务单据 |
| REQ-4.3-05 | 4.3 | 前端计算结果不得决定库存扣减 | 设计约定 | 已完成 | 阶段 2 库存服务由后端计算；文档已声明 |
| REQ-4.4-01 | 4.4 | 强一致操作同步完成，最终一致操作走 Outbox | `apps/core/services.py::publish_event`、`apps/integration/tasks.py` | 已完成 | 至少一次投递 + 消费者幂等 |

## 四、数据设计（任务书 5）

| 编号 | 来源 | 需求 | 实现位置 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| REQ-5.1-01 | 5.1 | MySQL 8.4 / InnoDB / utf8mb4 / 严格模式 | `config/settings/base.py` | 部分完成 | 版本偏差见 `docs/assumptions.md` |
| REQ-5.1-02 | 5.1 | 排序规则明确并记录 | `utf8mb4_0900_ai_ci`（测试库显式配置），`docs/data-model.md` | 已完成 | 大小写敏感问题在序列化器层处理，不依赖排序规则 |
| REQ-5.1-03 | 5.1 | 存储 UTC、`USE_TZ=True`、界面 Asia/Shanghai | `config/settings/base.py`、`frontend/src/utils/format.ts` | 已完成 | 跨日/跨月边界有单测（`format.spec.ts`） |
| REQ-5.1-04 | 5.1 | 使用专用应用账号，不用 root | `.env.example`、本机 `yishang_app@localhost` | 已完成 | 生产由编排注入 |
| REQ-5.2-01 | 5.2 | 通用字段（id/company/created_at/by/updated_at/by/version） | `apps/core/models.py::BaseModel` | 已完成 | 按实体需要附加组织字段，未机械铺满 |
| REQ-5.3-01 | 5.3 | 数量 Decimal(20,6)、金额按币种精度 | `apps/core/constants.py`、各模型 | 已完成 | `test_decimal_fields_use_decimal_not_float` |
| REQ-5.3-02 | 5.3 | 禁止 float 累计金额与库存 | 后端 DecimalField + 前端 decimal.js | 已完成 | `decimal.spec.ts` 锁定该约定 |
| REQ-5.3-03 | 5.3 | API 的 Decimal 以字符串输出 | `apps/core/serializers.py` | 已完成 | 前端类型中金额一律 `string` |
| REQ-5.3-04 | 5.3 | 舍入规则与发生环节明确 | `docs/data-model.md`（HALF_UP，服务层落库前） | 已完成 | 前端同样 HALF_UP，但最终以后端为准 |
| REQ-5.3-05 | 5.3 | 保存交易单位、基本单位、换算率与换算后数量 | `masterdata.Material`、`UoMConversion` | 部分完成 | 主数据已具备；单据侧换算在阶段 2 随单据落地 |
| REQ-5.4-01 | 5.4 | 业务编码 / 单据号 / SKU 组合唯一 | 各模型 `UniqueConstraint` | 已完成 | 数据库层约束，含 `uq_*` 命名 |
| REQ-5.4-02 | 5.4 | 同一业务事件处理唯一（幂等） | `core.IdempotencyRecord`（scope+key 唯一） | 已完成 | `test_idempotency_scope_key_unique` |
| REQ-5.4-03 | 5.4 | 库存余额维度唯一 + NULL 规范化键 | `docs/data-model.md` 设计约定 | 设计已完成 | 库存表在阶段 2 建立，必须先落规范化维度键再启用唯一约束 |
| REQ-5.4-04 | 5.4 | 不允许负数量的必要检查约束 | `docs/inventory-rules.md` | 设计已完成 | 阶段 2 由库存服务 + CHECK 约束共同保证 |
| REQ-5.4-05 | 5.4 | 外键关系及删除保护 | 各模型 `on_delete=PROTECT` | 已完成 | 已使用主数据不提供物理删除接口 |
| REQ-5.5-01 | 5.5 | 主数据使用后优先停用 | 各 ViewSet 的 `set-active` | 已完成 | 用户/角色/物料等均无 DELETE |
| REQ-5.5-02 | 5.5 | 已过账单据不得物理删除 | 阶段 2+ 单据模型 | 未开始 | 设计约定已写入 `docs/inventory-rules.md` |
| REQ-5.5-03 | 5.5 | 审计与库存流水不可通过普通接口修改 | 审计：只读接口；库存流水：阶段 2 | 部分完成 | 审计已实现 |
| REQ-5.6-01 | 5.6 | 关键服务使用 `transaction.atomic()` | `apps/core/services.py`、`apps/workflow/services.py` | 已完成 | 编号取号、审批迁移、发件箱写入均在事务内 |
| REQ-5.6-02 | 5.6 | 必要时 `select_for_update()`，固定加锁顺序 | `apps/core/services.py::generate_code` | 已完成 | 先锁规则行再锁流水行 |
| REQ-5.6-03 | 5.6 | 不存在余额行时不能假定已加锁，靠唯一约束并发创建 | `docs/inventory-rules.md` | 设计已完成 | 阶段 2 实施并测试 |
| REQ-5.6-04 | 5.6 | 死锁/锁超时有限重试且幂等 | `docs/api-conventions.md`（重试约定） | 设计已完成 | 阶段 2 随库存过账实现 |
| REQ-5.7-01 | 5.7 | 提交迁移、生产不自动 makemigrations | 迁移文件已提交；compose 中迁移为独立步骤 | 已完成 | — |
| REQ-5.7-02 | 5.7 | 空库与已有数据升级测试、备份与恢复步骤 | `docs/backup-restore.md` | 部分完成 | 文档已完成；恢复演练未执行（阶段 7） |
| REQ-5.7-03 | 5.7 | 说明 MySQL 部分 DDL 不可事务回滚，不虚假保证自动恢复 | `docs/backup-restore.md` | 已完成 | 已明示 |

## 五、认证、权限与审计（任务书 6）

| 编号 | 来源 | 需求 | 实现位置 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| REQ-6.1-01 | 6.1 | 同域部署，`/api/v1/` 前缀 | `config/urls.py`、`YISHANG_API_PREFIX` | 已完成 | 前端 Vite 代理保持一致同源语义 |
| REQ-6.1-02 | 6.1 | Session 认证，Cookie HttpOnly / 生产 Secure | `config/settings/base.py`、`prod.py` | 已完成 | 生产强制 HTTPS 相关项 |
| REQ-6.1-03 | 6.1 | 所有写操作 CSRF，登录接口同样防护 | `identity/auth/csrf/` + DRF SessionAuthentication | 已完成 | HTTP 验证：缺 CSRF 写操作 403 |
| REQ-6.1-04 | 6.1 | 退出使服务端会话失效 | `identity/auth/logout/` | 已完成 | HTTP 验证：退出后访问 403 |
| REQ-6.1-05 | 6.1 | 改密/停用按规则失效会话 | `identity/services.py`、`permission_version` | 已完成 | 停用后 `set-active` 拒绝登录 |
| REQ-6.1-06 | 6.1 | 独立移动端令牌认证 | — | 实施边界 | 任务书要求"以后再做"，本版不实现，避免堆叠多套认证 |
| REQ-6.1-07 | 6.1 | 设备上报使用独立设备凭证 | — | 未开始（阶段 5） | 设计见 `docs/hardware-integration.md` |
| REQ-6.2-01 | 6.2 | 首次迁移即自定义 User | `identity/migrations/0001_initial.py` | 已完成 | `AUTH_USER_MODEL=identity.User` |
| REQ-6.2-02 | 6.2 | 用户与员工档案分开，可一对一关联 | `identity.User` / `factory.Employee.user(OneToOne,nullable)` | 已完成 | 非所有员工都有登录账号 |
| REQ-6.3-01 | 6.3 | 四层权限（菜单/操作/接口/数据范围） | `permissions_registry`、`HasRequiredPermissions`、`resolve_data_scope` | 已完成 | 详见 `docs/permission-matrix.md` |
| REQ-6.3-02 | 6.3 | 权限编码形如 `模块.资源.动作` | 同上（当前 124 条） | 已完成 | 编码清单由注册表生成到文档（`docs/permission-matrix.md` §三） |
| REQ-6.3-03 | 6.3 | 六类数据范围 | `DataScopeType` | 已完成 | 公司/工厂/部门/仓库/本人/自定义 |
| REQ-6.3-04 | 6.3 | 权限合并逻辑写入文档并有测试 | `docs/permission-matrix.md` 第五节、`test_permissions.py` | 已完成 | 含"维度字段缺失即 fail-closed"断言 |
| REQ-6.4-01 | 6.4 | 列表查询过滤 | `apps/core/selectors.py::apply_data_scope` | 已完成 | — |
| REQ-6.4-02 | 6.4 | 详情访问校验 | 详情走同一 scope 查询集 | 已完成 | 范围外返回 404，不泄露存在性 |
| REQ-6.4-03 | 6.4 | 修改/审批/删除校验 | `HasRequiredPermissions` + `require_codes()` | 已完成 | — |
| REQ-6.4-04 | 6.4 | 关联对象选择校验 | 选项类接口同 scope | 已完成 | 避免通过 ID 探测范围外对象 |
| REQ-6.4-05 | 6.4 | 导出与异步任务校验 | — | 未开始（阶段 2 起） | 设计要求已写入 `docs/api-conventions.md` |
| REQ-6.4-06 | 6.4 | 附件下载校验 | `core.attachment.download` 权限 | 已完成 | — |
| REQ-6.4-07 | 6.4 | 图表汇总校验 | `analytics` 聚合按 scope | 已完成 | 看板接口按范围聚合 |
| REQ-6.4-08 | 6.4 | 不可凭前端 `factory_id` 决定权限 | 后端 scope 解析为唯一依据 | 已完成 | — |
| REQ-6.4-09 | 6.4 | 导出任务记录发起人，执行与下载分别校验 | — | 未开始（阶段 2 起） | 设计约定已文档化 |
| REQ-6.5-01 | 6.5 | Django 密码哈希，优先 Argon2 | `PASSWORD_HASHERS` | 已完成 | — |
| REQ-6.5-02 | 6.5 | 登录限流、失败锁定、解锁 | `failed_login_count`、`locked_until`、`LoginAttempt` | 已完成 | 有 `identity.user.unlock` 权限点 |
| REQ-6.5-03 | 6.5 | 密码与设备密钥不明文入日志 | 日志配置不含凭证字段 | 已完成 | — |
| REQ-6.5-04 | 6.5 | 参数化查询 | Django ORM | 已完成 | 未使用原生 SQL 拼接 |
| REQ-6.5-05 | 6.5 | 附件类型/大小/扩展名与内容检查 | `YISHANG_ATTACHMENT_*` | 已完成 | 扩展名白名单 + 大小上限 |
| REQ-6.5-06 | 6.5 | 对象存储默认私有 | `config/settings/base.py` | 部分完成 | 配置了 S3 才启用；本地开发为文件系统 |
| REQ-6.5-07 | 6.5 | 敏感导出留痕 | 审计记录导出动作 | 部分完成 | 审计框架就绪；导出功能在阶段 2 |
| REQ-6.5-08 | 6.5 | 生产 HTTPS + 安全响应头（CSP 等） | `prod.py`、`YISHANG_CSP_POLICY` | 已完成 | 未配置域名/来源时启动即失败 |
| REQ-6.5-09 | 6.5 | 职业健康等敏感信息单独授权 | — | 未开始（阶段 6） | 已声明不复用通用查看权限 |
| REQ-6.6-01 | 6.6 | 审计字段（操作人/组织/时间/请求标识/对象/动作/变更摘要/原因依据） | `core.AuditLog` | 已完成 | 字段齐备 |
| REQ-6.6-02 | 6.6 | 审计不保存完整密码、令牌或敏感原文 | `apps/core/services.py::record_audit` | 已完成 | 变更摘要为字段级 diff |
| REQ-6.6-03 | 6.6 | 关键审计与业务操作同事务 | 同上 | 已完成 | 非 `on_commit` 延迟写入 |

## 六、接口、异步任务与文件（任务书 7）

| 编号 | 来源 | 需求 | 实现位置 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| REQ-7.1-01 | 7.1 | 统一前缀 `/api/v1/` | `config/urls.py` | 已完成 | 可配置，未硬编码 |
| REQ-7.1-02 | 7.1 | 正确 HTTP 状态码 | `apps/core/exceptions.py` | 已完成 | 400/403/404/409/429 已使用 |
| REQ-7.1-03 | 7.1 | 统一错误格式 + 字段错误 | `yishang_exception_handler` | 已完成 | `details.fields` |
| REQ-7.1-04 | 7.1 | 分页最大页大小限制 | `apps/core/pagination.py` | 已完成 | 超限 400 `PAGE_SIZE_EXCEEDED` |
| REQ-7.1-05 | 7.1 | 排序/过滤白名单 | 各 ViewSet | 已完成 | 未透传任意查询表达式 |
| REQ-7.1-06 | 7.1 | OpenAPI 同步更新 | `/api/v1/schema/`、`/api/v1/docs/` | 已完成 | — |
| REQ-7.1-07 | 7.1 | 业务动作走 `{id}/action/` 形式 | `identity`、`workflow`、`core` 各动作接口 | 已完成 | 如 `{id}/set-active/`、`{id}/approve/` |
| REQ-7.2-01 | 7.2 | 幂等标识 | `core.IdempotencyRecord` | 已完成 | 表与唯一约束就绪 |
| REQ-7.2-02 | 7.2 | 同标识重复调用不产生重复结果 | 幂等表 + `request_hash` | 已完成 | 有单测覆盖唯一约束 |
| REQ-7.2-03 | 7.2 | 同标识不同内容拒绝 | `IdempotencyConflict` | 已完成 | 409 `IDEMPOTENCY_KEY_CONFLICT` |
| REQ-7.2-04 | 7.2 | 幂等结果与业务同事务提交 | 服务层约定 | 设计已完成 | 阶段 2 随库存过账落地 |
| REQ-7.2-05 | 7.2 | 单据状态与唯一约束作额外保障 | 设计约定 | 设计已完成 | 不把幂等表当唯一防线 |
| REQ-7.3-01 | 7.3 | Outbox 字段齐备 | `core.OutboxEvent` | 已完成 | 含 `dedup_key`、`attempts`、`next_retry_at`、`last_error` |
| REQ-7.3-02 | 7.3 | 事件与业务数据同事务写入 | `apps/core/services.py::publish_event` | 已完成 | — |
| REQ-7.3-03 | 7.3 | 后台轮询分发 | `apps/integration/tasks.py` | 部分完成 | 分发逻辑与手动触发接口已就绪；**Worker 未实际运行验证** |
| REQ-7.3-04 | 7.3 | 至少一次语义 + 消费者幂等 | `dedup_key`、`Notification.source_event_id` | 已完成 | 重放不重复通知有唯一约束保障 |
| REQ-7.3-05 | 7.3 | 超限进入人工处理 | `max_attempts`、`status=FAILED` | 已完成 | — |
| REQ-7.3-06 | 7.3 | 有权限的人工重放 | `integration.outbox.retry` 权限点 + `{id}/retry/` | 已完成 | — |
| REQ-7.3-07 | 7.3 | 保留业务关联关系 | `aggregate_type`/`aggregate_id`、`integration.DocumentLink` | 已完成 | — |
| REQ-7.3-08 | 7.3 | `on_commit` 仅加速唤醒，不替代 Outbox | 实现约定 | 已完成 | — |
| REQ-7.4-01 | 7.4 | Celery 适用任务（导入/导出/MRP/能源/告警/保养/通知/报表） | `config/celery.py`、各模块 `tasks.py` | 部分完成 | 框架与 `core/integration` 任务就绪；业务任务在阶段 2+；**未运行 Worker**。注：**MRP 采用同步计算，不经 Celery**（ADR-09） |
| REQ-7.4-02 | 7.4 | 任务可观测、超时、重试、失败原因 | `CELERY_TASK_TIME_LIMIT` 等 | 部分完成 | 配置就绪，未运行验证 |
| REQ-7.4-03 | 7.4 | 调度任务不重复生成业务单据 | 设计约定 | 设计已完成 | 阶段 2 起实现并测试 |
| REQ-7.4-04 | 7.4 | 长任务分批处理 | 设计约定 | 设计已完成 | 阶段 2 起 |
| REQ-7.4-05 | 7.4 | 执行前后持久化状态 | `OutboxEvent` 状态字段 | 已完成 | — |
| REQ-7.4-06 | 7.4 | 数据库是任务结果最终依据 | 设计约定 | 已完成 | 不把任务返回值当正式记录 |
| REQ-7.5-01 | 7.5 | 导入流程五步 | — | 未开始（阶段 2 起） | 流程与要求已写入 `docs/api-conventions.md` |
| REQ-7.5-02 | 7.5 | 提供模板、每行明确错误、不静默跳过 | — | 未开始（阶段 2 起） | 同上 |
| REQ-7.5-03 | 7.5 | 明确原子/分批导入策略 | — | 未开始（阶段 2 起） | 同上 |
| REQ-7.5-04 | 7.5 | 防公式注入与恶意文件 | 扩展名/大小校验已实现 | 部分完成 | 公式注入转义随导入功能实现 |
| REQ-7.5-05 | 7.5 | 下载链接设权限与有效期 | 附件下载走权限点 | 部分完成 | 有效期随对象存储启用后配置 |
| REQ-7.5-06 | 7.5 | 附件不能通过猜测地址绕过权限 | `core.Attachment` 下载接口 | 已完成 | 文件名不直接暴露为公开静态路径 |

## 七、界面与导航（任务书 8）

| 编号 | 来源 | 需求 | 实现位置 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| REQ-8.1-01 | 8.1 | 深蓝/科技蓝/白/浅灰，中文界面 | `frontend/src/styles/index.css`（设计令牌 + Element Plus 主题变量覆盖） | 已完成 | 品牌主色 `#1668dc` 统一到表格/按钮/标签/弹窗；主题变量由 `side-menu.spec.ts` 用 postcss 解析校验 |
| REQ-8.1-02 | 8.1 | 左侧导航、顶部工具栏、标签页、面包屑 | `frontend/src/layouts/BasicLayout.vue`、`components/SideMenu.vue` | 已完成 | **一级目录与二级页面按层级区分**：`depth` 生成 `ys-menu-group--dN` / `ys-menu-node--dN`，配合分组底色、缩进圆点、选中高亮块；`side-menu.spec.ts` 同时校验 DOM 层级 class 与样式规则；窄屏（≤1200px）自动折叠为图标态由 `composables/useAutoCollapse.ts` 控制，手动偏好优先、跨断点重置 |
| REQ-8.1-03 | 8.1 | 消息、待办、个人中心 | 顶部工具栏 + `system/NotificationList.vue` | 已完成 | — |
| REQ-8.1-04 | 8.1 | 不使用与业务无关的装饰 | 全局 | 已完成 | — |
| REQ-8.1-05 | 8.1 | 同一元素在不同页面观感一致（本条为界面样式增量） | `frontend/src/styles/index.css` 共享类 + 各视图模板；`frontend/tests/styles.spec.ts` | 已完成 | 共享类 `.ys-panel` / `.ys-panel--flush` / `.ys-section-title` / `.ys-stat-cards` / `.ys-stat-card` / `.ys-stat__label` / `.ys-stat__value` / `.ys-stat__hint` / `.ys-code-block`；视图内重复定义由 4 份降为 0，用例断言「任何 scoped 样式不得重定义共享类」 |
| REQ-8.1-06 | 8.1 | 窄屏可用（本条为响应式增量） | `frontend/src/composables/useAutoCollapse.ts`、`frontend/src/styles/index.css` 第 9 节、`frontend/tests/responsive.spec.ts` | 已完成 | 断点 1440（表格横向滚动）/ 1200（侧边栏自动折叠、内边距收窄）/ 992（标题竖排、统计卡整行、双列改单列、弹窗抽屉 92%）；JS 断点与 CSS 断点一致性由用例断言；**≤768px 手机布局与触摸手势未处理** |
| REQ-8.2-01 | 8.2 | 19 个一级菜单规划 | `permissions_registry.MENUS`（当前 51 项：10 个目录 + 41 个页面，一级入口 11 项） | 部分完成 | **只登记已实现的页面**；未实施模块不在菜单中放伪可用页面，改为在「实施进度」页标记规划状态 |
| REQ-8.2-02 | 8.2 | 各角色只显示有权访问的菜单 | `identity/menus/mine/` | 已完成 | 后端按权限下发，前端不硬编码 |
| REQ-8.3-01 | 8.3 | 查询、分页、排序 | `components/ProTable.vue`、`EntityListPage.vue` | 已完成 | 分页结构对齐后端 |
| REQ-8.3-02 | 8.3 | 新增、编辑、详情 | 各列表页 + 表单抽屉/对话框 | 已完成 | — |
| REQ-8.3-03 | 8.3 | 启停 | 各页 `set-active` 操作 | 已完成 | 主数据不提供物理删除 |
| REQ-8.3-04 | 8.3 | 导入导出 | 审计页提供当前页 CSV 导出 | 部分完成 | 业务批量导入导出在阶段 2 |
| REQ-8.3-05 | 8.3 | 附件 | `core.Attachment` | 已完成 | — |
| REQ-8.3-06 | 8.3 | 状态标签 | 各列表页状态列 | 已完成 | — |
| REQ-8.3-07 | 8.3 | 审批轨迹 | `workflow/instances/{id}/` + `ApprovalLog` | 已完成 | 我的申请/待办页可查看 |
| REQ-8.3-08 | 8.3 | 关联单据 | `integration.DocumentLink` 接口 | 部分完成 | 接口就绪；业务单据在阶段 2 |
| REQ-8.3-09 | 8.3 | 操作历史 | 审计日志页 | 已完成 | — |
| REQ-8.3-10 | 8.3 | 空、加载、异常状态 | 通用组件统一处理 | 已完成 | — |
| REQ-8.3-11 | 8.3 | 防重复提交 | 表单提交态禁用 | 已完成 | — |
| REQ-8.3-12 | 8.3 | 离开未保存表单时提示 | `utils` 表单守卫 | 已完成 | — |
| REQ-8.4-01 | 8.4 | 扫码枪按键输入 | — | 未开始（阶段 2 起） | 需业务单据配合 |
| REQ-8.4-02 | 8.4 | 移动浏览器扫码需 HTTPS | — | 未开始（阶段 2 起） | 部署文档已含 HTTPS 要求 |
| REQ-8.4-03 | 8.4 | 手工输入作为后备 | `masterdata/identifiers/resolve/` | 部分完成 | 标识解析接口已就绪，可按值手工查询 |
| REQ-8.4-04 | 8.4 | 扫码后展示识别对象与下一步操作 | `identifiers/resolve/` 返回 SKU/物料/批次 | 部分完成 | 解析已实现；"下一步操作"随业务页面落地 |
| REQ-8.4-05 | 8.4 | 错码/重复码/失效码明确提示 | `resolve` 接口返回明确原因 | 部分完成 | 错误码与提示就绪 |
| REQ-8.4-06 | 8.4 | 不因扫码成功绕过授权 | 后端权限独立校验 | 已完成 | 扫码仅是输入方式 |

## 八、主数据与服饰行业模型（任务书 9）

### 9.1 组织与工厂

| 编号 | 来源 | 需求 | 实现位置 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| REQ-9.1-01 | 9.1 | 公司、部门 | `factory.Company`、`factory.Department`（自关联 parent） | 已完成 | `departments/tree/` 提供树 |
| REQ-9.1-02 | 9.1 | 工厂、车间、线体、工位 | `Factory` / `Workshop` / `ProductionLine` / `Station` | 已完成 | 逐级外键，编码在同级唯一 |
| REQ-9.1-03 | 9.1 | 区域 | — | 实施边界 | 本版仓储侧用 `wms.Zone` 表达库区区域；生产侧区域随阶段 3 排产引入，未建独立主数据表 |
| REQ-9.1-04 | 9.1 | 员工、班组 | `Employee`、`Team`、`TeamMember` | 已完成 | 员工与用户一对一可空 |
| REQ-9.1-05 | 9.1 | 班次 | `factory.Shift`（`start_time`/`end_time`/`cross_day`/`break_minutes`） | 已完成 | `ShiftSerializer.validate()` 校验跨夜一致性 |
| REQ-9.1-06 | 9.1 | 排班规则 | — | 未开始（阶段 3） | 与线体排产同批交付 |
| REQ-9.1-07 | 9.1 | 排班日历 | — | 未开始（阶段 3） | 同上 |
| REQ-9.1-08 | 9.1 | 人员排班、班组排班 | `TeamMember` 已含 `start_date`/`end_date` | 部分完成 | 成员有效期已具备；按日历展开到日期级的排班在阶段 3 |
| REQ-9.1-09 | 9.1 | 层级关系合法 | 逐级外键（无跨级引用） | 已完成 | 结构上无法形成跨级挂靠 |
| REQ-9.1-10 | 9.1 | 已使用组织不得随意删除 | 外键 `on_delete=PROTECT` + 只提供 `set-active` | 已完成 | 无 DELETE 路由 |
| REQ-9.1-11 | 9.1 | 排班支持跨夜、休息、节假日、调班 | `Shift` 跨夜与休息时长已建模 | 部分完成 | 节假日与调班随排班日历在阶段 3 |
| REQ-9.1-12 | 9.1 | 检查人员时间冲突 | — | 未开始（阶段 3） | 对应必测案例 15（跨夜排班冲突） |
| REQ-9.1-13 | 9.1 | 班组排班展开为人员执行记录时保留成员快照 | `TeamMember` 记录关系本身 | 设计已完成 | 展开逻辑在阶段 3，快照字段随之落地 |

### 9.2 产品、款式与物料

| 编号 | 来源 | 需求 | 实现位置 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| REQ-9.2-01 | 9.2 | 统一物料分类（面料/辅料/半成品/成品/包装物/备品备件/消耗品） | `MaterialCategory.category_type` | 已完成 | 7 类由字典与分类类型共同约束 |
| REQ-9.2-02 | 9.2 | 款式/SPU → 颜色+尺码 → SKU | `Style` / `Color` / `Size` / `Sku` | 已完成 | `uq_sku_style_color_size` |
| REQ-9.2-03 | 9.2 | 成品 SKU 与库存物料唯一对应，避免两套库存编码 | `Sku.material`（OneToOne，唯一） | 已完成 | 唯一对应关系在数据库层强制 |
| REQ-9.2-04 | 9.2 | 编码、名称、规格、分类 | `Material.code/name/spec/category` | 已完成 | — |
| REQ-9.2-05 | 9.2 | 品牌、季节、年份、系列 | `Material.brand/season/year/series`、`Style` 同名 | 已完成 | — |
| REQ-9.2-06 | 9.2 | 颜色、尺码 | `Color`（含 `hex_code`）、`Size`（含 `size_group`） | 已完成 | — |
| REQ-9.2-07 | 9.2 | 图片 | `Material.image`、`Style.image` | 部分完成 | 字段就绪；图片上传走对象存储（阶段 2 启用） |
| REQ-9.2-08 | 9.2 | 基本单位 | `Material.base_uom` | 已完成 | 必填外键 |
| REQ-9.2-09 | 9.2 | 采购、销售辅助单位与换算规则 | `purchase_uom`/`purchase_factor`、`sales_uom`/`sales_factor`、`UoMConversion` | 已完成 | 换算率 Decimal(18,10) |
| REQ-9.2-10 | 9.2 | 批次管理 | `Material.is_batch_managed` | 已完成 | 面料的卷管理另见 `is_roll_managed` |
| REQ-9.2-11 | 9.2 | 安全库存 | `Material.safe_stock` + `ck_material_safe_stock_non_negative` | 已完成 | 不允许负值 |
| REQ-9.2-12 | 9.2 | 采购价、参考成本 | `Material.purchase_price`、`reference_cost` | 已完成 | 明确为**管理用参考成本**，非财务核算 |
| REQ-9.2-13 | 9.2 | 启停状态 | 全主数据 `is_active` + `set-active` | 已完成 | — |

### 9.3 面料特殊属性

| 编号 | 来源 | 需求 | 实现位置 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| REQ-9.3-01 | 9.3 | 成分 | `FabricProfile.composition` | 已完成 | — |
| REQ-9.3-02 | 9.3 | 幅宽、克重 | `FabricProfile.width_cm`、`gram_weight` | 已完成 | Decimal(20,6) |
| REQ-9.3-03 | 9.3 | 色号、缸号 | `FabricProfile.default_color_no`、`dye_lot_required` | 已完成 | 缸号要求可开关 |
| REQ-9.3-04 | 9.3 | 批次、卷号 | `Material.is_batch_managed`/`is_roll_managed`；卷实例在阶段 2 随库存落地 | 部分完成 | 主数据侧已标识管理要求 |
| REQ-9.3-05 | 9.3 | 米数、重量 | `FabricProfile.shrinkage_rate`；实测米重随库存卷记录 | 部分完成 | 卷级计量在阶段 2 |
| REQ-9.3-06 | 9.3 | 供应商批次 | `Identifier.batch_no` | 部分完成 | 字段就绪；随采购入库阶段 2 使用 |
| REQ-9.3-07 | 9.3 | 质检状态 | — | 未开始（阶段 3） | 质量状态属库存维度，随 QMS 落地 |
| REQ-9.3-08 | 9.3 | **米与公斤不得无条件统一换算**；换算因卷而异时保存实际计量值与该卷换算依据 | 设计约定 + `UoMConversion.is_fixed` | 设计已完成 | `is_fixed=false` 表示该换算非固定；卷级换算依据随阶段 2 库存卷记录保存 |

### 9.4 标识与追溯

| 编号 | 来源 | 需求 | 实现位置 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| REQ-9.4-01 | 9.4 | 六类标识分型（SKU 条码/批次码/卷号/箱码/RFID EPC/载具码） | `Identifier.identifier_type`（枚举分型） | 已完成 | 每类独立取值空间 |
| REQ-9.4-02 | 9.4 | **不能用一个字段混用** | 分型 + `uq_identifier_type_value` | 已完成 | 唯一约束按 (类型, 值) 生效，不同类可同值 |
| REQ-9.4-03 | 9.4 | 标识可解析到 SKU/物料/批次 | `identifiers/resolve/` | 已完成 | 返回识别对象 |

### 9.5 BOM 与工艺

| 编号 | 来源 | 需求 | 实现位置 | 状态 | 备注 |
| --- | --- | --- | --- | --- | --- |
| REQ-9.5-01 | 9.5 | BOM 版本、生效日期、审核状态 | `planning.Bom`（`/api/v1/planning/boms/`、`views/planning/BomList.vue`） | **已完成（阶段 3 第一步）** | 版本 + 生效区间 + `workflow` 审批；同一「款式/SKU 范围」同时只有一个生效版本 |
| REQ-9.5-02 | 9.5 | SKU 差异用料、标准用量、损耗 | `Bom.sku` / `BomLine.quantity` / `loss_rate` / `gross_quantity` | **已完成（阶段 3 第一步）** | 含损耗用量由后端计算（6 位小数 `ROUND_HALF_UP`），前端传值被忽略 |
| REQ-9.5-03 | 9.5 | 替代料审批 | `BomLine.line_type=substitute` + `substitute_for` | **已完成（阶段 3 第一步）** | 替代料行随所属 BOM 版本一起走 `workflow`，不新建审批体系 |
| REQ-9.5-04 | 9.5 | 工艺路线、标准工时、设备要求、工序质检点 | `planning.Routing` / `RoutingStep`（`/api/v1/planning/routings/`） | **已完成（阶段 3 第一步）** | `standard_hours` / `equipment_requirement` / `is_quality_gate`；与设备主数据的外键关联待阶段 4 |
| REQ-9.5-05 | 9.5 | 默认工艺 裁剪→缝制→整烫→检验→包装 | `planning.models.DEFAULT_ROUTING_STEPS` | **已完成（阶段 3 第一步）** | 不传工序即套用（「检验」带质检点）；显式空列表被拒（`ROUTING_STEP_REQUIRED`） |
| REQ-9.5-06 | 9.5 | 工单下达保存版本快照 | `services.build_bom_snapshot()` / `build_routing_snapshot()` | 部分完成（阶段 3 第一步） | 快照输出已实现并经真实库验证（服务与接口逐字段相等）；**快照落库依赖 MES 工单**（阶段 3 后续），对应必测案例 13 |

## 九、业务模块（任务书 10）

> 本节的 `未开始` 项**不是遗漏**，而是按任务书第十七章分阶段实施；每项均标注计划阶段。
> 阶段 0/1 **只做基座与主数据**，不创建空壳模块冒充完成。

### 10.1 系统管理与审批（阶段 1 ✅）

| 编号 | 来源 | 需求 | 实现位置 | 状态 |
| --- | --- | --- | --- | --- |
| REQ-10.1-01 | 10.1 | 用户、角色、菜单、资源 | `identity`（`permissions_registry` 157 权限 / 51 菜单） | 已完成 |
| REQ-10.1-02 | 10.1 | 部门、字典、参数 | `factory.Department`、`core.Dictionary`；参数由 `settings.YISHANG` 环境变量注入 | 已完成 |
| REQ-10.1-03 | 10.1 | 编码规则 | `core.CodeRule` + `CodeSequence`（`generate_code` 事务内取号） | 已完成 |
| REQ-10.1-04 | 10.1 | 登录与操作日志 | `identity.LoginAttempt`、`core.AuditLog` | 已完成 |
| REQ-10.1-05 | 10.1 | 附件 | `core.Attachment` | 已完成 |
| REQ-10.1-06 | 10.1 | 消息与待办 | `core.Notification`、`workflow` 待办接口 | 已完成 |
| REQ-10.1-07 | 10.1 | 定时任务 | `django-celery-beat` 已配置 | 部分完成（**未启动 Beat 验证**） |
| REQ-10.1-08 | 10.1 | 审批模板 | `workflow.ApprovalTemplate` + 节点 | 已完成 |
| REQ-10.1-09 | 10.1 | 顺序多级审批 | `ApprovalTemplateNode.seq` / `ApprovalStep` | 已完成 |
| REQ-10.1-10 | 10.1 | 金额、部门等条件路由 | `amount_min/amount_max`、`department_ids` | 已完成 |
| REQ-10.1-11 | 10.1 | 提交、通过、驳回、撤回 | `instances/{id}/{submit,approve,reject,withdraw}/` | 已完成 |
| REQ-10.1-12 | 10.1 | 审批意见、附件 | `ApprovalStep.comment`、`ApprovalLog` | 已完成 |
| REQ-10.1-13 | 10.1 | 代理审批需显式授权并留痕 | `ApprovalStep.assigned_user` + 日志 | 已完成 |
| REQ-10.1-14 | 10.1 | 流程版本快照 | `template_version` + `template_snapshot` | 已完成 |
| REQ-10.1-15 | 10.1 | 必要时限制申请人审批自己的单据 | `ApprovalTemplate.allow_self_approval` | 已完成 |
| REQ-10.1-16 | 10.1 | 审批通过与库存过账是不同动作 | 二者分离：`workflow` 不改库存 | 已完成（设计即分离） |

### 10.2 客户管理 CRM（阶段 2 基础 / 阶段 6 深化）

| 编号 | 来源 | 需求 | 计划阶段 | 状态 |
| --- | --- | --- | --- | --- |
| REQ-10.2-01 | 10.2 | 客户档案、联系人、地址 | 2 | **已完成**：`crm.Customer`、`crm.CustomerContact`；页面 `views/crm/CustomerList.vue`、`views/crm/CustomerContactList.vue`；API `/api/v1/crm/customers/`、`/api/v1/crm/customer-contacts/`；用例 `tests/test_crm_api.py`（**17 项**，含客户编码自动生成 6 项）。客户编码新增时留空即按编码规则（`CUS`）自动取号，可配置、可预演（见 §一之十一）；地址为档案文本字段；多地址簿与联系人分角色授权在阶段 6 深化 |
| REQ-10.2-02 | 10.2 | 分类、等级、标签 | 2 | 部分完成：分类 `category`、等级 `level`、合作状态 `status` 已完成，枚举由 `/api/v1/meta/` 下发；`tags` 已建模且接口可读写，但**前端通用表单不支持数组字段编辑，未提供界面入口**（见 `docs/progress.md` §6.8），故不写作已完成 |
| REQ-10.2-03 | 10.2 | 跟进与沟通 | 6 | 未开始：属服务过程记录，与阶段 6 的服务工单/投诉共用一套跟进模型，不在主数据阶段建表 |
| REQ-10.2-04 | 10.2 | 关联订单、发货、回款 | 2/3 | 未开始：`integration_documentlink` 基座已就绪并有唯一约束，但订单/发货/回款单据属阶段 2 后续增量，暂无可关联对象 |
| REQ-10.2-05 | 10.2 | 服务工单 | 6 | 未开始 |
| REQ-10.2-06 | 10.2 | 投诉流程 登记→分派→调查→处理→反馈→关闭 | 6 | 未开始（流程设计见 `docs/business-flows.md` 12.4） |
| REQ-10.2-07 | 10.2 | 反馈渠道 | 6 | 未开始 |
| REQ-10.2-08 | 10.2 | 满意度 | 6 | 未开始 |
| REQ-10.2-09 | 10.2 | 产品评价 | 6 | 未开始 |
| REQ-10.2-10 | 10.2 | 客户服务统计 | 6 | 未开始 |
| REQ-10.2-11 | 10.2 | 可关联 SKU、订单、批次和质量记录 | 6 | 部分就绪：SKU（`masterdata.Sku`）与六类标识分型（`masterdata.Identifier`）已实现；批次/质量记录与投诉的关联在阶段 6 落地 |
| REQ-10.2-12 | 10.2 | **平台使用评价与产品质量评价分开** | 6 | 设计约定已文档化（`docs/business-flows.md` 12.4）；两张评价表在阶段 6 分别建表，不合并 |

### 10.3 销售管理（阶段 2）

| 编号 | 来源 | 需求 | 状态 |
| --- | --- | --- | --- |
| REQ-10.3-01 | 10.3 | 销售计划 | 未开始（阶段 2 剩余） |
| REQ-10.3-02 | 10.3 | 销售订单 | **已通过阶段验收**：`sales.SalesOrder`/`SalesOrderLine` + `/api/v1/sales/orders/`，页面 `views/sales/SalesOrderList.vue` |
| REQ-10.3-03 | 10.3 | 颜色尺码矩阵 | 部分实现：订单行可关联成品 SKU（`SalesOrderLine.sku`，与库存物料一对一）；**矩阵批量录入界面未实现** |
| REQ-10.3-04 | 10.3 | 单价、折扣、金额 | 部分实现：单价与行/单头金额、税额**全部由后端计算**（`compute_line_amount`、`recalculate_order_amounts`，HALF_UP）；**折扣字段未实现** |
| REQ-10.3-05 | 10.3 | 交期、优先级 | **已通过阶段验收**：`order_date`/`expected_date`（单头与行）、`priority`（普通/加急），已进 meta 枚举 |
| REQ-10.3-06 | 10.3 | 审核、变更、取消 | 部分实现：提交 → 审批 → 批准/驳回/撤回已打通（复用 `workflow` 并回写状态）；取消与关闭已实现且**已发货不可取消**；**变更版本快照未实现** |
| REQ-10.3-07 | 10.3 | 库存占用 | **已通过阶段验收**：`POST /orders/{id}/reserve/`、`release/`；占用只改可用量、不写流水、幂等、只能占合格库存、库位/批次推荐 |
| REQ-10.3-08 | 10.3 | 发货申请、分批发货 | 部分实现：发货单 → 出库过账（`require_full_reservation`，必须由本订单占用覆盖），支持分批发货；**发货申请单、运单与物流对接未实现** |
| REQ-10.3-09 | 10.3 | 销售退货 | **已通过阶段验收**：`sales.SalesReturn`，收货过账进**待检** → 人工检验判定 → 合格回库/不合格；可退数量 = 已发货 − 已退货；退货入库继承原发货批次 |
| REQ-10.3-10 | 10.3 | 分销商 | 未开始（阶段 2 剩余） |
| REQ-10.3-11 | 10.3 | 历史分析、基础预测 | 未开始（阶段 3+；要求可解释、展示样本期间与误差） |
| REQ-10.3-12 | 10.3 | 应收与收款登记 | 未开始（阶段 2 剩余；**不等于完整财务记账**） |
| REQ-10.3-13 | 10.3 | 已发货部分不得直接删除或修改数量 | **已实现并有测试**：接口不提供 DELETE；`shipped_quantity`/`returned_quantity` 只读且由库存过账推进；已发货订单不可取消（`HAS_SHIPMENT`）；`ck_sales_order_line_shipped_within_quantity` 兜底 |
| REQ-10.3-14 | 10.3 | 订单变更保存版本 | 未实现：`version` 目前只用于乐观锁（`expected_version`），**业务变更快照未落库**（阶段 2 剩余） |

### 10.4 供应商管理 SRM（阶段 2）

| 编号 | 来源 | 需求 | 状态 |
| --- | --- | --- | --- |
| REQ-10.4-01 | 10.4 | 寻源、候选供应商、资质 | 部分完成：**资质已完成**——`srm.SupplierQualification`（资质类型、证书编号、发证机构、发证/到期日），含证书编号规范化去重 `dedup_key`（大小写不敏感；未填编号时为空值可并存多条）与后端计算的 `days_to_expiry` / `is_expired`；页面 `views/srm/SupplierQualificationList.vue`；用例 `tests/test_srm_api.py`。**寻源与候选供应商未开始** |
| REQ-10.4-02 | 10.4 | 准入审批 | 部分完成：`Supplier.admission_status`（待准入/已准入/未通过/暂停合作/已终止）与界面已具备，**但未接入 `workflow` 审批流程**——当前只是档案字段，不代替审批记录，故不写作已完成 |
| REQ-10.4-03 | 10.4 | 可供物料、报价及有效期 | 未开始：需先定义可供物料关联表（供应商 × 物料 × 报价 × 有效期），并与采购价联动，属阶段 2 后续增量 |
| REQ-10.4-04 | 10.4 | 分级、停用 | **已完成**：分级 `Supplier.grade`（A/B/C/D，枚举由 `/api/v1/meta/` 下发）；停用走 `set-active`（权限点 `srm.supplier.deactivate`），无 DELETE 路由，已使用供应商不被物理删除；用例覆盖启停与越权拒绝。其中「停用供应商不能新建正常采购订单」待采购订单落地后校验 |
| REQ-10.4-05 | 10.4 | 质量、技术、响应、交付、成本评价 | 未开始：本阶段**不写入任何评分数据**，界面也不展示评分，避免用默认值冒充评价结果 |
| REQ-10.4-06 | 10.4 | 权重总和 100% | 设计约定已文档化（`docs/assumptions.md`）；权重配置模型随评分功能落地 |
| REQ-10.4-07 | 10.4 | 保存评分依据 | 设计约定已文档化（`docs/assumptions.md`） |
| REQ-10.4-08 | 10.4 | 无数据不自动记零分，应标注缺失或重新分配有效权重 | 设计约定已文档化（`docs/assumptions.md`） |
| REQ-10.4-09 | 10.4 | 停用供应商不能新建正常采购订单，例外需授权 | **已完成（本轮）**：`procurement` 订单服务在创建 / 修改 / 提交时校验供应商未准入（`admission_status != admitted`）或已停用（`is_active = false`）即拒绝（`SUPPLIER_NOT_USABLE`）；持 `procurement.order.override_supplier` 且填写例外原因时可例外，订单落 `supplier_exception` / `supplier_exception_reason` 并写审计。用例 `test_suspended_supplier_cannot_be_used_without_reason`、`test_inactive_supplier_needs_override_permission`、`test_override_supplier_requires_reason_and_is_audited` |

### 10.5 采购管理（阶段 2）

| 编号 | 来源 | 需求 | 状态 |
| --- | --- | --- | --- |
| REQ-10.5-01 | 10.5 | 常规、计划、紧急申请 | **已完成**：`PurchaseRequisition.request_type`（`normal` / `planned` / `urgent`）+ 申请行（物料、数量、单位、需求日期、建议供应商）；单号 `PR{YYYYMMDD}{SEQ:4}`；页面 `views/procurement/RequisitionList.vue`；状态 `draft → submitted → approved / rejected / cancelled`，审批回写经 `workflow` 显式回调。用例 `test_requisition_create_persists_lines_and_generates_no`、`test_requisition_approval_writes_back_status` |
| REQ-10.5-02 | 10.5 | 采购订单、分批到货 | **已完成**：`PurchaseOrder` + 行（数量 / 单价 / 税率 / 金额 / 期望到货 / 仓库）；提交与审批；**分批到货**由多张收货单累计 `received_quantity`，订单状态 `partially_received → received`；`close_order` 可关闭未收完的订单。用例 `test_order_submit_then_approve_writes_back_status`、`test_order_can_be_closed_after_receipt`、`test_draft_receipts_reserve_remaining_quantity`。**未实现**：订单变更单 / 版本化修改（当前仅草稿可改） |
| REQ-10.5-03 | 10.5 | 待检收货、来料检验、合格入库 | **已完成（最低可用）**：收货过账落 `quarantine`；`inspect` 判 `qualified` 经 `stock.release_quality` 转合格；判不合格转 `rejected` 且不可动用。用例 `test_post_receipt_creates_quarantine_stock_and_blocks_issue`、`test_inspect_qualified_releases_stock_for_issue`、`test_inspect_rejected_keeps_stock_blocked`。**明确**：检验是**人工录入判定**，未接入检测设备（任务书 10.9 口径）；阶段 3 QMS 检验单落地后升级为引用检验单结果 |
| REQ-10.5-04 | 10.5 | 退货、到货差异 | **未开始**：本轮只实现「**不允许超收**」一条硬规则（`OVER_RECEIPT`）；退货出库与到货差异单属后续增量 |
| REQ-10.5-05 | 10.5 | 应付与付款登记 | **未开始**（任务书明确「登记不等于完整财务记账」） |
| REQ-10.5-06 | 10.5 | 采购价格与交付分析、备件采购 | **未开始**：分析报表属阶段 7 报表中心（准时率需先定义按行/按量口径）；备件采购可直接复用本模块流程，但备件档案属阶段 4 |
| REQ-10.5-07 | 10.5 | **区分实物到货、库存记账与质量放行** | **已完成**：三者实现上分离——`GoodsReceipt.status`（实物到货）、`receipt_document_id`（库存记账）、`inspection_result` + `quality_document_id`（质量放行）各自独立字段；库存只在过账时变动，质量状态只在放行时改变。用例 `test_post_receipt_creates_quarantine_stock_and_blocks_issue`、`test_inspect_qualified_releases_stock_for_issue` |

### 10.6 MRP 与计划（阶段 3）

| 编号 | 来源 | 需求 | 状态 |
| --- | --- | --- | --- |
| REQ-10.6-01 | 10.6 | 输入项（销售需求、生产计划、BOM、可用库存、在途、在制、占用、安全库存、提前期、批量规则） | **部分完成（阶段 3 第二步）**：已接销售需求（`sales_order`）+ 生效 BOM（`get_effective_bom` + `gross_quantity`）+ 可用库存 + 采购在途 + 占用（从可用量中扣除）；**未接**生产计划、在制（`in_progress_supply=not_implemented`，待 MES）、安全库存、提前期、批量规则（`lead_time_mode=lot_for_lot`）——逐条登记在 `docs/assumptions.md` §四之六 |
| REQ-10.6-02 | 10.6 | 时间分段净需求、多层 BOM 展开、损耗 | **已完成**：`day` / `week` 分段（`week` 归一到周一）、低层码分层净算、多层展开、损耗取含损耗用量 `gross_quantity`；用例 `test_net_requirement_nets_on_hand_and_on_order`、`test_explosion_uses_parent_net_requirement`、`test_low_level_code_net_calculated_once` |
| REQ-10.6-03 | 10.6 | 循环 BOM 检查 | **已完成**：`BOM_CYCLE_DETECTED`，并落一条 `failed` 运行记录（`test_cycle_bom_rejected_and_failed_run_recorded`） |
| REQ-10.6-04 | 10.6 | 缺料清单、采购建议、生产建议 | **已完成**：`MrpSuggestion`（`purchase` / `production`）+ 缺料清单页面；无 BOM 成品记入 `unexploded_materials`（`test_suggestion_type_rules_and_unexploded_materials`） |
| REQ-10.6-05 | 10.6 | 供需追溯、计算快照 | **已完成**：需求行保存来源（`source_type/source_id/source_no/source_line_no` + `path`）、建议保存 `detail.trace`、运行保存 `parameters` / `summary` 快照 |
| REQ-10.6-06 | 10.6 | 建议审核转单 | **已完成（采购路径）**：`convert_suggestion()` 生成**草稿采购申请** + `DocumentLink`（`generated_from`），后续仍走采购审批；**生产建议转单未实现**，返回 `PRODUCTION_ORDER_NOT_IMPLEMENTED`（等 MES） |
| REQ-10.6-07 | 10.6 | 销售订单与派生需求不得重复计算 | **已完成**：同一物料在低层码分层中只净算一次、父件按净需求展开（`test_low_level_code_net_calculated_once`） |
| REQ-10.6-08 | 10.6 | 已占用库存不得再作自由供给 | **已完成**：可用量 = `on_hand − frozen − reserved`，且只认合格质量状态（`test_usable_stock_excludes_frozen_reserved_and_unqualified`） |
| REQ-10.6-09 | 10.6 | 转单前重检有效性；同一建议不得重复转单 | **已完成**：锁内重取 → 运行状态 → 未转单 → 运行仍是最新已完成（`SUGGESTION_STALE`）→ 物料启用 → 类型；`test_convert_twice_rejected`、`test_convert_stale_suggestion_rejected`、`test_convert_inactive_material_rejected` |
| REQ-10.6-10 | 10.6 | 重算不自动覆盖已执行采购单/工单 | **已完成**：MRP 只读库存与在途，**不修改**任何已执行单据；重算只产生新运行，旧运行建议因 `SUGGESTION_STALE` / `MRP_RUN_NOT_ACTIVE` 不可再转单（`test_mrp_is_read_only_for_inventory`） |
| REQ-10.6-11 | 10.6 | 第一版可解释排程，**不宣称自动最优排产** | **已完成**：`lot_for_lot` 可解释净算，参数与分段净算过程全部落库可见；**不包含**产能约束与最优排产，文档与 UI 均未作此宣称 |

### 10.7 MES 制造执行（阶段 3）

| 编号 | 来源 | 需求 | 状态 |
| --- | --- | --- | --- |
| REQ-10.7-01 | 10.7 | 计划与工单、线体排产 | 未开始 |
| REQ-10.7-02 | 10.7 | 裁剪任务、裁片批次 | 未开始 |
| REQ-10.7-03 | 10.7 | 工序任务与派工 | 未开始（工位已含 `process_name`） |
| REQ-10.7-04 | 10.7 | 领料、补料、退料 | 未开始（经统一库存服务） |
| REQ-10.7-05 | 10.7 | 开工、暂停、恢复、完工 | 未开始 |
| REQ-10.7-06 | 10.7 | 数量、工时、不良报工 | 未开始（报工须幂等） |
| REQ-10.7-07 | 10.7 | 在制品转移、返工、报废 | 未开始 |
| REQ-10.7-08 | 10.7 | 完工检验与入库申请 | 未开始 |
| REQ-10.7-09 | 10.7 | 人员、物料、设备状态 | 未开始 |
| REQ-10.7-10 | 10.7 | 扫码、RFID 映射 | 部分就绪（`Identifier` 分型已实现） |
| REQ-10.7-11 | 10.7 | 吊挂载具和挂片流转 | 未开始（载具码已建模；**未获协议前不控制硬件**） |
| REQ-10.7-12 | 10.7 | 报工幂等、限制超量报工 | 设计约定（必测案例 14） |
| REQ-10.7-13 | 10.7 | 区分首次合格与返工合格，避免良率失真 | 设计约定已文档化 |
| REQ-10.7-14 | 10.7 | 返工必须关联原不良记录 | 设计约定已文档化 |
| REQ-10.7-15 | 10.7 | 投入/产出/在制/报废可核对 | 设计约定已文档化 |
| REQ-10.7-16 | 10.7 | 无协议时用人工扫码，不伪造硬件控制 | 已完成（本版无任何硬件控制） |

### 10.8 WMS 仓储（基础阶段 1 ✅ / 库存核心阶段 2 ✅）

| 编号 | 来源 | 需求 | 实现位置 | 状态 |
| --- | --- | --- | --- | --- |
| REQ-10.8-01 | 10.8 | 仓库、库区、储位 | `wms.Warehouse/Zone/Location` | 已完成 |
| REQ-10.8-02 | 10.8 | 收货、采购入库、待检、放行 | `wms/services/stock.py`（receipt / release_quality） | 部分完成：收货、待检放行已实现并测试；采购单驱动的入库待采购模块（阶段 2 剩余） |
| REQ-10.8-03 | 10.8 | 生产领料/退料、完工入库 | `wms/services/stock.py`（issue / receipt） | 部分完成：库存服务已具备出/入库能力；领料单与完工入库单属阶段 3 MES |
| REQ-10.8-04 | 10.8 | 销售出库、退货、采购退货 | `wms/services/stock.py`（issue） | 部分完成：出库能力与质量校验已实现并测试；销售/采购退货单据属阶段 2 剩余 |
| REQ-10.8-05 | 10.8 | 备件领用、退回 | `wms/services/stock.py`（共享服务） | 部分完成：备件库存走同一服务；备件单据属阶段 4（不重复建库存体系） |
| REQ-10.8-06 | 10.8 | 移库、调拨 | `wms/services/stock.py`（move） | 部分完成：同仓移库已实现（含并发守恒测试）；**跨仓调拨与在途状态未实现**，当前拒绝跨仓 |
| REQ-10.8-07 | 10.8 | 盘点、差异审批 | `wms/services/stock.py`（adjustment） | 部分完成：调整类型可用；**盘点单、范围冻结、差异审批未实现** |
| REQ-10.8-08 | 10.8 | 冻结、解冻 | `InventoryBalance.frozen` + 检查约束；`Location.is_locked` | 部分完成：冻结数量桶已建模并受约束保护；**冻结/解冻业务动作尚无入口** |
| REQ-10.8-09 | 10.8 | 占用、释放 | `InventoryBalance.reserved` + 检查约束 | 部分完成：占用数量桶已建模；**占用/释放动作需销售订单与工单驱动，未实现** |
| REQ-10.8-10 | 10.8 | 批次、卷号、箱码 | 库存维度 `batch_no`/`roll_no` + `masterdata.Identifier` | 已完成：批次/卷号为库存维度且不区分大小写（已测）；箱码仅在 `Identifier` 建模 |
| REQ-10.8-11 | 10.8 | 库位推荐 | — | 未开始（阶段 2） |
| REQ-10.8-12 | 10.8 | 标签打印 | — | 未开始（阶段 2） |
| REQ-10.8-13 | 10.8 | 库存余额与流水 | `wms.InventoryBalance` / `wms.InventoryTransaction`（迁移 `wms/0002`） | 已完成（只追加流水，无写入路由） |
| REQ-10.8-14 | 10.8 | 库存维度（公司+物料+仓库+储位+批次/卷号+质量状态） | `dimension_key` UNIQUE + `build_dimension_key()` | 已完成（并发创建仅一行，已测） |
| REQ-10.8-15 | 10.8 | 四类数量（实存/冻结/占用/可用） | `InventoryBalance.on_hand/frozen/reserved` + `available` | 已完成（检查约束保证非负且 frozen+reserved<=on_hand） |
| REQ-10.8-16 | 10.8 | 冻结与占用交叉规则明确，避免重复扣减 | 互斥数量桶 + 检查约束 | 已完成（桶互斥，由 DB 检查约束强制）；可追溯分配记录属阶段 3 |
| REQ-10.8-17 | 10.8 | 统一库存服务 | `apps/wms/services/stock.py` | 已完成 |
| REQ-10.8-18 | 10.8 | 默认禁止负库存 | `Warehouse.allow_negative_stock` 默认 false + `YISHANG_ALLOW_NEGATIVE_STOCK` | 已完成（建模与配置） |
| REQ-10.8-19 | 10.8 | 待检、不合格库存不能直接领用或销售 | `_assert_quality_allowed` | 已完成（待检/不合格出库被拒，已测） |
| REQ-10.8-20 | 10.8 | 所有变更生成流水 | `wms.InventoryTransaction`（只追加） | 已完成 |
| REQ-10.8-21 | 10.8 | 调拨发出后进入在途，不计入目标可用 | 仅设计约定 | 未实现：跨仓调拨未实现，当前直接拒绝跨仓 |
| REQ-10.8-22 | 10.8 | 盘点需处理期间移动，首版范围冻结 | 仅设计约定 | 未实现 |
| REQ-10.8-23 | 10.8 | 冲销不能忽略下游已消耗事实 | `_assert_reversible` | 已完成（下游已消耗时拒绝，已测） |

### 10.9 QMS 质量（阶段 3）

| 编号 | 来源 | 需求 | 状态 |
| --- | --- | --- | --- |
| REQ-10.9-01 | 10.9 | 检验项目 | 未开始 |
| REQ-10.9-02 | 10.9 | 标准及版本 | 未开始 |
| REQ-10.9-03 | 10.9 | 来料、首件、过程、成品、出货检验 | 未开始 |
| REQ-10.9-04 | 10.9 | 实测值与附件 | 未开始（`core.Attachment` 可复用） |
| REQ-10.9-05 | 10.9 | 自动阈值判定、人工复核 | 未开始 |
| REQ-10.9-06 | 10.9 | 不合格处置、返工、退货、报废、让步接收 | 未开始 |
| REQ-10.9-07 | 10.9 | 纠正预防措施、质量知识库、追溯与分析 | 未开始 |
| REQ-10.9-08 | 10.9 | 检验单保存标准快照 | 设计约定已文档化 |
| REQ-10.9-09 | 10.9 | 区分抽样数量与批次数量 | 设计约定已文档化 |
| REQ-10.9-10 | 10.9 | 检验结果修改留痕 | 设计约定已文档化（复用审计） |
| REQ-10.9-11 | 10.9 | 质量放行通过库存服务改变质量状态 | 接口已就绪并已测（`wms/services/stock.py::release_quality`、`wms.quality.release`）；QMS 检验单属阶段 3 |
| REQ-10.9-12 | 10.9 | 不合格转合格必须有授权处置依据 | 设计约定已文档化 |
| REQ-10.9-13 | 10.9 | 未配置真实检测接口时标明人工录入 | 设计约定已文档化 |

### 10.10 设备 EAM/CMMS（阶段 4）

| 编号 | 来源 | 需求 | 状态 |
| --- | --- | --- | --- |
| REQ-10.10-01 | 10.10 | 设备档案、类型、台账、品牌型号厂家、购置日期、所属区域/工厂/线体、保修期 | 未开始（工厂/线体主数据已就绪可复用） |
| REQ-10.10-02 | 10.10 | 零部件装机关系、配件与备件、寿命/有效期、备件采购申请 | 未开始（备件主数据复用 `masterdata`，**不重复建库存体系**） |
| REQ-10.10-03 | 10.10 | 保养：项目、标准、周期计划、任务、日历、执行、验收、超期提醒 | 未开始 |
| REQ-10.10-04 | 10.10 | 维修：报修、派工、接单、停机记录、备件领用、维修过程、验收关闭、费用与故障原因 | 未开始（备件领用经统一库存服务） |
| REQ-10.10-05 | 10.10 | 点巡检：项目、路线、计划、任务、测量记录、异常转报修 | 未开始 |
| REQ-10.10-06 | 10.10 | 监控：状态、测点、历史曲线、异常告警、自动生成检修任务、告警与工单去重 | 未开始（依赖阶段 5 采集） |
| REQ-10.10-07 | 10.10 | OEE 公式（时间开动率×性能开动率×良品率） | 设计约定已文档化 |
| REQ-10.10-08 | 10.10 | 混合产品按标准节拍计算理论时间 | 设计约定已文档化 |
| REQ-10.10-09 | 10.10 | 缺失数据或分母为零显示"无法计算"，不伪造数值 | 设计约定已文档化 |

### 10.11 EMS 能源（阶段 5）

| 编号 | 来源 | 需求 | 状态 |
| --- | --- | --- | --- |
| REQ-10.11-01 | 10.11 | 首页、仪表与测点、设备监控与运行记录 | 未开始 |
| REQ-10.11-02 | 10.11 | 能源看板，水/电/气/液统计，日月年报表 | 未开始 |
| REQ-10.11-03 | 10.11 | 尖峰平谷、价格版本 | 未开始（设计见 `docs/energy-calculation.md`） |
| REQ-10.11-04 | 10.11 | 阈值、区域/部门分析、单件与单位工时能耗 | 未开始 |
| REQ-10.11-05 | 10.11 | 越限、离线、单耗、总量报警 | 未开始 |
| REQ-10.11-06 | 10.11 | 调度建议与执行记录（**不默认自动控制**） | 设计约定已文档化 |
| REQ-10.11-07 | 10.11 | 区分瞬时值与累计值，累计值差分计算 | 设计已完成 |
| REQ-10.11-08 | 10.11 | 表计复位、换表保存事件 | 设计已完成 |
| REQ-10.11-09 | 10.11 | 倍率和单位有版本 | 设计已完成 |
| REQ-10.11-10 | 10.11 | 重复、迟到数据可重算相关汇总 | 设计已完成 |
| REQ-10.11-11 | 10.11 | 汇总任务可重复执行而不重复累计 | 设计已完成（区间覆盖写） |
| REQ-10.11-12 | 10.11 | 父子表不重复加总 | 设计已完成 |
| REQ-10.11-13 | 10.11 | 分时价格跨时段采样不足时明确分摊方法并标注估算 | 设计已完成 |
| REQ-10.11-14 | 10.11 | 不同液体介质与量纲不混加 | 设计已完成 |

### 10.12 厂内物流（阶段 6）

| 编号 | 来源 | 需求 | 状态 |
| --- | --- | --- | --- |
| REQ-10.12-01 | 10.12 | 取料、送料、回收任务；任务来源、起终点 | 未开始 |
| REQ-10.12-02 | 10.12 | 执行人或设备；派发、接单、取货、交接、完成 | 未开始 |
| REQ-10.12-03 | 10.12 | 异常与取消 | 未开始 |
| REQ-10.12-04 | 10.12 | 扫码凭据 | 部分就绪（`Identifier` 分型已实现） |
| REQ-10.12-05 | 10.12 | AGV、穿梭车、堆垛机档案及状态 | 未开始（**未获协议不控制硬件**） |
| REQ-10.12-06 | 10.12 | 物流任务完成不绕过库存服务，需库存变动时调用对应服务并保证幂等 | 设计约定已文档化 |

### 10.13 EHS 安全环保（阶段 6）

| 编号 | 来源 | 需求 | 状态 |
| --- | --- | --- | --- |
| REQ-10.13-01 | 10.13 | 安全：制度与版本、培训签到考核、风险分级、隐患整改复查、事故调查、职业健康、应急预案演练与处置 | 未开始 |
| REQ-10.13-02 | 10.13 | 环保：排污、固废/危废、废水废气、监测、转移凭证、许可与合规资料、到期提醒 | 未开始 |
| REQ-10.13-03 | 10.13 | 消防：设施、巡检、演练、动火作业、防火防爆 | 未开始 |
| REQ-10.13-04 | 10.13 | 设备设施安全：特种设备、检验期限、检维修许可、防爆防静电检查 | 未开始 |
| REQ-10.13-05 | 10.13 | 隐患流程 上报→分级→分派→整改→复查→关闭 | 设计已完成（`docs/business-flows.md` 12.5） |
| REQ-10.13-06 | 10.13 | 复查不合格可退回整改，超期提醒留痕 | 设计约定已文档化 |
| REQ-10.13-07 | 10.13 | 不宣称辅助记录自动满足全部法规要求 | 已完成（范围声明） |

### 10.14 工业终端安全（阶段 6）

| 编号 | 来源 | 需求 | 状态 |
| --- | --- | --- | --- |
| REQ-10.14-01 | 10.14 | 主机资产、系统版本、防病毒软件状态、特征库更新时间 | 未开始 |
| REQ-10.14-02 | 10.14 | 补丁台账、配置检查、风险整改、扫描报告附件、巡检与提醒 | 未开始 |
| REQ-10.14-03 | 10.14 | **明确区分人工登记 / 代理采集 / 文件导入** | 设计已完成（`docs/hardware-integration.md` 第五节） |
| REQ-10.14-04 | 10.14 | 不将人工录入包装成自动检测 | 设计约定已文档化 |
| REQ-10.14-05 | 10.14 | 补丁和重启操作需审批与维护窗口 | 设计约定已文档化（复用 `workflow`） |
| REQ-10.14-06 | 10.14 | 不自研杀毒引擎 | 已完成（范围声明） |

### 10.15 内部协同中心（阶段 1 部分 ✅）

| 编号 | 来源 | 需求 | 实现位置 | 状态 |
| --- | --- | --- | --- | --- |
| REQ-10.15-01 | 10.15 | 业务事件 | `core.OutboxEvent` | 已完成 |
| REQ-10.15-02 | 10.15 | Outbox 状态 | `integration/outbox-events/`（含 `health`） | 已完成 |
| REQ-10.15-03 | 10.15 | 跨模块流程、单据关系 | `integration.DocumentLink`、`document-links/` | 已完成（基座） |
| REQ-10.15-04 | 10.15 | 失败、重试、人工处理 | `status=FAILED`、`{id}/retry/`、`integration.outbox.retry` | 已完成（**Worker 未运行验证**） |
| REQ-10.15-05 | 10.15 | 数据导入任务 | — | 未开始（阶段 2 起） |
| REQ-10.15-06 | 10.15 | 定时任务 | `django-celery-beat` 配置 | 部分完成 |
| REQ-10.15-07 | 10.15 | 消息规则 | `core.Notification`（事件驱动） | 部分完成（规则配置界面在阶段 2） |
| REQ-10.15-08 | 10.15 | 硬件连接配置 | — | 未开始（阶段 5） |
| REQ-10.15-09 | 10.15 | 普通业务人员仅看到与自身相关的业务进度 | `workflow/instances/mine/`、`todo/`、`participated/` | 已完成 |

### 10.16 基础成本（阶段 7）

| 编号 | 来源 | 需求 | 状态 |
| --- | --- | --- | --- |
| REQ-10.16-01 | 10.16 | 直接材料、工时成本、外购备件维修成本、可配置制造费用分摊、单工单与单产品参考成本 | 未开始 |
| REQ-10.16-02 | 10.16 | 区分标准成本 / 实际归集成本 / 估算分摊成本 | 设计约定已文档化 |
| REQ-10.16-03 | 10.16 | 库存计价可用移动加权平均，但独立保存数量与价值流水、处理退货冲销、明确成本范围 | 设计已完成（`docs/inventory-rules.md` 第七节） |
| REQ-10.16-04 | 10.16 | **不得将参考成本描述为已完成完整财务核算** | 已完成（范围声明） |

## 十、硬件采集（任务书 11）

| 编号 | 来源 | 需求 | 实现位置 / 边界 | 状态 |
| --- | --- | --- | --- | --- |
| REQ-11.1-01 | 11.1 | 传感器 5 台（温度/电压/振动/电流） | 测点设计为完全可配置；**类型分配未明确**见 `docs/assumptions.md` A-01 | 设计已完成 |
| REQ-11.1-02 | 11.1 | 智能水表 2 台、智能电表 2 台 | 同上；协议待确认（A-02） | 设计已完成 |
| REQ-11.2-01 | 11.2 | 模型：连接配置→网关/设备→测点→原始消息→标准化读数→汇总/告警 | `docs/hardware-integration.md` 第二节 | 设计已完成 |
| REQ-11.2-02 | 11.2 | 读数必带字段（设备时间/接收时间/单位/质量/来源/消息 ID/去重依据/处理状态） | 同上 | 设计已完成 |
| REQ-11.3-01 | 11.3 | 独立可配置模拟器 | — | 未开始（阶段 5） |
| REQ-11.3-02 | 11.3 | HTTP 采集入口 | — | 未开始（阶段 5） |
| REQ-11.3-03 | 11.3 | 设备独立凭证 | — | 未开始（阶段 5） |
| REQ-11.3-04 | 11.3 | 请求限流与批次大小限制 | — | 未开始（阶段 5） |
| REQ-11.3-05 | 11.3 | 重复数据处理 | — | 未开始（阶段 5） |
| REQ-11.3-06 | 11.3 | 读数展示与历史查询 | — | 未开始（阶段 5） |
| REQ-11.3-07 | 11.3 | 离线告警、越限告警 | — | 未开始（阶段 5） |
| REQ-11.3-08 | 11.3 | 模拟标识 | — | 未开始（阶段 5，但已要求"必须显著标识"） |
| REQ-11.3-09 | 11.3 | 采集失败日志 | — | 未开始（阶段 5） |
| REQ-11.3-10 | 11.3 | MQTT/Modbus 保留适配设计，按真实设备开发，**不预先宣称完成** | `docs/hardware-integration.md` 第三节 | 已声明边界 |
| REQ-11.4-01 | 11.4 | 原始数据保存周期可配置 | — | 设计已完成 |
| REQ-11.4-02 | 11.4 | 分钟/小时/日汇总 | `docs/energy-calculation.md` 第四节 | 设计已完成 |
| REQ-11.4-03 | 11.4 | 归档清理有审计 | 设计约定 | 设计已完成 |
| REQ-11.4-04 | 11.4 | 初期用 MySQL 普通表 + 索引；**不盲目分区** | 设计已完成 | 设计已完成 |
| REQ-11.5-01 | 11.5 | 默认只读采集；不开放数据库/工控设备到互联网；远程访问受控 | `docs/hardware-integration.md` 第四节 | 已声明边界 |
| REQ-11.5-02 | 11.5 | 不在平台中下发安全逻辑修改 | 同上 | 已完成（本版无任何硬件控制能力） |

## 十一、业务闭环（任务书 12）

| 编号 | 来源 | 闭环 | 基座实现位置 | 状态 |
| --- | --- | --- | --- | --- |
| REQ-12.1-01 | 12.1 | 订单到交付 | `apps/sales/services.py` + 统一库存服务 | **部分打通**：销售侧「销售订单 → 库存占用 → 发货出库 → 退货 → 检验判定」与采购侧「申请 → 订单 → 到货 → 检验放行 → 合格库存」均已可用；**MRP 已打通**（销售需求 → 净算 → 采购建议转单，见 §一之七），**MES 工单 / 报工 / 成品入库未实现**，整条链路未打通（阶段 3） |
| REQ-12.1-02 | 12.1 | 可从订单查看所有关联单据与数量 | `GET /api/v1/sales/orders/{id}/chain/`（+ `integration.DocumentLink`） | **销售侧已实现**：一次返回订单、行交付进度（已发/已退/未发）、发货单、退货单与关联库存单据；跨模块统一关系表 `DocumentLink` 仍为基座就绪 |
| REQ-12.2-01 | 12.2 | 设备维修闭环 | 备件库存复用 `wms`，设备主数据在阶段 4 | 未打通（阶段 4） |
| REQ-12.3-01 | 12.3 | 能源告警闭环 | `docs/energy-calculation.md` 第五节 | 未打通（阶段 5） |
| REQ-12.4-01 | 12.4 | 客诉改善闭环 | `Identifier` 分型 + `DocumentLink` | 未打通（阶段 2/6） |
| REQ-12.5-01 | 12.5 | 安全整改闭环 | `core.Attachment` + `workflow` + 通知 | 未打通（阶段 6） |

> 详细设计见 `docs/business-flows.md`。**阶段 0/1 只交付这些闭环的平台基座**（权限、审批、
> 审计、主数据、单据关系、附件、通知），业务单据本身在后续阶段实现。

## 十二、报表与数据口径（任务书 13）

| 编号 | 来源 | 需求 | 实现位置 | 状态 |
| --- | --- | --- | --- | --- |
| REQ-13-01 | 13 | 每张报表说明数据来源、统计时间字段、组织范围、是否排除取消/冲销、是否含估算、更新时间 | `docs/api-conventions.md`、本矩阵 | 设计约定已文档化 |
| REQ-13-02 | 13 | 工作台看板从业务数据计算 | `analytics/dashboard/`（11 张卡片，来自各表实时聚合） | 已完成 |
| REQ-13-03 | 13 | 主数据完备度报表 | `analytics/masterdata-freshness/` | 已完成 |
| REQ-13-04 | 13 | 销售订单与交付 | — | 未开始（阶段 2/7） |
| REQ-13-05 | 13 | 采购到货与准时率 | — | 未开始（阶段 2/7） |
| REQ-13-06 | 13 | 库存余额与流水、库龄与低库存 | — | 未开始（阶段 2/7） |
| REQ-13-07 | 13 | 生产完成率、工序效率 | — | 未开始（阶段 3/7） |
| REQ-13-08 | 13 | 质量合格率与缺陷 | — | 未开始（阶段 3/7） |
| REQ-13-09 | 13 | 设备故障、维修与 OEE | — | 未开始（阶段 4/7） |
| REQ-13-10 | 13 | 能源消耗与费用 | — | 未开始（阶段 5/7） |
| REQ-13-11 | 13 | 客户投诉与满意度 | — | 未开始（阶段 6/7） |
| REQ-13-12 | 13 | 安全隐患整改、供应商评分 | — | 未开始（阶段 6/7） |
| REQ-13-13 | 13 | 准时率需定义按订单/行项目/数量；合格率需定义首次或最终；不同口径不混用同一名称 | 设计约定已文档化 | 已声明边界 |
| REQ-13-14 | 13 | 导出内容与页面筛选、权限保持一致 | 审计页当前页导出遵循筛选；业务导出阶段 2 | 部分完成 |

## 十三、测试与质量（任务书 14）

### 14.1 测试层级

| 编号 | 层级 | 实现位置 | 状态 |
| --- | --- | --- | --- |
| REQ-14.1-01 | 单元测试 | `backend/tests/test_core_services.py`、`test_crm_api.py`、`test_srm_api.py`、`test_wms_inventory.py` 等 | 已完成（148 项） |
| REQ-14.1-02 | MySQL 集成测试 | pytest 默认连 MySQL（`--reuse-db`） | 已完成 |
| REQ-14.1-03 | API 权限测试 | `backend/tests/test_permissions.py`（17 项）、`test_auth_api.py`（14 项，含 2 条登录 CSRF 回归） | 已完成 |
| REQ-14.1-04 | 并发事务测试 | `test_generate_code_unique_under_concurrency`、`test_wms_inventory.py` 真实多连接并发 | 部分完成（并发框架已验证；库存并发已完成；**工程数据「唯一生效版本」与 MRP「同一建议并发转单」未做真实多连接验证**，见 `docs/test-report.md` §15.7 / §16.7） |
| REQ-14.1-05 | 前端组件测试 | `frontend/tests/*.spec.ts`（9 文件 131 项） | 已完成 |
| REQ-14.1-08 | 文档一致性校验 | `backend/tests/test_docs_sync.py`（7 项）比对 `docs/user-guide.md` §11.5 事实行与权限点 / 菜单 / 模型 / 迁移 / 内置角色，并校验网页版说明与 Markdown 源一致 | 已完成（并做过「故意改错→按预期失败」反向验证） |
| REQ-14.1-06 | 端到端业务测试 | Playwright 配置就绪 | **未执行** |
| REQ-14.1-07 | 部署与恢复测试 | — | **未执行**（阶段 7） |

### 14.2 必测案例逐条对照

| # | 案例 | 状态 | 证据 / 说明 |
| --- | --- | --- | --- |
| 1 | 未登录访问被拒绝 | ✅ 已执行 | `test_unauthenticated_session_is_rejected`、`test_unauthenticated_requests_are_rejected`、HTTP 验证 |
| 2 | 无操作权限不能调用接口 | ✅ 已执行 | `test_operation_permission_required`、`test_approval_actions_require_permission` |
| 3 | 工厂和仓库范围不能越权 | ✅ 已执行 | `test_factory_scope_filters_list_and_blocks_out_of_range_create`、`test_warehouse_scope_limits_locations`、`test_company_boundary_is_applied` |
| 4 | 关联对象 ID 不能绕过范围限制 | ✅ 已执行 | `test_user_management_scope_is_enforced`、`test_scope_missing_dimension_fails_closed` |
| 5 | 重复过账不重复扣库存 | ✅ 已执行 | `test_same_idempotency_key_posts_once`、`test_api_idempotency_key_deducts_once`（库存侧）、`test_receipt_post_is_idempotent_with_header`、`test_inspect_with_idempotency_key_replays_without_second_release`（采购侧） |
| 6 | 并发出库不产生负库存 | ✅ 已执行 | `test_concurrent_issue_never_produces_negative_stock`（真实独立事务 + `Barrier`，非外层测试事务） |
| 7 | 新库存余额行并发创建不重复 | ✅ 已执行 | `test_concurrent_balance_creation_yields_single_row`（`dimension_key` UNIQUE + 保存点内 INSERT 重试方案） |
| 8 | 死锁重试不重复生成单据 | ✅ 已执行（库存侧） | `test_deadlock_retry_does_not_duplicate_ledger`、`test_non_retryable_error_is_not_retried`；采购转单的重复保护见 `test_convert_requisition_to_order_and_block_duplicates` |
| 9 | 不合格库存不可发货 | ✅ 已执行（库存侧） | `test_rejected_stock_cannot_be_issued`、`test_quarantine_stock_cannot_be_issued`、`test_inspect_rejected_keeps_stock_blocked`；**销售发货侧的发货校验**待销售模块落地后复验 |
| 10 | 已消耗库存不能任意冲销 | ✅ 已执行 | `test_reversal_blocked_when_stock_consumed`、`test_reversal_succeeds_after_stock_returned`、`test_double_reversal_is_rejected` |
| 11 | 调拨数量守恒 | 部分 | 同仓移库守恒已测（`test_move_conserves_quantity`、`test_concurrent_transfer_keeps_total`）；**跨仓调拨与在途状态未实现**（`test_move_to_other_warehouse_is_rejected` 记录当前边界） |
| 12 | MRP 不重复计算供需 | ✅ 已执行 | `test_low_level_code_net_calculated_once`（同一子件多层 BOM 只净算一次、父件按净需求展开）、`test_net_requirement_nets_on_hand_and_on_order`；真实 HTTP 链路见 `docs/test-report.md` §16.5 |
| 13 | BOM 历史快照不受修改影响 | 部分 | 快照机制已验证（`test_template_snapshot_survives_template_change`）；BOM 在阶段 3 |
| 14 | 报工、返工不重复计数 | 未执行 | 阶段 3 |
| 15 | 跨夜排班冲突正确 | 部分 | 跨夜建模与校验已测（`test_shift_cross_day_is_derived_not_trusted_from_client`、`test_shift_break_cannot_exceed_span`）；人员冲突检查在阶段 3 |
| 16 | 表计复位、迟到数据处理正确 | 未执行 | 阶段 5 |
| 17 | 报警去重及恢复正确 | 未执行 | 阶段 5（通知去重机制已验证可复用） |
| 18 | Outbox 重放不重复产生结果 | ✅ 已执行 | `test_outbox_dispatch_creates_notification_once`、`test_dispatch_is_at_least_once_but_notification_not_duplicated`、`test_publish_event_deduplicates_by_dedup_key` |
| 19 | 导入错误可定位到行 | 未执行 | 阶段 2 |
| 20 | 敏感附件不能越权下载 | ✅ 已执行 | `test_attachment_download_requires_permission` |
| 21 | 订单到交付链路通过 | 部分 | **采购子链路已通过**（申请 → 订单 → 收货 → 待检 → 放行）；**销售订单 → MRP → 采购建议已打通**（`test_mrp.py` + `docs/test-report.md` §16.5 真实链路）；**MES 生产领料 / 报工 / 成品入库段未打通**（阶段 3 第三步） |
| 22 | 备份可以恢复 | 未执行 | 阶段 7 |

> 另有超出的已执行用例：审计只写不改（`test_audit_log_is_write_once`）、审计随业务事务回滚
> （`test_audit_is_rolled_back_with_business_transaction`）、审计不保存密码（`test_audit_does_not_store_password`）、
> 取号并发唯一（`test_generate_code_unique_under_concurrency`）、幂等同键异体拒绝
> （`test_idempotent_execute_rejects_same_key_different_payload`）、审批自审限制
> （`test_self_approval_blocked_then_allowed_by_template_flag`）等。
> 完整清单与真实输出见 `docs/test-report.md`。

### 14.3 代码质量

| 编号 | 要求 | 状态 | 证据 |
| --- | --- | --- | --- |
| REQ-14.3-01 | Ruff 检查通过 | ✅ | `ruff check apps config tests` → All checks passed |
| REQ-14.3-02 | TypeScript 类型检查通过 | ✅ | `vue-tsc --build --force` 退出码 0 |
| REQ-14.3-03 | 前后端构建成功 | ✅ | `npm run build` 成功；`manage.py check` 无问题 |
| REQ-14.3-04 | 关键服务具备类型注解 | ✅ | 服务/选择器函数均带注解 |
| REQ-14.3-05 | 避免 N+1，使用 `select_related`/`prefetch_related` | ✅ | 列表查询按需 join |
| REQ-14.3-06 | 接口限制返回规模 | ✅ | 分页上限 200 |
| REQ-14.3-07 | 测试关键状态分支 | ✅ | 覆盖审批状态机、幂等冲突、范围失败等分支 |

### 14.4 性能

| 编号 | 要求 | 状态 |
| --- | --- | --- |
| REQ-14.4-01 | 先记录测试机器配置、数据规模、并发模型再给结果 | **未执行**（阶段 7） |
| REQ-14.4-02 | 百万级库存流水 / 采集读数、多用户并发查询、并发过账、大文件导出 | **未执行**（阶段 7） |
| REQ-14.4-03 | 性能目标在阶段 0 根据部署资源确定，不无依据承诺并发能力 | 已完成（**未做无依据承诺**） |

## 十四、演示数据与初始化（任务书 15）

| 编号 | 来源 | 需求 | 实现位置 | 状态 |
| --- | --- | --- | --- | --- |
| REQ-15-01 | 15 | 2 个工厂、多个车间/线体/工位 | `core/management/commands/seed_demo.py` | 已完成 |
| REQ-15-02 | 15 | 6 个款式、颜色尺码与 SKU | 同上 | 已完成 |
| REQ-15-03 | 15 | 原辅料、包装、备件 | 同上 | 已完成 |
| REQ-15-04 | 15 | 原料、成品、备件仓 | 同上 | 已完成 |
| REQ-15-05 | 15 | 客户、供应商 | — | **已完成**：`seed_demo` 新建客户 3 户（含分类/等级/信用额度/业务员）、客户联系人 4 人、供应商 3 家（面料/辅料/备件，含一家待准入）、供应商联系人 3 人、供应商资质 4 条（含已过期、未登记到期日、未填证书编号三种边界情形）。连续执行两次：首次新建 17 条，第二次「合计新建 0 条」，幂等性实测通过 |
| REQ-15-07 | 15 | 采购、销售、生产与库存单据 | — | 未开始（阶段 2/3） |
| REQ-15-08 | 15 | 质量异常、设备保养维修、投诉与安全隐患 | — | 未开始（阶段 3/4/6） |
| REQ-15-09 | 15 | 模拟传感器、水表、电表 | — | 未开始（阶段 5） |
| REQ-15-10 | 15 | 完整订单链路 | — | 未开始（阶段 2/3） |
| REQ-15-11 | 15 | 管理命令 `bootstrap_system` / `seed_demo` | `apps/core/management/commands/` | 已完成 |
| REQ-15-12 | 15 | 管理命令 `reconcile_inventory` / `rebuild_energy_summary` | — | 未开始（阶段 2 / 阶段 5） |
| REQ-15-13 | 15 | 命令具备重复执行保护 | `bootstrap_system`/`seed_demo` 幂等，有测试 | 已完成 |
| REQ-15-14 | 15 | `seed_demo` 禁止在生产环境误执行 | `test_seed_demo_refuses_production`、`test_seed_demo_requires_confirmation_outside_dev` | 已完成 |
| REQ-15-15 | 15 | 生产管理员通过安全初始化流程设置密码 | `bootstrap_system` 生产环境缺密码即失败；不覆盖既有密码 | 已完成 |
| REQ-15-16 | 15 | **不在代码中硬编码公开管理员密码** | 密码来自环境变量，未设置时随机生成并打印一次 | 已完成 |
| REQ-15-17 | 15 | 演示数据与真实采集来源明显区分 | 演示数据带标识；采集侧要求显著标注 | 部分完成（采集侧阶段 5） |

## 十五、部署、备份与运维（任务书 16）

| 编号 | 来源 | 需求 | 实现位置 | 状态 |
| --- | --- | --- | --- | --- |
| REQ-16.1-01 | 16.1 | 区分 development/test/staging/production | `config/settings/*.py` | 已完成 |
| REQ-16.1-02 | 16.1 | 配置由环境变量注入，`.env.example` 只放示例 | `.env.example` | 已完成 |
| REQ-16.2-01 | 16.2 | `DEBUG=False` | `prod.py` | 已完成 |
| REQ-16.2-02 | 16.2 | 域名、CSRF 来源、HTTPS（缺失即启动失败） | `prod.py` 抛 `ImproperlyConfigured` | 已完成 |
| REQ-16.2-03 | 16.2 | 非 root 容器 | `compose.yaml` / `deploy/docker/Dockerfile` | **未验证** |
| REQ-16.2-04 | 16.2 | 不公开 MySQL、Redis 管理端口 | `compose.yaml`（不映射宿主端口） | **未验证** |
| REQ-16.2-05 | 16.2 | 连接池或连接寿命合理配置 | `DB_CONN_MAX_AGE` | 已完成 |
| REQ-16.2-06 | 16.2 | 上传文件与代码分离、日志轮转 | volume 分离 | **未验证** |
| REQ-16.2-07 | 16.2 | 静态资源正确部署 | `deploy/nginx/` | **未验证** |
| REQ-16.2-08 | 16.2 | 不用 runserver 对外提供生产服务 | `compose.yaml` 使用 Gunicorn | 已完成（配置），**未验证** |
| REQ-16.3-01 | 16.3 | 存活/就绪检查 | `/healthz`、`/readyz` | 已完成（实测） |
| REQ-16.3-02 | 16.3 | Worker 状态、任务积压、Outbox 失败数量 | `integration/outbox-events/health/` | 部分完成（Outbox 健康接口已实测；Worker 未运行） |
| REQ-16.3-03 | 16.3 | 采集离线、磁盘与备份状态、接口错误率 | — | 未开始（阶段 5/7） |
| REQ-16.3-04 | 16.3 | 日志带 `request_id`，任务带任务 ID 与事件 ID | `core/middleware.py`、`core/logging.py` | 已完成 |
| REQ-16.4-01 | 16.4 | MySQL 定时备份、binlog、附件备份、加密与访问控制、保留周期 | `docs/backup-restore.md` | 设计已完成，**未执行** |
| REQ-16.4-02 | 16.4 | 定期恢复演练、记录 RPO/RTO | 同上（RPO/RTO 待项目方确认） | **未执行** |
| REQ-16.4-03 | 16.4 | 数据库与附件恢复需核对引用一致性 | 同上第六节 | 设计已完成 |
| REQ-16.5-01 | 16.5 | 发布前测试迁移、备份、兼容性迁移优先 | `docs/deployment.md` 第六节 | 设计已完成 |
| REQ-16.5-02 | 16.5 | 停止冲突后台任务、执行迁移、发布、健康检查与抽查 | 同上 | 设计已完成 |
| REQ-16.5-03 | 16.5 | **代码回滚不等于数据库自动回滚**，需独立恢复计划 | `docs/backup-restore.md` 第五节 | 已完成（已明示） |

## 十六、分阶段实施计划（任务书 17）

| 阶段 | 主要交付 | 本轮状态 |
| --- | --- | --- |
| 0 | 仓库检查、需求矩阵、架构、模型、环境 | **已完成**（Docker 未启动验证） |
| 1 | 登录、权限、组织、主数据、基础审批、日志 | **已完成**（本地验证通过） |
| 2 | 客户、供应商、采购、销售、WMS | **进行中**：客户与供应商主数据已完成（见 §一之二）；寻源/报价/评价、采购销售单据、库存余额未开始。补充要求：如需质检放行，**先实现最低可用的待检/放行状态** |
| 3 | BOM、工艺、MRP、MES、QMS | **进行中**：BOM 与工艺路线版本快照已完成（见 §一之六）；**MRP 已完成**（见 §一之七）；MES、QMS 未开始。工单下达须保存该版本快照 |
| 4 | 设备、备件、保养、点检、维修 | 未开始。备件主数据与库存由共享模块提供，**阶段 4 不重复创建库存体系** |
| 5 | 采集、EMS、能源报表与告警 | 未开始 |
| 6 | CRM 深化、EHS、物流、终端安全 | 未开始 |
| 7 | 综合报表、基础成本深化、性能、安全、运维 | 未开始 |

**每阶段输出要求**（任务书 17 末）：已实现功能、数据迁移、页面与 API、权限、演示数据、
测试执行结果、启动验证步骤、未完成事项、下一阶段依赖 —— 本阶段的完整输出见 `docs/progress.md`。

## 十七、追踪完整性与状态定义（任务书 19）

### 19.1 追踪完整性声明

- **任务书 1–17 章的全部条目**已在本矩阵中落到「实现位置」、或注明「合并到共享功能」、
  或明确标注「实施边界 / 计划阶段」，**无静默遗漏**。
- 原始编号存在重复（如多处"6.1"），已按 `REQ-<章节>-<序号>` 重新编号，并保留「来源」列映射。
- 阶段 0/1 之外的能力**一律标注计划阶段**，不用"基础功能"等模糊词替代交付清单。
- 未执行项在 `docs/test-report.md` 与 `docs/acceptance.md` 中同样标注为「未执行」，
  **不写作通过**。

### 19.2 状态定义

`未开始` / `设计中` / `开发中` / `待测试` / `已通过阶段验收` / `受外部条件阻塞`

本矩阵实际使用的状态值：`已完成`（阶段 0/1 范围内已通过验收）、`部分完成`（有可运行增量但存在明确未验证/未覆盖部分）、`设计已完成`（仅文档与模型就绪，功能在后续阶段）、`未开始`、`实施边界`（明确不做或不做为独立功能）、`**未验证**`（文件已编写但未实际运行）。

### 19.3 完成标准

见 `docs/acceptance.md` 第三节逐条对照。**「页面已存在」不等于「已通过阶段验收」。**