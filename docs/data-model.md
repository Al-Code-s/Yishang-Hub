# 数据模型（docs/data-model.md）

> 本文档描述**阶段 0/1 已落地**的数据结构，以及阶段 2 起必须遵守的设计约定。
> 字段清单以 `backend/apps/*/models.py` 为准；本文档负责说明**口径与规则**，不逐字段抄写。

## 一、数据库配置与口径

| 项 | 取值 | 说明 |
| --- | --- | --- |
| 引擎 | InnoDB | 事务与行锁 |
| 字符集 | `utf8mb4` | 支持完整 Unicode（含 emoji 与生僻字） |
| 排序规则 | `utf8mb4_0900_ai_ci` | **大小写不敏感**；需要区分的场景在服务层显式处理（见 `docs/assumptions.md` 第三节） |
| SQL 模式 | 严格模式（含 `STRICT_TRANS_TABLES`、`NO_ZERO_DATE`） | 由数据库侧配置；`docs/deployment.md` 记录 |
| 时区 | 存储 UTC，`USE_TZ=True` | 业务界面按 `Asia/Shanghai` 展示与分组 |
| 应用账号 | 专用账号 `yishang_app` | 不使用 `root` 连接应用 |

**时区边界**：跨日、跨月分组的正确性由 `frontend/src/utils/format.ts` 的时区化实现与
`tests/format.spec.ts` 覆盖；后端统计一律以 UTC 存储时间做区间过滤后再按业务时区聚合。

## 二、通用字段（`apps/core/models.py::BaseModel`）

```text
id            BigAutoField 主键
created_at    DateTimeField(auto_now_add) 带索引
created_by    FK -> identity.User (null, on_delete=SET_NULL)
updated_at    DateTimeField(auto_now)
updated_by    FK -> identity.User (null)
version       PositiveIntegerField 乐观并发计数
```

组织字段按实体归属**按需**增加，不机械铺满：

- `company`：跨公司存在归属歧义的实体（物料、款式、SKU、仓库、员工、班次…）。
- `factory`：库存与排产相关实体（仓库可归属工厂）。
- `department`：用户、员工、仓库可归属部门。
- `warehouse`：库存相关实体（阶段 2 起）。

审计与流水类实体（`AuditLog`、`CodeSequence`、`ApprovalStep`、`LoginAttempt`）
**不继承** `BaseModel`，因为它们要么是只写记录、要么由特定服务独占更新。

## 三、表清单（阶段 0/1）

### core（公共基础）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `core_auditlog` | `request_id, action, actor, actor_username, company, object_type, object_id, object_repr, changes(JSON), reason, approval_basis, ip_address, user_agent, created_at` | 只写不改；无删除接口 |
| `core_outboxevent` | `event_id(UUID,唯一), event_type, aggregate_type, aggregate_id, payload, status, attempts, max_attempts, next_retry_at, last_error, dedup_key(唯一,可空), processed_at` | 与业务同事务写入 |
| `core_idempotencyrecord` | `scope, key, user, request_hash, status_code, response_body, expires_at` + `uq_idempotency_scope_key` | 幂等结果与业务同事务提交 |
| `core_coderule` / `core_codesequence` | `code, pattern, reset_period` / `rule, period_key, last_value` + `uq_code_sequence_rule_period` | 单据编号按规则+周期取号 |
| `core_dictionary` / `core_dictionaryitem` | `code` / `dictionary, code, label, sort_order, extra` + `uq_dictionary_item_code` | 字典项同字典内编码唯一 |
| `core_attachment` | `file, original_name, content_type, size_bytes, sha256, biz_type, biz_id` | 对象存储默认私有；下载校验权限 |
| `core_notification` | `recipient, title, body, biz_type, biz_id, is_read, read_at, source_event_id(唯一,可空)` | `source_event_id` 保证事件重放不重复通知 |

### identity

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `identity_user` | `username(唯一), phone(唯一,可空), display_name, company, department, is_superuser, must_change_password, password_changed_at, failed_login_count, locked_until, permission_version` + M2M `roles` | 自定义用户模型，首次迁移即启用 |
| `identity_role` | `code(唯一), name, company, data_scope_type, is_system, is_active, sort_order` + M2M `permissions`、`menus` | 角色是权限与菜单的聚合载体 |
| `identity_permission` | `code(唯一), name, module, resource, action, permission_type, is_system` | 权限点，由 `permissions_registry` 单一契约生成 |
| `identity_menu` | `code(唯一), name, parent, path, component, icon, menu_type, permission_code, sort_order, visible` | 菜单与接口权限共用同一编码 |
| `identity_rolescopegrant` | `role, dimension(factory/department/warehouse), object_id` + `uq_role_scope_grant` | 自定义范围的多维度授权 |
| `identity_userrole` | `user, role` + `uq_user_role` | 显式中介表，便于审计与批量化管理 |
| `identity_loginattempt` | `username, user, ip_address, successful, failure_reason, created_at` | 登录限流与失败锁定依据 |

### factory（组织与排班）

| 表 | 唯一约束 | 说明 |
| --- | --- | --- |
| `factory_company` | `code` | 公司 |
| `factory_department` | `uq_department_company_code` | 自关联 `parent`，公司内编码唯一 |
| `factory_factory` | `uq_factory_company_code` | 工厂归属公司 |
| `factory_workshop` | `uq_workshop_factory_code` | 车间归属工厂 |
| `factory_productionline` | `uq_line_workshop_code` | 线体归属车间 |
| `factory_station` | `uq_station_line_code` | 工位归属线体，含 `process_name` |
| `factory_employee` | `uq_employee_company_no` | `user` 为 OneToOne 可空：员工不一定有登录账号 |
| `factory_shift` | `uq_shift_company_code` | `cross_day` 标记跨夜班次 |
| `factory_team` / `factory_teammember` | `code` / `uq_team_member` | 班组与成员，成员带 `start_date/end_date` |
| `factory_department.department_type` | choices：`management` 职能部门 / `production` 生产部门 / `quality` 质量部门 / `warehouse` 仓储部门 / `procurement` 采购部门 / `sales` 销售部门 / `equipment` 设备部门 / `other` 其他 | 枚举键存英文，接口同时返回 `department_type_display` 中文标签 |
| `factory_workshop.workshop_type` | choices：`cutting` 裁剪 / `sewing` 缝制 / `ironing` 整烫 / `finishing` 整烫包装 / `inspection` 检验 / `packing` 包装 / `other` 其他 | 同上，返回 `workshop_type_display` |

> **枚举约定（全平台）**：数据库与接口的**筛选、写入**一律使用英文枚举键；
> 展示用中文由后端在响应中附带 `<field>_display` 只读字段（见 `docs/api-conventions.md` §十二），
> 前端不得硬编码枚举中文映射。历史非法枚举值已由 `factory/0003` 修正，并用
> `backend/tests/test_enum_labels.py` 防止再次写入（`seed_demo` 全库复扫）。

### masterdata（服饰主数据）

```text
款式 Style ──┬── 颜色 Color
             └── 尺码 Size
                    ↓
        SKU = 款式 × 颜色 × 尺码   (uq_sku_style_color_size)
                    ↓
        成品物料 Material (Sku.material OneToOne，避免两套库存编码)
```

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `masterdata_materialcategory` | `parent, code, category_type` | 分类树；`category_type` 区分面料/辅料/半成品/成品/包装物/备品备件/消耗品 |
| `masterdata_material` | `company, code, name, category, spec, base_uom, purchase_uom+purchase_factor, sales_uom+sales_factor, is_batch_managed, is_roll_managed, is_serial_managed, safe_stock, purchase_price, reference_cost, brand, season, year, series, image` + `uq_material_company_code`、`ck_material_safe_stock_non_negative` | 统一物料主数据，含交易单位与换算率 |
| `masterdata_fabricprofile` | `material(OneToOne), composition, width_cm, gram_weight, default_color_no, dye_lot_required, shrinkage_rate` | 面料专属属性（成分/幅宽/克重/缸号要求） |
| `masterdata_uom` / `masterdata_uomconversion` | `code, category, decimal_places` / `from_uom, to_uom, factor, is_fixed` + `uq_uom_conversion_pair`、`ck_uom_conversion_distinct`、`ck_uom_conversion_factor_positive` | 计量单位与换算；禁止自换算、换算率必须为正 |
| `masterdata_color` / `masterdata_size` | `code` / `code, size_group` | 颜色含 `hex_code`；尺码按 `size_group` 分组 |
| `masterdata_style` | `company, code, name, category, size_group, brand, season, year, series, image` + `uq_style_company_code` | 款式/SPU |
| `masterdata_sku` | `company, style, color, size, code, material(OneToOne), barcode` + `uq_sku_company_code`、`uq_sku_style_color_size` | 组合唯一约束在**数据库层**强制 |
| `masterdata_identifier` | `identifier_type, value, sku, material, batch_no, extra` + `uq_identifier_type_value` | **标识分型**：SKU 条码 / 批次码 / 卷号 / 箱码 / RFID EPC / 载具码，绝不混用一个字段 |

### wms（仓储主数据 + 库存核心，阶段 1 / 阶段 2）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `wms_warehouse` | `company, factory, department, code, name, warehouse_type, allow_negative_stock` + `uq_warehouse_company_code` | `allow_negative_stock` 为仓库级开关，默认 false 且不鼓励开启 |
| `wms_zone` | `warehouse, code, zone_type, allow_mixed_batch` + `uq_zone_warehouse_code` | `allow_mixed_batch=false` 表示该库区禁止混批次 |
| `wms_location` | `zone, code, location_type, row_no, column_no, level_no, capacity, is_locked` + `uq_location_zone_code` | 储位层级与承载能力；`is_locked` 用于冻结储位 |

**库存核心表（阶段 2 新增，迁移 `wms/0002`）**：

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `wms_inventorybalance` | `company, material, warehouse, location, batch_no, roll_no, quality_status, dimension_key(UNIQUE,NOT NULL), on_hand, frozen, reserved` + `uq_inventory_balance_dimension`、`ck_inventory_balance_non_negative`、`ck_inventory_balance_buckets_within_on_hand` | 库存余额（按维度去重）；数量均为 `Decimal(20,6)`；`available` 为计算属性（！= 数据库列） |
| `wms_inventorytransaction` | `company, material, warehouse, location, batch_no, roll_no, quality_status, transaction_type, direction, quantity, document, document_line, document_no, biz_no, idempotency_key, occurred_at, created_by` + `uq_inventory_txn_idempotency` | 库存流水，**只追加**：模型 `save()` 对已有行抛 `ImmutableLedgerError`，`delete()` 总是抛异常 |
| `wms_inventorydocument` | `company, document_no(UNIQUE with company), document_type, status, warehouse, target_warehouse, reason, biz_no, idempotency_key, posted_at, posted_by, reversed_at, reversed_by, reversal_of` | 库存单据头；状态机 `draft → posted → reversed`，`cancelled` 仅限草稿 |
| `wms_inventorydocumentline` | `document, line_no, material, location, target_location, batch_no, roll_no, quantity, target_quality_status, remark` + `uq_inventory_doc_line_no`、`ck_inventory_line_quantity_positive` | 单据行；数量必须 > 0 |

**库存占用表（阶段 2 第四步新增，迁移 `wms/0003`）**：

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `wms_stockreservation` | `company, material, warehouse, location, batch_no, roll_no, quality_status, dimension_key, quantity, consumed_quantity, released_quantity, status, biz_type, biz_id, biz_no, request_key(UNIQUE), remark` + `ck_reservation_quantity_positive`、`ck_reservation_consumed_non_negative`、`ck_reservation_within_quantity`、`idx_reservation_dimension`、`idx_reservation_biz` | 库存占用记录。**占用不写库存流水**：流水只记实存量增减，占用有自己的生命周期（`active → closed`（消耗结束）/ `cancelled`（释放结束））。一致性口径：`InventoryBalance.reserved == 该维度未结占用之和`。`request_key` 单列唯一是并发幂等的最终保障 |

> `dimension_key` = `sha256("company|material|warehouse|location|normalize(batch)|normalize(roll)|normalize(quality)")[:32]`，
> 单列 `UNIQUE NOT NULL`，彻底绕过 MySQL 「NULL 不相等」导致的联合唯一索引失效问题（见本文第六节）。
> 实现位置：`backend/apps/wms/models/inventory.py`、`backend/apps/wms/services/stock.py`。


### crm（客户主数据，阶段 2 第一步）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `crm_customer` | `company, code, name, short_name, category, level, status, credit_limit, payment_terms, tax_no, address, primary_contact_name, salesman, tags(JSON), is_active` + `uq_customer_company_code`、`ck_customer_credit_limit_non_negative` | 客户归属公司（`CompanyScopedModel`）；信用额度仅作管理参考，不是财务应收余额 |
| `crm_customercontact` | `customer, name, position, phone, email, is_primary, is_active` + `uq_customer_contact_name` | 联系人公司归属由 `Customer` 间接确定；同一客户下不允许同名联系人 |

> 「同一客户只能有一个主联系人」**不是数据库约束**：MySQL 不支持带条件的部分唯一索引
> （Django `UniqueConstraint(condition=...)` 在 MySQL 上不被支持）。该规则由
> `apps/core/services.py::ensure_single_primary` 在写事务内保证，并在
> `test_crm_api.py` / `test_srm_api.py` 中覆盖。数据库层不做虚假承诺。

### srm（供应商主数据，阶段 2 第一步）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `srm_supplier` | `company, code, name, short_name, category, grade, admission_status, payment_terms, tax_no, address, primary_contact_name, buyer, tags(JSON), is_active` + `uq_supplier_company_code` | `admission_status` 只是档案字段，**不代替准入审批记录**（审批流程属后续增量） |
| `srm_suppliercontact` | `supplier, name, position, phone, email, is_primary, is_active` + `uq_supplier_contact_name` | 与客户联系人同构 |
| `srm_supplierqualification` | `supplier, qualification_type, certificate_no, issued_by, issued_date, expiry_date, is_active, dedup_key` + `ck_supplier_qualification_date_order` | 资质证书与有效期，供后续「到期提醒」使用；`expiry_date >= issued_date` 由检查约束强制 |

**资质证书编号的规范化去重键（与库存维度键同一思路）**：

`dedup_key` 是 `VARCHAR(191)`、`UNIQUE`、**可空**、`editable=False`，由模型 `save()` 统一生成：

```text
certificate_no 为空 → dedup_key = NULL          # MySQL 允许多个 NULL 并存
certificate_no 非空 → dedup_key = "<supplier_id>|<qualification_type>|<casefold(certificate_no)>"
```

因此：填写编号时按「供应商 + 资质类型 + 编号（忽略大小写）」判重；
**未填写编号时不参与去重，同类型可并存任意多条**（`test_srm_api.py` 已断言
`dedup_key IS NULL` 的行可以有多条）。这正好规避了「含可空列的联合唯一索引在 MySQL 上失效」
的陷阱。

### procurement（采购，阶段 2 第三步）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `procurement_purchaserequisition` | `company, requisition_no, request_type, status, applicant, department, factory, needed_date, purpose, approval_instance_id, approved_at` + `uq_requisition_company_no` | 单号 `PR{YYYYMMDD}{SEQ:4}`；状态机 `draft → submitted → approved / rejected / cancelled` |
| `procurement_purchaserequisitionline` | `requisition, line_no, material, quantity, uom, needed_date, suggested_supplier, ordered_quantity` + `uq_requisition_line_no`、`ck_requisition_line_quantity_positive` | `ordered_quantity` 由「转订单」在同一事务内累加，用于拦截重复转单 |
| `procurement_purchaseorder` | `company, order_no, supplier, status, source_requisition, buyer, order_date, expected_date, warehouse, currency, tax_rate, payment_terms, total_amount, tax_amount, amount_with_tax, supplier_exception, supplier_exception_reason, approval_instance_id, approved_at, closed_at` + `uq_order_company_no`、`ck_order_tax_rate_range` | 金额字段**全部由后端计算**后落库；`tax_rate` 是百分数（0~100），不是小数比率 |
| `procurement_purchaseorderline` | `order, line_no, material, quantity, received_quantity, price, amount, uom, expected_date, warehouse, source_line` + `uq_order_line_no`、`ck_order_line_quantity_positive`、`ck_order_line_received_non_negative`、`ck_order_line_received_within_quantity` | `received_quantity` **只读**，只能由库存过账推进；`source_line` 指向来源申请行，支持供需追溯 |
| `procurement_goodsreceipt` | `company, receipt_no, purchase_order, supplier, status, warehouse, received_at, received_by, supplier_delivery_no, inspection_result, inspected_at, inspected_by, inspection_remark, receipt_document_id, quality_document_id` + `uq_receipt_company_no` | `receipt_document_id` / `quality_document_id` 指向 `wms.InventoryDocument`；采购侧**不写库存余额与流水表** |
| `procurement_goodsreceiptline` | `receipt, line_no, order_line, material, quantity, location, batch_no, roll_no` + `uq_receipt_line_no`、`ck_receipt_line_quantity_positive` | 只能引用**同一订单**的订单行；`batch_no` / `roll_no` 直接决定库存维度键 |

**数量口径（本模块硬规则）**：订单可收数量 = `quantity - received_quantity - 已有草稿收货单数量`，
因此**草稿也占用额度**；超出即 `OVER_RECEIPT`。收货过账只把库存置为 `quarantine`，
只有经 `release_quality` 放行后该批次才可领用或销售（`docs/inventory-rules.md`）。
### sales（销售，阶段 2 第四步）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `sales_salesorder` | `company, order_no, customer, status, salesman, order_date, expected_date, priority, warehouse, currency, tax_rate, payment_terms, delivery_address, total_amount, tax_amount, amount_with_tax, approval_instance_id, approved_at, closed_at` + `uq_sales_order_company_no`、`ck_sales_order_tax_rate_range` | 单号 `SO{YYYYMMDD}{SEQ:4}`；状态机 `draft → submitted → approved → partially_shipped → shipped`，另有 `closed / rejected / cancelled`；金额字段**全部由后端计算**后落库 |
| `sales_salesorderline` | `order, line_no, material, sku, quantity, shipped_quantity, returned_quantity, price, amount, uom, expected_date` + `uq_sales_order_line_no`、`ck_sales_order_line_quantity_positive`、`ck_sales_order_line_progress_non_negative`、`ck_sales_order_line_shipped_within_quantity`、`ck_sales_order_line_returned_within_shipped` | `shipped_quantity` / `returned_quantity` **只读**，只能由库存过账推进；`remaining_quantity` / `returnable_quantity` 为计算属性 |
| `sales_salesshipment` | `company, shipment_no, sales_order, customer, status, warehouse, shipped_at, shipped_by, receiver_name, receiver_phone, delivery_address, carrier, tracking_no, issue_document_id` + `uq_shipment_company_no` | 单号 `SH{YYYYMMDD}{SEQ:4}`；`issue_document_id` 指向 `wms.InventoryDocument`（出库）；销售侧**不写库存余额与流水表** |
| `sales_salesshipmentline` | `shipment, line_no, order_line, material, quantity, location, batch_no, roll_no` + `uq_shipment_line_no`、`ck_shipment_line_quantity_positive` | 只能引用**同一订单**的订单行；行上留空的储位/批次/卷号由**占用维度**推导（`stock.open_reservation_hint`） |
| `sales_salesreturn` | `company, return_no, sales_order, shipment, customer, status, warehouse, reason, received_at, received_by, inspection_result, inspected_at, inspected_by, inspection_remark, receipt_document_id, quality_document_id` + `uq_sales_return_company_no` | 单号 `SR{YYYYMMDD}{SEQ:4}`；状态机 `draft → posted`（待检）`→ inspected`；收货用 `receipt_document_id`、质量转换用 `quality_document_id` |
| `sales_salesreturnline` | `return_doc, line_no, order_line, material, quantity, location, batch_no, roll_no` + `uq_return_line_no`、`ck_return_line_quantity_positive` | 可退数量 = 已发货 − 已退货（超出即 `OVER_RETURN`）；行未填维度时**继承原发货出库单据的批次**并写回本行 |

### planning（BOM 与工艺路线版本 阶段 3 第一步；MRP 阶段 3 第二步）

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `planning_bom` | `company, code, style, sku, version_no, scope_key, status, effective_from, effective_to, is_active, approval_instance_id, submitted_at, approved_at, approved_by, remark` + `uq_bom_company_code`、`uq_bom_scope_version`、`ck_bom_version_positive`、`ck_bom_effective_range` | 编号 `BOM{YYYYMMDD}{SEQ:4}`；状态机 `draft → submitted → approved / rejected`，另有 `obsolete`；`scope_key` 由 `engineering_scope_key(style_id, sku_id)` 生成（见 §六 第 10 条）；`sku` 为空表示款式通用版本 |
| `planning_bomline` | `bom, line_no, material, quantity, loss_rate, uom, line_type, substitute_for, position, is_key_material, remark` + `uq_bom_line_no`、`ck_bom_line_quantity_positive`、`ck_bom_line_loss_non_negative`、`ck_bom_line_loss_lt_one` | `quantity` 是**单位成品净用量**；`gross_quantity` 是**计算属性**（`quantity × (1 + loss_rate)`，按 6 位小数 `ROUND_HALF_UP`），**不落库**，避免同一口径存两份而漂移；`line_type=substitute` 时 `substitute_for` 必须指向同一 BOM 的正常用料行 |
| `planning_routing` | 与 `planning_bom` 同构（`code` / `style` / `sku` / `version_no` / `scope_key` / `status` / 生效区间 / 审批字段） + `uq_routing_company_code`、`uq_routing_scope_version`、`ck_routing_version_positive` | 编号 `RT{YYYYMMDD}{SEQ:4}`；版本与审批规则与 BOM **完全一致**（共用服务骨架） |
| `planning_routingstep` | `routing, sequence, name, workshop, workcenter, equipment_requirement, standard_hours, is_quality_gate, remark` + `uq_routing_step_sequence`、`ck_routing_step_sequence_positive`、`ck_routing_step_hours_non_negative` | `is_quality_gate` 对应任务书 9.5 的「工序质检点」；`standard_hours` 是单件标准工时（小时），供 OEE 理论产能与工序效率使用；`workshop` 受数据范围校验 |

**为什么本轮不建快照表**：任务书 9.5 要求「工单下达保存版本快照」，快照的归属方是**工单**（MES），
因此本轮只提供 `services.build_bom_snapshot()` / `build_routing_snapshot()` 输出不可变 dict
（含版本号、生效区间、明细行 / 工序，含损耗用量与质检点标记），
由阶段 3 后续的工单模型在**下达时**保存，**不预先创建空表**（任务书 4.3、20.3）。

**「同一范围同时只有一个生效版本」为何不靠索引**：MySQL 没有部分唯一索引
（`UNIQUE ... WHERE status='approved'`），因此由服务层在 `transaction.atomic()` +
`select_for_update()` 内切换版本状态，并在锁内重新校验；数据库层只保证
`(company, scope_key, version_no)` 不重复。

**MRP 表（阶段 3 第二步）**

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `planning_mrprun` | `company, run_no, status, bucket, horizon_start, horizon_end, warehouse, parameters(JSON), summary(JSON), started_at, finished_at, error_message, archived_at, archived_by, remark` + `uq_mrp_run_company_no`、`ck_mrp_horizon_ordered` | 一次 MRP 计算的**快照**：`run_no` 编号 `MRP{YYYYMMDD}{SEQ:4}`；`status` ∈ `completed / archived / failed`；`parameters` 固化本次口径（`bucket` / `lead_time_mode=lot_for_lot` / `in_progress_supply=not_implemented` / `frozen_and_reserved=excluded_from_available` / `include_substitutes=false` / `demand_sources=['sales_order']`），`summary` 存汇总（需求 / 供给 / 建议数量与计数、`buckets`、`unexploded_materials`）；**失败也落一条 `failed` 行并写 `error_message`**，便于排查 |
| `planning_mrdemandline` | `run, line_no, level, source_type, source_id, source_no, source_line_no, material, sku, style, warehouse, quantity, due_date, bucket_date, path, exploded, note` + `uq_mrp_demand_line_no`、`ck_mrp_demand_quantity_positive` | **展开后**的需求行：`level=0` 为销售订单需求，`level≥1` 来自父件净需求展开（`source_type=parent_item`）；`path` 保存来源链、`bucket_date` 为分段键（`week` 归一到周一）；`exploded` 标记该行是否已继续展开下级 |
| `planning_mrpsupplyline` | `run, line_no, source_type, reference_type, reference_id, reference_no, material, sku, style, warehouse, quantity, available_date, bucket_date` + `uq_mrp_supply_line_no`、`ck_mrp_supply_quantity_positive` | 本次计算**认到的供给**：`on_hand`（可用量 = `on_hand − frozen − reserved`，只认合格质量状态）与 `on_order`（采购订单未收数量，按承诺交期落段）；`in_progress` 枚举已定义但当前**不产生行**（MES 未实现） |
| `planning_mrsuggestion` | `run, line_no, suggestion_type, status, material, sku, style, warehouse, uom, quantity, bucket_date, due_date, reason, detail(JSON), converted_document_type/id/no, converted_at, converted_by, cancel_reason, remark` + `uq_mrp_suggestion_line_no`、`ck_mrp_suggestion_quantity_positive` | 缺料建议：`suggestion_type` ∈ `purchase / production`，`status` ∈ `open / converted / cancelled`；`detail` 保存 `level` / `bom_code` / `bom_version_no` / `trace` / `demand_sources`；转单后记录目标单据（当前只有 `procurement.PurchaseRequisition`，且必为**草稿**） |

**MRP 为何不建「供需平衡表」**：净算结果（净需求）本身可由需求行与供给行在同一分段内复算，
把中间量落库会引入第二份口径；因此只落**输入快照（需求行 / 供给行）**与**输出建议**，
中间计算过程通过 `MrpRun.parameters` + 分段净算展示（前端建议详情页签）复现。

**MRP 不写库存**：`mrp.py` 对 `wms.InventoryBalance` / `StockLedger` **只读**，
由 `test_mrp_is_read_only_for_inventory` 锁定；建议转单只创建**草稿采购申请**，不产生采购承诺。

### workflow / integration

| 表 | 关键字段 | 说明 |
| --- | --- | --- |
| `workflow_approvaltemplate` | `code, name, biz_type, company, allow_self_approval, version_no` | `allow_self_approval=false` 时限制申请人审批自己的单据 |
| `workflow_approvaltemplatenode` | `template, seq, approver_type, approver_role, approver_user, amount_min, amount_max, department_ids` + `uq_template_node_seq` | 金额区间与部门条件路由 |
| `workflow_approvalinstance` | `template, template_version, template_snapshot(JSON), biz_type, biz_id, biz_no, applicant, amount, status, current_seq` | `template_snapshot` 固化流程版本，模板后续修改不影响在途单据 |
| `workflow_approvalstep` / `workflow_approvallog` | `instance, seq, approver_type, assigned_user, status, decided_by, decision, comment` / `action, actor, actor_name, comment` | 步骤与轨迹分离；轨迹只写不改 |
| `integration_documentlink` | `source_type/source_id/source_no, target_type/target_id/target_no, relation, quantity` + `uq_document_link` | 单据关系用于「订单到交付」链路追溯 |

### analytics

`analytics` 当前**不建表**：看板数据一律从业务表实时聚合计算，避免出现与实际业务脱节的中间汇总表。
若后续为性能引入汇总表，必须可重算且标注更新时间。
## 四、数值规范

| 用途 | 类型 | 说明 |
| --- | --- | --- |
| 数量 | `DecimalField(max_digits=20, decimal_places=6)` | 物料数量、库存数量 |
| 换算率 | `DecimalField(max_digits=18, decimal_places=10)` | `UoMConversion.factor`、`Material.purchase_factor` |
| 单据金额 | `DecimalField(max_digits=20, decimal_places=4)` | 审批金额 `amount` |
| 参考成本/单价 | `DecimalField(max_digits=20, decimal_places=6)` | `purchase_price`、`reference_cost` |
| 能源读数 | 阶段 5 按仪表精度单独定义 | 见 `docs/energy-calculation.md` |

硬性要求：

1. **禁止**使用 Python `float` 累计金额与库存。后端全程 `Decimal`，前端使用 `decimal.js` 封装
   （`frontend/src/utils/decimal.ts`，由 `tests/decimal.spec.ts` 锁定）。
2. **API 的 Decimal 一律以字符串输出**（`apps/core/serializers.py`），前端类型中金额/数量一律为 `string`，
   避免 JSON 数字精度丢失。
3. **最终业务金额由后端计算与校验**，前端计算结果只用于展示，不参与落库决策。

### 舍入规则

- 舍入方式：**`ROUND_HALF_UP`**（四舍五入），集中定义在 `apps/core/constants.py`。
- 发生环节：**仅在服务层写库前的最终一步**发生一次舍入，中间计算过程保持全精度，避免多次舍入累积误差。
- 单据统计口径：单据保存**交易单位 + 基本单位 + 换算率 + 换算后数量**四要素，
  这样即使换算率后续被修改，历史单据的数量语义仍然可复现。
- 展示层可以按界面精度截断，但不得回写数据库。

## 五、数据库约束

已落地的约束类型：

| 类型 | 示例 | 目的 |
| --- | --- | --- |
| 业务编码唯一 | `uq_material_company_code`、`uq_style_company_code`、`uq_sku_company_code` | 编码在同公司内不重复 |
| 组合唯一 | `uq_sku_style_color_size` | 款式+颜色+尺码唯一确定 SKU |
| 标识唯一 | `uq_identifier_type_value` | 同一类型标识值全局唯一 |
| 幂等唯一 | `uq_idempotency_scope_key` | 同一业务事件只处理一次 |
| 层级唯一 | `uq_zone_warehouse_code`、`uq_location_zone_code` | 同级编码不重复 |
| 检查约束 | `ck_material_safe_stock_non_negative`、`ck_uom_conversion_distinct`、`ck_uom_conversion_factor_positive` | 不允许负安全库存、禁止自换算、换算率必须为正 |
| 外键保护 | 各 `ForeignKey(on_delete=PROTECT)` | 被引用主数据不可物理删除 |

## 六、NULL 唯一索引问题与规范化维度键方案（任务书 5.4 重点）

### 问题

MySQL 的唯一索引**不把两个 NULL 视为相等**。库存维度包含「批次」「卷号」等**可空**字段时，
若直接使用多列联合唯一索引防重：

```sql
-- 反例：不要这样做
UNIQUE KEY (company_id, material_id, warehouse_id, location_id, batch_no, roll_no, quality_status)
```

当 `batch_no IS NULL AND roll_no IS NULL` 时，同一维度**可以插入任意多行**重复余额，
并发场景下必然产生重复余额行与错误可用量。

### 采用的方案：显式规范化维度键

1. 库存余额表增加一列 `dimension_key`，类型 `CHAR(64)`（或 `VARCHAR(64)`），**NOT NULL**、全局唯一。
2. 该列由**库存服务统一生成**，不由调用方拼装：

```text
dimension_key = sha256("|".join([
    str(company_id), str(material_id), str(warehouse_id), str(location_id),
    normalize(batch_no), normalize(roll_no), normalize(quality_status),
])).hexdigest()[:32]
```

3. `normalize(x)` 规则：`None` / 空字符串 → 固定占位符 `"-"`；其余 `strip()` 后按业务大小写规则规范化
   （当前语义为不区分大小写，故统一 `casefold()`）。
4. **空值被显式编码**为占位符，因此「无批次无卷号」这一维度在数据库中是**确定的一个值**，
   联合唯一约束（`UNIQUE(dimension_key)`）从此真正生效。
5. 业务可读的维度列（`batch_no`、`roll_no` 等）仍然保留为可空列，仅用于查询与展示；
   **唯一起作用的是 `dimension_key`**。
6. 并发安全的余额行创建：

```text
BEGIN
  尝试 SELECT ... WHERE dimension_key = :k FOR UPDATE
  若不存在：
      INSERT ... （依赖 dimension_key 唯一约束）
      捕获 IntegrityError → 回滚该保存点后重新 SELECT FOR UPDATE
  在锁内重新校验可用数量与单据状态，再更新余额与写流水
COMMIT
```

> 关键点（任务书 5.6）：**尚不存在的余额行不能认为 `select_for_update()` 已提供锁保护**，
> 必须结合**唯一约束 + 并发安全的创建/重试**处理。这正是引入 `dimension_key` 的原因。

7. 验证要求：阶段 2 必须提供**并发测试**（独立数据库连接与真实事务，不依赖外层测试事务掩盖问题），
   断言并发创建同一维度余额行后**只有一行**、并发出库**不产生负库存**（对应必测案例 6、7）。

8. **已落地的同思路实现一（srm）**：`srm_supplierqualification.dedup_key`
   （见 §三 srm）把「可空标识 → 规范化键 + 单列唯一索引」用于供应商资质去重，
   并通过 `test_srm_api.py` 验证「编号为空时可并存多条、编号重复（含大小写差异）时被拒绝」。

9. **已落地的同思路实现二（库存，阶段 2 核心）**：`wms_inventorybalance.dimension_key`
   为 `CHAR(32)`、`UNIQUE`、`NOT NULL`，由 `apps/wms/services/stock.py::build_dimension_key()`
   统一生成；`normalize_token(None)` 与 `normalize_token("")` 均返回 `"-"`，
   其余值 `strip()` 后 `casefold()`（当前业务语义：批次/卷号不区分大小写）。

   已通过 `backend/tests/test_wms_inventory.py` 的**真实并发测试**验证
   （`threading` + `connections.close_all()` + `threading.Barrier`，`@pytest.mark.django_db(transaction=True)`，
   独立数据库连接与真实事务，不依赖测试框架外层事务掩盖）：

   - 并发创建同一维度余额行 → 最终**只有一行**；
   - 并发出库 → **不产生负库存**；
   - 并发同一幂等标识过账 → **只过账一次**。

   对应任务书必测案例 6、7（要求必须在真实独立事务与连接上执行）。

10. **已落地的同思路实现三（工程数据，阶段 3 第一步）**：`planning_bom.scope_key` /
    `planning_routing.scope_key` 把「款式 / SKU 范围」压成非空字符串
    （`engineering_scope_key()` → `"style:1"` 或 `"style:1:sku:3"`），
    唯一约束建在 `(company, scope_key, version_no)` 上，而不是直接对含可空列
    `(company, style, sku, version_no)` 建唯一索引 —— 原因见上文第 1 条：
    MySQL 唯一索引不约束 NULL，多行「款式通用」版本会互相冲突不到。
    已由 `backend/tests/test_planning.py::test_scope_version_unique_constraint_is_enforced`
    在真实 MySQL 上以 `IntegrityError` 验证。

    > 同一个坑在库里出现了三次（供应商资质编号、库存维度、工程版本范围），
    > 处理方式统一为「显式规范化键 + 单列/固定列数唯一约束 + 服务层语义校验」。

## 七、状态与删除策略

- 主数据被使用后**优先停用**（`is_active=false`），不物理删除；所有主数据资源只提供 `set-active`，不提供 `DELETE`。
- 已过账单据**不得物理删除**（阶段 2 起的单据模型遵守）。
- 审计记录与库存流水**不能通过普通业务接口修改**：审计只提供只读列表接口，无写入/更新/删除路由。
- **不滥用全局软删除**：未引入统一的 `deleted_at`，避免所有查询被迫带过滤条件而产生遗漏。
- 草稿删除前必须验证无下游依赖。
- 单据更正通过**撤回、变更单、冲销**等明确机制完成，不做原地改数。

## 八、迁移规范

- 使用 Django migrations，**迁移文件随代码提交**（当前 12 个 App 共 **19 个迁移文件**：
  `core` 3、`wms` 3、`factory` 3、`planning` 2，`identity`/`masterdata`/`workflow`/`integration`/`crm`/`srm`/
  `procurement`/`sales` 各 1；`analytics` 不建表故无迁移）。`planning/0002` 新增 4 张 MRP 表与 8 个约束；
  `factory/0003` 先 `RunPython` 修正历史非法枚举值，再扩展 `Department.department_type` 与
  `Workshop.workshop_type` 的 choices（反向迁移为显式空操作）。
- **生产启动时不自动执行 `makemigrations`**；`compose.yaml` 中迁移是独立的一次性步骤（`migrate` 服务），
  不由多个 Web 实例并发执行。
- 上线前执行**空库 + 已有数据升级**两类测试。
- 大表变更需评估锁表时间与执行时长。
- 数据迁移分批、可恢复。
- **明确声明：MySQL 部分 DDL（如 `ALTER TABLE`）不能像业务事务一样完整回滚**，
  因此不虚假保证「迁移失败后自动恢复」；发布前必须备份，并编写恢复步骤（见 `docs/backup-restore.md`）。