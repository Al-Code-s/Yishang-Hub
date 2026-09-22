<template>
  <entity-list-page
    title="区域管理"
    entity-label="计量区域"
    description="计量区域用于把仪表按厂区、车间或部门归口，能耗看板与统计按区域汇总。区域可以挂在上级区域下，形成层级。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'ems.area.create', update: 'ems.area.update' }"
    search-placeholder="搜索区域编码或名称"
    default-ordering="code"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { energyAreaApi } from '@/api/endpoints'
import { companyOptions, departmentOptions, employeeOptions, energyAreaOptions } from '@/composables/optionLoaders'
import { formatDecimal } from '@/utils/decimal'

const api = energyAreaApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '区域编码', width: 150, sortable: true },
  { prop: 'name', label: '区域名称', minWidth: 160 },
  { prop: 'parent_name', label: '上级区域', width: 150 },
  { prop: 'department_name', label: '归口部门', width: 140 },
  { prop: 'manager_name', label: '负责人', width: 110 },
  { prop: 'area_size', label: '面积（㎡）', width: 110, formatter: (row) => formatDecimal(row.area_size as string) },
  { prop: 'is_active', label: '启用', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  { prop: 'department_id', label: '归口部门', type: 'select' as const, optionsLoader: departmentOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'parent_name', label: '上级区域' },
  { prop: 'manager_name', label: '负责人' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  { prop: 'code', label: '区域编码', required: true, help: '同一公司内唯一，建议用厂区/车间拼音缩写' },
  { prop: 'name', label: '区域名称', required: true },
  { prop: 'parent_id', label: '上级区域', type: 'select', optionsLoader: energyAreaOptions },
  { prop: 'department_id', label: '归口部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'manager_id', label: '负责人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'area_size', label: '面积（㎡）', type: 'decimal', defaultValue: "0" },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
