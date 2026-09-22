<template>
  <entity-list-page
    title="备品备件"
    entity-label="备件"
    description="备件是可直接采购、可入库的备用零件主数据。备件编码留空时按编号规则自动生成；关联「对应物料」后，该备件的库存与采购统一走仓储与采购模块，不需要另建一套库存。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.spare_part.create', update: 'equipment.spare_part.update' }"
    search-placeholder="搜索备件编码、名称或规格"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { sparePartApi } from '@/api/endpoints'
import {
  companyOptions,
  equipmentTypeOptions,
  materialOptions,
  supplierOptions,
  uomOptions,
} from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatAmount } from '@/utils/decimal'

const meta = useMetaStore()
const api = sparePartApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '备件编码', width: 150, sortable: true },
  { prop: 'name', label: '备件名称', minWidth: 160 },
  { prop: 'part_type', label: '备件类别', width: 110 },
  { prop: 'spec', label: '规格型号', width: 140 },
  { prop: 'equipment_type_name', label: '适用设备类型', width: 140 },
  { prop: 'uom_name', label: '单位', width: 90 },
  {
    prop: 'safety_stock',
    label: '安全库存',
    width: 110,
    formatter: (row) => formatAmount(row.safety_stock as string),
  },
  {
    prop: 'reference_price',
    label: '参考单价',
    width: 110,
    formatter: (row) => formatAmount(row.reference_price as string),
  },
  { prop: 'life_days', label: '参考寿命（天）', width: 130 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  { prop: 'company_id', label: '所属公司', type: 'select' as const, optionsLoader: companyOptions },
  {
    prop: 'part_type',
    label: '备件类别',
    type: 'select' as const,
    options: meta.options('part_types'),
  },
  {
    prop: 'equipment_type_id',
    label: '适用设备类型',
    type: 'select' as const,
    optionsLoader: equipmentTypeOptions,
  },
])

const detailFields = [
  { prop: 'company_name', label: '所属公司' },
  { prop: 'material_name', label: '对应物料' },
  { prop: 'supplier_name', label: '常用供应商' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'company_id',
    label: '所属公司',
    type: 'select',
    required: true,
    optionsLoader: companyOptions,
  },
  {
    prop: 'code',
    label: '备件编码',
    onlyOnUpdate: true,
    help: '同一公司内唯一；留空时由系统按编号规则自动生成',
  },
  { prop: 'name', label: '备件名称', required: true },
  {
    prop: 'part_type',
    label: '备件类别',
    type: 'select',
    options: meta.options('part_types'),
  },
  { prop: 'spec', label: '规格型号' },
  {
    prop: 'material_id',
    label: '对应物料',
    type: 'select',
    optionsLoader: materialOptions,
    help: '关联后库存与采购复用仓储、采购模块',
  },
  {
    prop: 'equipment_type_id',
    label: '适用设备类型',
    type: 'select',
    optionsLoader: equipmentTypeOptions,
  },
  { prop: 'uom_id', label: '单位', type: 'select', optionsLoader: uomOptions },
  { prop: 'safety_stock', label: '安全库存', type: 'decimal', defaultValue: '0' },
  { prop: 'reference_price', label: '参考单价', type: 'decimal', defaultValue: '0' },
  {
    prop: 'life_days',
    label: '参考寿命（天）',
    type: 'number',
    defaultValue: 0,
    help: '0 表示未设定寿命',
  },
  { prop: 'supplier_id', label: '常用供应商', type: 'select', optionsLoader: supplierOptions },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>