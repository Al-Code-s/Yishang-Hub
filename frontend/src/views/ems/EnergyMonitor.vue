<template>
  <entity-list-page
    title="设备监控"
    entity-label="计量设备"
    description="按仪表展示当前状态、最近一次抄表读数与用量、本月累计用量和未关闭报警数。只有勾选「纳入监控」的仪表会出现在这里；数据全部来自抄表记录实时汇总，不做人工填报。"
    :api="api"
    :columns="columns"
    :filters="filters"
    search-placeholder="搜索仪表编码、名称或安装位置"
    default-ordering="code"
    readonly
    :page-size="20"
    :action-width="120"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { energyMonitorApi } from '@/api/energy'
import { companyOptions, energyAreaOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatDecimal } from '@/utils/decimal'
import { formatDateTime } from '@/utils/format'

const meta = useMetaStore()
const api = energyMonitorApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '仪表编码', width: 150, sortable: true },
  { prop: 'name', label: '仪表名称', minWidth: 150 },
  { prop: 'medium', label: '介质', width: 80 },
  { prop: 'status', label: '状态', width: 90 },
  { prop: 'area_name', label: '所属区域', width: 130 },
  { prop: 'equipment_name', label: '关联设备', width: 140 },
  { prop: 'location', label: '安装位置', width: 140 },
  {
    prop: 'last_reading',
    label: '最近读数',
    width: 120,
    formatter: (row) => formatDecimal(row.last_reading as string),
  },
  { prop: 'last_reading_at', label: '最近抄表时间', width: 170, formatter: (row) => formatDateTime(String(row.last_reading_at ?? '')) },
  {
    prop: 'month_consumption',
    label: '本月用量',
    width: 120,
    formatter: (row) => formatDecimal(row.month_consumption as string),
  },
  { prop: 'unit', label: '单位', width: 80 },
  { prop: 'open_alarm_count', label: '未关闭报警', width: 110 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'medium', label: '介质', type: 'select' as const, options: meta.options('energy_media') },
  { prop: 'area_id', label: '所属区域', type: 'select' as const, optionsLoader: energyAreaOptions },
  { prop: 'status', label: '仪表状态', type: 'select' as const, options: meta.options('meter_statuses') },
])
</script>
