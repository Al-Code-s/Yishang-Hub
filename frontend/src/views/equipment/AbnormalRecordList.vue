<template>
  <entity-list-page
    title="异常记录"
    entity-label="异常记录"
    description="异常记录是异常处理完成后沉淀的事实：谁在什么时候、做了什么处理、结果如何。由「异常任务」关闭时自动生成，也可以补录历史异常。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.abnormal_record.create', update: 'equipment.abnormal_record.update' }"
    search-placeholder="搜索记录编号、设备或处理结果"
    default-ordering="-handle_date"
    :toggleable="false"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { abnormalRecordApi } from '@/api/endpoints'
import { abnormalTypeOptions, employeeOptions, equipmentOptions } from '@/composables/optionLoaders'

const api = abnormalRecordApi as never

const columns: ProTableColumn[] = [
  { prop: 'record_no', label: '记录编号', width: 160, sortable: true },
  { prop: 'abnormal_type_name', label: '异常类型', width: 140 },
  { prop: 'equipment_name', label: '设备', minWidth: 150 },
  { prop: 'handle_date', label: '处理日期', width: 120, sortable: true },
  { prop: 'handler_name', label: '处理人', width: 110 },
  { prop: 'action', label: '处理动作', minWidth: 180 },
  { prop: 'result', label: '处理结果', minWidth: 180 },
]

const filters = computed(() => [
  {
    prop: 'abnormal_type_id',
    label: '异常类型',
    type: 'select' as const,
    optionsLoader: abnormalTypeOptions,
  },
  { prop: 'equipment_id', label: '设备', type: 'select' as const, optionsLoader: equipmentOptions },
  { prop: 'handler_id', label: '处理人', type: 'select' as const, optionsLoader: employeeOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'abnormal_type_id',
    label: '异常类型',
    type: 'select',
    required: true,
    optionsLoader: abnormalTypeOptions,
  },
  { prop: 'equipment_id', label: '设备', type: 'select', optionsLoader: equipmentOptions },
  { prop: 'handle_date', label: '处理日期', type: 'date', required: true },
  { prop: 'handler_id', label: '处理人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'action', label: '处理动作', type: 'textarea', span: 24 },
  { prop: 'result', label: '处理结果', type: 'textarea', span: 24 },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>