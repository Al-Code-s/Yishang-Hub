# 权限矩阵（docs/permission-matrix.md）

> 权限的唯一契约是 `backend/apps/identity/permissions_registry.py`。后端启动时由
> `apps/core/checks.py` 校验所有已声明的权限编码都存在于注册表；前端菜单树由
> `identity/menus/mine/` 下发。**不允许任何模块私自新增未注册的权限编码。**

## 一、四层权限（任务书 6.3）

| 层 | 名称 | 载体 | 执行位置 | 缺省行为 |
| --- | --- | --- | --- | --- |
| 1 | 菜单权限 | `identity_menu.permission_code` | 后端下发菜单树；前端据此注册路由 | 无权限 → 不下发该菜单，前端不注册路由 |
| 2 | 操作权限 | `Permission.code`（如 `sales.order.submit`） | `HasRequiredPermissions` + `require_codes()` 二次校验 | 未满足 → `403 PERMISSION_DENIED` |
| 3 | 接口权限 | 同操作权限，按 ViewSet 的 `required_permissions` 声明 | DRF 视图层 | 未声明权限的接口仅要求登录 |
| 4 | 数据范围 | `Role.data_scope_type` + `RoleScopeGrant` | `apps/core/selectors.py::resolve_data_scope`，用于所有查询 | 无角色/无授权 → **空集（fail-closed）** |

**关键约定**：前三层是「能不能做这个动作」，第四层是「能对哪些数据做这个动作」。
两者必须同时满足。前端传入的 `factory_id` / `warehouse_id` **只作为过滤条件，不作为授权依据**。

## 二、数据范围类型

| `data_scope_type` | 语义 | 实现 |
| --- | --- | --- |
| `all` | 全部数据 | 不加范围过滤（超级管理员亦走此档） |
| `company` | 本公司及以下 | 收敛到用户归属公司 |
| `factory` | 指定工厂 | 由 `RoleScopeGrant(dimension=factory)` 指定 |
| `department` | 指定部门 | 授权部门 + **部门子树**展开 |
| `warehouse` | 指定仓库 | 由 `RoleScopeGrant(dimension=warehouse)` 指定 |
| `self` | 仅本人 | 按 `created_by` / `applicant` 等归属字段过滤 |
| `custom` | 自定义组织范围 | 多维度 `RoleScopeGrant`，各维度内部取并集 |

## 三、权限编码清单（生成自注册表，实际共 173 条）

### analytics（1 条）

| 权限编码 | 名称 |
| --- | --- |
| `analytics.dashboard.view` | 查看工作台 |

### core（12 条）

| 权限编码 | 名称 |
| --- | --- |
| `core.attachment.delete` | 删除附件 |
| `core.attachment.download` | 下载附件 |
| `core.attachment.upload` | 上传附件 |
| `core.audit.view` | 查看审计日志 |
| `core.code_rule.create` | 新增编码规则 |
| `core.code_rule.update` | 修改编码规则 |
| `core.code_rule.view` | 查看编码规则 |
| `core.dictionary.create` | 新增数据字典 |
| `core.dictionary.update` | 修改数据字典 |
| `core.dictionary.view` | 查看数据字典 |
| `core.notification.view` | 查看通知 |
| `core.progress.view` | 查看实施进度 |

### crm（7 条）

| 权限编码 | 名称 |
| --- | --- |
| `crm.customer.create` | 新增客户 |
| `crm.customer.deactivate` | 启用/停用客户 |
| `crm.customer.update` | 修改客户 |
| `crm.customer.view` | 查看客户 |
| `crm.customer_contact.create` | 新增客户联系人 |
| `crm.customer_contact.update` | 修改客户联系人 |
| `crm.customer_contact.view` | 查看客户联系人 |

### factory（27 条）

| 权限编码 | 名称 |
| --- | --- |
| `factory.company.create` | 新增公司 |
| `factory.company.update` | 修改公司 |
| `factory.company.view` | 查看公司 |
| `factory.department.create` | 新增部门 |
| `factory.department.update` | 修改部门 |
| `factory.department.view` | 查看部门 |
| `factory.employee.create` | 新增员工 |
| `factory.employee.update` | 修改员工 |
| `factory.employee.view` | 查看员工 |
| `factory.factory.create` | 新增工厂 |
| `factory.factory.update` | 修改工厂 |
| `factory.factory.view` | 查看工厂 |
| `factory.line.create` | 新增线体 |
| `factory.line.update` | 修改线体 |
| `factory.line.view` | 查看线体 |
| `factory.shift.create` | 新增班次 |
| `factory.shift.update` | 修改班次 |
| `factory.shift.view` | 查看班次 |
| `factory.station.create` | 新增工位 |
| `factory.station.update` | 修改工位 |
| `factory.station.view` | 查看工位 |
| `factory.team.create` | 新增班组 |
| `factory.team.update` | 修改班组 |
| `factory.team.view` | 查看班组 |
| `factory.workshop.create` | 新增车间 |
| `factory.workshop.update` | 修改车间 |
| `factory.workshop.view` | 查看车间 |

### identity（15 条）

| 权限编码 | 名称 |
| --- | --- |
| `identity.log.view` | 查看登录记录 |
| `identity.menu.view` | 查看菜单 |
| `identity.permission.view` | 查看权限点 |
| `identity.role.assign_permission` | 配置角色权限与数据范围 |
| `identity.role.create` | 新增角色 |
| `identity.role.delete` | 删除角色 |
| `identity.role.update` | 修改角色 |
| `identity.role.view` | 查看角色 |
| `identity.user.assign_role` | 分配用户角色 |
| `identity.user.create` | 新增用户 |
| `identity.user.deactivate` | 启用/停用用户 |
| `identity.user.reset_password` | 重置用户密码 |
| `identity.user.unlock` | 解除用户锁定 |
| `identity.user.update` | 修改用户 |
| `identity.user.view` | 查看用户 |

### integration（3 条）

| 权限编码 | 名称 |
| --- | --- |
| `integration.document_link.view` | 查看单据关系 |
| `integration.outbox.retry` | 重试发件箱事件 |
| `integration.outbox.view` | 查看发件箱事件 |

### masterdata（27 条）

| 权限编码 | 名称 |
| --- | --- |
| `masterdata.color.create` | 新增颜色 |
| `masterdata.color.update` | 修改颜色 |
| `masterdata.color.view` | 查看颜色 |
| `masterdata.identifier.create` | 新增标识 |
| `masterdata.identifier.deactivate` | 停用标识 |
| `masterdata.identifier.update` | 修改标识 |
| `masterdata.identifier.view` | 查看标识 |
| `masterdata.material.create` | 新增物料 |
| `masterdata.material.deactivate` | 启用/停用物料 |
| `masterdata.material.update` | 修改物料 |
| `masterdata.material.view` | 查看物料 |
| `masterdata.material_category.create` | 新增物料分类 |
| `masterdata.material_category.update` | 修改物料分类 |
| `masterdata.material_category.view` | 查看物料分类 |
| `masterdata.size.create` | 新增尺码 |
| `masterdata.size.update` | 修改尺码 |
| `masterdata.size.view` | 查看尺码 |
| `masterdata.sku.create` | 新增 SKU |
| `masterdata.sku.generate` | 批量生成 SKU |
| `masterdata.sku.update` | 修改 SKU |
| `masterdata.sku.view` | 查看 SKU |
| `masterdata.style.create` | 新增款式 |
| `masterdata.style.update` | 修改款式 |
| `masterdata.style.view` | 查看款式 |
| `masterdata.uom.create` | 新增计量单位 |
| `masterdata.uom.update` | 修改计量单位 |
| `masterdata.uom.view` | 查看计量单位 |

### planning（15 条）

| 权限编码 | 名称 |
| --- | --- |
| `planning.bom.create` | 新增 BOM |
| `planning.bom.obsolete` | 作废 BOM 版本 |
| `planning.bom.submit` | 提交 BOM 审批 |
| `planning.bom.update` | 修改 BOM 草稿 |
| `planning.bom.view` | 查看 BOM |
| `planning.mrp.archive` | 归档 MRP 运行 |
| `planning.mrp.cancel` | 取消 MRP 建议 |
| `planning.mrp.convert` | MRP 建议转单 |
| `planning.mrp.run` | 运行 MRP 计算 |
| `planning.mrp.view` | 查看 MRP 运行与建议 |
| `planning.routing.create` | 新增工艺路线 |
| `planning.routing.obsolete` | 作废工艺路线版本 |
| `planning.routing.submit` | 提交工艺路线审批 |
| `planning.routing.update` | 修改工艺路线草稿 |
| `planning.routing.view` | 查看工艺路线 |

### procurement（15 条）

| 权限编码 | 名称 |
| --- | --- |
| `procurement.order.close` | 关闭采购订单 |
| `procurement.order.create` | 新增采购订单 |
| `procurement.order.override_supplier` | 采购订单供应商例外授权 |
| `procurement.order.submit` | 提交采购订单审批 |
| `procurement.order.update` | 修改/取消采购订单 |
| `procurement.order.view` | 查看采购订单 |
| `procurement.receipt.create` | 新增采购收货单 |
| `procurement.receipt.inspect` | 来料检验判定（质量放行） |
| `procurement.receipt.post` | 采购收货过账（记待检库存） |
| `procurement.receipt.update` | 修改/取消采购收货单 |
| `procurement.receipt.view` | 查看采购收货单 |
| `procurement.requisition.create` | 新增采购申请 |
| `procurement.requisition.submit` | 提交采购申请审批 |
| `procurement.requisition.update` | 修改/取消采购申请 |
| `procurement.requisition.view` | 查看采购申请 |

### sales（16 条）

| 权限编码 | 名称 |
| --- | --- |
| `sales.order.close` | 关闭销售订单 |
| `sales.order.create` | 新增销售订单 |
| `sales.order.release` | 释放销售订单库存占用 |
| `sales.order.reserve` | 销售订单库存占用 |
| `sales.order.submit` | 提交销售订单审批 |
| `sales.order.update` | 修改/取消销售订单 |
| `sales.order.view` | 查看销售订单 |
| `sales.return.create` | 新增销售退货单 |
| `sales.return.inspect` | 销售退货检验判定 |
| `sales.return.post` | 销售退货收货过账 |
| `sales.return.update` | 修改/取消销售退货单 |
| `sales.return.view` | 查看销售退货单 |
| `sales.shipment.create` | 新增销售发货单 |
| `sales.shipment.post` | 销售发货出库过账 |
| `sales.shipment.update` | 修改/取消销售发货单 |
| `sales.shipment.view` | 查看销售发货单 |

### srm（10 条）

| 权限编码 | 名称 |
| --- | --- |
| `srm.supplier.create` | 新增供应商 |
| `srm.supplier.deactivate` | 启用/停用供应商 |
| `srm.supplier.update` | 修改供应商 |
| `srm.supplier.view` | 查看供应商 |
| `srm.supplier_contact.create` | 新增供应商联系人 |
| `srm.supplier_contact.update` | 修改供应商联系人 |
| `srm.supplier_contact.view` | 查看供应商联系人 |
| `srm.supplier_qualification.create` | 新增供应商资质 |
| `srm.supplier_qualification.update` | 修改供应商资质 |
| `srm.supplier_qualification.view` | 查看供应商资质 |

### wms（18 条）

| 权限编码 | 名称 |
| --- | --- |
| `wms.document.create` | 创建库存单据 |
| `wms.document.post` | 库存单据过账 |
| `wms.document.reverse` | 库存单据冲销 |
| `wms.document.update` | 修改库存单据草稿 |
| `wms.document.view` | 查看库存单据 |
| `wms.inventory.release` | 释放库存占用 |
| `wms.inventory.reserve` | 库存占用 |
| `wms.inventory.view` | 查看库存余额与流水 |
| `wms.location.create` | 新增储位 |
| `wms.location.update` | 修改储位 |
| `wms.location.view` | 查看储位 |
| `wms.quality.release` | 库存质量放行 |
| `wms.warehouse.create` | 新增仓库 |
| `wms.warehouse.update` | 修改仓库 |
| `wms.warehouse.view` | 查看仓库 |
| `wms.zone.create` | 新增库区 |
| `wms.zone.update` | 修改库区 |
| `wms.zone.view` | 查看库区 |

### workflow（7 条）

| 权限编码 | 名称 |
| --- | --- |
| `workflow.instance.approve` | 审批通过/驳回 |
| `workflow.instance.submit` | 提交审批 |
| `workflow.instance.view` | 查看审批单 |
| `workflow.instance.withdraw` | 撤回审批 |
| `workflow.template.create` | 新增审批模板 |
| `workflow.template.update` | 修改审批模板 |
| `workflow.template.view` | 查看审批模板 |

## 四、菜单树与页面映射（生成自注册表，实际共 56 项）

| 菜单编码 | 名称 | 路由 | 组件 | 所需权限 | 类型 |
| --- | --- | --- | --- | --- | --- |
| `workspace` | 工作台 | /workspace | views/workspace/Index.vue | `analytics.dashboard.view` | page |
| `masterdata` | 基础资料 | /masterdata | Layout | - | directory |
| 　└ `masterdata.material` | 物料档案 | /masterdata/materials | views/masterdata/MaterialList.vue | `masterdata.material.view` | page |
| 　└ `masterdata.material-category` | 物料分类 | /masterdata/material-categories | views/masterdata/MaterialCategoryList.vue | `masterdata.material_category.view` | page |
| 　└ `masterdata.style` | 款式档案 | /masterdata/styles | views/masterdata/StyleList.vue | `masterdata.style.view` | page |
| 　└ `masterdata.sku` | SKU 档案 | /masterdata/skus | views/masterdata/SkuList.vue | `masterdata.sku.view` | page |
| 　└ `masterdata.color-size` | 颜色与尺码 | /masterdata/color-size | views/masterdata/ColorSizeList.vue | `masterdata.color.view` | page |
| 　└ `masterdata.uom` | 计量单位 | /masterdata/uoms | views/masterdata/UomList.vue | `masterdata.uom.view` | page |
| `factory` | 工厂与排班 | /factory | Layout | - | directory |
| 　└ `factory.company` | 公司 | /factory/companies | views/factory/CompanyList.vue | `factory.company.view` | page |
| 　└ `factory.department` | 部门 | /factory/departments | views/factory/DepartmentList.vue | `factory.department.view` | page |
| 　└ `factory.factory` | 工厂 | /factory/factories | views/factory/FactoryList.vue | `factory.factory.view` | page |
| 　└ `factory.workshop` | 车间与线体 | /factory/workshops | views/factory/WorkshopList.vue | `factory.workshop.view` | page |
| 　└ `factory.employee` | 员工档案 | /factory/employees | views/factory/EmployeeList.vue | `factory.employee.view` | page |
| 　└ `factory.team` | 班组 | /factory/teams | views/factory/TeamList.vue | `factory.team.view` | page |
| 　└ `factory.shift` | 班次 | /factory/shifts | views/factory/ShiftList.vue | `factory.shift.view` | page |
| `crm` | 客户管理 | /crm | Layout | - | directory |
| 　└ `crm.customer` | 客户档案 | /crm/customers | views/crm/CustomerList.vue | `crm.customer.view` | page |
| 　└ `crm.customer-contact` | 客户联系人 | /crm/customer-contacts | views/crm/CustomerContactList.vue | `crm.customer_contact.view` | page |
| `sales` | 销售管理 | /sales | Layout | - | directory |
| 　└ `sales.order` | 销售订单 | /sales/orders | views/sales/SalesOrderList.vue | `sales.order.view` | page |
| 　└ `sales.shipment` | 销售发货 | /sales/shipments | views/sales/SalesShipmentList.vue | `sales.shipment.view` | page |
| 　└ `sales.return` | 销售退货 | /sales/returns | views/sales/SalesReturnList.vue | `sales.return.view` | page |
| `srm` | 供应商管理 | /srm | Layout | - | directory |
| 　└ `srm.supplier` | 供应商档案 | /srm/suppliers | views/srm/SupplierList.vue | `srm.supplier.view` | page |
| 　└ `srm.supplier-contact` | 供应商联系人 | /srm/supplier-contacts | views/srm/SupplierContactList.vue | `srm.supplier_contact.view` | page |
| 　└ `srm.supplier-qualification` | 供应商资质 | /srm/supplier-qualifications | views/srm/SupplierQualificationList.vue | `srm.supplier_qualification.view` | page |
| `procurement` | 采购管理 | /procurement | Layout | - | directory |
| 　└ `procurement.requisition` | 采购申请 | /procurement/requisitions | views/procurement/RequisitionList.vue | `procurement.requisition.view` | page |
| 　└ `procurement.order` | 采购订单 | /procurement/orders | views/procurement/PurchaseOrderList.vue | `procurement.order.view` | page |
| 　└ `procurement.receipt` | 采购收货 | /procurement/receipts | views/procurement/GoodsReceiptList.vue | `procurement.receipt.view` | page |
| `planning` | 计划管理 | /planning | Layout | - | directory |
| 　└ `planning.bom` | 物料清单（BOM） | /planning/boms | views/planning/BomList.vue | `planning.bom.view` | page |
| 　└ `planning.routing` | 工艺路线 | /planning/routings | views/planning/RoutingList.vue | `planning.routing.view` | page |
| 　└ `planning.mrp` | MRP 运算 | /planning/mrp-runs | views/planning/MrpRunList.vue | `planning.mrp.view` | page |
| 　└ `planning.mrp_suggestion` | 缺料与建议 | /planning/mrp-suggestions | views/planning/MrpSuggestionList.vue | `planning.mrp.view` | page |
| `wms` | 仓储管理 | /wms | Layout | - | directory |
| 　└ `wms.warehouse` | 仓库与储位 | /wms/warehouses | views/wms/WarehouseList.vue | `wms.warehouse.view` | page |
| 　└ `wms.inventory-balance` | 库存余额 | /wms/inventory-balances | views/wms/InventoryBalanceList.vue | `wms.inventory.view` | page |
| 　└ `wms.inventory-transaction` | 库存流水 | /wms/inventory-transactions | views/wms/InventoryTransactionList.vue | `wms.inventory.view` | page |
| 　└ `wms.inventory-document` | 库存单据 | /wms/inventory-documents | views/wms/InventoryDocumentList.vue | `wms.document.view` | page |
| `workflow` | 审批中心 | /workflow | Layout | - | directory |
| 　└ `workflow.todo` | 我的待办 | /workflow/todo | views/workflow/TodoList.vue | `workflow.instance.view` | page |
| 　└ `workflow.my-requests` | 我的申请 | /workflow/my-requests | views/workflow/MyRequestList.vue | `workflow.instance.view` | page |
| 　└ `workflow.template` | 审批模板 | /workflow/templates | views/workflow/TemplateList.vue | `workflow.template.view` | page |
| `integration` | 内部协同 | /integration | Layout | - | directory |
| 　└ `integration.outbox` | 事件与协同 | /integration/outbox | views/integration/OutboxList.vue | `integration.outbox.view` | page |
| `system` | 系统管理 | /system | Layout | - | directory |
| 　└ `system.user` | 用户管理 | /system/users | views/system/UserList.vue | `identity.user.view` | page |
| 　└ `system.role` | 角色权限 | /system/roles | views/system/RoleList.vue | `identity.role.view` | page |
| 　└ `system.permission` | 权限与菜单 | /system/permissions | views/system/PermissionList.vue | `identity.permission.view` | page |
| 　└ `system.dictionary` | 数据字典 | /system/dictionaries | views/system/DictionaryList.vue | `core.dictionary.view` | page |
| 　└ `system.code-rule` | 编码规则 | /system/code-rules | views/system/CodeRuleList.vue | `core.code_rule.view` | page |
| 　└ `system.audit` | 审计与登录日志 | /system/audit-logs | views/system/AuditLogList.vue | `core.audit.view` | page |
| 　└ `system.notification` | 我的通知 | /system/notifications | views/system/NotificationList.vue | `core.notification.view` | page |
| 　└ `system.progress` | 实施进度 | /system/progress | views/system/ProgressView.vue | `core.progress.view` | page |


## 五、权限合并规则（多角色用户）

规则实现在 `apps/core/selectors.py::resolve_data_scope`，**后端启动与测试均校验该规则**：

1. **超级管理员**不受限制：`is_superuser=True` 的账号在数据范围上直接得到 `all`；
   在操作权限上 `User.permission_codes()` 返回的是**通配符 `{"*"}`**，而不是 173 条编码的展开。

   > ⚠️ **通配符契约（真实缺陷的教训）**：任何客户端都必须把 `*` 解释为「全部权限」。
   > 前端实现在 `frontend/src/stores/auth.ts::hasFullAccess`；
   > 早期版本只做 `permissions.includes(code)`，导致超级管理员被误判为「没有任何权限」、
   > 所有新增 / 编辑 / 删除按钮全部消失（已修复，回归用例 `frontend/tests/auth-store.spec.ts`）。
   > 后端 `has_permission_codes()` 同步支持 `*`，两者语义必须一致。
2. **无角色**用户 → 空范围（`none`），看不到任何业务数据。
3. **操作权限取并集**：用户拥有多个角色时，只要任一角色授予某权限编码，即视为拥有。
4. **数据范围取最宽的一档**：按 `DataScopeType.rank_map()` 排序，取 rank 最高的角色档次作为生效档次。
   - 例：角色 A = 指定仓库，角色 B = 本公司 → 生效档次为「本公司」。
5. **同档次内取并集**：多个角色均为 `custom` 时，各角色授权的组织范围合并。
6. **先公司边界，再细分维度**：`company` 边界首先施加，工厂/部门/仓库维度只在公司边界内生效，
   不能借由某个角色的组织授权突破公司边界。
7. **自定义范围维度间取并集、与公司边界取交集**（即 `OR(维度并集) AND 公司边界`）。
8. **单一维度范围缺少对应字段时 fail-closed**：若角色范围为 `factory`/`department`/`warehouse`，
   但被查询模型上**没有该维度字段**，则返回**空集**（就严不就宽），而不是退化为「不过滤」。
9. **共享主数据显式放开**：`scope_fields=None` 的模型（如颜色、尺码、计量单位等全局共享主数据）
   不施加数据范围过滤，属于**显式声明**，不是遗漏。

> 规则 8 是安全关键点：任何「维度字段缺失」都必须收敛为「看不到」，不允许静默放宽。

## 六、权限执行位置（任务书 6.4）

| 位置 | 实现方式 | 对应测试 |
| --- | --- | --- |
| 列表查询过滤 | Selector 中统一 `apply_data_scope()` | `test_permissions.py`（范围过滤断言） |
| 详情访问校验 | `get_object()` 走同一 scope 过滤后的查询集 | `test_permissions.py` |
| 修改 / 审批 / 删除校验 | `HasRequiredPermissions` + Service 内 `require_codes()` | `test_permissions.py`、`test_workflow_api.py` |
| 关联对象选择校验 | 选项类接口（下拉数据源）同样走 scope | `test_permissions.py`（跨范围选项不可见） |
| 导出与异步任务校验 | 导出任务记录发起人，执行与下载时**重新校验**权限状态 | 阶段 2 随导出实现 |
| 附件下载校验 | `core.attachment.download` 权限 + 业务对象可达性校验 | `test_core_services.py` |
| 图表汇总校验 | `analytics` 聚合同样按 scope 过滤 | `test_smoke_api.py::test_dashboard_endpoint` |

**权限撤销后的收敛**：`identity_user.permission_version` 用于在权限变更时使已缓存的权限判定失效；
后台导出任务在执行与下载两个时点**分别校验**，避免账号权限被撤销后仍可下载敏感数据。
登录态变更（改密、停用）按规则使现有会话失效。

## 七、必测案例映射（任务书 14.2 中与权限相关的部分）

| 必测案例 | 覆盖测试 |
| --- | --- |
| 1. 未登录访问被拒绝 | `test_auth_api.py`（未认证返回 403）、HTTP 验证脚本（未登录访问 `/identity/users/`） |
| 2. 无操作权限不能调用接口 | `test_permissions.py::test_*permission_denied*` |
| 3. 工厂和仓库范围不能越权 | `test_permissions.py`（scope 过滤断言） |
| 4. 关联对象 ID 不能绕过范围限制 | `test_permissions.py`（跨范围详情返回 404/403） |
| 20. 敏感附件不能越权下载 | `test_permissions.py::test_attachment_download_requires_permission` |
| 3/4（客户与供应商主数据） | `test_crm_api.py`、`test_srm_api.py`：列表 / 详情 / 写入三处范围校验；联系人、资质通过 `customer__company_id`、`supplier__company_id` 继承父级范围，跨公司详情返回 404、跨公司写入返回 403 `OUT_OF_DATA_SCOPE` |
| 3 （库存数据范围） | `test_wms_inventory.py::test_api_enforces_warehouse_scope`：仓库范围外的仓库 ID 不可查询、不可建单 |
| 2 （库存操作权限） | `test_wms_inventory.py::test_inventory_endpoints_require_permission`：无 `wms.document.post` 的用户过账返回 403 |
| 1 （库存未登录） | `test_wms_inventory.py::test_inventory_endpoints_require_login`：余额/流水/单据三类接口未登录均被拒 |
| 1 / 2 / 3 / 4 （MRP） | `test_mrp.py`：`test_anonymous_access_rejected`（匿名 403）、`test_view_only_user_cannot_run_mrp`、`test_user_without_convert_permission_cannot_convert`、`test_convert_requires_procurement_requisition_create`（转单同时要求 `planning.mrp.convert` 与 `procurement.requisition.create`）、`test_api_run_scoped_to_company_and_warehouse`（公司 / 仓库范围）、`test_mrp_permissions_do_not_grant_other_modules`（权限不外溢）、`test_archive_api_requires_permission_and_is_audited` |

其余必测案例（部分并发场景、排班冲突、表计复位等）属于后续阶段，见 `docs/test-report.md` 的「未执行」清单。

## 八、安全限制（硬性）

- **Django 内置权限不能替代业务数据权限**：`is_staff` 不等于业务权限；业务接口一律走权限点 + 数据范围。
- 前端不做最终授权：即使前端隐藏按钮，后端仍必须独立校验（已通过 HTTP 验证脚本确认：直接调用接口会被拒绝）。
- 权限编码是**跨模块契约**：新增页面/接口必须先在 `permissions_registry` 注册，否则启动自检失败。
- 职业健康等敏感信息在阶段 6 落地时**单独授权**，不复用通用查看权限。
- 密码与设备密钥不得明文记入日志；审计不保存完整密码、令牌或无必要的敏感原文。