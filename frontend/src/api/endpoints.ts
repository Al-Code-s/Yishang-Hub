import { createCrudApi } from '@/api/crud'
import type {
  AbnormalRecord,
  AbnormalTask,
  AbnormalType,
  AccidentRecord,
  Attachment,
  AuditLog,
  AutomationDevice,
  Bom,
  BomInput,
  CodeRule,
  Color,
  Company,
  ComplianceCheck,
  Customer,
  CustomerComplaint,
  CustomerContact,
  Department,
  Dictionary,
  DictionaryItem,
  EhsOperationLog,
  EmergencyPlan,
  Employee,
  EnergyAlarm,
  EnergyArea,
  EnergyMeter,
  EnergyPrice,
  EnergyRunRecord,
  EnergyThreshold,
  EnvironmentMonitor,
  Equipment,
  EquipmentPart,
  EquipmentType,
  Factory,
  FaultReport,
  FireDrill,
  FireFacility,
  GoodsReceipt,
  GoodsReceiptInput,
  HazardRecord,
  InventoryBalance,
  InventoryDocument,
  InventoryDocumentInput,
  InspectionItem,
  InspectionRecord,
  InspectionTask,
  InventoryTransaction,
  IoTConnection,
  IoTGateway,
  IoTMessage,
  IoTPoint,
  IoTReading,
  Location,
  LogisticsOperationLog,
  LogisticsTask,
  Material,
  MaintenanceItem,
  MaintenancePlan,
  MaintenanceRecord,
  MaintenanceTask,
  MaterialCategory,
  MeterReading,
  MrpRun,
  MrpRunInput,
  MrpSuggestion,
  PermissionRow,
  ProductReview,
  ProductionLine,
  ProductionOrder,
  ProductionReport,
  PurchaseOrder,
  PurchaseOrderInput,
  PurchaseRequisition,
  QualityAlert,
  QualityInspectionItem,
  QualityInspectionOrder,
  QualityIssue,
  RepairRecord,
  RepairTask,
  RequisitionInput,
  ReturnInput,
  Role,
  Routing,
  RoutingInput,
  SafetyCheck,
  SafetyRegulation,
  SafetyTraining,
  SalesOrder,
  SalesOrderInput,
  SalesReturn,
  SalesShipment,
  ShipmentInput,
  Shift,
  Size,
  Sku,
  SparePart,
  SparePartStockRow,
  SpecialEquipmentInspection,
  Station,
  Style,
  Supplier,
  SupplierContact,
  SupplierEvaluation,
  SupplierEvaluationWeight,
  SupplierQualification,
  Team,
  UoM,
  UserRow,
  Warehouse,
  WasteRecord,
  WorkPermit,
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
// 客户管理（投诉与评价：状态只能经 accept / resolve / close / reply 动作推进）
export const customerComplaintApi = createCrudApi<CustomerComplaint>('/crm/complaints')
export const productReviewApi = createCrudApi<ProductReview>('/crm/product-reviews')

// 设备数采与监控（只读采集：接入配置 + 采集数据；读数与报文只读）
export const iotConnectionApi = createCrudApi<IoTConnection>('/iot/connections')
export const iotGatewayApi = createCrudApi<IoTGateway>('/iot/gateways')
export const iotPointApi = createCrudApi<IoTPoint>('/iot/points')
export const iotReadingApi = createCrudApi<IoTReading>('/iot/readings')
export const iotMessageApi = createCrudApi<IoTMessage>('/iot/messages')

// 供应商管理（阶段 2 第一步：供应商、联系人、资质有效期）
export const supplierApi = createCrudApi<Supplier>('/srm/suppliers')
export const supplierContactApi = createCrudApi<SupplierContact>('/srm/supplier-contacts')
export const supplierQualificationApi = createCrudApi<SupplierQualification>(
  '/srm/supplier-qualifications',
)
// 供应商管理（五维量化评价：权重配置只增不改，评价总分只能由后端算）
export const supplierEvaluationWeightApi = createCrudApi<SupplierEvaluationWeight>(
  '/srm/supplier-evaluation-weights',
)
export const supplierEvaluationApi = createCrudApi<SupplierEvaluation>(
  '/srm/supplier-evaluations',
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

// 质量管理（检验项目、检验单与结果判定、质量报警、质量问题知识库）
export const qualityInspectionItemApi = createCrudApi<QualityInspectionItem>('/qms/inspection-items')
export const qualityInspectionApi = createCrudApi<QualityInspectionOrder>('/qms/inspections')
export const qualityAlertApi = createCrudApi<QualityAlert>('/qms/alerts')
export const qualityIssueApi = createCrudApi<QualityIssue>('/qms/issues')

// 设备管理（阶段 4 第一步：设备类型、设备台账、零部件、备品备件）
export const equipmentTypeApi = createCrudApi<EquipmentType>('/equipment/equipment-types')
export const equipmentApi = createCrudApi<Equipment>('/equipment/equipments')
export const equipmentPartApi = createCrudApi<EquipmentPart>('/equipment/equipment-parts')
export const sparePartApi = createCrudApi<SparePart>('/equipment/spare-parts')

// 设备管理（阶段 4 第二步：保养 / 维修 / 点巡检 / 异常上报）
export const maintenanceItemApi = createCrudApi<MaintenanceItem>('/equipment/maintenance-items')
export const maintenancePlanApi = createCrudApi<MaintenancePlan>('/equipment/maintenance-plans')
export const maintenanceTaskApi = createCrudApi<MaintenanceTask>('/equipment/maintenance-tasks')
export const maintenanceRecordApi = createCrudApi<MaintenanceRecord>(
  '/equipment/maintenance-records',
)
export const faultReportApi = createCrudApi<FaultReport>('/equipment/fault-reports')
export const repairTaskApi = createCrudApi<RepairTask>('/equipment/repair-tasks')
export const repairRecordApi = createCrudApi<RepairRecord>('/equipment/repair-records')
export const inspectionItemApi = createCrudApi<InspectionItem>('/equipment/inspection-items')
export const inspectionTaskApi = createCrudApi<InspectionTask>('/equipment/inspection-tasks')
export const inspectionRecordApi = createCrudApi<InspectionRecord>('/equipment/inspection-records')
export const abnormalTypeApi = createCrudApi<AbnormalType>('/equipment/abnormal-types')
export const abnormalTaskApi = createCrudApi<AbnormalTask>('/equipment/abnormal-tasks')
export const abnormalRecordApi = createCrudApi<AbnormalRecord>('/equipment/abnormal-records')
// 只读汇总：备件现存量。写入只能经仓储的库存服务，因此不提供增删改。
export const sparePartStockApi = createCrudApi<SparePartStockRow>('/equipment/spare-part-stock')

// 能源管理（基础管理：区域、计量设备、价格、阈值）
export const energyAreaApi = createCrudApi<EnergyArea>('/ems/areas')
export const energyMeterApi = createCrudApi<EnergyMeter>('/ems/meters')
export const energyPriceApi = createCrudApi<EnergyPrice>('/ems/prices')
export const energyThresholdApi = createCrudApi<EnergyThreshold>('/ems/thresholds')

// 能源管理（运行数据：抄表读数只读 + 录入动作，运行记录状态机，报警处理）
export const meterReadingApi = createCrudApi<MeterReading>('/ems/readings')
export const energyRunRecordApi = createCrudApi<EnergyRunRecord>('/ems/run-records')
export const energyAlarmApi = createCrudApi<EnergyAlarm>('/ems/alarms')

// 生产物流管理（自动化设备台账、任务状态机、操作日志）
export const automationDeviceApi = createCrudApi<AutomationDevice>('/logistics/automation-devices')
export const logisticsTaskApi = createCrudApi<LogisticsTask>('/logistics/tasks')
export const logisticsOperationLogApi = createCrudApi<LogisticsOperationLog>(
  '/logistics/operation-logs',
)

// 安全环保管理（安全管理）
export const safetyRegulationApi = createCrudApi<SafetyRegulation>('/ehs/regulations')
export const safetyTrainingApi = createCrudApi<SafetyTraining>('/ehs/trainings')
export const hazardRecordApi = createCrudApi<HazardRecord>('/ehs/hazards')
export const emergencyPlanApi = createCrudApi<EmergencyPlan>('/ehs/emergency-plans')
export const accidentRecordApi = createCrudApi<AccidentRecord>('/ehs/accidents')

// 安全环保管理（环保管理）
export const environmentMonitorApi = createCrudApi<EnvironmentMonitor>('/ehs/env-monitors')
export const wasteRecordApi = createCrudApi<WasteRecord>('/ehs/wastes')
export const complianceCheckApi = createCrudApi<ComplianceCheck>('/ehs/compliance-checks')

// 安全环保管理（消防管理）
export const fireFacilityApi = createCrudApi<FireFacility>('/ehs/fire-facilities')
export const fireDrillApi = createCrudApi<FireDrill>('/ehs/fire-drills')
export const workPermitApi = createCrudApi<WorkPermit>('/ehs/work-permits')

// 安全环保管理（设备设施安全 + 操作日志）
export const safetyCheckApi = createCrudApi<SafetyCheck>('/ehs/safety-checks')
export const specialEquipmentInspectionApi = createCrudApi<SpecialEquipmentInspection>(
  '/ehs/special-equipment-inspections',
)
export const ehsOperationLogApi = createCrudApi<EhsOperationLog>('/ehs/operation-logs')

// 生产执行（MES：工单状态机、用料、工序、报工台账）
export const productionOrderApi = createCrudApi<ProductionOrder>('/mes/orders')
export const productionReportApi = createCrudApi<ProductionReport>('/mes/reports')

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
