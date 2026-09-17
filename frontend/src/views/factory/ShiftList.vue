<template>
  <entity-list-page
    title="班次"
    entity-label="班次"
    description="支持跨夜班：结束时间早于或等于开始时间时由后端推导为跨夜班。跨夜班总时长 = 24 小时 − 开始时间 + 结束时间 − 休息时长。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :permissions="{ create: 'factory.shift.create', update: 'factory.shift.update' }"
    default-ordering="code"
    search-placeholder="搜索班次编码或名称"
  >
    <template #column-cross_day="{ row }">
      <el-tag :type="row.cross_day ? 'warning' : 'info'" size="small" effect="light">
        {{ row.cross_day ? '跨夜班' : '正常班' }}
      </el-tag>
    </template>
    <template #column-duration_hours="{ row }">
      {{ row.duration_hours }} 小时
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { shiftApi } from '@/api/endpoints'
import { companyOptions } from '@/composables/optionLoaders'

const api = shiftApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '班次编码', width: 120, sortable: true },
  { prop: 'name', label: '班次名称', minWidth: 140 },
  { prop: 'company_name', label: '所属公司', width: 180 },
  { prop: 'start_time', label: '上班时间', width: 110 },
  { prop: 'end_time', label: '下班时间', width: 110 },
  { prop: 'cross_day', label: '班次类型', width: 110 },
  { prop: 'break_minutes', label: '休息(分钟)', width: 110 },
  { prop: 'duration_hours', label: '有效工时', width: 110 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
])

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '班次编码', required: true },
  { prop: 'name', label: '班次名称', required: true },
  { prop: 'start_time', label: '上班时间', required: true, placeholder: 'HH:MM:SS，例如 20:00:00' },
  { prop: 'end_time', label: '下班时间', required: true, placeholder: 'HH:MM:SS，例如 04:00:00' },
  {
    prop: 'break_minutes',
    label: '休息(分钟)',
    type: 'number',
    help: '休息时长必须小于班次总时长',
  },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>