import { ref } from 'vue'
import { defineStore } from 'pinia'

import { coreApi, factoryApi } from '@/api/modules'
import { departmentApi } from '@/api/endpoints'
import type { Department, EnumOption, MetaPayload } from '@/types/models'

const EMPTY_META: MetaPayload = {
  department_types: [],
  workshop_types: [],
  line_types: [],
  employee_genders: [],
  employment_types: [],
  employee_statuses: [],
  material_category_types: [],
  uom_categories: [],
  warehouse_types: [],
  zone_types: [],
  location_types: [],
  identifier_types: [],
  data_scope_types: [],
  permission_types: [],
  approver_types: [],
  approval_statuses: [],
  approval_step_statuses: [],
  customer_categories: [],
  customer_levels: [],
  customer_statuses: [],
  supplier_categories: [],
  supplier_grades: [],
  admission_statuses: [],
  qualification_types: [],
  quality_statuses: [],
  inventory_document_types: [],
  inventory_document_statuses: [],
  inventory_transaction_types: [],
  inventory_directions: [],
  requisition_types: [],
  requisition_statuses: [],
  purchase_order_statuses: [],
  receipt_statuses: [],
  inspection_results: [],
}

const STATUS_OPTIONS: EnumOption[] = [
  { value: 'pending', label: '审批中' },
  { value: 'approved', label: '已通过' },
  { value: 'rejected', label: '已驳回' },
  { value: 'withdrawn', label: '已撤回' },
  { value: 'draft', label: '草稿' },
  { value: 'cancelled', label: '已取消' },
]

/**
 * 全局字典与枚举。
 *
 * 枚举一律从后端 /api/v1/meta/ 获取，不在前端硬编码中文标签，
 * 避免后端新增取值后前端静默漏项。
 */
export const useMetaStore = defineStore('meta', () => {
  const meta = ref<MetaPayload>({ ...EMPTY_META })
  const departments = ref<Department[]>([])
  const loaded = ref(false)
  const loading = ref(false)

  async function ensureLoaded(): Promise<void> {
    if (loaded.value || loading.value) {
      return
    }
    loading.value = true
    try {
      meta.value = await coreApi.meta()
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  async function ensureDepartments(): Promise<Department[]> {
    if (departments.value.length > 0) {
      return departments.value
    }
    const page = await departmentApi.list({ page_size: 200, ordering: 'code' })
    departments.value = page.results
    return departments.value
  }

  function options(key: keyof MetaPayload): EnumOption[] {
    return meta.value[key] ?? []
  }

  function label(key: keyof MetaPayload, value: string | null | undefined): string {
    if (!value) {
      return '-'
    }
    const found = options(key).find((item) => item.value === value)
    return found ? found.label : value
  }

  function approvalStatusOptions(): EnumOption[] {
    return meta.value.approval_statuses.length > 0 ? meta.value.approval_statuses : STATUS_OPTIONS
  }

  function reset(): void {
    meta.value = { ...EMPTY_META }
    departments.value = []
    loaded.value = false
  }

  async function departmentTree(): Promise<Department[]> {
    return factoryApi.departmentTree({ page_size: 200 })
  }

  return {
    meta,
    departments,
    loaded,
    loading,
    ensureLoaded,
    ensureDepartments,
    options,
    label,
    approvalStatusOptions,
    departmentTree,
    reset,
  }
})