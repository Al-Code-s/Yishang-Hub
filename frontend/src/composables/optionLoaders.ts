import {
  colorApi,
  companyApi,
  customerApi,
  departmentApi,
  employeeApi,
  factoryApi,
  lineApi,
  locationApi,
  materialApi,
  materialCategoryApi,
  roleApi,
  shiftApi,
  sizeApi,
  stationApi,
  styleApi,
  supplierApi,
  teamApi,
  uomApi,
  userApi,
  warehouseApi,
  workshopApi,
  zoneApi,
} from '@/api/endpoints'
import type { EnumOption } from '@/types/models'

/**
 * 下拉选项加载器。
 *
 * 规则：
 * - 统一在 `page_size` 上限内取数（后端 PAGE_SIZE_MAX 默认 200），超过会被拒绝；
 * - 只返回启用中的数据，避免把已停用主数据带进新单据；
 * - 选项值使用主键（数字），显示文本为「编码 名称」。
 *
 * 这里刻意不对返回行做强类型约束：各资源的单元格字段不同，强约束只会让
 * 调用方到处写断言。真正需要类型的地方在页面里，不在选项加载器。
 */

interface ListParams {
  /** 需要索引签名，才能与通用 CRUD 的 QueryParams 兼容 */
  [key: string]: unknown
  page_size: number
  is_active: boolean
  ordering?: string
}

type ListLoader = (params: ListParams) => Promise<{ results: unknown[] }>

function toOptions(rows: unknown[], primary: string, secondary?: string): EnumOption[] {
  return rows.map((row) => {
    const record = (row ?? {}) as Record<string, unknown>
    const id = Number(record.id)
    const primaryText = record[primary] === null || record[primary] === undefined ? '' : String(record[primary])
    const secondaryText =
      secondary && record[secondary] !== null && record[secondary] !== undefined
        ? String(record[secondary])
        : ''
    return {
      value: id,
      label: secondaryText ? `${primaryText} ${secondaryText}` : primaryText,
    }
  })
}

async function loadAll(loader: ListLoader, primary: string, secondary?: string): Promise<EnumOption[]> {
  const page = await loader({ page_size: 200, is_active: true, ordering: 'code' })
  return toOptions(page.results, primary, secondary)
}

export const companyOptions = (): Promise<EnumOption[]> => loadAll(companyApi.list, 'code', 'name')

export const departmentOptions = (): Promise<EnumOption[]> =>
  loadAll(departmentApi.list, 'code', 'name')

export const factoryOptions = (): Promise<EnumOption[]> => loadAll(factoryApi.list, 'code', 'name')

export const workshopOptions = (): Promise<EnumOption[]> => loadAll(workshopApi.list, 'code', 'name')

export const lineOptions = (): Promise<EnumOption[]> => loadAll(lineApi.list, 'code', 'name')

export const stationOptions = (): Promise<EnumOption[]> => loadAll(stationApi.list, 'code', 'name')

export const employeeOptions = (): Promise<EnumOption[]> =>
  loadAll(employeeApi.list, 'employee_no', 'name')

export const shiftOptions = (): Promise<EnumOption[]> => loadAll(shiftApi.list, 'code', 'name')

export const teamOptions = (): Promise<EnumOption[]> => loadAll(teamApi.list, 'code', 'name')

export const roleOptions = (): Promise<EnumOption[]> => loadAll(roleApi.list, 'code', 'name')

export const userOptions = (): Promise<EnumOption[]> =>
  loadAll(userApi.list, 'username', 'display_name')

export const materialCategoryOptions = (): Promise<EnumOption[]> =>
  loadAll(materialCategoryApi.list, 'code', 'name')

export const uomOptions = (): Promise<EnumOption[]> => loadAll(uomApi.list, 'code', 'name')

export const materialOptions = (): Promise<EnumOption[]> => loadAll(materialApi.list, 'code', 'name')

export const styleOptions = (): Promise<EnumOption[]> => loadAll(styleApi.list, 'code', 'name')

export const colorOptions = (): Promise<EnumOption[]> => loadAll(colorApi.list, 'code', 'name')

export const sizeOptions = (): Promise<EnumOption[]> => loadAll(sizeApi.list, 'code', 'name')

export const warehouseOptions = (): Promise<EnumOption[]> => loadAll(warehouseApi.list, 'code', 'name')

export const zoneOptions = (): Promise<EnumOption[]> => loadAll(zoneApi.list, 'code', 'name')

export const locationOptions = (): Promise<EnumOption[]> => loadAll(locationApi.list, 'code', 'name')

export const customerOptions = (): Promise<EnumOption[]> => loadAll(customerApi.list, 'code', 'name')

export const supplierOptions = (): Promise<EnumOption[]> => loadAll(supplierApi.list, 'code', 'name')
