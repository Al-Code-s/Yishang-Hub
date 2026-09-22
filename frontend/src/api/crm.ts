import { get } from '@/api/http'
import type { QueryParams } from '@/api/crud'
import type { ComplaintStatistics, ProductReviewStatistics } from '@/types/models'

/**
 * 客户投诉与产品评价的统计接口。
 *
 * 统计由后端**按明细实时聚合**（不落汇总表），因此是只读的自定义动作，
 * 不走通用 CRUD 客户端。平均满意度只按已回访的投诉计算，
 * 未回访的条数单独返回（`unrated_total`），不会用 0 分把平均值拉低。
 */

export const complaintStatisticsApi = {
  load: (params: QueryParams = {}) =>
    get<ComplaintStatistics>('/crm/complaints/statistics/', { params }),
}

export const productReviewStatisticsApi = {
  load: (params: QueryParams = {}) =>
    get<ProductReviewStatistics>('/crm/product-reviews/statistics/', { params }),
}
