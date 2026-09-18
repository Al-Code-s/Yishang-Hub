import { createCrudApi } from '@/api/crud'
import type {
  Attachment,
  AuditLog,
  Bom,
  BomInput,
  CodeRule,
  Color,
  Company,
  Customer,
  CustomerContact,
  Department,
  Dictionary,
  DictionaryItem,
  Employee,
  Factory,
  GoodsReceipt,
  GoodsReceiptInput,
  InventoryBalance,
  InventoryDocument,
  InventoryDocumentInput,
  InventoryTransaction,
  Location,
  Material,
  MaterialCategory,
  MrpRun,
  MrpRunInput,
  MrpSuggestion,
  PermissionRow,
  ProductionLine,
  PurchaseOrder,
  PurchaseOrderInput,
  PurchaseRequisition,
  RequisitionInput,
  ReturnInput,
  Role,
  Routing,
  RoutingInput,
  SalesOrder,
  SalesOrderInput,
  SalesReturn,
  SalesShipment,
  ShipmentInput,
  Shift,
  Size,
  Sku,
  Station,
  Style,
  Supplier,
  SupplierContact,
  SupplierQualification,
  Team,
  UoM,
  UserRow,
  Warehouse,
  Zone,
} from '@/types/models'

/** 资源路径集中定义，避免各页面自行拼字符串导致 URL 漂移。 */

// 基础资料
export const materialApi = createCrudApi<Material>('/masterdata/materials')
export const materialCategoryApi = createCrudApi<MaterialCategory>('/masterdata/material-categories')
export const styleApi = createCrudApi<Style>('/masterdata/styles')
export const skuApi = createCrudApi<Sku>('/masterdata/skus')
export const colorApi = createCrudApi<Color>('/masterdata/colors')
export const sizeApi = createCrudApi<Size>('/masterdata/sizes')
export const uomApi = createCrudApi<UoM>('/masterdata/uoms')
export const uomConversionApi = createCrudApi<{ id: number }>('/masterdata/uom-conversions')

// 组织与工厂
export const companyApi = createCrudApi<Company>('/factory/companies')
export const departmentApi = createCrudApi<Department>('/factory/departments')
export const factoryApi = createCrudApi<Factory>('/factory/factories')
export const workshopApi = createCrudApi<{ id: number }>('/factory/workshops')
export const lineApi = createCrudApi<ProductionLine>('/factory/lines')
export const stationApi = createCrudApi<Station>('/factory/stations')
export const employeeApi = createCrudApi<Employee>('/factory/employees')
export const shiftApi = createCrudApi<Shift>('/factory/shifts')
export const teamApi = createCrudApi<Team>('/factory/teams')

// 仓储基础（阶段 1 仅主数据）
export const warehouseApi = createCrudApi<Warehouse>('/wms/warehouses')
export const zoneApi = createCrudApi<Zone>('/wms/zones')
export const locationApi = createCrudApi<Location>('/wms/locations')

// 仓储库存（阶段 2：统一库存服务）。余额与流水只读，写入只能经由库存服务。
export const inventoryBalanceApi = createCrudApi<InventoryBalance>('/wms/inventory-balances')
export const inventoryTransactionApi = createCrudApi<InventoryTransaction>(
  '/wms/inventory-transactions',
)
export const inventoryDocumentApi = createCrudApi<InventoryDocument, InventoryDocumentInput>(
  '/wms/inventory-documents',
)

// 客户管理（阶段 2 第一步：客户档案与联系人主数据）
export const customerApi = createCrudApi<Customer>('/crm/customers')
export const customerContactApi = createCrudApi<CustomerContact>('/crm/customer-contacts')

// 供应商管理（阶段 2 第一步：供应商、联系人、资质有效期）
export const supplierApi = createCrudApi<Supplier>('/srm/suppliers')
export const supplierContactApi = createCrudApi<SupplierContact>('/srm/supplier-contacts')
export const supplierQualificationApi = createCrudApi<SupplierQualification>(
  '/srm/supplier-qualifications',
)

// 采购管理（阶段 2 增量：申请 / 订单 / 到货收货）
export const requisitionApi = createCrudApi<PurchaseRequisition, RequisitionInput>(
  '/procurement/requisitions',
)
export const purchaseOrderApi = createCrudApi<PurchaseOrder, PurchaseOrderInput>(
  '/procurement/orders',
)
export const goodsReceiptApi = createCrudApi<GoodsReceipt, GoodsReceiptInput>(
  '/procurement/receipts',
)

// 销售管理（阶段 2 增量：订单 → 库存占用 → 发货 / 退货）
export const salesOrderApi = createCrudApi<SalesOrder, SalesOrderInput>('/sales/orders')
export const salesShipmentApi = createCrudApi<SalesShipment, ShipmentInput>(
  '/sales/shipments',
)
export const salesReturnApi = createCrudApi<SalesReturn, ReturnInput>('/sales/returns')

// 计划管理（阶段 3 第一步：BOM 与工艺路线版本快照）
export const bomApi = createCrudApi<Bom, BomInput>('/planning/boms')
export const routingApi = createCrudApi<Routing, RoutingInput>('/planning/routings')
export const mrpRunApi = createCrudApi<MrpRun, MrpRunInput>('/planning/mrp-runs')
export const mrpSuggestionApi = createCrudApi<MrpSuggestion>('/planning/mrp-suggestions')

// 系统管理
export const userApi = createCrudApi<UserRow>('/identity/users')
export const roleApi = createCrudApi<Role>('/identity/roles')
export const dictionaryApi = createCrudApi<Dictionary>('/dictionaries')
export const dictionaryItemApi = createCrudApi<DictionaryItem>('/dictionary-items')
export const codeRuleApi = createCrudApi<CodeRule>('/code-rules')
export const attachmentApi = createCrudApi<Attachment>('/attachments')

export const auditLogApiBase = '/audit-logs'
export type { PermissionRow, AuditLog }
export { createCrudApi }