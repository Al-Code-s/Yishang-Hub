"""权限与菜单注册表。

权限编码是后端与前端共同依赖的契约：
* bootstrap_system 依据本表写入 identity.Permission / identity.Menu；
* apps/core/checks.py 会校验视图声明的编码都在本表中，防止拼写错误悄悄放行。
"""

from __future__ import annotations

from typing import NamedTuple


class PermissionDef(NamedTuple):
    code: str
    name: str
    permission_type: str = "action"

    @property
    def module(self) -> str:
        return self.code.split(".")[0]

    @property
    def resource(self) -> str:
        return self.code.split(".")[1]

    @property
    def action(self) -> str:
        return ".".join(self.code.split(".")[2:])


PERMISSIONS: list[PermissionDef] = [
    # 工作台
    PermissionDef("analytics.dashboard.view", "查看工作台"),
    # 系统管理 - 用户
    PermissionDef("identity.user.view", "查看用户"),
    PermissionDef("identity.user.create", "新增用户"),
    PermissionDef("identity.user.update", "修改用户"),
    PermissionDef("identity.user.deactivate", "启用/停用用户"),
    PermissionDef("identity.user.reset_password", "重置用户密码"),
    PermissionDef("identity.user.unlock", "解除用户锁定"),
    PermissionDef("identity.user.assign_role", "分配用户角色"),
    # 系统管理 - 角色
    PermissionDef("identity.role.view", "查看角色"),
    PermissionDef("identity.role.create", "新增角色"),
    PermissionDef("identity.role.update", "修改角色"),
    PermissionDef("identity.role.delete", "删除角色"),
    PermissionDef("identity.role.assign_permission", "配置角色权限与数据范围"),
    PermissionDef("identity.menu.view", "查看菜单"),
    PermissionDef("identity.permission.view", "查看权限点"),
    PermissionDef("identity.log.view", "查看登录记录"),
    # 组织与工厂
    PermissionDef("factory.company.view", "查看公司"),
    PermissionDef("factory.company.create", "新增公司"),
    PermissionDef("factory.company.update", "修改公司"),
    PermissionDef("factory.department.view", "查看部门"),
    PermissionDef("factory.department.create", "新增部门"),
    PermissionDef("factory.department.update", "修改部门"),
    PermissionDef("factory.factory.view", "查看工厂"),
    PermissionDef("factory.factory.create", "新增工厂"),
    PermissionDef("factory.factory.update", "修改工厂"),
    PermissionDef("factory.workshop.view", "查看车间"),
    PermissionDef("factory.workshop.create", "新增车间"),
    PermissionDef("factory.workshop.update", "修改车间"),
    PermissionDef("factory.line.view", "查看线体"),
    PermissionDef("factory.line.create", "新增线体"),
    PermissionDef("factory.line.update", "修改线体"),
    PermissionDef("factory.station.view", "查看工位"),
    PermissionDef("factory.station.create", "新增工位"),
    PermissionDef("factory.station.update", "修改工位"),
    PermissionDef("factory.employee.view", "查看员工"),
    PermissionDef("factory.employee.create", "新增员工"),
    PermissionDef("factory.employee.update", "修改员工"),
    PermissionDef("factory.shift.view", "查看班次"),
    PermissionDef("factory.shift.create", "新增班次"),
    PermissionDef("factory.shift.update", "修改班次"),
    PermissionDef("factory.team.view", "查看班组"),
    PermissionDef("factory.team.create", "新增班组"),
    PermissionDef("factory.team.update", "修改班组"),
    # 基础资料 - 计量单位
    PermissionDef("masterdata.uom.view", "查看计量单位"),
    PermissionDef("masterdata.uom.create", "新增计量单位"),
    PermissionDef("masterdata.uom.update", "修改计量单位"),
    # 基础资料 - 物料分类
    PermissionDef("masterdata.material_category.view", "查看物料分类"),
    PermissionDef("masterdata.material_category.create", "新增物料分类"),
    PermissionDef("masterdata.material_category.update", "修改物料分类"),
    # 基础资料 - 物料
    PermissionDef("masterdata.material.view", "查看物料"),
    PermissionDef("masterdata.material.create", "新增物料"),
    PermissionDef("masterdata.material.update", "修改物料"),
    PermissionDef("masterdata.material.deactivate", "启用/停用物料"),
    # 基础资料 - 颜色 / 尺码
    PermissionDef("masterdata.color.view", "查看颜色"),
    PermissionDef("masterdata.color.create", "新增颜色"),
    PermissionDef("masterdata.color.update", "修改颜色"),
    PermissionDef("masterdata.size.view", "查看尺码"),
    PermissionDef("masterdata.size.create", "新增尺码"),
    PermissionDef("masterdata.size.update", "修改尺码"),
    # 基础资料 - 款式与 SKU
    PermissionDef("masterdata.style.view", "查看款式"),
    PermissionDef("masterdata.style.create", "新增款式"),
    PermissionDef("masterdata.style.update", "修改款式"),
    PermissionDef("masterdata.sku.view", "查看 SKU"),
    PermissionDef("masterdata.sku.create", "新增 SKU"),
    PermissionDef("masterdata.sku.update", "修改 SKU"),
    PermissionDef("masterdata.sku.generate", "批量生成 SKU"),
    # 基础资料 - 标识（条码 / 批次 / 卷号 / 箱码 / RFID / 载具）
    PermissionDef("masterdata.identifier.view", "查看标识"),
    PermissionDef("masterdata.identifier.create", "新增标识"),
    PermissionDef("masterdata.identifier.update", "修改标识"),
    PermissionDef("masterdata.identifier.deactivate", "停用标识"),
    # 仓储 - 仓库 / 库区 / 储位
    # 仓储 - 库存占用（销售发货「先占用、后发货」的业务规则依赖它）
    PermissionDef("wms.inventory.reserve", "库存占用"),
    PermissionDef("wms.inventory.release", "释放库存占用"),
    # 销售管理 - 销售订单
    PermissionDef("sales.order.view", "查看销售订单"),
    PermissionDef("sales.order.create", "新增销售订单"),
    PermissionDef("sales.order.update", "修改/取消销售订单"),
    PermissionDef("sales.order.submit", "提交销售订单审批"),
    PermissionDef("sales.order.close", "关闭销售订单"),
    PermissionDef("sales.order.reserve", "销售订单库存占用"),
    PermissionDef("sales.order.release", "释放销售订单库存占用"),
    # 销售管理 - 发货
    PermissionDef("sales.shipment.view", "查看销售发货单"),
    PermissionDef("sales.shipment.create", "新增销售发货单"),
    PermissionDef("sales.shipment.update", "修改/取消销售发货单"),
    PermissionDef("sales.shipment.post", "销售发货出库过账"),
    # 销售管理 - 退货
    PermissionDef("sales.return.view", "查看销售退货单"),
    PermissionDef("sales.return.create", "新增销售退货单"),
    PermissionDef("sales.return.update", "修改/取消销售退货单"),
    PermissionDef("sales.return.post", "销售退货收货过账"),
    PermissionDef("sales.return.inspect", "销售退货检验判定"),
    # 采购管理 - 采购申请
    PermissionDef("procurement.requisition.view", "查看采购申请"),
    PermissionDef("procurement.requisition.create", "新增采购申请"),
    PermissionDef("procurement.requisition.update", "修改/取消采购申请"),
    PermissionDef("procurement.requisition.submit", "提交采购申请审批"),
    # 采购管理 - 采购订单
    PermissionDef("procurement.order.view", "查看采购订单"),
    PermissionDef("procurement.order.create", "新增采购订单"),
    PermissionDef("procurement.order.update", "修改/取消采购订单"),
    PermissionDef("procurement.order.submit", "提交采购订单审批"),
    PermissionDef("procurement.order.close", "关闭采购订单"),
    PermissionDef(
        "procurement.order.override_supplier", "采购订单供应商例外授权"
    ),
    # 采购管理 - 收货与检验
    PermissionDef("procurement.receipt.view", "查看采购收货单"),
    PermissionDef("procurement.receipt.create", "新增采购收货单"),
    PermissionDef("procurement.receipt.update", "修改/取消采购收货单"),
    PermissionDef("procurement.receipt.post", "采购收货过账（记待检库存）"),
    PermissionDef("procurement.receipt.inspect", "来料检验判定（质量放行）"),
    PermissionDef("wms.warehouse.view", "查看仓库"),
    PermissionDef("wms.warehouse.create", "新增仓库"),
    PermissionDef("wms.warehouse.update", "修改仓库"),
    PermissionDef("wms.zone.view", "查看库区"),
    PermissionDef("wms.zone.create", "新增库区"),
    PermissionDef("wms.zone.update", "修改库区"),
    PermissionDef("wms.location.view", "查看储位"),
    PermissionDef("wms.location.create", "新增储位"),
    PermissionDef("wms.location.update", "修改储位"),
    # 仓储 - 库存（统一库存服务，阶段 2）
    PermissionDef("wms.inventory.view", "查看库存余额与流水"),
    PermissionDef("wms.document.view", "查看库存单据"),
    PermissionDef("wms.document.create", "创建库存单据"),
    PermissionDef("wms.document.update", "修改库存单据草稿"),
    PermissionDef("wms.document.post", "库存单据过账"),
    PermissionDef("wms.document.reverse", "库存单据冲销"),
    PermissionDef("wms.quality.release", "库存质量放行"),
    # 审批
    PermissionDef("workflow.template.view", "查看审批模板"),
    PermissionDef("workflow.template.create", "新增审批模板"),
    PermissionDef("workflow.template.update", "修改审批模板"),
    PermissionDef("workflow.instance.view", "查看审批单"),
    PermissionDef("workflow.instance.submit", "提交审批"),
    PermissionDef("workflow.instance.approve", "审批通过/驳回"),
    PermissionDef("workflow.instance.withdraw", "撤回审批"),
    # 客户管理
    PermissionDef("crm.customer.view", "查看客户"),
    PermissionDef("crm.customer.create", "新增客户"),
    PermissionDef("crm.customer.update", "修改客户"),
    PermissionDef("crm.customer.deactivate", "启用/停用客户"),
    PermissionDef("crm.customer_contact.view", "查看客户联系人"),
    PermissionDef("crm.customer_contact.create", "新增客户联系人"),
    PermissionDef("crm.customer_contact.update", "修改客户联系人"),
    # 供应商管理
    PermissionDef("srm.supplier.view", "查看供应商"),
    PermissionDef("srm.supplier.create", "新增供应商"),
    PermissionDef("srm.supplier.update", "修改供应商"),
    PermissionDef("srm.supplier.deactivate", "启用/停用供应商"),
    PermissionDef("srm.supplier_contact.view", "查看供应商联系人"),
    PermissionDef("srm.supplier_contact.create", "新增供应商联系人"),
    PermissionDef("srm.supplier_contact.update", "修改供应商联系人"),
    PermissionDef("srm.supplier_qualification.view", "查看供应商资质"),
    PermissionDef("srm.supplier_qualification.create", "新增供应商资质"),
    PermissionDef("srm.supplier_qualification.update", "修改供应商资质"),
    # 计划管理 - BOM（物料清单）
    PermissionDef("planning.bom.view", "查看 BOM"),
    PermissionDef("planning.bom.create", "新增 BOM"),
    PermissionDef("planning.bom.update", "修改 BOM 草稿"),
    PermissionDef("planning.bom.submit", "提交 BOM 审批"),
    PermissionDef("planning.bom.obsolete", "作废 BOM 版本"),
    # 计划管理 - 工艺路线
    PermissionDef("planning.routing.view", "查看工艺路线"),
    PermissionDef("planning.routing.create", "新增工艺路线"),
    PermissionDef("planning.routing.update", "修改工艺路线草稿"),
    PermissionDef("planning.routing.submit", "提交工艺路线审批"),
    PermissionDef("planning.routing.obsolete", "作废工艺路线版本"),
    # 计划管理 - MRP 运算
    PermissionDef("planning.mrp.view", "查看 MRP 运行与建议"),
    PermissionDef("planning.mrp.run", "运行 MRP 计算"),
    PermissionDef("planning.mrp.convert", "MRP 建议转单"),
    PermissionDef("planning.mrp.cancel", "取消 MRP 建议"),
    PermissionDef("planning.mrp.archive", "归档 MRP 运行"),
    # 公共
    PermissionDef("core.dictionary.view", "查看数据字典"),
    PermissionDef("core.dictionary.create", "新增数据字典"),
    PermissionDef("core.dictionary.update", "修改数据字典"),
    PermissionDef("core.code_rule.view", "查看编码规则"),
    PermissionDef("core.code_rule.create", "新增编码规则"),
    PermissionDef("core.code_rule.update", "修改编码规则"),
    PermissionDef("core.audit.view", "查看审计日志"),
    PermissionDef("core.attachment.upload", "上传附件"),
    PermissionDef("core.attachment.download", "下载附件"),
    PermissionDef("core.attachment.delete", "删除附件"),
    PermissionDef("core.notification.view", "查看通知"),
    PermissionDef("core.progress.view", "查看实施进度"),
    # 内部协同
    PermissionDef("integration.outbox.view", "查看发件箱事件"),
    PermissionDef("integration.outbox.retry", "重试发件箱事件"),
    PermissionDef("integration.document_link.view", "查看单据关系"),
]


class MenuDef(NamedTuple):
    code: str
    name: str
    parent: str | None
    path: str
    component: str
    icon: str
    sort_order: int
    menu_type: str = "page"
    permission_code: str = ""


# 只登记阶段 1 已实际实现的页面，未实施模块不放置伪可用菜单
MENUS: list[MenuDef] = [
    # 工作台绑定 analytics.dashboard.view：能看到看板的用户就应看到入口
    MenuDef(
        "workspace", "工作台", None, "/workspace", "views/workspace/Index.vue", "Odometer", 10,
        "page", "analytics.dashboard.view",
    ),
    MenuDef("masterdata", "基础资料", None, "/masterdata", "Layout", "Files", 20, "directory"),
    MenuDef(
        "masterdata.material", "物料档案", "masterdata", "/masterdata/materials",
        "views/masterdata/MaterialList.vue", "Box", 21, "page", "masterdata.material.view",
    ),
    MenuDef(
        "masterdata.material-category", "物料分类", "masterdata", "/masterdata/material-categories",
        "views/masterdata/MaterialCategoryList.vue", "Collection", 22, "page",
        "masterdata.material_category.view",
    ),
    MenuDef(
        "masterdata.style", "款式档案", "masterdata", "/masterdata/styles",
        "views/masterdata/StyleList.vue", "Suitcase", 23, "page", "masterdata.style.view",
    ),
    MenuDef(
        "masterdata.sku", "SKU 档案", "masterdata", "/masterdata/skus",
        "views/masterdata/SkuList.vue", "Grid", 24, "page", "masterdata.sku.view",
    ),
    MenuDef(
        "masterdata.color-size", "颜色与尺码", "masterdata", "/masterdata/color-size",
        "views/masterdata/ColorSizeList.vue", "Brush", 25, "page", "masterdata.color.view",
    ),
    MenuDef(
        "masterdata.uom", "计量单位", "masterdata", "/masterdata/uoms",
        "views/masterdata/UomList.vue", "ScaleToOriginal", 26, "page", "masterdata.uom.view",
    ),
    MenuDef("factory", "工厂与排班", None, "/factory", "Layout", "OfficeBuilding", 30, "directory"),
    MenuDef(
        "factory.company", "公司", "factory", "/factory/companies",
        "views/factory/CompanyList.vue", "Postcard", 31, "page", "factory.company.view",
    ),
    MenuDef(
        "factory.department", "部门", "factory", "/factory/departments",
        "views/factory/DepartmentList.vue", "Share", 32, "page", "factory.department.view",
    ),
    MenuDef(
        "factory.factory", "工厂", "factory", "/factory/factories",
        "views/factory/FactoryList.vue", "OfficeBuilding", 33, "page", "factory.factory.view",
    ),
    MenuDef(
        "factory.workshop", "车间与线体", "factory", "/factory/workshops",
        "views/factory/WorkshopList.vue", "SetUp", 34, "page", "factory.workshop.view",
    ),
    MenuDef(
        "factory.employee", "员工档案", "factory", "/factory/employees",
        "views/factory/EmployeeList.vue", "User", 35, "page", "factory.employee.view",
    ),
    MenuDef(
        "factory.team", "班组", "factory", "/factory/teams",
        "views/factory/TeamList.vue", "UserFilled", 36, "page", "factory.team.view",
    ),
    MenuDef(
        "factory.shift", "班次", "factory", "/factory/shifts",
        "views/factory/ShiftList.vue", "Clock", 37, "page", "factory.shift.view",
    ),
    MenuDef("crm", "客户管理", None, "/crm", "Layout", "Tickets", 40, "directory"),
    MenuDef(
        "crm.customer", "客户档案", "crm", "/crm/customers",
        "views/crm/CustomerList.vue", "Avatar", 41, "page", "crm.customer.view",
    ),
    MenuDef(
        "crm.customer-contact", "客户联系人", "crm", "/crm/customer-contacts",
        "views/crm/CustomerContactList.vue", "Phone", 42, "page", "crm.customer_contact.view",
    ),
    MenuDef("sales", "销售管理", None, "/sales", "Layout", "Sell", 50, "directory"),
    MenuDef(
        "sales.order", "销售订单", "sales", "/sales/orders",
        "views/sales/SalesOrderList.vue", "Document", 51, "page", "sales.order.view",
    ),
    MenuDef(
        "sales.shipment", "销售发货", "sales", "/sales/shipments",
        "views/sales/SalesShipmentList.vue", "Van", 52, "page", "sales.shipment.view",
    ),
    MenuDef(
        "sales.return", "销售退货", "sales", "/sales/returns",
        "views/sales/SalesReturnList.vue", "RefreshLeft", 53, "page", "sales.return.view",
    ),
    MenuDef("srm", "供应商管理", None, "/srm", "Layout", "Shop", 60, "directory"),
    MenuDef(
        "srm.supplier", "供应商档案", "srm", "/srm/suppliers",
        "views/srm/SupplierList.vue", "OfficeBuilding", 61, "page", "srm.supplier.view",
    ),
    MenuDef(
        "srm.supplier-contact", "供应商联系人", "srm", "/srm/supplier-contacts",
        "views/srm/SupplierContactList.vue", "PhoneFilled", 62, "page", "srm.supplier_contact.view",
    ),
    MenuDef(
        "srm.supplier-qualification", "供应商资质", "srm", "/srm/supplier-qualifications",
        "views/srm/SupplierQualificationList.vue", "Medal", 63, "page",
        "srm.supplier_qualification.view",
    ),
    MenuDef("procurement", "采购管理", None, "/procurement", "Layout", "ShoppingCart", 70, "directory"),
    MenuDef(
        "procurement.requisition", "采购申请", "procurement", "/procurement/requisitions",
        "views/procurement/RequisitionList.vue", "Document", 71, "page",
        "procurement.requisition.view",
    ),
    MenuDef(
        "procurement.order", "采购订单", "procurement", "/procurement/orders",
        "views/procurement/PurchaseOrderList.vue", "ShoppingCart", 72, "page",
        "procurement.order.view",
    ),
    MenuDef(
        "procurement.receipt", "采购收货", "procurement", "/procurement/receipts",
        "views/procurement/GoodsReceiptList.vue", "Van", 73, "page",
        "procurement.receipt.view",
    ),
    MenuDef("planning", "计划管理", None, "/planning", "Layout", "Calendar", 75, "directory"),
    MenuDef(
        "planning.bom", "物料清单（BOM）", "planning", "/planning/boms",
        "views/planning/BomList.vue", "Files", 76, "page", "planning.bom.view",
    ),
    MenuDef(
        "planning.routing", "工艺路线", "planning", "/planning/routings",
        "views/planning/RoutingList.vue", "Guide", 77, "page", "planning.routing.view",
    ),
    MenuDef(
        "planning.mrp", "MRP 运算", "planning", "/planning/mrp-runs",
        "views/planning/MrpRunList.vue", "TrendCharts", 78, "page", "planning.mrp.view",
    ),
    MenuDef(
        "planning.mrp_suggestion", "缺料与建议", "planning", "/planning/mrp-suggestions",
        "views/planning/MrpSuggestionList.vue", "Warning", 79, "page", "planning.mrp.view",
    ),
    MenuDef("wms", "仓储管理", None, "/wms", "Layout", "Box", 80, "directory"),
    MenuDef(
        "wms.warehouse", "仓库与储位", "wms", "/wms/warehouses",
        "views/wms/WarehouseList.vue", "House", 81, "page", "wms.warehouse.view",
    ),
    MenuDef(
        "wms.inventory-balance", "库存余额", "wms", "/wms/inventory-balances",
        "views/wms/InventoryBalanceList.vue", "Coin", 82, "page", "wms.inventory.view",
    ),
    MenuDef(
        "wms.inventory-transaction", "库存流水", "wms", "/wms/inventory-transactions",
        "views/wms/InventoryTransactionList.vue", "Tickets", 83, "page", "wms.inventory.view",
    ),
    MenuDef(
        "wms.inventory-document", "库存单据", "wms", "/wms/inventory-documents",
        "views/wms/InventoryDocumentList.vue", "Document", 84, "page", "wms.document.view",
    ),
    MenuDef("workflow", "审批中心", None, "/workflow", "Layout", "Stamp", 100, "directory"),
    MenuDef(
        "workflow.todo", "我的待办", "workflow", "/workflow/todo",
        "views/workflow/TodoList.vue", "Bell", 101, "page", "workflow.instance.view",
    ),
    MenuDef(
        "workflow.my-requests", "我的申请", "workflow", "/workflow/my-requests",
        "views/workflow/MyRequestList.vue", "Document", 102, "page", "workflow.instance.view",
    ),
    MenuDef(
        "workflow.template", "审批模板", "workflow", "/workflow/templates",
        "views/workflow/TemplateList.vue", "SetUp", 103, "page", "workflow.template.view",
    ),
    MenuDef("integration", "内部协同", None, "/integration", "Layout", "Connection", 110, "directory"),
    MenuDef(
        "integration.outbox", "事件与协同", "integration", "/integration/outbox",
        "views/integration/OutboxList.vue", "Promotion", 111, "page", "integration.outbox.view",
    ),
    MenuDef("system", "系统管理", None, "/system", "Layout", "Setting", 190, "directory"),
    MenuDef(
        "system.user", "用户管理", "system", "/system/users",
        "views/system/UserList.vue", "User", 191, "page", "identity.user.view",
    ),
    MenuDef(
        "system.role", "角色权限", "system", "/system/roles",
        "views/system/RoleList.vue", "Lock", 192, "page", "identity.role.view",
    ),
    MenuDef(
        "system.permission", "权限与菜单", "system", "/system/permissions",
        "views/system/PermissionList.vue", "Key", 193, "page", "identity.permission.view",
    ),
    MenuDef(
        "system.dictionary", "数据字典", "system", "/system/dictionaries",
        "views/system/DictionaryList.vue", "Notebook", 194, "page", "core.dictionary.view",
    ),
    MenuDef(
        "system.code-rule", "编码规则", "system", "/system/code-rules",
        "views/system/CodeRuleList.vue", "Ticket", 195, "page", "core.code_rule.view",
    ),
    MenuDef(
        "system.audit", "审计与登录日志", "system", "/system/audit-logs",
        "views/system/AuditLogList.vue", "Document", 196, "page", "core.audit.view",
    ),
    MenuDef(
        "system.notification", "我的通知", "system", "/system/notifications",
        "views/system/NotificationList.vue", "ChatDotRound", 197, "page", "core.notification.view",
    ),
    MenuDef(
        "system.progress", "实施进度", "system", "/system/progress",
        "views/system/ProgressView.vue", "DataLine", 198, "page", "core.progress.view",
    ),
]

PERMISSION_CODES: set[str] = {item.code for item in PERMISSIONS}
MENU_CODES: set[str] = {item.code for item in MENUS}

# 权限模块的中文名。
#
# 权限编码的第一段是模块（如 ``core.user.view`` 的 ``core``），角色配置界面的
# 一级分组若只显示英文模块名，业务人员无法判断「core」到底管什么。
# 界面上统一显示为 ``模块编码（中文名）``，例如 ``core（公共基础）``。
#
# 名称尽量与左侧一级菜单保持一致，便于对照；``core`` 这类不直接对应菜单的
# 基础能力单独命名，不与「用户与权限」重复。
# 新增权限模块时**必须**在此登记，否则 ``yishang.E002`` 启动检查会报错。
MODULE_LABELS: dict[str, str] = {
    "analytics": "工作台与看板",
    "core": "公共基础",
    "crm": "客户管理",
    "factory": "工厂与排班",
    "identity": "用户与权限",
    "integration": "内部协同",
    "masterdata": "基础资料",
    "planning": "计划管理",
    "procurement": "采购管理",
    "sales": "销售管理",
    "srm": "供应商管理",
    "wms": "仓储管理",
    "workflow": "审批中心",
}


def module_label(module: str) -> str:
    """模块中文名；未登记时返回空串，界面只显示模块编码。"""
    return MODULE_LABELS.get(module, "")

