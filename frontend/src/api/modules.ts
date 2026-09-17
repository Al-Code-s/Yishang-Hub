import { get, post } from '@/api/http'
import { createCrudApi, type QueryParams } from '@/api/crud'
import type {
  ApprovalInstance,
  ApprovalTemplate,
  Attachment,
  AuditLog,
  Company,
  DashboardPayload,
  Department,
  DispatchResult,
  DocumentLink,
  Employee,
  GoodsReceipt,
  InventoryDocument,
  MetaPayload,
  PurchaseOrder,
  PurchaseOrderInput,
  PurchaseRequisition,
  OutboxEvent,
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