import { get, post } from '@/api/http'
import { createCrudApi, type QueryParams } from '@/api/crud'
import type {
  ApprovalInstance,
  ApprovalTemplate,
  Attachment,
  AuditLog,
  Bom,
  BomSnapshot,
  Company,
  DashboardPayload,
  Department,
  DispatchResult,
  DocumentLink,
  Employee,
  GoodsReceipt,
  InventoryDocument,
  MetaPayload,
  MrpDemandLine,
  MrpRun,
  MrpSuggestion,
  MrpSupplyLine,
  PurchaseOrder,
  PurchaseOrderInput,
  PurchaseRequisition,
  OutboxEvent,
  Routing,
  RoutingSnapshot,
  SalesOrder,
  SalesOrderChain,
  SalesReturn,
  SalesShipment,
  OutboxHealth,
  Paginated,
  QualityReleaseInput,
  Team,
  WarehouseTreeNode,
} from '@/types/models'

/** 组织与工厂相关动作（部门树、班组人员、工位归属等不适用通用 CRUD）。 */
export const factoryApi = {
  departmentTree: (params: QueryParams = {}) =>
    get<Department[]>('/factory/departments/tree/', { params }),
  teamMembers: (teamId: number, members: { employee_id: number; role_in_team?: string }[]) =>
    post<Team>(`/factory/teams/${teamId}/members/`, { members }),
  companies: (params: QueryParams = {}) => get<Paginated<Company>>('/factory/companies/', { params }),
  employees: (params: QueryParams = {}) => get<Paginated<Employee>>('/factory/employees/', { params }),
}

/** 仓储基础数据。阶段 1 只有仓库 / 库区 / 储位主数据，不含库存与单据。 */
export const wmsApi = {
  warehouseTree: () => get<WarehouseTreeNode[]>('/wms/locations/tree/'),
}

/**
 * 库存单据动作（阶段 2 统一库存服务）。
 *
 * 过账与冲销都会改变库存，因此后端要求 `Idempotency-Key`：同一键重复提交
 * 只产生一次库存变化，不会重复扣减。
 */
export const inventoryActionApi = {
  postDocument: (id: number, reason = '', idempotencyKey = '') =>
    post<InventoryDocument>(
      `/wms/inventory-documents/${id}/post/`,
      { reason },
      idempotencyKey ? { headers: { 'Idempotency-Key': idempotencyKey } } : undefined,
    ),
  reverseDocument: (id: number, reason: string) =>
    post<InventoryDocument>(`/wms/inventory-documents/${id}/reverse/`, { reason }),
  releaseQuality: (payload: QualityReleaseInput) =>
    post<InventoryDocument>('/wms/inventory-documents/release-quality/', payload),
}

/** 编码规则预览：不消耗流水号。 */
export const codeApi = {
  /** 预演编号：不消耗流水号，因此可以在界面上反复点击。 */
  preview: (code: string, sample = 1) =>
    post<{ code: string; preview: string }>('/code-rules/preview/', { code, sample }),
}

export const coreApi = {
  meta: () => get<MetaPayload>('/meta/'),
  auditLogs: (params: QueryParams = {}) => get<Paginated<AuditLog>>('/audit-logs/', { params }),
  attachmentList: (params: QueryParams = {}) => get<Paginated<Attachment>>('/attachments/', { params }),
  uploadAttachment: (form: FormData) =>
    post<Attachment>('/attachments/', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
}

export const analyticsApi = {
  dashboard: () => get<DashboardPayload>('/analytics/dashboard/'),
  masterdataFreshness: (days = 7) =>
    get<{ since: string; days: number; materials: number; styles: number; skus: number }>(
      '/analytics/masterdata-freshness/',
      { params: { days } },
    ),
}

export const workflowApi = {
  template: createCrudApi<ApprovalTemplate>('/workflow/templates'),
  instances: (params: QueryParams = {}) =>
    get<Paginated<ApprovalInstance>>('/workflow/instances/', { params }),
  todo: (params: QueryParams = {}) =>
    get<Paginated<ApprovalInstance>>('/workflow/instances/todo/', { params }),
  mine: (params: QueryParams = {}) =>
    get<Paginated<ApprovalInstance>>('/workflow/instances/mine/', { params }),
  participated: (params: QueryParams = {}) =>
    get<Paginated<ApprovalInstance>>('/workflow/instances/participated/', { params }),
  pendingSummary: () => get<{ todo_count: number }>('/workflow/instances/pending-summary/'),
  detail: (id: number) => get<ApprovalInstance>(`/workflow/instances/${id}/`),
  create: (payload: {
    title: string
    template_code?: string
    biz_type?: string
    biz_id?: string
    biz_no?: string
    summary?: string
    amount?: string | null
    department_id?: number | null
  }) => post<ApprovalInstance>('/workflow/instances/', payload),
  submit: (id: number, comment = '') =>
    post<ApprovalInstance>(`/workflow/instances/${id}/submit/`, { comment }),
  approve: (id: number, comment = '') =>
    post<ApprovalInstance>(`/workflow/instances/${id}/approve/`, { comment }),
  reject: (id: number, comment: string) =>
    post<ApprovalInstance>(`/workflow/instances/${id}/reject/`, { comment }),
  withdraw: (id: number, comment = '') =>
    post<ApprovalInstance>(`/workflow/instances/${id}/withdraw/`, { comment }),
  comment: (id: number, comment: string) =>
    post<{ id: number }>(`/workflow/instances/${id}/comment/`, { comment }),
}

/** 采购申请：提交审批、取消、按申请转采购订单。 */
export const requisitionActionApi = {
  submit: (id: number, comment = '') =>
    post<PurchaseRequisition>(`/procurement/requisitions/${id}/submit/`, { comment }),
  cancel: (id: number, reason: string) =>
    post<PurchaseRequisition>(`/procurement/requisitions/${id}/cancel/`, { reason }),
  convert: (id: number, payload: Partial<PurchaseOrderInput> & { supplier_id: number }) =>
    post<PurchaseOrder>(`/procurement/requisitions/${id}/convert/`, payload),
}

/** 采购订单：提交审批、取消、关闭（不再收货）。 */
export const purchaseOrderActionApi = {
  submit: (id: number, comment = '') =>
    post<PurchaseOrder>(`/procurement/orders/${id}/submit/`, { comment }),
  cancel: (id: number, reason: string) =>
    post<PurchaseOrder>(`/procurement/orders/${id}/cancel/`, { reason }),
  close: (id: number, reason = '') =>
    post<PurchaseOrder>(`/procurement/orders/${id}/close/`, { reason }),
}

/** 收货单：过账（记入待检库存）、来料检验判定、取消。 */
export const goodsReceiptActionApi = {
  /** 过账：幂等键由调用方生成，网络重试不会重复记账 */
  postReceipt: (id: number, idempotencyKey: string) =>
    post<GoodsReceipt>(
      `/procurement/receipts/${id}/post/`,
      {},
      { headers: { 'Idempotency-Key': idempotencyKey } },
    ),
  /** 来料检验判定：人工录入结论（未接入真实检测设备） */
  inspect: (id: number, result: string, remark: string, idempotencyKey?: string) =>
    post<GoodsReceipt>(
      `/procurement/receipts/${id}/inspect/`,
      { result, remark },
      idempotencyKey ? { headers: { 'Idempotency-Key': idempotencyKey } } : undefined,
    ),
  cancel: (id: number, reason: string) =>
    post<GoodsReceipt>(`/procurement/receipts/${id}/cancel/`, { reason }),
}

/**
 * 销售订单动作（阶段 2 增量）。
 *
 * 库存占用与发货出库都会改变库存，后端要求同时具备销售侧与库存侧权限；
 * 发货过账带 `Idempotency-Key`，网络重试不会重复扣减库存。
 */
export const salesOrderActionApi = {
  submit: (id: number, comment = '') =>
    post<SalesOrder>(`/sales/orders/${id}/submit/`, { comment }),
  cancel: (id: number, reason: string) =>
    post<SalesOrder>(`/sales/orders/${id}/cancel/`, { reason }),
  close: (id: number, reason = '') => post<SalesOrder>(`/sales/orders/${id}/close/`, { reason }),
  /** 库存占用：按未发货数量占用合格库存（幂等，重复点击不重复占用） */
  reserve: (id: number, reason = '') =>
    post<{ order_id: number; order_no: string; reserved: { reservation_id: number }[] }>(
      `/sales/orders/${id}/reserve/`,
      { reason },
    ),
  /** 释放尚未消耗的占用 */
  release: (id: number, reason: string) =>
    post<{ order_id: number; released: number[]; released_count: number }>(
      `/sales/orders/${id}/release/`,
      { reason },
    ),
  /** 订单到交付链路：关联单据与数量（任务书 12.1） */
  chain: (id: number) => get<SalesOrderChain>(`/sales/orders/${id}/chain/`),
}

/** 销售发货：出库过账（消耗本订单占用）、取消。 */
export const salesShipmentActionApi = {
  postShipment: (id: number, idempotencyKey: string) =>
    post<SalesShipment>(
      `/sales/shipments/${id}/post/`,
      {},
      { headers: { 'Idempotency-Key': idempotencyKey } },
    ),
  cancel: (id: number, reason: string) =>
    post<SalesShipment>(`/sales/shipments/${id}/cancel/`, { reason }),
}

/** 销售退货：收货（待检库存）、检验判定（合格回库 / 不合格）、取消。 */
export const salesReturnActionApi = {
  postReturn: (id: number, idempotencyKey: string) =>
    post<SalesReturn>(
      `/sales/returns/${id}/post/`,
      {},
      { headers: { 'Idempotency-Key': idempotencyKey } },
    ),
  /** 退货检验判定：人工录入结论（未接入真实检测设备） */
  inspect: (id: number, result: string, remark: string, idempotencyKey?: string) =>
    post<SalesReturn>(
      `/sales/returns/${id}/inspect/`,
      { result, remark },
      idempotencyKey ? { headers: { 'Idempotency-Key': idempotencyKey } } : undefined,
    ),
  cancel: (id: number, reason: string) =>
    post<SalesReturn>(`/sales/returns/${id}/cancel/`, { reason }),
}

/** 内部协同中心：业务事件、失败重试、单据关系。仅面向有权限的管理员。 */
export const integrationApi = {
  outbox: (params: QueryParams = {}) =>
    get<Paginated<OutboxEvent>>('/integration/outbox-events/', { params }),
  outboxDetail: (id: number) => get<OutboxEvent>(`/integration/outbox-events/${id}/`),
  outboxHealth: () => get<OutboxHealth>('/integration/outbox-events/health/'),
  retry: (id: number) => post<OutboxEvent>(`/integration/outbox-events/${id}/retry/`),
  dispatchNow: () => post<DispatchResult>('/integration/outbox-events/dispatch-now/'),
  documentLinks: (params: QueryParams = {}) =>
    get<Paginated<DocumentLink>>('/integration/document-links/', { params }),
}

/** 计划管理：BOM 与工艺路线的提交 / 派生新版本 / 作废 / 快照。 */
export const bomActionApi = {
  submit: (id: number, comment = '') => post<Bom>(`/planning/boms/${id}/submit/`, { comment }),
  /** 作废只改状态与启用标记，不物理删除；必须填写原因 */
  obsolete: (id: number, reason: string) => post<Bom>(`/planning/boms/${id}/obsolete/`, { reason }),
  /** 派生新草稿版本：已审核版本内容不可修改，变更只能新建版本 */
  newVersion: (id: number, effectiveFrom = '') =>
    post<Bom>(
      `/planning/boms/${id}/new-version/`,
      effectiveFrom ? { effective_from: effectiveFrom } : {},
    ),
  snapshot: (id: number) => get<BomSnapshot>(`/planning/boms/${id}/snapshot/`),
}

export const mrpActionApi = {
  run: (payload: Record<string, unknown>) => post<MrpRun>('/planning/mrp-runs/', payload),
  archive: (id: number, reason = '') =>
    post<MrpRun>(`/planning/mrp-runs/${id}/archive/`, { reason }),
  demands: (id: number, params: QueryParams = {}) =>
    get<Paginated<MrpDemandLine>>(`/planning/mrp-runs/${id}/demands/`, { params }),
  supplies: (id: number, params: QueryParams = {}) =>
    get<Paginated<MrpSupplyLine>>(`/planning/mrp-runs/${id}/supplies/`, { params }),
  suggestions: (id: number, params: QueryParams = {}) =>
    get<Paginated<MrpSuggestion>>(`/planning/mrp-runs/${id}/suggestions/`, { params }),
}

export const mrpSuggestionActionApi = {
  /** 采购建议 → 草稿采购申请（仍走采购审批）；生产建议由后端明确拒绝 */
  convert: (id: number, payload: { needed_date?: string; remark?: string } = {}) =>
    post<MrpSuggestion>(`/planning/mrp-suggestions/${id}/convert/`, payload),
  cancel: (id: number, reason: string) =>
    post<MrpSuggestion>(`/planning/mrp-suggestions/${id}/cancel/`, { reason }),
}

export const routingActionApi = {
  submit: (id: number, comment = '') => post<Routing>(`/planning/routings/${id}/submit/`, { comment }),
  obsolete: (id: number, reason: string) =>
    post<Routing>(`/planning/routings/${id}/obsolete/`, { reason }),
  newVersion: (id: number, effectiveFrom = '') =>
    post<Routing>(
      `/planning/routings/${id}/new-version/`,
      effectiveFrom ? { effective_from: effectiveFrom } : {},
    ),
  snapshot: (id: number) => get<RoutingSnapshot>(`/planning/routings/${id}/snapshot/`),
}
