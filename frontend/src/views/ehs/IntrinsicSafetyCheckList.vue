<template>
  <entity-list-page
    title="本质安全检查"
    entity-label="检查记录"
    description="本质安全检查记录：检查设备设施本身的安全防护是否到位（防护罩、联锁、急停、限位等）。检查类型固定为本检查，编号留空时按编号规则自动生成。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.safety_check.create', update: 'ehs.safety_check.update' }"
    search-placeholder="搜索检查编号、标题、检查内容或结论"
    default-ordering="-check_date"
    :toggleable="false"
    :initial-filters="{ check_type: CHECK_TYPE }"
    :transform="transform"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { safetyCheckApi } from '@/api/endpoints'
import { companyOptions, departmentOptions, employeeOptions, equipmentOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const api = safetyCheckApi as never
const meta = useMetaStore()
const CHECK_TYPE = 'intrinsic'
const transform = (payload: Record<string, unknown>): Record<string, unknown> => ({
  ...payload,
  check_type: CHECK_TYPE,
})

const columns: ProTableColumn[] = [
  { prop: 'check_no', label: '检查编号', width: 150, sortable: true },
  { prop: 'title', label: '检查标题', minWidth: 180 },
  { prop: 'check_type', label: '检查类型', width: 150 },
  { prop: 'check_date', label: '检查日期', width: 120, sortable: true },
  { prop: 'checker_name', label: '检查人', width: 110 },
  { prop: 'department_name', label: '受检部门', width: 140 },
  { prop: 'equipment_name', label: '受检设备', width: 150 },
  { prop: 'problem_count', label: '问题数', width: 90, sortable: true },
  { prop: 'conclusion', label: '检查结论', minWidth: 180 },
  { prop: 'status', label: '状态', width: 110 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('safety_check_statuses') },
  { prop: 'department_id', label: '受检部门', type: 'select' as const, optionsLoader: departmentOptions },
  { prop: 'equipment_id', label: '受检设备', type: 'select' as const, optionsLoader: equipmentOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'rectify_requirement', label: '整改要求' },
  { prop: 'rectified_date', label: '整改完成日期' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'check_no', label: '检查编号', help: '留空时由系统按编号规则自动生成', onlyOnUpdate: true },
  { prop: 'title', label: '检查标题', required: true, span: 24 },
  { prop: 'check_date', label: '检查日期', type: 'date' },
  { prop: 'checker_id', label: '检查人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'department_id', label: '受检部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'equipment_id', label: '受检设备', type: 'select', optionsLoader: equipmentOptions },
  { prop: 'problem_count', label: '问题数', type: 'number', defaultValue: 0 },
  { prop: 'check_content', label: '检查内容', type: 'textarea', span: 24 },
  { prop: 'conclusion', label: '检查结论', type: 'textarea', span: 24 },
  { prop: 'status', label: '状态', type: 'select', options: meta.options('safety_check_statuses'), defaultValue: "normal" },
  { prop: 'rectify_requirement', label: '整改要求', type: 'textarea', span: 24 },
  { prop: 'rectified_date', label: '整改完成日期', type: 'date' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
