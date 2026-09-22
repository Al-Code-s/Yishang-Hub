<template>
  <entity-list-page
    title="保养记录"
    entity-label="保养记录"
    description="保养记录是已经发生的保养事实。由「保养任务」完成时自动生成，也可以在设备突然保养后手工补录。记录写完即历史，不参与排期。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.maintenance_record.create', update: 'equipment.maintenance_record.update' }"
    search-placeholder="搜索记录编号、设备或保养内容"
    default-ordering="-maintain_date"
    :toggleable="false"
    :page-size="20"
  >
    <template #column-is_qualified="{ row }">
      <el-tag v-if="row.is_qualified" type="success" size="small" effect="light">合格</el-tag>
      <el-tag v-else type="danger" size="small" effect="light">不合格</el-tag>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { maintenanceRecordApi } from '@/api/endpoints'
import { employeeOptions, equipmentOptions } from '@/composables/optionLoaders'
import { maintenanceItemOptions } from '@/composables/optionLoaders'
import { formatAmount } from '@/utils/decimal'

const api = maintenanceRecordApi as never

const columns: ProTableColumn[] = [
  { prop: 'record_no', label: '记录编号', width: 160, sortable: true },
  { prop: 'equipment_name', label: '设备', minWidth: 160 },
  { prop: 'item_name', label: '保养项目', width: 140 },
  { prop: 'maintain_date', label: '保养日期', width: 120, sortable: true },
  { prop: 'executor_name', label: '保养人', width: 110 },
  { prop: 'is_qualified', label: '验收', width: 90 },
  {
    prop: 'cost',
    label: '保养费用',
    width: 110,
    formatter: (row) => formatAmount(row.cost as string),
  },
  { prop: 'content', label: '保养内容', minWidth: 180 },
]

const filters = computed(() => [
  { prop: 'equipment_id', label: '设备', type: 'select' as const, optionsLoader: equipmentOptions },
  {
    prop: 'item_id',
    label: '保养项目',
    type: 'select' as const,
    optionsLoader: maintenanceItemOptions,
  },
  { prop: 'executor_id', label: '保养人', type: 'select' as const, optionsLoader: employeeOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'result', label: '保养结果' },
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
  { prop: 'maintain_date', label: '保养日期', type: 'date', required: true },
  {
    prop: 'item_id',
    label: '保养项目',
    type: 'select',
    optionsLoader: maintenanceItemOptions,
  },
  { prop: 'executor_id', label: '保养人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'content', label: '保养内容', type: 'textarea', span: 24 },
  { prop: 'result', label: '保养结果', type: 'textarea', span: 24 },
  { prop: 'is_qualified', label: '验收合格', type: 'switch' },
  { prop: 'cost', label: '保养费用', type: 'decimal', defaultValue: '0' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>