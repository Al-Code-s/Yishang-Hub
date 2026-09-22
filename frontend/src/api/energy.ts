import { download, get, post } from '@/api/http'
import type { QueryParams } from '@/api/crud'
import type {
  EnergyHomeSummary,
  EnergyMonitorRow,
  EnergyReportPayload,
  EnergyRunRecord,
  EnergyStatisticsPayload,
  MeterReading,
  Paginated,
} from '@/types/models'

/**
 * 能源管理的只读聚合接口。
 *
 * 首页、设备监控、能耗统计与能耗报表都是后端实时聚合出来的结果，
 * 没有对应的业务表，因此不套用通用 CRUD 客户端。
 */

/** 能源首页：今日/本月用量与费用、仪表状态、报警与趋势。 */
export const energyHomeApi = {
  load: (params: QueryParams = {}) => get<EnergyHomeSummary>('/ems/home/', { params }),
}

/** 设备监控：仪表状态 + 最近抄表 + 本月用量 + 未处理报警数。 */
export const energyMonitorApi = {
  list: (params: QueryParams = {}) =>
    get<Paginated<EnergyMonitorRow>>('/ems/monitor/', { params }),
}

/** 能耗统计：按介质、区域、部门、设备、仪表或时间维度聚合。 */
export const energyStatisticsApi = {
  load: (params: QueryParams = {}) =>
    get<EnergyStatisticsPayload>('/ems/statistics/', { params }),
}

/** 能耗报表：日 / 月 / 年用能统计，支持尖峰平谷分时段与 Excel 导出。 */
export const energyReportApi = {
  load: (params: QueryParams = {}) => get<EnergyReportPayload>('/ems/report/', { params }),
  /** 导出真实 xlsx 文件流（后端用 openpyxl 生成，不是改后缀的 CSV）。 */
  exportXlsx: (params: QueryParams = {}) =>
    download('/ems/report/', { params: { ...params, export: 'xlsx' } }),
}

/**
 * 抄表录入、开始运行记录、离线扫描都没有实例 id（作用于集合），
 * 不能用通用 CRUD 客户端的 `action(id, ...)` 拼 URL。
 */
export const energyActions = {
  recordReading: (payload: Record<string, unknown>) =>
    post<MeterReading>('/ems/readings/record/', payload),
  startRun: (payload: Record<string, unknown>) =>
    post<EnergyRunRecord>('/ems/run-records/start/', payload),
  scanOffline: (companyId?: number | null) =>
    post<{ created: number; alarms: { id: number; alarm_no: string; message: string }[] }>(
      '/ems/alarms/scan-offline/',
      companyId ? { company_id: companyId } : {},
    ),
}

/** 触发浏览器保存一个已下载的二进制文件。 */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}
