<template>
  <entity-list-page
    title="计量单位"
    entity-label="单位"
    description="计量单位用于统一数量口径，可分别设置采购、销售等辅助单位与换算率。小数位只影响页面显示的小数位数，不改变系统内部的计算精度。"
    :api="api"
    :columns="columns"
    :filters="filters"
    :form-fields="formFields"
    :permissions="{ create: 'masterdata.uom.create', update: 'masterdata.uom.update' }"
    search-placeholder="搜索单位编码或名称"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'

import EntityListPage, { type FormFieldDef } from '@/components/EntityListPage.vue'
import type { ProTableColumn } from '@/components/ProTable.vue'
import { uomApi } from '@/api/endpoints'
import { useMetaStore } from '@/stores/meta'

const meta = useMetaStore()
const api = uomApi as never

const columns: ProTableColumn[] = [
  { prop: 'code', label: '单位编码', width: 140, sortable: true },
  { prop: 'name', label: '单位名称', minWidth: 140 },
  { prop: 'category', label: '计量类型', width: 120 },
  { prop: 'decimal_places', label: '小数位', width: 90 },
  { prop: 'is_active', label: '状态', width: 90 },
]

const filters = computed(() => [
  {
    prop: 'category',
    label: '计量类型',
    type: 'select' as const,
    options: meta.options('uom_categories'),
  },
])

const formFields = computed<FormFieldDef[]>(() => [
  { prop: 'code', label: '单位编码', required: true },
  { prop: 'name', label: '单位名称', required: true },
  {
    prop: 'category',
    label: '计量类型',
    type: 'select',
    options: meta.options('uom_categories'),
  },
  {
    prop: 'decimal_places',
    label: '小数位',
    type: 'number',
    help: '仅影响页面显示的小数位数，系统内部始终按 6 位小数计算',
  },
  { prop: 'is_active', label: '启用', type: 'switch' },
  { prop: 'remark', label: '备注', type: 'textarea', span: 24 },
])
</script>