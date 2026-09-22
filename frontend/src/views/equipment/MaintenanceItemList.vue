<template>
  <entity-list-page
    title="保养项目"
    entity-label="保养项目"
    description="保养项目说明「保养做什么、做到什么标准」。项目可按设备类型复用：一台设备的保养计划可以直接引用多条项目，不必重复录入。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.maintenance_item.create', update: 'equipment.maintenance_item.update', deactivate: 'equipment.maintenance_item.update' }"
    search-placeholder="搜索项目编码、名称或标准"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { maintenanceItemApi } from '@/api/endpoints'
import { equipmentTypeOptions } from '@/composables/optionLoaders'
import { useMetaStore } from '@/stores/meta'

const meta = useMetaStore()
const api = maintenanceItemApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '项目编码', width: 140, sortable: true },
  { prop: 'name', label: '项目名称', minWidth: 160 },
  { prop: 'category', label: '保养类别', width: 120 },
  { prop: 'equipment_type_name', label: '适用设备类型', width: 150 },
  { prop: 'cycle_days', label: '建议周期（天）', width: 130 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  {
    prop: 'category',
    label: '保养类别',
    type: 'select' as const,
    options: meta.options('maintenance_categories'),
  },
  {
    prop: 'equipment_type_id',
    label: '适用设备类型',
    type: 'select' as const,
    optionsLoader: equipmentTypeOptions,
  },
])

const detailFields = [
  { prop: 'standard', label: '保养内容与标准' },
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'code', label: '项目编码', required: true, help: '平台内唯一' },
  { prop: 'name', label: '项目名称', required: true },
  {
    prop: 'category',
    label: '保养类别',
    type: 'select',
    options: meta.options('maintenance_categories'),
  },
  {
    prop: 'equipment_type_id',
    label: '适用设备类型',
    type: 'select',
    optionsLoader: equipmentTypeOptions,
    help: '留空表示适用于所有设备类型',
  },
  {
    prop: 'cycle_days',
    label: '建议周期（天）',
    type: 'number',
    defaultValue: 0,
    help: '0 表示由保养计划按设备实际情况设定',
  },
  {
    prop: 'standard',
    label: '保养内容与标准',
    type: 'textarea',
    span: 24,
    help: '写清楚做到什么程度算合格，执行人在任务里能看到这段内容',
  },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>