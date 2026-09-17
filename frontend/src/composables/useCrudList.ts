import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { ApiError } from '@/api/http'
import type { CrudApi, QueryParams } from '@/api/crud'

/**
 * 列表页通用逻辑：查询、分页、排序、错误提示、启停与删除。
 *
 * 约束：
 * - 失败必须显式提示，不做「静默当成空列表」；
 * - 分页大小受后端上限约束，超限错误直接展示后端 message；
 * - 停止使用（set-active）与删除是两个不同动作，不能混用。
 */
export interface CrudListOptions<T> {
  api: CrudApi<T, never> | { list: (params?: QueryParams) => Promise<{ count: number; results: T[] }> }
  pageSize?: number
  defaultFilters?: Record<string, unknown>
  defaultOrdering?: string
  /** 传入后启用「启用/停用」，值为后端字段名（默认 is_active） */
  activeField?: string
  /** 是否允许删除（仅当后端提供 DELETE 且无下游依赖时才开启） */
  removable?: boolean
  /** 删除前必须校验的提示文本 */
  removeWarning?: string
}

export function useCrudList<T extends { id: number; version?: number }>(
  options: CrudListOptions<T>,
) {
  const rows = ref<T[]>([]) as { value: T[] }
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(options.pageSize ?? 20)
  const ordering = ref(options.defaultOrdering ?? '')
  const loading = ref(false)
  const errorMessage = ref('')

  const filters = reactive<Record<string, unknown>>({ ...(options.defaultFilters ?? {}) })

  function buildParams(): QueryParams {
    const params: QueryParams = { page: page.value, page_size: pageSize.value }
    if (ordering.value) {
      params.ordering = ordering.value
    }
    for (const [key, value] of Object.entries(filters)) {
      if (value === '' || value === null || value === undefined) {
        continue
      }
      params[key] = value
    }
    return params
  }

  async function load(): Promise<void> {
    loading.value = true
    errorMessage.value = ''
    try {
      const result = await options.api.list(buildParams())
      rows.value = result.results as T[]
      total.value = result.count
    } catch (error) {
      rows.value = []
      total.value = 0
      errorMessage.value =
        error instanceof ApiError
          ? `${error.message}${error.code ? `（${error.code}）` : ''}`
          : '加载数据失败'
    } finally {
      loading.value = false
    }
  }

  function resetFilters(): void {
    for (const key of Object.keys(filters)) {
      filters[key] = options.defaultFilters?.[key] ?? ''
    }
    page.value = 1
    void load()
  }

  function onSortChange(payload: { prop: string; order: 'ascending' | 'descending' | null }): void {
    if (!payload.order) {
      ordering.value = options.defaultOrdering ?? ''
    } else {
      ordering.value = `${payload.order === 'descending' ? '-' : ''}${payload.prop}`
    }
    page.value = 1
    void load()
  }

  function activeFlag(row: T): boolean {
    const field = options.activeField ?? 'is_active'
    return (row as Record<string, unknown>)[field] !== false
  }

  const canToggleActive = computed(() => Boolean(options.activeField))
  const canRemove = computed(() => options.removable === true)

  async function toggleActive(row: T): Promise<boolean> {
    const api = options.api as unknown as CrudApi<T, never>
    if (typeof api.setActive !== 'function') {
      ElMessage.warning('该资源不支持启停操作')
      return false
    }
    const next = !activeFlag(row)
    if (!next) {
      const confirmed = await ElMessageBox.confirm(
        '停用后该数据仍会保留历史引用，但不能在新单据中被选择。确认停用？',
        '停用确认',
        { type: 'warning', confirmButtonText: '确认停用', cancelButtonText: '取消' },
      ).catch(() => false)
      if (!confirmed) {
        return false
      }
    }
    try {
      await api.setActive(row.id, next)
      ElMessage.success(next ? '已启用' : '已停用')
      await load()
      return true
    } catch (error) {
      ElMessage.error(error instanceof ApiError ? error.message : '操作失败')
      return false
    }
  }

  async function remove(row: T): Promise<boolean> {
    const api = options.api as unknown as CrudApi<T, never>
    if (typeof api.remove !== 'function') {
      ElMessage.warning('该资源不支持删除')
      return false
    }
    const confirmed = await ElMessageBox.confirm(
      options.removeWarning ?? '删除后不可恢复。确认删除这条数据？',
      '删除确认',
      { type: 'warning', confirmButtonText: '确认删除', cancelButtonText: '取消' },
    ).catch(() => false)
    if (!confirmed) {
      return false
    }
    try {
      await api.remove(row.id)
      ElMessage.success('已删除')
      await load()
      return true
    } catch (error) {
      ElMessage.error(
        error instanceof ApiError
          ? `${error.message}${error.code ? `（${error.code}）` : ''}`
          : '删除失败',
      )
      return false
    }
  }

  watch(page, () => void load())
  watch(pageSize, () => {
    page.value = 1
    void load()
  })

  return {
    rows,
    total,
    page,
    pageSize,
    ordering,
    filters,
    loading,
    errorMessage,
    load,
    resetFilters,
    onSortChange,
    toggleActive,
    activeFlag,
    canToggleActive,
    canRemove,
    remove,
    buildParams,
  }
}