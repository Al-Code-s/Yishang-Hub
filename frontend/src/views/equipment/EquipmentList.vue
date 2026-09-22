<template>
  <entity-list-page
    title="设备台账"
    entity-label="设备"
    description="设备台账记录每台设备的基础信息与归属：新增时不必手工输入设备编号，留空即按编号规则自动生成（可在「系统管理 → 编码规则」调整）。设备状态当前为台账属性，维修、点巡检带来的自动流转随对应功能上线。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.equipment.create', update: 'equipment.equipment.update' }"
    search-placeholder="搜索设备编号、名称、牌号或出厂编号"
    :page-size="20"
  >
    <template #column-status="{ row }">
      <el-tag :type="statusTagType(String(row.status))" size="small" effect="light">
        {{ meta.label('equipment_statuses', String(row.status)) }}
      </el-tag>
    </template>
    <template #column-is_special="{ row }">
      <el-tag v-if="row.is_special" type="warning" size="small" effect="light">特种设备</el-tag>
      <span v-else>—</span>
    </template>
  </entity-list-page>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { equipmentApi } from '@/api/endpoints'
import {
  companyOptions,
  departmentOptions,
  employeeOptions,
  equipmentTypeOptions,
  factoryOptions,
  lineOptions,
  stationOptions,
  supplierOptions,
  workshopOptions,
} from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatAmount } from '@/utils/decimal'

const meta = useMetaStore()
const api = equipmentApi as never

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'in_use') return 'success'
  if (status === 'repairing') return 'warning'
  if (status === 'scrapped' || status === 'stopped') return 'danger'
  return 'info'
}

const columns: ProTableColumn[] = [
  { prop: 'code', label: '设备编号', width: 150, sortable: true },
  { prop: 'name', label: '设备名称', minWidth: 160 },
  { prop: 'equipment_type_name', label: '设备类型', width: 140 },
  { prop: 'status', label: '设备状态', width: 110 },
  { prop: 'factory_name', label: '所属工厂', width: 140 },
  { prop: 'location', label: '安装位置', width: 140 },
  { prop: 'model_no', label: '规格型号', width: 130 },
  {
    prop: 'original_value',
    label: '资产原值',
    width: 130,
    formatter: (row) => formatAmount(row.original_value as string),
  },
  { prop: 'is_special', label: '特种设备', width: 100 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'equipment_type_id',
    label: '设备类型',
    type: 'select' as const,
    optionsLoader: equipmentTypeOptions,
  },
  {
    prop: 'status',
    label: '设备状态',
    type: 'select' as const,
    options: meta.options('equipment_statuses'),
  },
  { prop: 'factory_id', label: '所属工厂', type: 'select' as const, optionsLoader: factoryOptions },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'workshop_name', label: '所属车间' },
  { prop: 'production_line_name', label: '所属线体' },
  { prop: 'station_name', label: '工位' },
  { prop: 'brand', label: '品牌' },
  { prop: 'serial_no', label: '出厂编号' },
  { prop: 'supplier_name', label: '供应商' },
  { prop: 'purchase_date', label: '采购日期' },
  { prop: 'start_date', label: '启用日期' },
  { prop: 'warranty_until', label: '保修截止日期' },
  { prop: 'owner_department_name', label: '负责部门' },
  { prop: 'owner_employee_name', label: '责任人' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'company_id', label: '所属公司', type: 'select', required: true, optionsLoader: companyOptions },
  {
    prop: 'code',
    label: '设备编号',
    onlyOnUpdate: true,
    help: '同一公司内唯一，被保养/维修记录引用后不建议修改',
  },
  { prop: 'name', label: '设备名称', required: true },
  {
    prop: 'equipment_type_id',
    label: '设备类型',
    type: 'select',
    required: true,
    optionsLoader: equipmentTypeOptions,
  },
  {
    prop: 'status',
    label: '设备状态',
    type: 'select',
    options: meta.options('equipment_statuses'),
  },
  { prop: 'factory_id', label: '所属工厂', type: 'select', optionsLoader: factoryOptions },
  { prop: 'workshop_id', label: '所属车间', type: 'select', optionsLoader: workshopOptions },
  { prop: 'production_line_id', label: '所属线体', type: 'select', optionsLoader: lineOptions },
  { prop: 'station_id', label: '工位', type: 'select', optionsLoader: stationOptions },
  { prop: 'location', label: '安装位置' },
  { prop: 'brand', label: '品牌' },
  { prop: 'model_no', label: '规格型号' },
  { prop: 'serial_no', label: '出厂编号' },
  { prop: 'supplier_id', label: '供应商', type: 'select', optionsLoader: supplierOptions },
  { prop: 'purchase_date', label: '采购日期', type: 'date' },
  { prop: 'start_date', label: '启用日期', type: 'date' },
  { prop: 'original_value', label: '资产原值', type: 'decimal', defaultValue: '0' },
  { prop: 'warranty_until', label: '保修截止日期', type: 'date' },
  { prop: 'is_special', label: '特种设备', type: 'switch' },
  { prop: 'owner_department_id', label: '负责部门', type: 'select', optionsLoader: departmentOptions },
  { prop: 'owner_employee_id', label: '责任人', type: 'select', optionsLoader: employeeOptions },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
