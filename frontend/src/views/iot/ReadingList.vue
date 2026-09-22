<template>
  <entity-list-page
    title="采集读数"
    description="每一条读数都带设备时间、接收时间、数值、单位、数据质量与来源。读数只增不改：设备重发同一时刻的数据不会产生第二条记录（按「测点 + 设备时间」判重），需要核对时请对照「采集日志」里的原始报文。模拟读数会标注「模拟」，不与真实采集数据混用。"
    entity-label="采集读数"
    readonly
    :api="api"
    :columns="columns"
    :filters="filters"
    search-placeholder="搜索测点编码、名称或设备编码"
    default-ordering="-device_time"
    :toggleable="false"
    empty-text="暂无采集读数。设备成功上报后才会产生读数。"
  >
    <template #column-quality="{ row }">
      <el-tag :type="qualityTagType(String(row.quality))" size="small" effect="light">
        {{ row.quality_display || meta.label('iot_reading_qualities', String(row.quality)) }}
      </el-tag>
    </template>
    <template #column-source="{ row }">
      {{ row.source_display || meta.label('iot_reading_sources', String(row.source)) }}
    </template>
    <template #column-unit="{ row }">
      {{ row.unit || '-' }}
    </template>
    <template #column-is_simulated="{ row }">
      <el-tag v-if="row.is_simulated" type="warning" size="small" effect="dark">模拟</el-tag>
      <span v-else class="ys-muted">真实</span>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FilterDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { iotReadingApi } from '@/api/endpoints'
import { iotGatewayOptions, iotPointOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatDateTime } from '@/utils/format'

const meta = useMetaStore()
const api = iotReadingApi as never

function qualityTagType(quality: string): 'success' | 'warning' | 'danger' {
  if (quality === 'good') return 'success'
  if (quality === 'bad') return 'danger'
  return 'warning'
}

const columns: ProTableColumn[] = [
  {
    prop: 'device_time',
    label: '设备时间',
    width: 170,
    sortable: true,
    formatter: (row) => formatDateTime(String(row.device_time ?? '')),
  },
  {
    prop: 'received_at',
    label: '接收时间',
    width: 170,
    formatter: (row) => formatDateTime(String(row.received_at ?? '')),
  },
  { prop: 'gateway_code', label: '设备编码', width: 140 },
  { prop: 'point_code', label: '测点编码', width: 140 },
  { prop: 'point_name', label: '测点名称', minWidth: 150 },
  { prop: 'quantity', label: '物理量', width: 100 },
  { prop: 'value', label: '读数', width: 130 },
  { prop: 'unit', label: '单位', width: 80 },
  { prop: 'quality', label: '数据质量', width: 100 },
  { prop: 'source', label: '数据来源', width: 110 },
  { prop: 'is_simulated', label: '数据标识', width: 100 },
]

const filters = computed<FilterDef[]>(() => [
  { prop: 'gateway_id', label: '数采设备', type: 'select' as const, optionsLoader: iotGatewayOptions },
  { prop: 'point_id', label: '测点', type: 'select' as const, optionsLoader: iotPointOptions },
  {
    prop: 'quality',
    label: '数据质量',
    type: 'select' as const,
    options: meta.options('iot_reading_qualities'),
  },
  {
    prop: 'source',
    label: '数据来源',
    type: 'select' as const,
    options: meta.options('iot_reading_sources'),
  },
])
</script>
