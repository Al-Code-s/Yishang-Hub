<template>
  <entity-list-page
    title="设备类型管理"
    entity-label="设备类型"
    description="设备类型决定设备台账的分类与默认保养周期：锅炉、压力容器等特种设备请勾选「特种设备」，便于后续按特种设备要求管理。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :detail-fields="detailFields"
    :permissions="{ create: 'equipment.type.create', update: 'equipment.type.update' }"
    search-placeholder="搜索类型编码或名称"
    :page-size="20"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { equipmentTypeApi } from '@/api/endpoints'
import { useMetaStore } from '@/stores/meta'

const meta = useMetaStore()
const api = equipmentTypeApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '类型编码', width: 140, sortable: true },
  { prop: 'name', label: '类型名称', minWidth: 160 },
  { prop: 'category', label: '设备分类', width: 140 },
  { prop: 'is_special', label: '特种设备', width: 110 },
  { prop: 'maintenance_cycle_days', label: '保养周期（天）', width: 130 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  {
    prop: 'category',
    label: '设备分类',
    type: 'select' as const,
    options: meta.options('equipment_categories'),
  },
  { prop: 'is_special', label: '特种设备', type: 'select' as const },
])

const detailFields = [
  { prop: 'remark', label: '备注' },
]

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'code', label: '类型编码', required: true, help: '平台内唯一' },
  { prop: 'name', label: '类型名称', required: true },
  {
    prop: 'category',
    label: '设备分类',
    type: 'select',
    options: meta.options('equipment_categories'),
  },
  {
    prop: 'is_special',
    label: '特种设备',
    type: 'switch',
    help: '锅炉、压力容器、起重机械等需定期检验的设备',
  },
  {
    prop: 'maintenance_cycle_days',
    label: '保养周期（天）',
    type: 'number',
    defaultValue: 0,
    help: '0 表示尚未设定周期',
  },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>
