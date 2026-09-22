<template>
  <entity-list-page
    title="消防演练"
    entity-label="消防演练"
    description="灭火实操、疏散演练与联合演练记录：计划日期、实际开展日期、组织者、参加人数、用时、评估结论与发现问题。演练编号留空时按编号规则自动生成；关联应急预案后可以自动核对演练周期是否达标。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.fire_drill.create', update: 'ehs.fire_drill.update' }"
    search-placeholder="搜索演练编号、主题或组织者"
    default-ordering="-planned_date"
    :toggleable="false"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { fireDrillApi } from '@/api/endpoints'
import { companyOptions, emergencyPlanOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const api = fireDrillApi as never
const meta = useMetaStore()

const columns: ProTableColumn[] = [
  { prop: 'drill_no', label: '演练编号', width: 150, sortable: true },
  { prop: 'topic', label: '演练主题', minWidth: 180 },
  { prop: 'drill_type', label: '演练类型', width: 120 },
  { prop: 'plan_name', label: '关联预案', width: 160 },
  { prop: 'planned_date', label: '计划日期', width: 120 },
  { prop: 'actual_date', label: '实际日期', width: 120 },
  { prop: 'organizer', label: '组织者', width: 120 },
  { prop: 'participant_count', label: '参加人数', width: 110 },
  { prop: 'duration_minutes', label: '用时（分钟）', width: 120 },
  { prop: 'assessment', label: '评估结论', minWidth: 160 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'drill_type', label: '演练类型', type: 'select' as const, options: meta.options('fire_drill_types') },
  { prop: 'plan_id', label: '关联预案', type: 'select' as const, optionsLoader: emergencyPlanOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'issues', label: '发现问题' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'drill_no', label: '演练编号', help: '留空时由系统按编号规则自动生成', onlyOnUpdate: true },
  { prop: 'topic', label: '演练主题', required: true, span: 24 },
  { prop: 'drill_type', label: '演练类型', type: 'select', options: meta.options('fire_drill_types'), defaultValue: "extinguisher" },
  { prop: 'plan_id', label: '关联预案', type: 'select', optionsLoader: emergencyPlanOptions },
  { prop: 'planned_date', label: '计划日期', type: 'date' },
  { prop: 'actual_date', label: '实际日期', type: 'date' },
  { prop: 'organizer', label: '组织者' },
  { prop: 'participant_count', label: '参加人数', type: 'number', defaultValue: 0 },
  { prop: 'duration_minutes', label: '用时（分钟）', type: 'number', defaultValue: 0 },
  { prop: 'assessment', label: '评估结论', type: 'textarea', span: 24 },
  { prop: 'issues', label: '发现问题', type: 'textarea', span: 24 },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
