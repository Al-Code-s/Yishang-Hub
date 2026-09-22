<template>
  <entity-list-page
    title="采集日志"
    description="每一次上报都留一行，包括重复报文与处理失败的报文——这是排查「设备说发了、平台说没收到」时唯一可信的依据。重复报文按「设备 + 消息 ID」判定；处理失败会在「处理说明」里写明原因。本页只读，不提供新增、修改或删除。"
    entity-label="采集报文"
    readonly
    :api="api"
    :columns="columns"
    :filters="filters"
    search-placeholder="搜索消息 ID、设备编码或处理说明"
    default-ordering="-received_at"
    :toggleable="false"
    :action-width="120"
    empty-text="暂无采集报文。设备开始上报后这里才会有记录。"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ row.status_display || meta.label('iot_message_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-is_simulated="{ row }">
      <el-tag v-if="row.is_simulated" type="warning" size="small" effect="dark">模拟</el-tag>
      <span v-else class="ys-muted">真实</span>
    </template>
    <template #column-error_message="{ row }">
      <span v-if="row.error_message">{{ row.error_message }}</span>
      <span v-else class="ys-muted">-</span>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FilterDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { iotMessageApi } from '@/api/endpoints'
import { iotGatewayOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatDateTime } from '@/utils/format'

const meta = useMetaStore()
const api = iotMessageApi as never

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'processed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'duplicated') return 'warning'
  return 'info'
}

const columns: ProTableColumn[] = [
  {
    prop: 'received_at',
    label: '接收时间',
    width: 170,
    sortable: true,
    formatter: (row) => formatDateTime(String(row.received_at ?? '')),
  },
  { prop: 'gateway_code', label: '设备编码', width: 140 },
  { prop: 'gateway_name', label: '设备名称', minWidth: 140 },
  { prop: 'message_id', label: '消息 ID', width: 160 },
  { prop: 'point_count', label: '测点数', width: 90 },
  { prop: 'status', label: '处理状态', width: 110 },
  { prop: 'error_message', label: '处理说明', minWidth: 200 },
  { prop: 'source_ip', label: '来源 IP', width: 140 },
  { prop: 'is_simulated', label: '数据标识', width: 100 },
]

const filters = computed<FilterDef[]>(() => [
  { prop: 'gateway_id', label: '数采设备', type: 'select' as const, optionsLoader: iotGatewayOptions },
  {
    prop: 'status',
    label: '处理状态',
    type: 'select' as const,
    options: meta.options('iot_message_statuses'),
  },
])
</script>
