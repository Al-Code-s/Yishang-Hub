<template>
  <entity-list-page
    title="操作日志"
    entity-label="操作日志"
    description="安全环保各模块的状态推进都会在这里留痕：整改、验收、调查、审批、关闭等。日志由服务层在同一事务里写入，不提供新增与修改接口，因此可以作为追溯依据。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :detail-fields="detailFields"
    search-placeholder="搜索说明、业务编号或动作"
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
import { ehsOperationLogApi } from '@/api/endpoints'
import { companyOptions, employeeOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatDateTime } from '@/utils/format'

const api = ehsOperationLogApi as never
const meta = useMetaStore()

const columns: ProTableColumn[] = [
  {
    prop: 'occurred_at',
    label: '发生时间',
    width: 170,
    sortable: true,
    formatter: (row) => formatDateTime(String(row.occurred_at ?? '')),
  },
  { prop: 'domain', label: '业务领域', width: 130 },
  { prop: 'business_type', label: '业务对象', width: 160 },
  { prop: 'business_label', label: '业务编号', width: 160 },
  { prop: 'action', label: '动作', width: 130 },
  { prop: 'operator_name', label: '操作人', width: 110 },
  { prop: 'detail', label: '说明', minWidth: 240 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'domain', label: '业务领域', type: 'select' as const, options: meta.options('ehs_domains') },
  { prop: 'operator_id', label: '操作人', type: 'select' as const, optionsLoader: employeeOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
]
</script>
