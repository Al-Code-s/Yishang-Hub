<template>
  <entity-list-page
    title="安全制度"
    entity-label="安全制度"
    description="安全生产管理制度、操作规程与应急制度的台账，含版本号、发布机构与生效日期。制度编号留空时按编号规则自动生成；修订后建议新增一条并把旧记录的版本状态改为「已修订」，历史版本的生效区间才能追溯。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.regulation.create', update: 'ehs.regulation.update' }"
    search-placeholder="搜索制度编号、名称或发布机构"
    default-ordering="code"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { safetyRegulationApi } from '@/api/endpoints'
import { companyOptions, departmentOptions, employeeOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const api = safetyRegulationApi as never
const meta = useMetaStore()

const columns: ProTableColumn[] = [
  { prop: 'code', label: '制度编号', width: 150, sortable: true },
  { prop: 'name', label: '制度名称', minWidth: 200 },
  { prop: 'category', label: '制度类别', width: 110 },
  { prop: 'version_no', label: '版本号', width: 90 },
  { prop: 'issue_org', label: '发布机构', width: 150 },
  { prop: 'issue_date', label: '发布日期', width: 120 },
  { prop: 'effective_date', label: '生效日期', width: 120, sortable: true },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'owner_department_name', label: '归口部门', width: 140 },
  { prop: 'is_active', label: '启用', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'category', label: '制度类别', type: 'select' as const, options: meta.options('regulation_categories') },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('regulation_statuses') },
  { prop: 'owner_department_id', label: '归口部门', type: 'select' as const, optionsLoader: departmentOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'owner_employee_name', label: '负责人' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '制度编号', help: '同一公司内唯一；留空时由系统按编号规则自动生成', onlyOnUpdate: true },
  { prop: 'name', label: '制度名称', required: true, span: 24 },
  { prop: 'category', label: '制度类别', type: 'select', required: true, options: meta.options('regulation_categories'), defaultValue: "system" },
  { prop: 'version_no', label: '版本号', defaultValue: "V1.0" },
  { prop: 'issue_org', label: '发布机构' },
  { prop: 'issue_date', label: '发布日期', type: 'date' },
  { prop: 'effective_date', label: '生效日期', type: 'date' },
  { prop: 'status', label: '状态', type: 'select', options: meta.options('regulation_statuses'), defaultValue: "draft" },
  { prop: 'owner_department_id', label: '归口部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'owner_employee_id', label: '负责人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
