import { get } from '@/api/http'
import type { QueryParams } from '@/api/crud'
import type { SupplierEvaluationStatistics } from '@/types/models'

/**
 * 供应商评价统计接口。
 *
 * 统计由后端**按明细实时聚合**（不落汇总表），因此是只读的自定义动作，
 * 不走通用 CRUD 客户端。平均分只统计口径完整的评价，
 * 缺数据（未评级）的条数单独返回（`ungraded_total`），不会用缺项总分把平均值拉低。
 */

export const supplierEvaluationStatisticsApi = {
  load: (params: QueryParams = {}) =>
    get<SupplierEvaluationStatistics>('/srm/supplier-evaluations/statistics/', { params }),
}
