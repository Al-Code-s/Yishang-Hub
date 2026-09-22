<template>
  <entity-list-page
    title="维修记录"
    entity-label="维修记录"
    description="维修记录是维修完成后沉淀的事实：故障原因、维修措施、领用备件说明、停机时长与费用都在这里。由「维修任务」完成时自动生成，也可以补录历史维修。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.repair_record.create', update: 'equipment.repair_record.update' }"
    search-placeholder="搜索记录编号、设备、故障原因或维修措施"
    default-ordering="-repair_date"
    :toggleable="false"
    :page-size="20"
  >
    <template #column-cost="{ row }">{{ formatAmount(row.cost as string) }}</template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { repairRecordApi } from '@/api/endpoints'
import { employeeOptions, equipmentOptions } from '@/composables/optionLoaders'
import { formatAmount } from '@/utils/decimal'

const api = repairRecordApi as never

const columns: ProTableColumn[] = [
  { prop: 'record_no', label: '记录编号', width: 160, sortable: true },
  { prop: 'equipment_name', label: '设备', minWidth: 160 },
  { prop: 'task_no', label: '来源任务', width: 150 },
  { prop: 'repair_date', label: '维修日期', width: 120, sortable: true },
  { prop: 'repairer_name', label: '维修人', width: 110 },
  { prop: 'fault_reason', label: '故障原因', minWidth: 180 },
  { prop: 'downtime_minutes', label: '停机时长（分钟）', width: 140 },
  { prop: 'cost', label: '维修费用', width: 110 },
]

const filters = computed(() => [
  { prop: 'equipment_id', label: '设备', type: 'select' as const, optionsLoader: equipmentOptions },
  { prop: 'repairer_id', label: '维修人', type: 'select' as const, optionsLoader: employeeOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'solution', label: '维修措施' },
  { prop: 'parts_used', label: '领用备件说明' },
  { prop: 'result', label: '维修结果' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'equipment_id',
    label: '设备',
    type: 'select',
    required: true,
    optionsLoader: equipmentOptions,
  },
  { prop: 'repair_date', label: '维修日期', type: 'date', required: true },
  { prop: 'repairer_id', label: '维修人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'fault_reason', label: '故障原因', type: 'textarea', span: 24 },
  { prop: 'solution', label: '维修措施', type: 'textarea', span: 24 },
  {
    prop: 'parts_used',
    label: '领用备件说明',
    type: 'textarea',
    span: 24,
    help: '如需扣减库存，请到仓储模块登记领料出库',
  },
  {
    prop: 'downtime_minutes',
    label: '停机时长（分钟）',
    type: 'number',
    defaultValue: 0,
  },
  { prop: 'cost', label: '维修费用', type: 'decimal', defaultValue: '0' },
  { prop: 'result', label: '维修结果', type: 'textarea', span: 24 },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>