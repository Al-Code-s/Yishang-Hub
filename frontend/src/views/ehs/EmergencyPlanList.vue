<template>
  <entity-list-page
    title="应急预案"
    entity-label="应急预案"
    description="火灾、生产安全事故、突发环境事件与职业健康预案的台账，含响应级别、评审日期与演练周期。系统按演练周期算出下次演练日期，消防演练记录可以关联到对应预案。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.emergency_plan.create', update: 'ehs.emergency_plan.update' }"
    search-placeholder="搜索预案编号或名称"
    default-ordering="code"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { emergencyPlanApi } from '@/api/endpoints'
import { companyOptions, employeeOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const api = emergencyPlanApi as never
const meta = useMetaStore()

const columns: ProTableColumn[] = [
  { prop: 'code', label: '预案编号', width: 150, sortable: true },
  { prop: 'name', label: '预案名称', minWidth: 200 },
  { prop: 'plan_type', label: '预案类型', width: 140 },
  { prop: 'response_level', label: '响应级别', width: 110 },
  { prop: 'issue_date', label: '发布日期', width: 120 },
  { prop: 'review_date', label: '评审日期', width: 120 },
  { prop: 'drill_cycle_days', label: '演练周期（天）', width: 140 },
  { prop: 'next_drill_date', label: '下次演练日期', width: 140, sortable: true },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'is_active', label: '启用', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'plan_type', label: '预案类型', type: 'select' as const, options: meta.options('emergency_plan_types') },
  { prop: 'response_level', label: '响应级别', type: 'select' as const, options: meta.options('response_levels') },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('regulation_statuses') },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'owner_employee_name', label: '负责人' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '预案编号', help: '留空时由系统按编号规则自动生成', onlyOnUpdate: true },
  { prop: 'name', label: '预案名称', required: true, span: 24 },
  { prop: 'plan_type', label: '预案类型', type: 'select', options: meta.options('emergency_plan_types'), defaultValue: "fire" },
  { prop: 'response_level', label: '响应级别', type: 'select', options: meta.options('response_levels'), defaultValue: "company" },
  { prop: 'issue_date', label: '发布日期', type: 'date' },
  { prop: 'review_date', label: '评审日期', type: 'date' },
  { prop: 'drill_cycle_days', label: '演练周期（天）', type: 'number', defaultValue: 365 },
  { prop: 'next_drill_date', label: '下次演练日期', type: 'date' },
  { prop: 'status', label: '状态', type: 'select', options: meta.options('regulation_statuses'), defaultValue: "draft" },
  { prop: 'owner_employee_id', label: '负责人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
