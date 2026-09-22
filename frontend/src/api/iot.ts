import { get, post } from '@/api/http'
import type { QueryParams } from '@/api/crud'
import type {
  IoTMonitorPayload,
  IoTStatisticsPayload,
  IoTTokenRotateResult,
} from '@/types/models'

/**
 * 设备数采的只读聚合接口与设备令牌动作。
 *
 * 「设备监控」是跨设备的实时状态聚合（在线数、离线数、最新读数、近 24 小时失败报文），
 * 没有对应的业务单据，因此不走通用 CRUD 客户端。
 */

export const iotMonitorApi = {
  load: (params: QueryParams = {}) => get<IoTMonitorPayload>('/iot/monitor/', { params }),
}

/**
 * 采集统计（只读聚合）。
 *
 * 后端按「测点 × 时间桶」实时聚合采集明细，不落汇总表——设备补发或重传之后
 * 统计立刻跟着变，页面上的数字能回到「采集读数」逐条核对。分桶按业务时区截断。
 */
export const iotStatisticsApi = {
  load: (params: QueryParams = {}) => get<IoTStatisticsPayload>('/iot/statistics/', { params }),
}

export const iotGatewayActions = {
  /**
   * 生成 / 轮换设备令牌。
   *
   * 返回的 `token` 是**唯一的明文**，只能在这里拿到一次；平台只保存摘要，
   * 界面必须提示用户立即写入设备侧。
   */
  rotateToken: (id: number, reason = '') =>
    post<IoTTokenRotateResult>(`/iot/gateways/${id}/rotate-token/`, { reason }),
}
