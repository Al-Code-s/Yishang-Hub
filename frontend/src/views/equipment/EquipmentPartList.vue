<template>
  <entity-list-page
    title="设备零部件"
    entity-label="零部件"
    description="零部件用于登记设备上装有哪些组成件与易损件，并记录参考寿命；可以采购、可以入库的备件请到「备品备件」维护，两者不是同一份数据。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.part.create', update: 'equipment.part.update' }"
    search-placeholder="搜索零部件名称、规格或安装位置"
    default-ordering="name"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { equipmentPartApi } from '@/api/endpoints'
import { equipmentOptions, uomOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'
import { formatAmount } from '@/utils/decimal'

const meta = useMetaStore()
const api = equipmentPartApi as never

const columns: ProTableColumn[] = [
  { prop: 'equipment_name', label: '所属设备', minWidth: 180 },
  { prop: 'name', label: '零部件名称', width: 150 },
  { prop: 'part_type', label: '零件类别', width: 110 },
  { prop: 'spec', label: '规格型号', width: 140 },
  {
    prop: 'quantity',
    label: '数量',
    width: 100,
    formatter: (row) => formatAmount(row.quantity as string),
  },
  { prop: 'uom_name', label: '单位', width: 90 },
  { prop: 'position', label: '安装位置', width: 130 },
  { prop: 'life_days', label: '参考寿命（天）', width: 130 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  { prop: 'equipment_id', label: '所属设备', type: 'select' as const, optionsLoader: equipmentOptions },
  {
    prop: 'part_type',
    label: '零件类别',
    type: 'select' as const,
    options: meta.options('part_types'),
  },
])

const detailFields = [
  { prop: 'equipment_name', label: '所属设备' },
  { prop: 'position', label: '安装位置' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  {
    prop: 'equipment_id',
    label: '所属设备',
    type: 'select',
    required: true,
    optionsLoader: equipmentOptions,
  },
  { prop: 'name', label: '零部件名称', required: true, help: '同一设备下不允许同名零部件' },
  {
    prop: 'part_type',
    label: '零件类别',
    type: 'select',
    options: meta.options('part_types'),
  },
  { prop: 'spec', label: '规格型号' },
  { prop: 'quantity', label: '数量', type: 'decimal', defaultValue: '1' },
  { prop: 'uom_id', label: '单位', type: 'select', optionsLoader: uomOptions },
  { prop: 'position', label: '安装位置' },
  {
    prop: 'life_days',
    label: '参考寿命（天）',
    type: 'number',
    defaultValue: 0,
    help: '0 表示未设定寿命',
  },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>