<template>
  <entity-list-page
    title="安全培训"
    entity-label="安全培训"
    description="三级教育、专项培训、复训与演练培训的台账，记录计划日期、实际开展日期、学时与考核通过人数。培训编号留空时按编号规则自动生成。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.training.create', update: 'ehs.training.update' }"
    search-placeholder="搜索培训编号、主题或讲师"
    default-ordering="-planned_date"
    :toggleable="false"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { safetyTrainingApi } from '@/api/endpoints'
import { companyOptions, departmentOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatDecimal } from '@/utils/decimal'

const api = safetyTrainingApi as never
const meta = useMetaStore()

const columns: ProTableColumn[] = [
  { prop: 'training_no', label: '培训编号', width: 150, sortable: true },
  { prop: 'topic', label: '培训主题', minWidth: 200 },
  { prop: 'training_type', label: '培训类型', width: 120 },
  { prop: 'trainer', label: '讲师', width: 110 },
  { prop: 'department_name', label: '组织部门', width: 140 },
  { prop: 'planned_date', label: '计划日期', width: 120, sortable: true },
  { prop: 'actual_date', label: '实际日期', width: 120 },
  { prop: 'duration_hours', label: '学时', width: 90, formatter: (row) => formatDecimal(row.duration_hours as string) },
  { prop: 'participant_count', label: '参加人数', width: 110 },
  { prop: 'passed_count', label: '通过人数', width: 110 },
  { prop: 'status', label: '状态', width: 100 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'training_type', label: '培训类型', type: 'select' as const, options: meta.options('training_types') },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('training_statuses') },
  { prop: 'department_id', label: '组织部门', type: 'select' as const, optionsLoader: departmentOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'training_no', label: '培训编号', help: '留空时由系统按编号规则自动生成', onlyOnUpdate: true },
  { prop: 'topic', label: '培训主题', required: true, span: 24 },
  { prop: 'training_type', label: '培训类型', type: 'select', options: meta.options('training_types'), defaultValue: "induction" },
  { prop: 'trainer', label: '讲师' },
  { prop: 'department_id', label: '组织部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'planned_date', label: '计划日期', type: 'date' },
  { prop: 'actual_date', label: '实际日期', type: 'date' },
  { prop: 'duration_hours', label: '学时', type: 'decimal', defaultValue: "0" },
  { prop: 'participant_count', label: '参加人数', type: 'number', defaultValue: 0 },
  { prop: 'passed_count', label: '通过人数', type: 'number', defaultValue: 0, help: '通过人数不能大于参加人数' },
  { prop: 'status', label: '状态', type: 'select', options: meta.options('training_statuses'), defaultValue: "planned" },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
