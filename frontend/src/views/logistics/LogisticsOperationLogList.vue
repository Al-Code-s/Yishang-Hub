<template>
  <entity-list-page
    title="操作日志"
    entity-label="操作日志"
    description="自动化设备与物流任务的每一步动作都会在这里留痕：创建、下发、开始执行、完成、取消，以及设备状态变更。日志由服务层写入，不提供新增与修改，因此不会出现「日志被改过」的情况。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :detail-fields="detailFields"
    search-placeholder="搜索说明、设备编码或任务编号"
    default-ordering="-occurred_at"
    :toggleable="false"
    readonly
    empty-text="暂无操作日志"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { logisticsOperationLogApi } from '@/api/endpoints'
import { automationDeviceOptions, companyOptions, employeeOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatDateTime } from '@/utils/format'

const api = logisticsOperationLogApi as never
const meta = useMetaStore()

const columns: ProTableColumn[] = [
  {
    prop: 'occurred_at',
    label: '发生时间',
    width: 170,
    sortable: true,
    formatter: (row) => formatDateTime(String(row.occurred_at ?? '')),
  },
  { prop: 'action', label: '动作', width: 120 },
  { prop: 'device_code', label: '设备编码', width: 150 },
  { prop: 'device_name', label: '设备名称', minWidth: 140 },
  { prop: 'task_no', label: '任务编号', width: 160 },
  { prop: 'operator_name', label: '操作人', width: 110 },
  { prop: 'detail', label: '说明', minWidth: 220 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'action', label: '动作', type: 'select' as const, options: meta.options('logistics_log_actions') },
  { prop: 'device_id', label: '设备', type: 'select' as const, optionsLoader: automationDeviceOptions },
  { prop: 'operator_id', label: '操作人', type: 'select' as const, optionsLoader: employeeOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'business_label', label: '业务对象' },
]
</script>
