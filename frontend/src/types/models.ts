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
  complaint_types: EnumOption[]
  complaint_levels: EnumOption[]
  complaint_statuses: EnumOption[]
  complaint_sources: EnumOption[]
  product_review_statuses: EnumOption[]
  iot_protocols: EnumOption[]
  iot_gateway_types: EnumOption[]
  iot_gateway_statuses: EnumOption[]
  iot_point_quantities: EnumOption[]
  iot_message_statuses: EnumOption[]
  iot_reading_qualities: EnumOption[]
  iot_reading_sources: EnumOption[]
  supplier_categories: EnumOption[]
  supplier_grades: EnumOption[]
  admission_statuses: EnumOption[]
  qualification_types: EnumOption[]
  supplier_evaluation_statuses: EnumOption[]
  supplier_evaluation_dimensions: EnumOption[]
  missing_dimension_policies: EnumOption[]
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
  sales_order_statuses: EnumOption[]
  sales_order_priorities: EnumOption[]
  shipment_statuses: EnumOption[]
  return_statuses: EnumOption[]
  return_dispositions: EnumOption[]
  reservation_statuses: EnumOption[]
  bom_statuses: EnumOption[]
  routing_statuses: EnumOption[]
  bom_line_types: EnumOption[]
  mrp_run_statuses: EnumOption[]
  mrp_buckets: EnumOption[]
  mrp_demand_sources: EnumOption[]
  mrp_supply_sources: EnumOption[]
  mrp_suggestion_types: EnumOption[]
  mrp_suggestion_statuses: EnumOption[]
  production_order_statuses: EnumOption[]
  production_source_types: EnumOption[]
  production_material_sources: EnumOption[]
  production_step_statuses: EnumOption[]
  production_report_types: EnumOption[]
  equipment_categories: EnumOption[]
  equipment_statuses: EnumOption[]
  part_types: EnumOption[]
  task_statuses: EnumOption[]
  maintenance_categories: EnumOption[]
  inspection_methods: EnumOption[]
  inspection_task_types: EnumOption[]
  equipment_inspection_results: EnumOption[]
  fault_levels: EnumOption[]
  fault_report_statuses: EnumOption[]
  abnormal_sources: EnumOption[]
  abnormal_statuses: EnumOption[]
  quality_inspection_types: EnumOption[]
  quality_inspection_statuses: EnumOption[]
  quality_judgements: EnumOption[]
  inspection_categories: EnumOption[]
  inspection_value_types: EnumOption[]
  quality_alert_levels: EnumOption[]
  quality_alert_statuses: EnumOption[]
  quality_issue_categories: EnumOption[]
  quality_issue_statuses: EnumOption[]
  energy_media: EnumOption[]
  tariff_periods: EnumOption[]
  meter_statuses: EnumOption[]
  reading_sources: EnumOption[]
  run_statuses: EnumOption[]
  alarm_types: EnumOption[]
  alarm_levels: EnumOption[]
  alarm_statuses: EnumOption[]
  alarm_sources: EnumOption[]
  automation_device_types: EnumOption[]
  automation_device_statuses: EnumOption[]
  logistics_task_types: EnumOption[]
  logistics_task_priorities: EnumOption[]
  logistics_task_statuses: EnumOption[]
  logistics_log_actions: EnumOption[]
  ehs_domains: EnumOption[]
  regulation_statuses: EnumOption[]
  regulation_categories: EnumOption[]
  training_types: EnumOption[]
  training_statuses: EnumOption[]
  hazard_levels: EnumOption[]
  hazard_sources: EnumOption[]
  hazard_statuses: EnumOption[]
  accident_categories: EnumOption[]
  accident_levels: EnumOption[]
  accident_statuses: EnumOption[]
  response_levels: EnumOption[]
  emergency_plan_types: EnumOption[]
  environment_media: EnumOption[]
  waste_types: EnumOption[]
  waste_statuses: EnumOption[]
  compliance_results: EnumOption[]
  compliance_statuses: EnumOption[]
  compliance_check_types: EnumOption[]
  fire_facility_types: EnumOption[]
  fire_facility_statuses: EnumOption[]
  fire_drill_types: EnumOption[]
  permit_types: EnumOption[]
  permit_risk_levels: EnumOption[]
  permit_statuses: EnumOption[]
  safety_check_types: EnumOption[]
  safety_check_statuses: EnumOption[]
  special_equipment_results: EnumOption[]
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
  /** 模块中文名（后端 MODULE_LABELS）；未登记时为空串 */
  module_name: string
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
  /** object_type 的中文名（后端按模型 verbose_name 生成，供界面直接展示） */
  object_type_display: string
  object_id: string
  object_repr: string
  changes: Record<string, unknown> | null
  /** 变更摘要的中文条目：{ 字段, 中文名, 变更前, 变更后 } */
  changes_display: { field: string; label: string; before: string; after: string }[]
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
  aggregate_type_display: string
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

/** 工作台「最近操作记录」的一条：都带中文展示名，界面不做翻译。 */
export interface DashboardActivity {
  id: number
  action: string
  action_display: string
  object_type: string
  object_type_display: string
  object_repr: string
  actor_name: string
  created_at: string
}

export interface DashboardPayload {
  generated_at: string
  business_timezone: string
  cards: DashboardCard[]
  approval: { todo: number | null; my_submitted_pending: number | null }
  recent_activity: DashboardActivity[]
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

/** 客户投诉：待受理 → 处理中 → 已解决 → 已关闭（状态由后端动作接口推进）。 */
export interface CustomerComplaint extends Stamped {
  id: number
  company_id: number
  company_name: string
  complaint_no: string
  customer_id: number
  customer_name: string
  complaint_type: string
  complaint_type_display?: string
  level: string
  level_display?: string
  status: string
  status_display?: string
  source: string
  source_display?: string
  title: string
  content: string
  complained_at: string
  reporter: string
  reporter_phone: string
  related_no: string
  receiver_id: number | null
  receiver_name: string
  handler_id: number | null
  handler_name: string
  accepted_at: string | null
  resolved_at: string | null
  closed_at: string | null
  handle_measure: string
  /** 0 表示客户尚未回访评价；1~5 为回访评分 */
  satisfaction: number
  remark: string
}

/** 产品评价：待回复 → 已回复 → 已关闭。 */
export interface ProductReview extends Stamped {
  id: number
  company_id: number
  company_name: string
  review_no: string
  customer_id: number
  customer_name: string
  sku_id: number | null
  sku_code: string
  product_desc: string
  /** 1~5 分，由客户给出 */
  score: number
  status: string
  status_display?: string
  reviewer_name: string
  reviewed_at: string
  content: string
  reply: string
  replier_id: number | null
  replier_name: string
  replied_at: string | null
  closed_at: string | null
  remark: string
}

/** 统计分布中的一档：value 为枚举值，label 为中文名，total 为条数 */
export interface StatisticsSlice {
  value: string | number
  label: string
  total: number
}

/** 投诉统计（后端按明细实时聚合，不落汇总表） */
export interface ComplaintStatistics {
  since: string | null
  until: string | null
  total: number
  open_total: number
  closed_total: number
  /** 尚未回访的条数：不计入平均满意度 */
  unrated_total: number
  /** 一例都没回访时为 null，不会用 0 分糊弄 */
  avg_satisfaction: string | null
  by_status: StatisticsSlice[]
  by_type: StatisticsSlice[]
  by_level: StatisticsSlice[]
  by_source: StatisticsSlice[]
}

/** 产品评价统计：好评指 4 分及以上 */
export interface ProductReviewStatistics {
  since: string | null
  until: string | null
  total: number
  pending_total: number
  closed_total: number
  avg_score: string | null
  good_total: number
  good_rate: string
  by_status: StatisticsSlice[]
  /** 固定列出 1~5 分五档 */
  by_score: StatisticsSlice[]
}

// ---------------------------------------------------------------------------
// 设备数采与监控（IoT）—— 只读采集：连接、设备、测点、读数、采集日志
// ---------------------------------------------------------------------------

export interface IoTConnection extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  protocol: string
  protocol_display?: string
  endpoint: string
  /** 凭证说明或引用位置；平台不在业务表里保存明文密钥 */
  credential_ref: string
  timeout_seconds: number
  batch_limit: number
  rate_limit_per_minute: number
  is_enabled: boolean
  is_simulated: boolean
  is_active: boolean
  remark: string
}

export interface IoTGateway extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  gateway_type: string
  gateway_type_display?: string
  connection_id: number | null
  connection_name: string
  equipment_id: number | null
  equipment_name: string
  factory_id: number | null
  factory_name: string
  workshop_id: number | null
  workshop_name: string
  production_line_id: number | null
  production_line_name: string
  location: string
  status: string
  status_display?: string
  last_seen_at: string | null
  offline_minutes: number
  /** 已下发令牌的前缀；明文令牌只在生成时返回一次 */
  token_prefix: string
  token_rotated_at: string | null
  has_token: boolean
  is_simulated: boolean
  is_active: boolean
  remark: string
}

export interface IoTPoint extends Stamped {
  id: number
  company_id: number | null
  company_name: string
  gateway_id: number
  gateway_code: string
  gateway_name: string
  code: string
  name: string
  quantity: string
  quantity_display?: string
  unit: string
  range_min: string | null
  range_max: string | null
  precision: number
  is_cumulative: boolean
  upper_limit: string | null
  lower_limit: string | null
  alarm_enabled: boolean
  meter_id: number | null
  meter_code: string
  is_active: boolean
  remark: string
}

export interface IoTMessage extends Stamped {
  id: number
  company_id: number
  company_name: string
  gateway_id: number
  gateway_code: string
  gateway_name: string
  message_id: string
  received_at: string
  device_time: string | null
  source_ip: string | null
  point_count: number
  status: string
  status_display?: string
  error_message: string
  is_simulated: boolean
  payload: Record<string, unknown>
}

export interface IoTReading extends Stamped {
  id: number
  company_id: number
  company_name: string
  gateway_id: number
  gateway_code: string
  point_id: number
  point_code: string
  point_name: string
  quantity: string
  device_time: string
  received_at: string
  value: string
  unit: string
  quality: string
  quality_display?: string
  source: string
  source_display?: string
  is_simulated: boolean
}

export interface IoTMonitorPoint {
  point_id: number
  code: string
  name: string
  quantity: string
  unit: string
  lower_limit: string | null
  upper_limit: string | null
  latest_value: string | null
  latest_device_time: string | null
  is_simulated: boolean
  is_over_limit: boolean
}

export interface IoTMonitorGateway {
  id: number
  code: string
  name: string
  gateway_type: string
  status: string
  location: string
  connection_name: string
  is_simulated: boolean
  offline_minutes: number
  last_seen_at: string | null
  points: IoTMonitorPoint[]
}

export interface IoTMonitorSummary {
  gateway_total: number
  online: number
  offline: number
  unknown: number
  simulated: number
  readings_24h: number
  failed_messages_24h: number
  duplicated_messages_24h: number
  open_alarms: number
}

export interface IoTMonitorPayload {
  generated_at: string
  summary: IoTMonitorSummary
  message_stats: { status: string; total: number }[]
  gateways: IoTMonitorGateway[]
  recent_readings: {
    id: number
    gateway_code: string
    point_code: string
    point_name: string
    value: string
    unit: string
    device_time: string
    is_simulated: boolean
  }[]
}

/** 采集统计的「测点 × 时间桶」明细行 */
export interface IoTStatisticsRow {
  bucket: string
  granularity: string
  point_id: number
  point_code: string
  point_name: string
  quantity: string
  unit: string
  gateway_code: string
  lower_limit: string | null
  upper_limit: string | null
  sample_count: number
  simulated_count: number
  value_sum: string
  value_min: string | null
  value_max: string | null
  value_avg: string
  is_over_limit: boolean
  /** 整桶都是模拟数据时为 true；混有真实读数时保持 false */
  is_simulated: boolean
}

/** 采集统计的桶级趋势 */
export interface IoTStatisticsBucket {
  bucket: string
  sample_count: number
  simulated_count: number
  value_sum: string
}

export interface IoTStatisticsPayload {
  granularity: string
  since: string
  until: string
  row_limit: number
  /** 明细行超过上限被截断时为 true，界面要提示「只看最近 N 条」 */
  truncated: boolean
  rows: IoTStatisticsRow[]
  buckets: IoTStatisticsBucket[]
  totals: {
    sample_count: number
    simulated_count: number
    point_count: number
    gateway_count: number
    value_sum: string | null
  }
}

export interface IoTTokenRotateResult {
  gateway_id: number
  gateway_code: string
  token_prefix: string
  token: string
  token_rotated_at: string
  note: string
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
// 供应商五维量化评价（权重配置 + 评价单）
// ---------------------------------------------------------------------------

/** 五维评价权重配置。只增不改：调整权重会派生新版本，旧版本保留。 */
export interface SupplierEvaluationWeight extends Stamped {
  id: number
  company_id: number
  company_name: string
  version_no: number
  quality_weight: string
  technology_weight: string
  response_weight: string
  delivery_weight: string
  cost_weight: string
  /** 后端计算的合计，必须为 100.00 */
  total_weight: string
  is_active: boolean
  remark: string
}

/** 评价明细：一个维度一行，保存原始观测值与计算过程。 */
export interface SupplierEvaluationLine extends Stamped {
  id: number
  evaluation_id: number
  dimension: string
  /** 留空 = 该维度没有数据（会被标记缺失，不是 0 分） */
  raw_score: string | null
  raw_observation: Record<string, unknown>
  weight: string
  effective_weight: string
  weighted_score: string | null
  is_missing: boolean
  remark: string
}

export interface SupplierEvaluation extends Stamped {
  id: number
  company_id: number
  company_name: string
  evaluation_no: string
  supplier_id: number
  supplier_name: string
  supplier_code: string
  weight_config_id: number
  weight_config_version: number | null
  /** 评分时的权重快照：历史评价不因后来改权重而变化 */
  weight_snapshot: Record<string, string>
  missing_dimension_policy: string
  period_start: string | null
  period_end: string | null
  evaluated_by_id: number | null
  evaluated_by_name: string
  evaluated_at: string | null
  status: string
  total_score: string | null
  effective_weight_total: string | null
  /** 缺数据且不重分配权重时为空串：不完整口径不贴等级 */
  grade: string
  missing_dimensions: string[]
  is_editable: boolean
  lines: SupplierEvaluationLine[]
  is_active: boolean
  remark: string
}

/** 某个维度的评分分布（缺失维度单独计数，与 0 分不是一回事） */
export interface SupplierEvaluationDimensionRow {
  value: string
  label: string
  scored_total: number
  missing_total: number
  /** 没有任何评分样本时为 null */
  avg_score: string | null
}

export interface SupplierEvaluationStatistics {
  since: string | null
  until: string | null
  total: number
  draft_total: number
  effective_total: number
  archived_total: number
  scored_total: number
  /** 缺数据、口径不完整的条数：不参与平均分 */
  ungraded_total: number
  supplier_total: number
  avg_total_score: string | null
  missing_policy_total: number
  line_total: number
  line_missing_total: number
  missing_rate: string
  by_grade: StatisticsSlice[]
  by_status: StatisticsSlice[]
  by_policy: StatisticsSlice[]
  by_dimension: SupplierEvaluationDimensionRow[]
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

export interface SalesOrderLine extends Stamped {
  id: number
  order_id: number
  line_no: number
  material_id: number
  material_code: string
  material_name: string
  sku_id: number | null
  sku_code: string
  color_name: string
  size_name: string
  quantity: string
  shipped_quantity: string
  returned_quantity: string
  remaining_quantity: string
  returnable_quantity: string
  price: string
  amount: string
  uom_id: number | null
  uom_name: string
  expected_date: string | null
  remark: string
}

export interface SalesOrder extends Stamped {
  id: number
  company_id: number
  company_name: string
  order_no: string
  customer_id: number
  customer_code: string
  customer_name: string
  status: string
  status_display: string
  salesman_id: number | null
  salesman_name: string
  order_date: string | null
  expected_date: string | null
  priority: string
  priority_display: string
  warehouse_id: number | null
  warehouse_name: string
  currency: string
  /** 税率按百分比记录（0~100） */
  tax_rate: string
  payment_terms: string
  delivery_address: string
  total_amount: string
  tax_amount: string
  amount_with_tax: string
  approval_instance_id: number | null
  approved_at: string | null
  closed_at: string | null
  remark: string
  lines: SalesOrderLine[]
}

export interface SalesOrderLineInput {
  material_id: number
  quantity: string
  sku_id?: number | null
  price?: string
  uom_id?: number | null
  expected_date?: string | null
  remark?: string
}

export interface SalesOrderInput {
  order_no?: string
  customer_id: number
  order_date?: string | null
  expected_date?: string | null
  priority?: string
  warehouse_id?: number | null
  salesman_id?: number | null
  currency?: string
  tax_rate?: string
  payment_terms?: string
  delivery_address?: string
  remark?: string
  lines: SalesOrderLineInput[]
}

export interface SalesShipmentLine extends Stamped {
  id: number
  shipment_id: number
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

export interface SalesShipment extends Stamped {
  id: number
  company_id: number
  company_name: string
  shipment_no: string
  sales_order_id: number
  order_no: string
  customer_id: number
  customer_name: string
  status: string
  status_display: string
  warehouse_id: number
  warehouse_name: string
  shipped_at: string | null
  shipped_by_name: string
  receiver_name: string
  receiver_phone: string
  delivery_address: string
  carrier: string
  tracking_no: string
  issue_document_id: number | null
  remark: string
  lines: SalesShipmentLine[]
}

export interface ShipmentLineInput {
  order_line_id: number
  quantity: string
  location_id?: number | null
  batch_no?: string
  roll_no?: string
  remark?: string
}

export interface ShipmentInput {
  shipment_no?: string
  sales_order_id: number
  warehouse_id?: number | null
  receiver_name?: string
  receiver_phone?: string
  delivery_address?: string
  carrier?: string
  tracking_no?: string
  remark?: string
  lines: ShipmentLineInput[]
}

export interface SalesReturnLine extends Stamped {
  id: number
  return_doc_id: number
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

export interface SalesReturn extends Stamped {
  id: number
  company_id: number
  company_name: string
  return_no: string
  sales_order_id: number
  order_no: string
  shipment_id: number | null
  shipment_no: string
  customer_id: number
  customer_name: string
  status: string
  status_display: string
  warehouse_id: number
  warehouse_name: string
  reason: string
  received_at: string | null
  received_by_name: string
  inspection_result: string
  inspection_result_display: string
  inspected_at: string | null
  inspected_by_name: string
  inspection_remark: string
  receipt_document_id: number | null
  quality_document_id: number | null
  remark: string
  lines: SalesReturnLine[]
}

export interface ReturnLineInput {
  order_line_id: number
  quantity: string
  location_id?: number | null
  batch_no?: string
  roll_no?: string
  remark?: string
}

export interface ReturnInput {
  return_no?: string
  sales_order_id: number
  shipment_id?: number | null
  warehouse_id?: number | null
  reason?: string
  remark?: string
  lines: ReturnLineInput[]
}

/** 订单到交付链路（任务书 12.1）。 */
export interface SalesOrderChain {
  order: {
    id: number
    order_no: string
    status: string
    status_display: string
    amount_with_tax: string
  }
  lines: {
    line_id: number
    line_no: number
    material_id: number
    material_code: string
    material_name: string
    quantity: string
    shipped_quantity: string
    returned_quantity: string
    remaining_quantity: string
  }[]
  shipments: {
    id: number
    shipment_no: string
    status: string
    shipped_at: string | null
    issue_document_id: number | null
  }[]
  returns: { id: number; return_no: string; status: string; inspection_result: string }[]
  inventory_documents: {
    id: number
    document_no: string
    document_type: string
    status: string
  }[]
}

/** 库存占用记录（WMS 只读视图）。 */
export interface StockReservation extends Stamped {
  id: number
  company_id: number
  material_id: number
  material_code: string
  material_name: string
  warehouse_id: number
  warehouse_name: string
  location_id: number | null
  batch_no: string
  roll_no: string
  quality_status: string
  quantity: string
  consumed_quantity: string
  released_quantity: string
  open_quantity: string
  status: string
  status_display: string
  biz_type: string
  biz_id: string
  biz_no: string
  remark: string
}

/** BOM 明细行。`gross_quantity`（含损耗用量）由后端计算，前端传入会被忽略。 */
export interface BomLine extends Stamped {
  id: number
  bom_id: number
  line_no: number
  material_id: number
  material_code: string
  material_name: string
  quantity: string
  loss_rate: string
  gross_quantity: string
  uom_id: number | null
  uom_name: string
  line_type: string
  line_type_display: string
  substitute_for_id: number | null
  substitute_for_line_no: number | null
  position: string
  is_key_material: boolean
  remark: string
}

/** BOM（物料清单）版本。同一「款式 + SKU 范围」同时只有一个已审核版本生效。 */
export interface Bom extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  style_id: number
  style_code: string
  style_name: string
  sku_id: number | null
  sku_code: string
  scope_label: string
  version_no: number
  status: string
  status_display: string
  effective_from: string | null
  effective_to: string | null
  is_active: boolean
  approval_instance_id: number | null
  submitted_at: string | null
  approved_at: string | null
  approved_by_id: number | null
  approved_by_name: string
  remark: string
  lines: BomLine[]
  line_count: number
}

export interface BomLineInput {
  material_id: number
  quantity: string
  loss_rate?: string
  uom_id?: number | null
  line_type?: string
  substitute_for_line_no?: number | null
  position?: string
  is_key_material?: boolean
  remark?: string
}

export interface BomInput {
  code?: string
  style_id: number
  sku_id?: number | null
  effective_from?: string | null
  effective_to?: string | null
  remark?: string
  lines: BomLineInput[]
}

/** 工序。`is_quality_gate` 表示该工序是质检点（MES 必须产生检验记录）。 */
export interface RoutingStep extends Stamped {
  id: number
  routing_id: number
  sequence: number
  name: string
  workshop_id: number | null
  workshop_name: string
  workcenter: string
  equipment_requirement: string
  standard_hours: string
  is_quality_gate: boolean
  is_outsourced: boolean
  remark: string
}

/** 工艺路线版本。版本与审核规则和 BOM 一致。 */
export interface Routing extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  style_id: number
  style_code: string
  style_name: string
  sku_id: number | null
  sku_code: string
  scope_label: string
  version_no: number
  status: string
  status_display: string
  effective_from: string | null
  effective_to: string | null
  is_active: boolean
  approval_instance_id: number | null
  submitted_at: string | null
  approved_at: string | null
  approved_by_id: number | null
  approved_by_name: string
  remark: string
  steps: RoutingStep[]
  step_count: number
  quality_gate_count: number
}

export interface RoutingStepInput {
  sequence?: number
  name: string
  workshop_id?: number | null
  workcenter?: string
  equipment_requirement?: string
  standard_hours?: string
  is_quality_gate?: boolean
  is_outsourced?: boolean
  remark?: string
}

export interface RoutingInput {
  code?: string
  style_id: number
  sku_id?: number | null
  effective_from?: string | null
  effective_to?: string | null
  remark?: string
  steps?: RoutingStepInput[]
}

/** BOM 快照（不可变结构，MES 工单下达时保存同一份内容）。 */
export interface BomSnapshot {
  bom_id: number
  bom_code: string
  status: string
  version_no: number
  style_id: number
  sku_id: number | null
  scope_key: string
  effective_from: string | null
  effective_to: string | null
  line_count: number
  lines: {
    line_no: number
    material_id: number
    material_code: string
    quantity: string
    loss_rate: string
    gross_quantity: string
    uom_id: number | null
    line_type: string
    substitute_for_line_no: number | null
    position: string
    is_key_material: boolean
  }[]
}

/** 工艺路线快照。 */
export interface RoutingSnapshot {
  routing_id: number
  routing_code: string
  status: string
  version_no: number
  style_id: number
  sku_id: number | null
  scope_key: string
  effective_from: string | null
  effective_to: string | null
  step_count: number
  steps: {
    sequence: number
    name: string
    workshop_id: number | null
    workcenter: string
    equipment_requirement: string
    standard_hours: string
    is_quality_gate: boolean
    is_outsourced: boolean
  }[]
}


/** MRP 运行的净算过程分段（可解释性：期初、供给、需求、净需求、期末）。 */
export interface MrpBucketTrace {
  bucket_date: string
  opening: string
  supply: string
  demand: string
  net_requirement: string
  closing: string
}

/** MRP 运行记录。 */
export interface MrpRun extends Stamped {
  id: number
  company_id: number
  company_name: string
  run_no: string
  status: string
  status_display: string
  bucket: string
  bucket_display: string
  horizon_start: string
  horizon_end: string
  warehouse_id: number | null
  warehouse_name: string
  parameters: Record<string, unknown>
  summary: {
    item_count?: number
    level_count?: number
    demand_line_count?: number
    demand_quantity?: string
    supply_line_count?: number
    supply_quantity?: string
    suggestion_count?: number
    purchase_suggestion_count?: number
    production_suggestion_count?: number
    suggestion_quantity?: string
    unexploded_materials?: string[]
    bucket_count?: number
    buckets?: string[]
  }
  demand_count: number
  supply_count: number
  suggestion_count: number
  started_at: string | null
  finished_at: string | null
  error_message: string
  archived_at: string | null
  archived_by_id: number | null
  archived_by_name: string
  remark: string
}

export interface MrpRunInput {
  company_id?: number | null
  horizon_start?: string | null
  horizon_end?: string | null
  bucket?: string
  warehouse_id?: number | null
  remark?: string
}

/** MRP 需求行（销售需求或父件派生需求，含来源路径用于供需追溯）。 */
export interface MrpDemandLine extends Stamped {
  id: number
  run_id: number
  line_no: number
  level: number
  source_type: string
  source_type_display: string
  source_id: string
  source_no: string
  source_line_no: number | null
  material_id: number
  material_code: string
  material_name: string
  sku_id: number | null
  sku_code: string
  style_id: number | null
  style_code: string
  warehouse_id: number | null
  warehouse_name: string
  quantity: string
  due_date: string | null
  bucket_date: string
  path: string
  exploded: boolean
  note: string
}

/** MRP 供给行（现有可用库存 / 采购在途）。 */
export interface MrpSupplyLine extends Stamped {
  id: number
  run_id: number
  line_no: number
  source_type: string
  source_type_display: string
  material_id: number
  material_code: string
  material_name: string
  warehouse_id: number | null
  warehouse_name: string
  quantity: string
  available_date: string
  bucket_date: string
  reference_type: string
  reference_id: string
  reference_no: string
  remark: string
}

/** MRP 建议（缺料清单）：采购建议可转草稿采购申请，生产建议待 MES 工单落地。 */
export interface MrpSuggestion extends Stamped {
  id: number
  run_id: number
  run_no: string
  run_status: string
  line_no: number
  suggestion_type: string
  suggestion_type_display: string
  status: string
  status_display: string
  material_id: number
  material_code: string
  material_name: string
  sku_id: number | null
  sku_code: string
  style_id: number | null
  style_code: string
  warehouse_id: number | null
  warehouse_name: string
  quantity: string
  uom_id: number | null
  uom_name: string
  due_date: string
  bucket_date: string
  reason: string
  detail: {
    level?: number
    bom_id?: number | null
    bom_code?: string | null
    bom_version_no?: number | null
    trace?: MrpBucketTrace[]
    demand_sources?: string[]
  }
  converted_document_type: string
  converted_document_id: string
  converted_document_no: string
  converted_at: string | null
  converted_by_id: number | null
  converted_by_name: string
  cancel_reason: string
  remark: string
  /** 前端按钮提示用；真正的拦截在后端服务层 */
  convertible: boolean
}

// ---------------------------------------------------------------------------
// 设备管理（设备基础信息）—— 阶段 4 第一步：设备类型、台账、零部件、备品备件
// ---------------------------------------------------------------------------

export interface EquipmentType extends Stamped {
  id: number
  code: string
  name: string
  category: string
  is_special: boolean
  maintenance_cycle_days: number
  remark: string
  is_active: boolean
}

export interface Equipment extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  equipment_type_id: number
  equipment_type_name: string
  status: string
  factory_id: number | null
  factory_name: string
  workshop_id: number | null
  workshop_name: string
  production_line_id: number | null
  production_line_name: string
  station_id: number | null
  station_name: string
  location: string
  brand: string
  model_no: string
  serial_no: string
  supplier_id: number | null
  supplier_name: string
  purchase_date: string | null
  start_date: string | null
  original_value: string
  warranty_until: string | null
  is_special: boolean
  owner_department_id: number | null
  owner_department_name: string
  owner_employee_id: number | null
  owner_employee_name: string
  remark: string
  is_active: boolean
}

export interface EquipmentPart extends Stamped {
  id: number
  equipment_id: number
  equipment_name: string
  company_id: number | null
  name: string
  part_type: string
  spec: string
  quantity: string
  uom_id: number | null
  uom_name: string
  position: string
  life_days: number
  remark: string
  is_active: boolean
}

export interface SparePart extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  part_type: string
  spec: string
  material_id: number | null
  material_name: string
  equipment_type_id: number | null
  equipment_type_name: string
  uom_id: number | null
  uom_name: string
  safety_stock: string
  reference_price: string
  life_days: number
  supplier_id: number | null
  supplier_name: string
  remark: string
  is_active: boolean
}

export interface MaintenanceItem extends Stamped {
  id: number
  code: string
  name: string
  category: string
  equipment_type_id: number | null
  equipment_type_name: string
  cycle_days: number
  standard: string
  is_active: boolean
  remark: string
}

export interface MaintenancePlan extends Stamped {
  id: number
  company_id: number
  company_name: string
  plan_no: string
  name: string
  equipment_id: number
  equipment_name: string
  cycle_days: number
  start_date: string
  next_date: string
  item_ids: number[]
  item_names: string
  responsible_employee_id: number | null
  responsible_employee_name: string
  department_id: number | null
  department_name: string
  is_active: boolean
  remark: string
}

export interface MaintenanceTask extends Stamped {
  id: number
  company_id: number
  company_name: string
  task_no: string
  plan_id: number | null
  plan_no: string
  equipment_id: number
  equipment_name: string
  item_id: number | null
  item_name: string
  plan_date: string
  status: string
  assignee_id: number | null
  assignee_name: string
  started_at: string | null
  finished_at: string | null
  result: string
  remark: string
}

export interface MaintenanceRecord extends Stamped {
  id: number
  company_id: number
  company_name: string
  record_no: string
  task_id: number | null
  equipment_id: number
  equipment_name: string
  item_id: number | null
  item_name: string
  maintain_date: string
  executor_id: number | null
  executor_name: string
  content: string
  result: string
  is_qualified: boolean
  cost: string
  remark: string
}

export interface FaultReport extends Stamped {
  id: number
  company_id: number
  company_name: string
  report_no: string
  equipment_id: number
  equipment_name: string
  level: string
  description: string
  reporter_id: number | null
  reporter_name: string
  reported_at: string
  status: string
  closed_at: string | null
  remark: string
}

export interface RepairTask extends Stamped {
  id: number
  company_id: number
  company_name: string
  task_no: string
  fault_report_id: number | null
  report_no: string
  equipment_id: number
  equipment_name: string
  symptom: string
  level: string
  assignee_id: number | null
  assignee_name: string
  assigned_date: string | null
  status: string
  started_at: string | null
  finished_at: string | null
  downtime_minutes: number
  remark: string
}

export interface RepairRecord extends Stamped {
  id: number
  company_id: number
  company_name: string
  record_no: string
  task_id: number | null
  task_no: string
  equipment_id: number
  equipment_name: string
  repair_date: string
  repairer_id: number | null
  repairer_name: string
  fault_reason: string
  solution: string
  parts_used: string
  cost: string
  downtime_minutes: number
  result: string
  remark: string
}

export interface InspectionItem extends Stamped {
  id: number
  code: string
  name: string
  method: string
  standard: string
  uom_id: number | null
  uom_name: string
  lower_limit: string | null
  upper_limit: string | null
  is_active: boolean
  remark: string
}

export interface InspectionTask extends Stamped {
  id: number
  company_id: number
  company_name: string
  task_no: string
  task_type: string
  equipment_id: number
  equipment_name: string
  plan_date: string
  status: string
  assignee_id: number | null
  assignee_name: string
  item_ids: number[]
  item_names: string
  started_at: string | null
  finished_at: string | null
  result: string
  remark: string
}

export interface InspectionRecord extends Stamped {
  id: number
  company_id: number
  company_name: string
  record_no: string
  task_id: number | null
  equipment_id: number
  equipment_name: string
  item_id: number | null
  item_name: string
  inspected_at: string
  inspector_id: number | null
  inspector_name: string
  measured_value: string | null
  result: string
  abnormal_desc: string
  remark: string
}

export interface AbnormalType extends Stamped {
  id: number
  code: string
  name: string
  level: string
  is_active: boolean
  remark: string
}

export interface AbnormalTask extends Stamped {
  id: number
  company_id: number
  company_name: string
  task_no: string
  abnormal_type_id: number
  abnormal_type_name: string
  equipment_id: number | null
  equipment_name: string
  source: string
  description: string
  reported_by_id: number | null
  reported_by_name: string
  reported_at: string
  status: string
  handler_id: number | null
  handler_name: string
  deadline: string | null
  handling: string
  closed_at: string | null
  remark: string
}

export interface AbnormalRecord extends Stamped {
  id: number
  company_id: number
  company_name: string
  record_no: string
  task_id: number | null
  abnormal_type_id: number | null
  abnormal_type_name: string
  equipment_id: number | null
  equipment_name: string
  handle_date: string
  handler_id: number | null
  handler_name: string
  action: string
  result: string
  remark: string
}

/** 备件现存量（库存台账）：数据来自仓储模块的统一库存余额，只读。 */
export interface SparePartStockRow {
  id: number
  spare_part_id: number
  code: string
  name: string
  part_type: string
  spec: string
  equipment_type_name: string
  uom_name: string
  warehouse_id: number | null
  warehouse_name: string
  location_name: string
  batch_no: string
  quality_status: string
  on_hand: string
  frozen: string
  reserved: string
  available: string
  safety_stock: string
  below_safety: boolean
  life_days: number
}

// ---------------------------------------------------------------------------
// 能源管理
// ---------------------------------------------------------------------------

export interface EnergyArea extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  parent_id: number | null
  parent_name: string
  department_id: number | null
  department_name: string
  manager_id: number | null
  manager_name: string
  area_size: string
  remark: string
  is_active: boolean
}

export interface EnergyMeter extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  medium: string
  area_id: number | null
  area_name: string
  equipment_id: number | null
  equipment_name: string
  department_id: number | null
  department_name: string
  meter_model: string
  serial_no: string
  multiplier: string
  unit: string
  status: string
  location: string
  install_date: string | null
  last_reading_at: string | null
  is_monitored: boolean
  remark: string
  is_active: boolean
}

export interface EnergyPrice extends Stamped {
  id: number
  company_id: number
  company_name: string
  medium: string
  tariff_period: string
  name: string
  unit_price: string
  currency_unit: string
  effective_from: string
  effective_to: string | null
  remark: string
  is_active: boolean
}

export interface EnergyThreshold extends Stamped {
  id: number
  company_id: number
  company_name: string
  name: string
  medium: string
  meter_id: number | null
  meter_name: string
  upper_limit: string | null
  lower_limit: string | null
  daily_limit: string | null
  unit_consumption_limit: string | null
  offline_minutes: number
  alarm_level: string
  remark: string
  is_active: boolean
}

export interface MeterReading extends Stamped {
  id: number
  company_id: number
  company_name: string
  meter_id: number
  meter_code: string
  meter_name: string
  medium: string
  unit: string
  reading_at: string
  reading: string
  consumption: string
  tariff_period: string
  source: string
  recorder_id: number | null
  recorder_name: string
  note: string
}

export interface EnergyRunRecord extends Stamped {
  id: number
  company_id: number
  company_name: string
  record_no: string
  meter_id: number
  meter_code: string
  meter_name: string
  unit: string
  equipment_id: number | null
  equipment_name: string
  status: string
  started_at: string
  finished_at: string | null
  run_minutes: number | null
  output_desc: string
  output_qty: string
  energy_consumption: string
  unit_consumption: string | null
  operator_id: number | null
  operator_name: string
  remark: string
}

export interface EnergyAlarm extends Stamped {
  id: number
  company_id: number
  company_name: string
  alarm_no: string
  meter_id: number | null
  meter_code: string
  meter_name: string
  area_id: number | null
  area_name: string
  alarm_type: string
  level: string
  status: string
  source: string
  occurred_at: string
  message: string
  triggered_value: string | null
  threshold_value: string | null
  handler_id: number | null
  handler_name: string
  handled_at: string | null
  handle_note: string
  closed_at: string | null
  remark: string
}

/** 设备监控行：仪表状态 + 最近抄表 + 本月用量 + 未处理报警数。 */
export interface EnergyMonitorRow {
  id: number
  code: string
  name: string
  medium: string
  medium_display: string
  unit: string
  status: string
  status_display: string
  area_name: string
  department_name: string
  equipment_name: string
  location: string
  last_reading: string | null
  last_reading_at: string | null
  last_consumption: string | null
  month_consumption: string
  open_alarm_count: number
  is_monitored: boolean
}

/** 能耗聚合行：统计与报表共用同一结构。 */
export interface EnergyConsumptionRow {
  key: number | string
  code: string
  label: string
  unit: string
  medium: string
  medium_label: string
  consumption: string
  cost: string
  priced: boolean
  periods: { period: string; period_label: string; consumption: string }[]
}

export interface EnergyStatisticsPayload {
  dimension: string
  start: string | null
  end: string | null
  rows: EnergyConsumptionRow[]
  totals: { row_count: number; unpriced: number; consumption: string; cost: string }
}

export interface EnergyReportPayload {
  period: string
  medium: string | null
  medium_label: string
  start: string | null
  end: string | null
  rows: EnergyConsumptionRow[]
  peak_valley: { label: string; period: string; period_label: string; consumption: string }[]
  totals: { consumption: string; cost: string; unpriced: number }
}

/** 能源首页汇总。 */
export interface EnergyHomeSummary {
  generated_at: string
  today: EnergyMediumTotals
  month: EnergyMediumTotals
  meters: { total: number; online: number; offline: number; stopped: number; monitored: number }
  alarms: {
    open: number
    pending: number
    today: number
    by_type: Record<string, number>
  }
  trend: { date: string; consumption: string }[]
  ranking: EnergyConsumptionRow[]
}

export interface EnergyMediumTotals {
  start: string
  end: string
  total_consumption: string
  total_cost: string
  by_medium: Record<string, { consumption: string; cost: string; label: string }>
}

// ---------------------------------------------------------------------------
// 生产物流管理
// ---------------------------------------------------------------------------

export interface AutomationDevice extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  device_type: string
  status: string
  workshop_id: number | null
  workshop_name: string
  location: string
  max_load: string
  speed: string
  battery_level: number | null
  commissioned_date: string | null
  last_maintenance_date: string | null
  next_maintenance_date: string | null
  remark: string
  is_active: boolean
}

export interface LogisticsTask extends Stamped {
  id: number
  company_id: number
  company_name: string
  task_no: string
  task_type: string
  device_id: number | null
  device_code: string
  device_name: string
  priority: string
  status: string
  warehouse_id: number | null
  warehouse_name: string
  from_location_id: number | null
  from_location_name: string
  to_location_id: number | null
  to_location_name: string
  material_id: number | null
  material_name: string
  quantity: string
  container_no: string
  requested_by_id: number | null
  requested_by_name: string
  assignee_id: number | null
  assignee_name: string
  planned_at: string | null
  dispatched_at: string | null
  started_at: string | null
  finished_at: string | null
  result: string
  remark: string
}

export interface LogisticsOperationLog extends Stamped {
  id: number
  company_id: number
  company_name: string
  device_id: number | null
  device_code: string
  device_name: string
  task_id: number | null
  task_no: string
  action: string
  operator_id: number | null
  operator_name: string
  occurred_at: string
  detail: string
  payload: Record<string, unknown> | null
}

// ---------------------------------------------------------------------------
// 安全环保管理
// ---------------------------------------------------------------------------

export interface SafetyRegulation extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  category: string
  version_no: string
  issue_org: string
  issue_date: string | null
  effective_date: string | null
  status: string
  owner_department_id: number | null
  owner_department_name: string
  owner_employee_id: number | null
  owner_employee_name: string
  remark: string
  is_active: boolean
}

export interface SafetyTraining extends Stamped {
  id: number
  company_id: number
  company_name: string
  training_no: string
  topic: string
  training_type: string
  trainer: string
  department_id: number | null
  department_name: string
  planned_date: string | null
  actual_date: string | null
  duration_hours: string
  participant_count: number
  passed_count: number
  status: string
  remark: string
}

export interface HazardRecord extends Stamped {
  id: number
  company_id: number
  company_name: string
  hazard_no: string
  title: string
  description: string
  level: string
  source: string
  location: string
  department_id: number | null
  department_name: string
  reported_by_id: number | null
  reported_by_name: string
  found_date: string | null
  due_date: string | null
  status: string
  rectify_measure: string
  rectified_by_id: number | null
  rectified_by_name: string
  rectified_date: string | null
  verify_result: string
  verified_by_id: number | null
  verified_by_name: string
  verified_date: string | null
  is_overdue: boolean
  remark: string
}

export interface EmergencyPlan extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  plan_type: string
  response_level: string
  issue_date: string | null
  review_date: string | null
  drill_cycle_days: number
  next_drill_date: string | null
  status: string
  owner_employee_id: number | null
  owner_employee_name: string
  remark: string
  is_active: boolean
}

export interface AccidentRecord extends Stamped {
  id: number
  company_id: number
  company_name: string
  accident_no: string
  title: string
  category: string
  level: string
  occurred_at: string
  location: string
  department_id: number | null
  department_name: string
  injured_count: number
  lost_days: number
  loss_amount: string
  description: string
  causes: string
  measures: string
  reporter_id: number | null
  reporter_name: string
  reported_at: string | null
  investigator_id: number | null
  investigator_name: string
  investigation_result: string
  status: string
  closed_date: string | null
  remark: string
}

export interface EnvironmentMonitor extends Stamped {
  id: number
  company_id: number
  company_name: string
  monitor_no: string
  medium: string
  point_name: string
  pollutant: string
  limit_value: string | null
  measured_value: string | null
  unit: string
  is_compliant: boolean
  is_over_limit: boolean
  monitored_at: string
  permit_no: string
  monitor_org: string
  remark: string
}

export interface WasteRecord extends Stamped {
  id: number
  company_id: number
  company_name: string
  waste_no: string
  waste_name: string
  waste_type: string
  waste_code: string
  quantity: string
  unit: string
  produced_date: string | null
  storage_location: string
  disposal_method: string
  disposal_org: string
  transfer_no: string
  disposed_date: string | null
  status: string
  remark: string
}

export interface ComplianceCheck extends Stamped {
  id: number
  company_id: number
  company_name: string
  check_no: string
  title: string
  check_type: string
  check_date: string | null
  organization: string
  checker_id: number | null
  checker_name: string
  result: string
  issues: string
  rectify_due_date: string | null
  status: string
  rectified_date: string | null
  owner_employee_id: number | null
  owner_employee_name: string
  remark: string
}

export interface FireFacility extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  facility_type: string
  location: string
  quantity: string
  unit: string
  last_check_date: string | null
  next_check_date: string | null
  status: string
  department_id: number | null
  department_name: string
  owner_employee_id: number | null
  owner_employee_name: string
  remark: string
  is_active: boolean
}

export interface FireDrill extends Stamped {
  id: number
  company_id: number
  company_name: string
  drill_no: string
  topic: string
  drill_type: string
  planned_date: string | null
  actual_date: string | null
  organizer: string
  participant_count: number
  duration_minutes: number
  assessment: string
  issues: string
  plan_id: number | null
  plan_name: string
  remark: string
}

export interface WorkPermit extends Stamped {
  id: number
  company_id: number
  company_name: string
  permit_no: string
  permit_type: string
  status: string
  work_content: string
  work_location: string
  risk_level: string
  protective_measures: string
  applicant_id: number | null
  applicant_name: string
  department_id: number | null
  department_name: string
  start_at: string | null
  end_at: string | null
  approver_id: number | null
  approver_name: string
  approved_at: string | null
  guardian_id: number | null
  guardian_name: string
  started_at: string | null
  finished_at: string | null
  accepted_by_id: number | null
  accepted_by_name: string
  accepted_at: string | null
  result: string
  remark: string
}

export interface SafetyCheck extends Stamped {
  id: number
  company_id: number
  company_name: string
  check_no: string
  check_type: string
  title: string
  check_date: string | null
  checker_id: number | null
  checker_name: string
  department_id: number | null
  department_name: string
  equipment_id: number | null
  equipment_name: string
  check_content: string
  problem_count: number
  conclusion: string
  status: string
  rectify_requirement: string
  rectified_date: string | null
  remark: string
}

export interface SpecialEquipmentInspection extends Stamped {
  id: number
  company_id: number
  company_name: string
  certificate_no: string
  equipment_id: number | null
  equipment_code: string
  linked_equipment_name: string
  equipment_name: string
  inspection_org: string
  inspection_date: string | null
  next_inspection_date: string | null
  result: string
  inspector: string
  issue_date: string | null
  remark: string
}

export interface EhsOperationLog extends Stamped {
  id: number
  company_id: number
  company_name: string
  domain: string
  business_type: string
  business_label: string
  action: string
  operator_id: number | null
  operator_name: string
  occurred_at: string
  detail: string
  payload: Record<string, unknown> | null
}

/** 检验项目：检验单明细的判定依据（判定口径的唯一来源）。 */
export interface QualityInspectionItem extends Stamped {
  id: number
  company_id: number
  company_name: string
  code: string
  name: string
  category: string
  value_type: string
  unit: string
  method: string
  standard_text: string
  lower_limit: string | null
  upper_limit: string | null
  is_active: boolean
  remark: string
}

/** 检验结果明细：定量项目的「是否合格」由后端按上下限计算，前端只读。 */
export interface QualityInspectionResult {
  id: number
  order_id: number
  item_id: number
  item_code: string
  item_name: string
  item_category: string
  item_category_display: string
  unit: string
  lower_limit: string | null
  upper_limit: string | null
  method: string
  measured_value: string | null
  text_value: string
  is_qualified: boolean
  remark: string
  sort_order: number
}

export interface QualityInspectionOrder extends Stamped {
  id: number
  company_id: number
  company_name: string
  order_no: string
  inspection_type: string
  status: string
  judgement: string
  source_no: string
  material_id: number | null
  material_name: string
  product_desc: string
  batch_no: string
  supplier_id: number | null
  supplier_name: string
  workshop_id: number | null
  workshop_name: string
  production_line_id: number | null
  production_line_name: string
  equipment_id: number | null
  equipment_name: string
  quantity: string
  sample_quantity: string
  unit: string
  inspector_id: number | null
  inspector_name: string
  inspected_at: string | null
  judge_remark: string
  judged_at: string | null
  results: QualityInspectionResult[]
  result_count: number
  failed_count: number
  is_active: boolean
  remark: string
}

export interface QualityAlert extends Stamped {
  id: number
  company_id: number
  company_name: string
  alert_no: string
  order_id: number | null
  order_no: string
  level: string
  status: string
  title: string
  description: string
  material_id: number | null
  material_name: string
  batch_no: string
  handler_id: number | null
  handler_name: string
  handled_at: string | null
  close_remark: string
  closed_at: string | null
}

export interface QualityIssue extends Stamped {
  id: number
  company_id: number
  company_name: string
  issue_no: string
  title: string
  category: string
  severity: string
  phenomenon: string
  cause: string
  corrective_action: string
  preventive_action: string
  material_id: number | null
  material_name: string
  product_desc: string
  tags: string[]
  source_order_id: number | null
  source_order_no: string
  source_alert_id: number | null
  source_alert_no: string
  status: string
  published_at: string | null
  is_active: boolean
  remark: string
}

// ---------------------------------------------------------------------------
// 生产执行（MES）
// ---------------------------------------------------------------------------

export interface ProductionOrderMaterial {
  id: number
  order_id: number
  line_no: number
  material_id: number
  material_code: string
  material_name: string
  source: string
  source_display: string
  required_quantity: string
  issued_quantity: string
  unit: string
  location_id: number | null
  location_name: string
  remark: string
}

export interface ProductionOrderStep {
  id: number
  order_id: number
  sequence: number
  name: string
  workshop_id: number | null
  workshop_name: string
  workcenter: string
  equipment_requirement: string
  standard_hours: string
  is_quality_gate: boolean
  is_outsourced: boolean
  status: string
  status_display: string
  reported_quantity: string
  qualified_quantity: string
  scrap_quantity: string
  started_at: string | null
  finished_at: string | null
  inspection_order_id: number | null
  inspection_order_no: string
  inspection_judgement: string
  remark: string
}

export interface ProductionOrder extends Stamped {
  id: number
  company_id: number
  company_name: string
  order_no: string
  source_type: string
  source_type_display: string
  source_no: string
  factory_id: number | null
  factory_name: string
  workshop_id: number | null
  workshop_name: string
  production_line_id: number | null
  production_line_name: string
  style_id: number
  style_name: string
  sku_id: number | null
  sku_name: string
  product_material_id: number | null
  product_material_name: string
  quantity: string
  completed_quantity: string
  qualified_quantity: string
  scrap_quantity: string
  unit: string
  status: string
  status_display: string
  planned_start: string | null
  planned_end: string | null
  actual_start: string | null
  actual_end: string | null
  material_warehouse_id: number | null
  material_warehouse_name: string
  receipt_warehouse_id: number | null
  receipt_warehouse_name: string
  bom_snapshot: Record<string, unknown>
  routing_snapshot: Record<string, unknown>
  owner_id: number | null
  owner_name: string
  released_at: string | null
  closed_at: string | null
  cancel_reason: string
  issue_document_id: number | null
  issue_document_no: string
  receipt_document_id: number | null
  receipt_document_no: string
  progress_rate: string
  materials: ProductionOrderMaterial[]
  steps: ProductionOrderStep[]
  report_count: number
  is_active: boolean
  remark: string
}

export interface ProductionReport extends Stamped {
  id: number
  company_id: number
  company_name: string
  report_no: string
  order_id: number
  order_no: string
  step_id: number
  step_name: string
  step_sequence: number
  report_type: string
  report_type_display: string
  quantity: string
  qualified_quantity: string
  rework_quantity: string
  scrap_quantity: string
  operator_id: number | null
  operator_name: string
  equipment_id: number | null
  equipment_name: string
  work_hours: string
  started_at: string | null
  finished_at: string | null
  reported_at: string | null
  remark: string
}
