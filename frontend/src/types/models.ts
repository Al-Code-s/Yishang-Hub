/** 与后端 DRF 序列化结果一一对应的类型。Decimal 一律为字符串，前端不得用 float 累加。 */

export interface Paginated<T> {
  count: number
  page: number
  page_size: number
  results: T[]
}

export interface MenuNode {
  id: number
  code: string
  name: string
  parent_id: number | null
  path: string
  component: string
  icon: string
  menu_type: 'directory' | 'page' | 'button'
  sort_order: number
  visible: boolean
  permission_code: string
  children: MenuNode[]
}

export interface RoleBrief {
  id: number
  code: string
  name: string
}

export interface CurrentUser {
  id: number
  username: string
  display_name: string
  phone: string | null
  email: string
  company_id: number | null
  company_name: string
  department_id: number | null
  department_name: string
  is_active: boolean
  is_staff: boolean
  must_change_password: boolean
  failed_login_count: number
  locked_until: string | null
  is_locked: boolean
  last_login: string | null
  last_login_ip: string | null
  roles: RoleBrief[] | string
  version: number
  remark: string
  date_joined: string
  updated_at: string
}

export interface SessionPayload {
  user: CurrentUser
  permissions: string[]
  menus: MenuNode[]
  unread_notifications: number
}

export interface MetaPayload {
  department_types: EnumOption[]
  workshop_types: EnumOption[]
  line_types: EnumOption[]
  employee_genders: EnumOption[]
  employment_types: EnumOption[]
  employee_statuses: EnumOption[]
  material_category_types: EnumOption[]
  uom_categories: EnumOption[]
  warehouse_types: EnumOption[]
  zone_types: EnumOption[]
  location_types: EnumOption[]
  identifier_types: EnumOption[]
  data_scope_types: EnumOption[]
  permission_types: EnumOption[]
  approver_types: EnumOption[]
  approval_statuses: EnumOption[]
  approval_step_statuses: EnumOption[]
  customer_categories: EnumOption[]
  customer_levels: EnumOption[]
  customer_statuses: EnumOption[]
  supplier_categories: EnumOption[]
  supplier_grades: EnumOption[]
  admission_statuses: EnumOption[]
  qualification_types: EnumOption[]
  quality_statuses: EnumOption[]
  inventory_document_types: EnumOption[]
  inventory_document_statuses: EnumOption[]
  inventory_transaction_types: EnumOption[]
  inventory_directions: EnumOption[]
  requisition_types: EnumOption[]
  requisition_statuses: EnumOption[]
  purchase_order_statuses: EnumOption[]
  receipt_statuses: EnumOption[]
  inspection_results: EnumOption[]
}

export interface EnumOption {
  /** 字符串用于枚举取值，数字用于主数据主键 */
  value: string | number
  label: string
}

/** 所有主数据通用的时间戳与乐观锁字段 */
export interface Stamped {
  version: number
  created_at: string
  updated_at: string
}

export interface Company extends Stamped {
  id: number
  code: string
  name: string
  short_name: string
  address: string
  contact_person: string
  contact_phone: string
  is_active: boolean
  remark: string
}

export interface Department extends Stamped {
  id: number
  company_id: number
  company_name: string
  parent_id: number | null
  parent_name: string
  full_path: string
  code: string
  name: string
  department_type: string
  sort_order: number
  is_active: boolean
  remark: string
}

export interface Factory extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  address: string
  manager_id: number | null
  manager_name: string
  is_active: boolean
  remark: string
}

export interface Workshop extends Stamped {
  id: number
  factory_id: number
  factory_name: string
  code: string
  name: string
  workshop_type: string
  sort_order: number
  is_active: boolean
  remark: string
}

export interface ProductionLine extends Stamped {
  id: number
  workshop_id: number
  workshop_name: string
  factory_id: number
  code: string
  name: string
  line_type: string
  daily_capacity: string | null
  is_active: boolean
  remark: string
}

export interface Station extends Stamped {
  id: number
  line_id: number
  line_name: string
  workshop_id: number
  code: string
  name: string
  station_type: string
  sort_order: number
  is_active: boolean
  remark: string
}

export interface Employee extends Stamped {
  id: number
  company_id: number
  company_name: string
  department_id: number | null
  department_name: string
  factory_id: number | null
  factory_name: string
  user_id: number | null
  username: string
  employee_no: string
  name: string
  gender: string
  phone: string
  email: string
  position: string
  employment_type: string
  hire_date: string | null
  leave_date: string | null
  status: string
  is_active: boolean
  remark: string
}

export interface Shift extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  start_time: string
  end_time: string
  cross_day: boolean
  break_minutes: number
  duration_hours: string
  is_active: boolean
  remark: string
}

export interface TeamMemberRow {
  id: number
  employee_id: number
  employee_no: string
  name: string
  role_in_team: string
  is_active: boolean
}

export interface Team extends Stamped {
  id: number
  code: string
  name: string
  workshop_id: number | null
  workshop_name: string
  leader_id: number | null
  leader_name: string
  shift_id: number | null
  shift_name: string
  members: TeamMemberRow[]
  is_active: boolean
  remark: string
}

export interface UoM extends Stamped {
  id: number
  code: string
  name: string
  category: string
  decimal_places: number
  is_active: boolean
  remark: string
}

export interface MaterialCategory extends Stamped {
  id: number
  parent_id: number | null
  parent_name: string
  code: string
  name: string
  category_type: string
  sort_order: number
  is_active: boolean
  remark: string
}

export interface FabricProfile {
  composition: string
  width_cm: string | null
  gram_weight: string | null
  default_color_no: string
  dye_lot_required: boolean
  shrinkage_rate: string | null
}

export interface Material extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  category_id: number
  category_name: string
  category_type: string
  spec: string
  base_uom_id: number
  base_uom_name: string
  purchase_uom_id: number | null
  purchase_uom_name: string
  purchase_factor: string | null
  sales_uom_id: number | null
  sales_uom_name: string
  sales_factor: string | null
  is_batch_managed: boolean
  is_roll_managed: boolean
  is_serial_managed: boolean
  safe_stock: string
  purchase_price: string | null
  reference_cost: string | null
  brand: string
  season: string
  year: string
  series: string
  image: string
  is_active: boolean
  remark: string
  fabric_profile: FabricProfile | null
}

export interface Color extends Stamped {
  id: number
  code: string
  name: string
  hex_code: string
  sort_order: number
  is_active: boolean
  remark: string
}

export interface Size extends Stamped {
  id: number
  code: string
  name: string
  sort_order: number
  is_active: boolean
  remark: string
}

export interface Style extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  category_id: number | null
  category_name: string
  brand: string
  season: string
  year: string
  series: string
  gender: string
  description: string
  image: string
  is_active: boolean
  remark: string
}

export interface Sku extends Stamped {
  id: number
  company_id: number
  company_name: string
  style_id: number
  style_code: string
  style_name: string
  color_id: number
  color_name: string
  size_id: number
  size_name: string
  material_id: number
  material_code: string
  material_name: string
  code: string
  name: string
  barcode: string
  safe_stock: string
  reference_cost: string | null
  is_active: boolean
  remark: string
}

export interface Warehouse extends Stamped {
  id: number
  company_id: number
  company_name: string
  factory_id: number | null
  factory_name: string
  department_id: number | null
  department_name: string
  code: string
  name: string
  warehouse_type: string
  address: string
  manager_name: string
  allow_negative_stock: boolean
  is_active: boolean
  remark: string
}

export interface Zone extends Stamped {
  id: number
  warehouse_id: number
  warehouse_name: string
  company_id: number
  code: string
  name: string
  zone_type: string
  allow_mixed_batch: boolean
  sort_order: number
  location_count: number
  is_active: boolean
  remark: string
}

export interface Location extends Stamped {
  id: number
  zone_id: number
  zone_name: string
  warehouse_id: number
  warehouse_code: string
  code: string
  name: string
  location_type: string
  row_no: string
  column_no: string
  level_no: string
  capacity: string | null
  is_locked: boolean
  is_active: boolean
  remark: string
}

export interface WarehouseTreeNode {
  id: number
  code: string
  name: string
  warehouse_type: string
  zones: {
    id: number
    code: string
    name: string
    zone_type: string
    locations: { id: number; code: string; name: string; is_locked: boolean; is_active: boolean }[]
  }[]
}

export interface PermissionRow {
  id: number
  code: string
  name: string
  module: string
  resource: string
  action: string
  permission_type: string
}

export interface PermissionGroup {
  module: string
  permissions: {
    code: string
    name: string
    resource: string
    action: string
    permission_type: string
  }[]
}

export interface ScopeGrant {
  id: number
  dimension: 'company' | 'factory' | 'department' | 'warehouse'
  object_id: number
}

export interface Role extends Stamped {
  id: number
  code: string
  name: string
  company_id: number | null
  company_name: string
  data_scope_type: string
  is_system: boolean
  is_active: boolean
  sort_order: number
  remark: string
  permission_codes: string[]
  menu_codes: string[]
  scope_grants: ScopeGrant[]
  user_count: number
}

export interface UserRow {
  id: number
  username: string
  display_name: string
  phone: string | null
  email: string
  company_id: number | null
  company_name: string
  department_id: number | null
  department_name: string
  is_active: boolean
  is_staff: boolean
  must_change_password: boolean
  failed_login_count: number
  locked_until: string | null
  is_locked: boolean
  last_login: string | null
  last_login_ip: string | null
  roles: RoleBrief[]
  version: number
  remark: string
  date_joined: string
  updated_at: string
}

export interface LoginAttempt {
  id: number
  username: string
  user_id: number | null
  ip_address: string | null
  successful: boolean
  failure_reason: string
  created_at: string
}

export interface Dictionary extends Stamped {
  id: number
  code: string
  name: string
  is_active: boolean
  remark: string
}

export interface DictionaryItem extends Stamped {
  id: number
  dictionary_id: number
  dictionary_code: string
  dictionary_name: string
  code: string
  label: string
  sort_order: number
  is_active: boolean
  extra: Record<string, unknown> | null
}

export interface CodeRule extends Stamped {
  id: number
  code: string
  name: string
  pattern: string
  reset_period: string
  is_active: boolean
  remark: string
}

export interface AuditLog {
  id: number
  request_id: string
  action: string
  action_display: string
  actor_id: number | null
  actor_name: string
  actor_username: string
  company_id: number | null
  object_type: string
  object_id: string
  object_repr: string
  changes: Record<string, unknown> | null
  reason: string
  approval_basis: string
  ip_address: string | null
  user_agent: string
  created_at: string
}

export interface Notification {
  id: number
  title: string
  body: string
  biz_type: string
  biz_id: string
  is_read: boolean
  read_at: string | null
  created_at: string
}

export interface Attachment {
  id: number
  original_name: string
  content_type: string
  size_bytes: number
  sha256: string
  biz_type: string
  biz_id: string
  uploaded_by_name: string
  download_url: string
  created_at: string
}

export interface ApprovalTemplateNode {
  id: number
  template_id: number
  seq: number
  name: string
  approver_type: 'role' | 'user'
  approver_role_id: number | null
  approver_role_name: string
  approver_user_id: number | null
  approver_user_name: string
  amount_min: string | null
  amount_max: string | null
  department_ids: number[] | null
  is_active: boolean
}

export interface ApprovalTemplate extends Stamped {
  id: number
  code: string
  name: string
  biz_type: string
  company_id: number | null
  company_name: string
  allow_self_approval: boolean
  version_no: number
  description: string
  is_active: boolean
  nodes: ApprovalTemplateNode[]
}

export interface ApprovalStep {
  id: number
  seq: number
  name: string
  approver_type: string
  approver_role_id: number | null
  approver_role_name: string
  assigned_user_id: number | null
  assigned_user_name: string
  candidate_user_ids: number[]
  status: string
  decided_by_id: number | null
  decided_by_name: string
  decided_at: string | null
  decision: string
  comment: string
}

export interface ApprovalLogRow {
  id: number
  seq: number
  action: string
  action_display: string
  actor_id: number | null
  actor_name: string
  comment: string
  created_at: string
}

export interface ApprovalInstance {
  id: number
  biz_no: string
  title: string
  summary: string
  biz_type: string
  biz_id: string
  template_id: number
  template_name: string
  template_version: number
  applicant_id: number
  applicant_name: string
  company_id: number | null
  department_id: number | null
  amount: string | null
  status: string
  status_display: string
  current_seq: number
  current_step_name: string
  steps: ApprovalStep[]
  logs: ApprovalLogRow[]
  can_approve: boolean
  can_withdraw: boolean
  submitted_at: string | null
  finished_at: string | null
  version: number
  created_at: string
  updated_at: string
}

export interface OutboxEvent {
  id: number
  event_id: string
  event_type: string
  aggregate_type: string
  aggregate_id: string
  payload: Record<string, unknown> | null
  status: string
  status_display: string
  attempts: number
  max_attempts: number
  next_retry_at: string | null
  last_error: string
  dedup_key: string | null
  created_at: string
  processed_at: string | null
}

export interface OutboxHealth {
  pending: number
  processing: number
  failed: number
  dead: number
  done: number
}

export interface DispatchResult {
  claimed: number
  done: number
  failed: number
}

export interface DocumentLink {
  id: number
  source_type: string
  source_id: string
  source_no: string
  target_type: string
  target_id: string
  target_no: string
  relation: string
  quantity: string | null
  remark: string
  created_at: string
}

export interface DashboardCard {
  key: string
  label: string
  value: number | null
  definition: {
    source: string
    time_field: string
    scope: string
    excludes_cancelled: boolean
    updated_at: string
    permission: string
  }
}

export interface DashboardPayload {
  generated_at: string
  business_timezone: string
  cards: DashboardCard[]
  approval: { todo: number | null; my_submitted_pending: number | null }
  recent_activity: {
    id: number
    action: string
    object_type: string
    object_repr: string
    actor_name: string
    created_at: string
  }[]
}
// ---------------------------------------------------------------------------
// 客户管理（CRM）—— 阶段 2 第一步：仅客户档案与联系人主数据
// ---------------------------------------------------------------------------

export interface Customer extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  short_name: string
  category: string
  level: string
  status: string
  credit_limit: string
  payment_terms: string
  tax_no: string
  address: string
  primary_contact_name: string
  primary_contact_phone: string
  salesman_id: number | null
  salesman_name: string
  tags: string[]
  is_active: boolean
  remark: string
}

export interface CustomerContact extends Stamped {
  id: number
  customer_id: number
  customer_name: string
  company_id: number | null
  name: string
  position: string
  phone: string
  email: string
  is_primary: boolean
  is_active: boolean
  remark: string
}

// ---------------------------------------------------------------------------
// 供应商管理（SRM）—— 阶段 2 第一步：供应商、联系人、资质有效期
// ---------------------------------------------------------------------------

export interface Supplier extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  short_name: string
  category: string
  grade: string
  admission_status: string
  payment_terms: string
  tax_no: string
  address: string
  primary_contact_name: string
  primary_contact_phone: string
  buyer_id: number | null
  buyer_name: string
  tags: string[]
  is_active: boolean
  remark: string
}

export interface SupplierContact extends Stamped {
  id: number
  supplier_id: number
  supplier_name: string
  company_id: number | null
  name: string
  position: string
  phone: string
  email: string
  is_primary: boolean
  is_active: boolean
  remark: string
}

export interface SupplierQualification extends Stamped {
  id: number
  supplier_id: number
  supplier_name: string
  company_id: number | null
  qualification_type: string
  certificate_no: string
  issued_by: string
  issued_date: string | null
  expiry_date: string | null
  /** 剩余有效天数；未登记到期日时为 null（前端不得当成 0 天） */
  days_to_expiry: number | null
  /** 未登记到期日时为 null，不能当成「未过期」 */
  is_expired: boolean | null
  is_active: boolean
  remark: string
}
// ---------------------------------------------------------------------------
// 仓储库存（统一库存服务）—— 阶段 2：余额、流水、库存单据
// ---------------------------------------------------------------------------

/** 库存质量状态。待检 / 不合格库存不能直接领用或销售。 */
export interface InventoryBalance extends Stamped {
  id: number
  company_id: number
  company_name: string
  material_id: number
  material_code: string
  material_name: string
  warehouse_id: number
  warehouse_code: string
  warehouse_name: string
  location_id: number | null
  location_code: string
  batch_no: string
  roll_no: string
  quality_status: string
  quality_status_display: string
  /** 实存量（Decimal 字符串） */
  on_hand: string
  /** 冻结量；与占用量互斥 */
  frozen: string
  /** 占用量；与冻结量互斥 */
  reserved: string
  /** 可用量 = 实存 - 冻结 - 占用，由后端计算 */
  available: string
}

export interface InventoryTransaction {
  id: number
  company_id: number
  document_id: number | null
  document_no: string
  document_line_id: number | null
  transaction_type: string
  transaction_type_display: string
  material_id: number
  material_code: string
  material_name: string
  warehouse_id: number
  warehouse_code: string
  location_id: number | null
  location_code: string
  batch_no: string
  roll_no: string
  quality_status: string
  quality_status_display: string
  /** 有符号数量：入库为正，出库为负 */
  quantity: string
  on_hand_before: string
  on_hand_after: string
  frozen_after: string
  reserved_after: string
  reason: string
  operator_id: number | null
  operator_name: string
  created_at: string
}

export interface InventoryDocumentLine extends Stamped {
  id: number
  document_id: number
  line_no: number
  material_id: number
  material_code: string
  material_name: string
  location_id: number | null
  location_code: string
  target_location_id: number | null
  target_location_code: string
  batch_no: string
  roll_no: string
  quality_status: string
  quality_status_display: string
  target_quality_status: string
  direction: string
  quantity: string
  remark: string
}

export interface InventoryDocument extends Stamped {
  id: number
  company_id: number
  document_no: string
  document_type: string
  document_type_display: string
  status: string
  status_display: string
  warehouse_id: number
  warehouse_name: string
  warehouse_code: string
  biz_type: string
  biz_id: string
  biz_no: string
  posted_at: string | null
  posted_by_id: number | null
  posted_by_name: string
  reversed_at: string | null
  reversed_by_id: number | null
  reversed_by_name: string
  reverse_reason: string
  remark: string
  lines: InventoryDocumentLine[]
}

export interface InventoryDocumentLineInput {
  material_id: number
  location_id?: number | null
  target_location_id?: number | null
  batch_no?: string
  roll_no?: string
  quality_status?: string
  target_quality_status?: string
  direction?: string
  quantity: string
  remark?: string
}

export interface InventoryDocumentInput {
  document_type: string
  warehouse_id: number
  biz_type?: string
  biz_id?: string
  biz_no?: string
  remark?: string
  lines: InventoryDocumentLineInput[]
}

export interface QualityReleaseInput {
  /** 可省略：后端按仓库归属推导公司；传入时必须与仓库所属公司一致 */
  company_id?: number
  warehouse_id: number
  material_id: number
  quantity: string
  location_id?: number | null
  batch_no?: string
  roll_no?: string
  from_status?: string
  to_status?: string
  biz_type?: string
  biz_id?: string
  biz_no?: string
  reason?: string
}


// ---------------------------------------------------------------------------
// 采购（阶段 2 增量：采购申请 / 采购订单 / 到货收货 / 来料检验）
// 金额与已收数量均为后端计算，前端只读展示，不参与提交。
// ---------------------------------------------------------------------------

export interface PurchaseRequisitionLine extends Stamped {
  id: number
  requisition_id: number
  line_no: number
  material_id: number
  material_code: string
  material_name: string
  quantity: string
  uom_id: number | null
  uom_name: string
  needed_date: string | null
  suggested_supplier_id: number | null
  suggested_supplier_name: string
  /** 已转订单数量，由服务层累加 */
  ordered_quantity: string
  remark: string
}

export interface PurchaseRequisition extends Stamped {
  id: number
  company_id: number
  company_name: string
  requisition_no: string
  request_type: string
  request_type_display: string
  status: string
  status_display: string
  applicant_id: number | null
  applicant_name: string
  department_id: number | null
  factory_id: number | null
  needed_date: string | null
  purpose: string
  approval_instance_id: number | null
  approved_at: string | null
  remark: string
  lines: PurchaseRequisitionLine[]
}

export interface RequisitionLineInput {
  material_id: number
  quantity: string
  uom_id?: number | null
  needed_date?: string | null
  suggested_supplier_id?: number | null
  remark?: string
}

export interface RequisitionInput {
  requisition_no?: string
  request_type?: string
  needed_date?: string | null
  department_id?: number | null
  factory_id?: number | null
  purpose?: string
  remark?: string
  lines: RequisitionLineInput[]
}

export interface PurchaseOrderLine extends Stamped {
  id: number
  order_id: number
  line_no: number
  material_id: number
  material_code: string
  material_name: string
  quantity: string
  received_quantity: string
  remaining_quantity: string
  price: string
  amount: string
  uom_id: number | null
  uom_name: string
  expected_date: string | null
  warehouse_id: number | null
  source_line_id: number | null
  remark: string
}

export interface PurchaseOrder extends Stamped {
  id: number
  company_id: number
  company_name: string
  order_no: string
  supplier_id: number
  supplier_name: string
  status: string
  status_display: string
  source_requisition_id: number | null
  source_requisition_no: string
  buyer_id: number | null
  buyer_name: string
  order_date: string | null
  expected_date: string | null
  warehouse_id: number | null
  warehouse_name: string
  currency: string
  /** 税率按百分比记录（0~100） */
  tax_rate: string
  payment_terms: string
  total_amount: string
  tax_amount: string
  amount_with_tax: string
  supplier_exception: boolean
  supplier_exception_reason: string
  approval_instance_id: number | null
  approved_at: string | null
  closed_at: string | null
  remark: string
  lines: PurchaseOrderLine[]
}

export interface OrderLineInput {
  material_id: number
  quantity: string
  price?: string
  uom_id?: number | null
  expected_date?: string | null
  warehouse_id?: number | null
  source_line_id?: number | null
  remark?: string
}

export interface PurchaseOrderInput {
  order_no?: string
  supplier_id: number
  order_date?: string | null
  expected_date?: string | null
  warehouse_id?: number | null
  buyer_id?: number | null
  source_requisition_id?: number | null
  currency?: string
  tax_rate?: string
  payment_terms?: string
  supplier_exception_reason?: string
  remark?: string
  lines: OrderLineInput[]
}

export interface GoodsReceiptLine extends Stamped {
  id: number
  receipt_id: number
  line_no: number
  order_line_id: number
  order_line_no: number
  material_id: number
  material_code: string
  material_name: string
  quantity: string
  location_id: number | null
  location_name: string
  batch_no: string
  roll_no: string
  remark: string
}

export interface GoodsReceipt extends Stamped {
  id: number
  company_id: number
  company_name: string
  receipt_no: string
  purchase_order_id: number
  order_no: string
  supplier_id: number
  supplier_name: string
  status: string
  status_display: string
  warehouse_id: number
  warehouse_name: string
  received_at: string | null
  received_by_name: string
  supplier_delivery_no: string
  inspection_result: string
  inspection_result_display: string
  inspected_at: string | null
  inspected_by_name: string
  inspection_remark: string
  receipt_document_id: number | null
  quality_document_id: number | null
  remark: string
  lines: GoodsReceiptLine[]
}

export interface ReceiptLineInput {
  order_line_id: number
  quantity: string
  location_id?: number | null
  batch_no?: string
  roll_no?: string
  remark?: string
}

export interface GoodsReceiptInput {
  receipt_no?: string
  purchase_order_id: number
  warehouse_id?: number | null
  supplier_delivery_no?: string
  remark?: string
  lines: ReceiptLineInput[]
}
