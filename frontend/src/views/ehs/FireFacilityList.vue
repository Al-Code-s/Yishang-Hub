<template>
  <entity-list-page
    title="消防设施"
    entity-label="消防设施"
    description="灭火器、消火栓、火灾自动报警、自动喷淋与疏散设施的台账，记录数量、上次检查日期与下次检查日期。到期未检的设施会在状态里体现，检查结果请及时回填。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ehs.fire_facility.create', update: 'ehs.fire_facility.update' }"
    search-placeholder="搜索设施编号、名称或位置"
    default-ordering="code"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { fireFacilityApi } from '@/api/endpoints'
import { companyOptions, departmentOptions, employeeOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatDecimal } from '@/utils/decimal'

const api = fireFacilityApi as never
const meta = useMetaStore()

const columns: ProTableColumn[] = [
  { prop: 'code', label: '设施编号', width: 150, sortable: true },
  { prop: 'name', label: '设施名称', minWidth: 160 },
  { prop: 'facility_type', label: '设施类型', width: 140 },
  { prop: 'location', label: '位置', width: 160 },
  { prop: 'quantity', label: '数量', width: 100, formatter: (row) => formatDecimal(row.quantity as string) },
  { prop: 'unit', label: '单位', width: 80 },
  { prop: 'last_check_date', label: '上次检查日期', width: 140 },
  { prop: 'next_check_date', label: '下次检查日期', width: 140, sortable: true },
  { prop: 'status', label: '状态', width: 100 },
  { prop: 'department_name', label: '责任部门', width: 140 },
  { prop: 'is_active', label: '启用', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'facility_type', label: '设施类型', type: 'select' as const, options: meta.options('fire_facility_types') },
  { prop: 'status', label: '状态', type: 'select' as const, options: meta.options('fire_facility_statuses') },
  { prop: 'department_id', label: '责任部门', type: 'select' as const, optionsLoader: departmentOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'owner_employee_name', label: '责任人' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '设施编号', help: '留空时由系统按编号规则自动生成', onlyOnUpdate: true },
  { prop: 'name', label: '设施名称', required: true },
  { prop: 'facility_type', label: '设施类型', type: 'select', options: meta.options('fire_facility_types'), defaultValue: "extinguisher" },
  { prop: 'location', label: '位置' },
  { prop: 'quantity', label: '数量', type: 'decimal', defaultValue: "0" },
  { prop: 'unit', label: '单位', defaultValue: "个" },
  { prop: 'last_check_date', label: '上次检查日期', type: 'date' },
  { prop: 'next_check_date', label: '下次检查日期', type: 'date' },
  { prop: 'status', label: '状态', type: 'select', options: meta.options('fire_facility_statuses'), defaultValue: "normal" },
  { prop: 'department_id', label: '责任部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'owner_employee_id', label: '责任人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
